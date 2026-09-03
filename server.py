"""
SYNAPSE — Integration API Server
Module 06: Frontend, Reviewer Queue, Audit Trail & User Experience
Owner: Aliadnan

This is the backend-for-frontend (BFF) layer. It owns NO AI logic of its own —
every intelligent decision is delegated to a teammate's module:

    Adithyan        event_extraction    raw text/files  -> ExecutionEvent
    Yazeen          schedule_parser     P6/MSP/CSV      -> ScheduleActivity
    Amritha         amrita.matcher      event           -> match + confidence
    Adithyanbalu    progress_analytics  link            -> variance / risk / conflict
    Adithyagopan    knowledge_base      activity        -> historical delay risk

What this layer adds is the story the judges see: orchestration, multi-source
conflict aggregation, the reviewer queue, the audit trail, and the schedule
state that results from human decisions.

Run:  uvicorn server:app
UI:   http://127.0.0.1:8000/
"""

from __future__ import annotations

import os
import re
import shutil
import tempfile
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from pydantic import BaseModel, Field

# --- teammate modules -------------------------------------------------------
from event_extraction import ExtractionPipeline
from event_extraction.clarification import apply_clarification, generate_clarification
from event_extraction.models import ExecutionEvent, SourceType

from schedule_parser import ScheduleParser

from amrita.matcher import SynapseMatchingEngine

from progress_analytics.activity import Activity
from progress_analytics.analytics import calculate_finish_variance
from progress_analytics.conflict import detect_status_conflict
from progress_analytics.confidence import ReviewDecision, get_review_decision
from progress_analytics.progress import calculate_progress
from progress_analytics.project import calculate_project_summary
from progress_analytics.risk import calculate_risk
from progress_analytics.status import ActivityStatus

from knowledge_base import DelayRiskEngine, KnowledgeBase, NLQueryEngine, ProductivityTracker

ROOT = Path(__file__).parent
DATA = ROOT / "data"
FRONTEND = ROOT / "frontend"

SCHEDULE_CSV = DATA / "schedule.csv"
HISTORY_CSV = DATA / "historical_knowledge_base.csv"

UPLOAD_SUFFIXES = {".txt", ".text", ".md", ".csv", ".xlsx", ".xls", ".pdf"}


# ===========================================================================
# Auth — JWT-based role system (supervisor / admin)
# ===========================================================================

import hashlib
import secrets as _secrets

_JWT_SECRET = os.environ.get("SYNAPSE_JWT_SECRET", "synapse-sih2026-secret-key")
_JWT_ALGORITHM = "HS256"
_JWT_EXPIRE_HOURS = 8

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/login")


def _hash_pw(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()


# Demo users — in production these would come from a database
_USERS = {
    "supervisor": {
        "username": "supervisor",
        "hashed_password": _hash_pw("site123"),
        "role": "supervisor",
        "display_name": "Site Supervisor",
    },
    "admin": {
        "username": "admin",
        "hashed_password": _hash_pw("synapse2026"),
        "role": "admin",
        "display_name": "Project Manager",
    },
}


def _create_token(username: str, role: str) -> str:
    from datetime import timedelta
    payload = {
        "sub": username,
        "role": role,
        "exp": datetime.now(timezone.utc) + timedelta(hours=_JWT_EXPIRE_HOURS),
    }
    return jwt.encode(payload, _JWT_SECRET, algorithm=_JWT_ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, _JWT_SECRET, algorithms=[_JWT_ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")


def get_current_user(token: str = Depends(_oauth2_scheme)) -> dict:
    payload = _decode_token(token)
    username = payload.get("sub")
    if not username or username not in _USERS:
        raise HTTPException(status_code=401, detail="User not found")
    return {"username": username, "role": payload.get("role"), "display_name": _USERS[username]["display_name"]}


def require_supervisor(user: dict = Depends(get_current_user)) -> dict:
    """Any logged-in user (supervisor or admin) can submit reports."""
    return user


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    """Only admin can approve/reject, resolve conflicts, configure settings."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


# ===========================================================================
# Small helpers shared by the orchestration layer
# ===========================================================================

def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _iso_to_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


#: Event status vocabulary (Adithyan) -> schedule status vocabulary (Adithyanbalu).
#: The text parser emits "in_progress" while the CSV parser passes the
#: spreadsheet's own "in progress" through untouched, so lookup is done on a
#: separator-normalized key rather than on either spelling.
STATUS_MAP: dict[str, ActivityStatus] = {
    "completed": ActivityStatus.COMPLETED,
    "complete": ActivityStatus.COMPLETED,
    "done": ActivityStatus.COMPLETED,
    "finished": ActivityStatus.COMPLETED,
    "started": ActivityStatus.IN_PROGRESS,
    "in_progress": ActivityStatus.IN_PROGRESS,
    "ongoing": ActivityStatus.IN_PROGRESS,
    "delayed": ActivityStatus.IN_PROGRESS,
    "blocked": ActivityStatus.ON_HOLD,
    "on_hold": ActivityStatus.ON_HOLD,
    "held_up": ActivityStatus.ON_HOLD,
    "not_started": ActivityStatus.NOT_STARTED,
    "pending": ActivityStatus.NOT_STARTED,
    "cancelled": ActivityStatus.CANCELLED,
}

#: Schedule activity names -> the activity_type vocabulary used by the
#: knowledge base, so historical risk lookups actually hit records.
ACTIVITY_TYPE_KEYWORDS: list[tuple[tuple[str, ...], str]] = [
    (("hydrotest", "hydro test"), "hydrotest"),
    (("insulat",), "insulation"),
    (("valve",), "valve installation"),
    (("erect",), "erection"),
    (("weld",), "welding"),
    (("fabricat",), "erection"),
    (("cable tray",), "cable tray installation"),
    (("pull",), "cable pulling"),
    (("terminat", "gland"), "termination"),
    (("panel", "mcc"), "panel installation"),
    (("loop check",), "loop check"),
    (("transmitter", "gauge", "instrument"), "instrument installation"),
    (("excavat",), "excavation"),
    (("concret", "reinforce", "pour", "road", "hardstand"), "concreting"),
    (("backfill", "curing"), "backfilling"),
    (("align",), "alignment"),
    (("commission",), "commissioning"),
    (("set ", "setting", "connect"), "equipment setting"),
]


def infer_activity_type(name: str) -> str:
    """Best-effort mapping of a schedule activity name onto a KB activity_type."""
    lowered = (name or "").lower()
    for keywords, activity_type in ACTIVITY_TYPE_KEYWORDS:
        if any(k in lowered for k in keywords):
            return activity_type
    return ""


def normalize_status(value: Optional[str]) -> Optional[ActivityStatus]:
    """
    Map an event's status onto the schedule vocabulary.

    Returns None when the event makes no status claim ("unknown", blank, or a
    word we do not recognise). None is not NOT_STARTED: an event that never said
    how far the work got must not move the schedule, and must not be counted as
    disagreeing with an event that did say.
    """
    key = re.sub(r"[\s\-]+", "_", (value or "").strip().lower())
    return STATUS_MAP.get(key)


def status_label(value: Optional[str]) -> str:
    """How a status is shown to a human — never invent one that wasn't reported."""
    status = normalize_status(value)
    return status.value if status else "UNKNOWN"


def confidence_band(confidence: float) -> str:
    """HIGH / MEDIUM / LOW band via Adithyanbalu's threshold function."""
    decision = get_review_decision(max(0.0, min(1.0, float(confidence))))
    return {
        ReviewDecision.AUTO: "HIGH",
        ReviewDecision.REVIEW: "MEDIUM",
        ReviewDecision.REJECT: "LOW",
    }[decision]


# ===========================================================================
# Application state — the demo runs entirely in memory
# ===========================================================================

class SynapseState:
    """Holds the loaded teammate engines plus the session's working state."""

    def __init__(self) -> None:
        self.parser: ScheduleParser | None = None
        self.extractor: ExtractionPipeline | None = None
        self.engine: SynapseMatchingEngine | None = None
        self.kb: KnowledgeBase | None = None
        self.risk_engine: DelayRiskEngine | None = None
        self.nl_query: NLQueryEngine | None = None
        self.productivity: ProductivityTracker | None = None

        self._openrouter_key: str | None = os.environ.get("OPENROUTER_API_KEY")
        self._openrouter_model: str = "google/gemini-2.0-flash-exp:free"

        self.activities: dict[str, dict] = {}     # activity_id -> parsed activity
        self.actuals: dict[str, dict] = {}        # activity_id -> observed state
        self.events: dict[str, dict] = {}         # event_id -> tracked event record
        self.event_order: list[str] = []
        self.conflicts: dict[str, dict] = {}      # conflict_id -> conflict record
        self.audit: list[dict] = []
        self.pending_clarifications: dict[str, dict] = {}
        self._risk_cache: dict[str, dict] = {}

    # -- bootstrap ----------------------------------------------------------

    def bootstrap(self) -> None:
        self.parser = ScheduleParser()
        self.extractor = ExtractionPipeline(
            use_llm=bool(self._openrouter_key), llm_api_key=self._openrouter_key
        )

        parse_result = self.parser.parse(str(SCHEDULE_CSV))
        for activity in parse_result.to_amritha_format():
            self.activities[activity["activity_id"]] = activity

        self.engine = SynapseMatchingEngine()
        self.engine.load_activities(list(self.activities.values()))

        self.kb = KnowledgeBase()
        if HISTORY_CSV.exists():
            self.kb.load_csv(str(HISTORY_CSV))
        self.risk_engine = DelayRiskEngine(self.kb)
        self.nl_query = NLQueryEngine(self.kb)
        self.productivity = ProductivityTracker(self.kb)

        self.log_audit(
            stage="SYSTEM",
            summary=f"Schedule loaded — {len(self.activities)} L5/L6 activities, "
                    f"{len(self.kb)} historical records",
            detail={
                "format_detected": parse_result.format_detected,
                "quality_errors": parse_result.quality_report.error_count,
                "quality_warnings": parse_result.quality_report.warning_count,
            },
        )

    # -- audit trail --------------------------------------------------------

    def log_audit(
        self,
        stage: str,
        summary: str,
        event_id: Optional[str] = None,
        activity_id: Optional[str] = None,
        actor: str = "SYNAPSE",
        detail: Optional[dict] = None,
    ) -> dict:
        entry = {
            "audit_id": f"AUD-{uuid.uuid4().hex[:8].upper()}",
            "timestamp": _now(),
            "stage": stage,
            "summary": summary,
            "event_id": event_id,
            "activity_id": activity_id,
            "actor": actor,
            "detail": detail or {},
        }
        self.audit.append(entry)
        return entry

    # -- schedule state -----------------------------------------------------

    def actual_for(self, activity_id: str) -> dict:
        return self.actuals.setdefault(
            activity_id,
            {
                "activity_id": activity_id,
                "status": ActivityStatus.NOT_STARTED.value,
                "actual_start": None,
                "actual_finish": None,
                "actual_start_inferred": False,
                "evidence": [],
                "last_source": None,
                "last_updated": None,
            },
        )

    def apply_event_to_schedule(self, tracked: dict, actor: str = "SYNAPSE") -> Optional[dict]:
        """Push a confirmed event/activity link into the schedule state."""
        activity_id = tracked.get("linked_activity_id")
        if not activity_id or activity_id not in self.activities:
            return None

        event = tracked["event"]
        state_row = self.actual_for(activity_id)
        new_status = normalize_status(event.get("status"))
        event_date = event.get("event_date") or date.today().isoformat()

        previous = dict(state_row)

        # No status claim → the link is still evidence, but nothing about how
        # far the work got, so the schedule state is left where it was.

        if new_status == ActivityStatus.COMPLETED:
            state_row["actual_finish"] = event_date
            if not state_row["actual_start"]:
                # Nobody reported a start — fall back to the plan so the row has
                # a span, but flag it so the UI never draws an observed duration
                # we were never told.
                state_row["actual_start"] = self.activities[activity_id].get("planned_start")
                state_row["actual_start_inferred"] = True
            state_row["status"] = ActivityStatus.COMPLETED.value
        elif new_status == ActivityStatus.IN_PROGRESS:
            state_row["actual_start"] = state_row["actual_start"] or event_date
            if state_row["status"] != ActivityStatus.COMPLETED.value:
                state_row["status"] = ActivityStatus.IN_PROGRESS.value
        elif new_status == ActivityStatus.ON_HOLD:
            state_row["actual_start"] = state_row["actual_start"] or event_date
            if state_row["status"] != ActivityStatus.COMPLETED.value:
                state_row["status"] = ActivityStatus.ON_HOLD.value

        state_row["evidence"] = sorted(set(state_row["evidence"] + [tracked["event_id"]]))
        state_row["last_source"] = event.get("source_id")
        state_row["last_updated"] = _now()

        self.log_audit(
            stage="SCHEDULE_UPDATE",
            summary=(
                f"{activity_id} → {state_row['status']}"
                + (f", actual finish {state_row['actual_finish']}" if state_row["actual_finish"] else "")
            ),
            event_id=tracked["event_id"],
            activity_id=activity_id,
            actor=actor,
            detail={"before": previous, "after": dict(state_row)},
        )
        return state_row

    # -- derived views ------------------------------------------------------

    def schedule_row(self, activity_id: str) -> dict:
        activity = self.activities[activity_id]
        observed = self.actuals.get(activity_id)
        status = ActivityStatus(observed["status"]) if observed else ActivityStatus.NOT_STARTED

        planned_start = _iso_to_date(activity.get("planned_start"))
        planned_finish = _iso_to_date(activity.get("planned_finish"))
        actual_start = _iso_to_date(observed.get("actual_start")) if observed else None
        actual_finish = _iso_to_date(observed.get("actual_finish")) if observed else None

        variance = None
        if planned_finish and actual_finish:
            variance = calculate_finish_variance(
                Activity(
                    activity_id=activity_id,
                    planned_start=planned_start or planned_finish,
                    planned_finish=planned_finish,
                    status=status,
                    actual_start=actual_start,
                    actual_finish=actual_finish,
                )
            )

        progress = calculate_progress(status)
        # calculate_progress returns 0.0-1.0 but calculate_risk validates a
        # 0-100 percentage — the two halves of progress_analytics use different
        # scales, so bridge them here rather than in either module.
        risk = calculate_risk(variance or 0, progress * 100).value

        return {
            "activity_id": activity_id,
            "activity_name": activity.get("activity_name", ""),
            "discipline": activity.get("discipline", ""),
            "location": activity.get("location", ""),
            "wbs_id": activity.get("wbs_id", ""),
            "planned_start": activity.get("planned_start"),
            "planned_finish": activity.get("planned_finish"),
            "duration_days": activity.get("duration_days"),
            "actual_start": observed.get("actual_start") if observed else None,
            "actual_finish": observed.get("actual_finish") if observed else None,
            "actual_start_inferred": bool(observed.get("actual_start_inferred")) if observed else False,
            "status": status.value,
            "progress_percent": round(progress * 100, 1),
            "variance_days": variance,
            "schedule_risk": risk,
            "evidence_event_ids": observed.get("evidence", []) if observed else [],
            "last_source": observed.get("last_source") if observed else None,
        }

    def activity_objects(self) -> list[Activity]:
        objects: list[Activity] = []
        for activity_id, activity in self.activities.items():
            planned_start = _iso_to_date(activity.get("planned_start"))
            planned_finish = _iso_to_date(activity.get("planned_finish"))
            if not planned_start or not planned_finish:
                continue
            observed = self.actuals.get(activity_id)
            objects.append(
                Activity(
                    activity_id=activity_id,
                    planned_start=planned_start,
                    planned_finish=planned_finish,
                    status=ActivityStatus(observed["status"]) if observed else ActivityStatus.NOT_STARTED,
                    actual_start=_iso_to_date(observed.get("actual_start")) if observed else None,
                    actual_finish=_iso_to_date(observed.get("actual_finish")) if observed else None,
                )
            )
        return objects

    def historical_risk(self, activity_id: str) -> dict:
        if activity_id in self._risk_cache:
            return self._risk_cache[activity_id]

        activity = self.activities[activity_id]
        result = self.risk_engine.assess(
            activity_description=activity.get("activity_name", ""),
            discipline=activity.get("discipline") or None,
            activity_type=infer_activity_type(activity.get("activity_name", "")) or None,
            planned_duration_days=activity.get("duration_days"),
        )
        payload = result.model_dump() if hasattr(result, "model_dump") else dict(result.__dict__)
        self._risk_cache[activity_id] = payload
        return payload


state = SynapseState()


# ===========================================================================
# Orchestration — the SYNAPSE pipeline as the UI experiences it
# ===========================================================================

def track_event(event: ExecutionEvent, source_label: str) -> dict:
    """Register an extracted event and run it through the matching engine."""
    payload = event.model_dump(mode="json")
    tracked = {
        "event_id": event.event_id,
        "event": payload,
        "source_label": source_label,
        "ingested_at": _now(),
        "match": None,
        "linked_activity_id": None,
        "link_state": "unmatched",
        "confidence_band": "LOW",
        "review": None,
        "clarification": None,
    }
    state.events[event.event_id] = tracked
    state.event_order.append(event.event_id)

    state.log_audit(
        stage="EXTRACT",
        summary=f'"{payload["raw_text"][:80]}" → {payload["description"][:80]}',
        event_id=event.event_id,
        detail={
            "discipline": payload.get("discipline"),
            "asset": payload.get("asset"),
            "status": payload.get("status"),
            "event_date": payload.get("event_date"),
            "extraction_confidence": payload.get("extraction_confidence"),
            "source_type": payload.get("source_type"),
        },
    )

    match = state.engine.process_event(payload)
    tracked["match"] = match
    tracked["confidence_band"] = confidence_band(match.get("confidence", 0.0))

    if match.get("requires_clarification"):
        tracked["link_state"] = "clarification_needed"
        tracked["clarification"] = {
            "question": match.get("clarification_question"),
            "options": match.get("candidates", []),
        }
        state.log_audit(
            stage="CLARIFY",
            summary=f"Ambiguous — {match.get('clarification_question')}",
            event_id=event.event_id,
            detail={"candidates": match.get("candidates", [])},
        )
    elif match["decision"] == "auto_linked":
        tracked["link_state"] = "auto_linked"
        tracked["linked_activity_id"] = match["matched_activity_id"]
    elif match["decision"] == "review":
        tracked["link_state"] = "pending_review"
    else:
        tracked["link_state"] = "unmatched"

    state.log_audit(
        stage="MATCH",
        summary=(
            f"{match.get('matched_activity_id') or 'no match'} "
            f"@ {round(match.get('confidence', 0.0) * 100)}% → {tracked['link_state']}"
        ),
        event_id=event.event_id,
        activity_id=match.get("matched_activity_id"),
        detail={
            "candidates": match.get("candidates", []),
            "explanation": match.get("explanation"),
        },
    )

    if tracked["link_state"] == "auto_linked":
        state.apply_event_to_schedule(tracked)

    return tracked


def ingest_events(events: list[ExecutionEvent], source_label: str) -> dict:
    tracked_events = [track_event(event, source_label) for event in events]
    conflicts = detect_conflicts()
    return {
        "source": source_label,
        "events_detected": len(tracked_events),
        "auto_linked": sum(1 for t in tracked_events if t["link_state"] == "auto_linked"),
        "needs_review": sum(1 for t in tracked_events if t["link_state"] == "pending_review"),
        "needs_clarification": sum(1 for t in tracked_events if t["link_state"] == "clarification_needed"),
        "unmatched": sum(1 for t in tracked_events if t["link_state"] == "unmatched"),
        "conflicts_detected": len(conflicts),
        "events": [public_event(t) for t in tracked_events],
        "conflicts": conflicts,
    }


def detect_conflicts() -> list[dict]:
    """
    SYNAPSE differentiator: multi-source conflict detection.

    Two reports of the same activity on the same day that disagree about status
    are a contradiction no single-source pipeline can see. Grouping is a
    UI-facing concern and lives here; the pairwise contradiction test is
    delegated to Adithyanbalu's detect_status_conflict.
    """
    groups: dict[tuple[str, str], list[dict]] = {}
    for event_id in state.event_order:
        tracked = state.events[event_id]
        activity_id = tracked.get("linked_activity_id") or (
            tracked["match"].get("matched_activity_id") if tracked.get("match") else None
        )
        if not activity_id:
            continue
        if tracked["link_state"] in {"rejected", "superseded"}:
            continue
        # An event that made no status claim cannot contradict one that did.
        if normalize_status(tracked["event"].get("status")) is None:
            continue
        event = tracked["event"]
        key = (activity_id, (event.get("event_date") or "undated"))
        groups.setdefault(key, []).append(tracked)

    found: list[dict] = []
    for (activity_id, event_date), tracked_list in groups.items():
        statuses = {normalize_status(t["event"].get("status")) for t in tracked_list}
        sources = {t["event"].get("source_id") for t in tracked_list}
        if len(statuses) < 2 or len(sources) < 2:
            continue

        conflict_id = f"CFL-{activity_id}-{event_date}"
        existing = state.conflicts.get(conflict_id)
        if existing and existing.get("resolved"):
            continue

        seen_sources: dict[str, int] = {}
        claims = []
        for t in sorted(tracked_list, key=lambda x: x["ingested_at"]):
            source_id = t["event"].get("source_id")
            seen_sources[source_id] = seen_sources.get(source_id, 0) + 1
            nth = seen_sources[source_id]
            claims.append(
                {
                    "event_id": t["event_id"],
                    "source_id": source_id,
                    # Distinguishes two sentences from the same report.
                    "claim_label": source_id if nth == 1 else f"{source_id} (report {nth})",
                    "source_type": t["event"].get("source_type"),
                    "source_label": t.get("source_label"),
                    "reported_at": (t["event"].get("end_time") or t["event"].get("start_time")
                                    or t["ingested_at"]),
                    "status": status_label(t["event"].get("status")),
                    "raw_text": t["event"].get("raw_text"),
                    "confidence": t["match"]["confidence"] if t.get("match") else None,
                }
            )

        # detect_status_conflict decides whether a pair is a hard contradiction.
        # Its message is phrased for schedule-vs-execution comparison, so the
        # wording is rewritten here for the source-vs-source case the planner is
        # actually looking at — and claims are named by report, not just source,
        # because one DPR can contain two sentences that disagree.
        contradictions = []
        for index, first in enumerate(claims):
            for second in claims[index + 1:]:
                conflict = (detect_status_conflict(first["status"], second["status"])
                            or detect_status_conflict(second["status"], first["status"]))
                if conflict:
                    contradictions.append(
                        {
                            "between": [first["claim_label"], second["claim_label"]],
                            "type": conflict.conflict_type,
                            "message": (
                                f"{first['claim_label']} reports {first['status']}, "
                                f"but {second['claim_label']} reports {second['status']}."
                            ),
                            "severity": conflict.severity,
                        }
                    )

        record = {
            "conflict_id": conflict_id,
            "activity_id": activity_id,
            "activity_name": state.activities.get(activity_id, {}).get("activity_name", ""),
            "event_date": event_date,
            "claims": claims,
            "contradictions": contradictions,
            "kind": "same_day",
            "severity": "HIGH" if contradictions else "MEDIUM",
            "resolved": False,
            "resolution": None,
            "detected_at": _now(),
        }

        if not existing:
            state.log_audit(
                stage="CONFLICT",
                summary=f"{activity_id} on {event_date}: "
                        + " vs ".join(f"{c['source_id']}={c['status']}" for c in claims),
                activity_id=activity_id,
                detail={"claims": claims, "contradictions": contradictions},
            )
        else:
            record["detected_at"] = existing["detected_at"]

        state.conflicts[conflict_id] = record
        found.append(record)

    found.extend(_detect_state_regressions())
    return found


#: States that contradict an activity already recorded as finished.
#: detect_status_conflict owns IN_PROGRESS and NOT_STARTED; ON_HOLD is added
#: here because its signature has no notion of a blocked activity, and "the
#: record says done, the field says blocked" is precisely the contradiction a
#: planner needs to see.
_REGRESSION_STATES = {
    ActivityStatus.IN_PROGRESS.value,
    ActivityStatus.NOT_STARTED.value,
    ActivityStatus.ON_HOLD.value,
}


def _detect_state_regressions() -> list[dict]:
    """
    The second kind of contradiction: a later report walks back an activity
    that an earlier source already recorded as finished.

    This is the spec's supervisor case — the DPR says complete, the supervisor
    on site says blocked — and it is invisible to same-day grouping because the
    two reports are days apart.
    """
    by_activity: dict[str, list[dict]] = {}
    for event_id in state.event_order:
        tracked = state.events[event_id]
        if tracked["link_state"] in {"rejected", "superseded", "unmatched"}:
            continue
        activity_id = tracked.get("linked_activity_id")
        if not activity_id or normalize_status(tracked["event"].get("status")) is None:
            continue
        by_activity.setdefault(activity_id, []).append(tracked)

    found: list[dict] = []
    for activity_id, tracked_list in by_activity.items():
        ordered = sorted(
            tracked_list,
            key=lambda t: (t["event"].get("event_date") or "", t["ingested_at"]),
        )
        completed_by = next(
            (t for t in ordered
             if normalize_status(t["event"].get("status")) == ActivityStatus.COMPLETED),
            None,
        )
        if not completed_by:
            continue

        regressions = [
            t for t in ordered
            if t["ingested_at"] > completed_by["ingested_at"]
            and status_label(t["event"].get("status")) in _REGRESSION_STATES
            and t["event"].get("source_id") != completed_by["event"].get("source_id")
        ]
        if not regressions:
            continue

        conflict_id = f"CFL-{activity_id}-STATE"
        existing = state.conflicts.get(conflict_id)
        if existing and existing.get("resolved"):
            continue

        claims = [
            {
                "event_id": t["event_id"],
                "source_id": t["event"].get("source_id"),
                "claim_label": t["event"].get("source_id"),
                "source_type": t["event"].get("source_type"),
                "source_label": t.get("source_label"),
                "reported_at": t["event"].get("event_date") or t["ingested_at"][:10],
                "status": status_label(t["event"].get("status")),
                "raw_text": t["event"].get("raw_text"),
                "confidence": t["match"]["confidence"] if t.get("match") else None,
            }
            for t in [completed_by, *regressions]
        ]

        contradictions = [
            {
                "between": [claims[0]["claim_label"], c["claim_label"]],
                "type": "STATE_REGRESSION",
                "message": (
                    f"{claims[0]['claim_label']} recorded this as COMPLETED on "
                    f"{claims[0]['reported_at']}, but {c['claim_label']} now reports "
                    f"{c['status']}."
                ),
                "severity": "HIGH",
            }
            for c in claims[1:]
        ]

        record = {
            "conflict_id": conflict_id,
            "activity_id": activity_id,
            "activity_name": state.activities.get(activity_id, {}).get("activity_name", ""),
            "event_date": claims[-1]["reported_at"],
            "claims": claims,
            "contradictions": contradictions,
            "kind": "state_regression",
            "severity": "HIGH",
            "resolved": False,
            "resolution": existing.get("resolution") if existing else None,
            "detected_at": existing["detected_at"] if existing else _now(),
        }

        if not existing:
            state.log_audit(
                stage="CONFLICT",
                summary=f"{activity_id}: recorded COMPLETED, but "
                        + " and ".join(f"{c['claim_label']} reports {c['status']}"
                                       for c in claims[1:]),
                activity_id=activity_id,
                detail={"claims": claims, "contradictions": contradictions},
            )

        state.conflicts[conflict_id] = record
        found.append(record)

    return found


def public_event(tracked: dict) -> dict:
    """Shape a tracked event for the UI — never hide uncertainty."""
    event = tracked["event"]
    match = tracked.get("match") or {}

    # An event the planner turned down has no live link, even though the engine
    # still has an opinion. Showing that opinion as `matched_activity_id` would
    # read as a link that is not there — the candidate list carries it instead.
    decided_against = tracked["link_state"] in {"rejected", "superseded"}
    activity_id = tracked.get("linked_activity_id") or (
        None if decided_against else match.get("matched_activity_id")
    )
    activity = state.activities.get(activity_id, {}) if activity_id else {}

    return {
        "event_id": tracked["event_id"],
        "raw_text": event.get("raw_text"),
        "description": event.get("description"),
        "discipline": event.get("discipline"),
        "activity_type": event.get("activity_type"),
        "asset": event.get("asset"),
        "location": event.get("location"),
        "status": event.get("status"),
        "event_type": event.get("event_type"),
        "event_date": event.get("event_date"),
        "quantity": event.get("quantity"),
        "unit": event.get("unit"),
        "source_id": event.get("source_id"),
        "source_type": event.get("source_type"),
        "source_reference": event.get("source_reference"),
        "source_label": tracked.get("source_label"),
        "extraction_confidence": event.get("extraction_confidence"),
        "match_confidence": match.get("confidence"),
        "confidence_band": tracked.get("confidence_band"),
        "decision": match.get("decision"),
        "link_state": tracked["link_state"],
        "matched_activity_id": activity_id,
        "matched_activity_name": activity.get("activity_name") or match.get("matched_activity_name"),
        "candidates": match.get("candidates", []),
        "explanation": match.get("explanation"),
        "proposed_activity_id": match.get("matched_activity_id"),
        "clarification": tracked.get("clarification"),
        "review": tracked.get("review"),
        "ingested_at": tracked["ingested_at"],
    }


# ===========================================================================
# FastAPI application
# ===========================================================================

@asynccontextmanager
async def lifespan(_: FastAPI):
    state.bootstrap()
    yield


app = FastAPI(
    title="SYNAPSE",
    description="Synchronized NLP Activity-to-Plan Scheduling Engine — integration API and UI",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- request models ---------------------------------------------------------

class TextIngestRequest(BaseModel):
    text: str = Field(..., description="Pasted daily report or free text")
    source_id: str = Field(default="pasted_text")
    source_type: str = Field(default="daily_report")


class SupervisorMessageRequest(BaseModel):
    text: str = Field(..., description="What the supervisor typed or spoke")
    supervisor: str = Field(default="site_supervisor")


class ClarifyRequest(BaseModel):
    event_id: str
    answer: str = Field(..., description="Chosen option label, activity_id, or free text")


class ReviewRequest(BaseModel):
    decision: str = Field(..., description="approve | reject | reassign")
    activity_id: Optional[str] = Field(default=None, description="Required for reassign")
    reviewer: str = Field(default="planner")
    note: Optional[str] = None


class ConflictResolveRequest(BaseModel):
    trusted_source_id: Optional[str] = Field(default=None)
    action: str = Field(default="trust", description="trust | investigate")
    reviewer: str = Field(default="planner")
    note: Optional[str] = None


# --- health & meta ----------------------------------------------------------

@app.get("/api/health", tags=["Meta"])
def health() -> dict:
    return {
        "status": "ok",
        "module": "frontend_integration",
        "owner": "aliadnan",
        "activities_loaded": len(state.activities),
        "historical_records": len(state.kb) if state.kb else 0,
        "events_tracked": len(state.events),
        "llm_extraction_active": bool(os.environ.get("OPENROUTER_API_KEY")),
        "modules": {
            "event_extraction": "adithyan",
            "schedule_parser": "yazeen",
            "matching_engine": "amritha",
            "progress_analytics": "adithyanbalu",
            "knowledge_base": "adithyagopan",
        },
    }


@app.post("/api/login", tags=["Auth"])
def login(form: OAuth2PasswordRequestForm = Depends()) -> dict:
    user = _USERS.get(form.username)
    if not user or not _secrets.compare_digest(_hash_pw(form.password), user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    token = _create_token(user["username"], user["role"])
    return {
        "access_token": token,
        "token_type": "bearer",
        "role": user["role"],
        "display_name": user["display_name"],
    }


@app.get("/api/me", tags=["Auth"])
def me(user: dict = Depends(get_current_user)) -> dict:
    return user


@app.get("/api/demo/sources", tags=["Meta"])
def demo_sources() -> dict:
    """Bundled sample sources so the demo never depends on a local file picker."""
    files = []
    for path in sorted(DATA.glob("daily_reports/*.txt")) + sorted(DATA.glob("discipline_report_*.csv")):
        files.append(
            {
                "name": path.name,
                "path": str(path.relative_to(ROOT)).replace("\\", "/"),
                "kind": "Daily report (DPR)" if path.suffix == ".txt" else "Discipline sheet",
            }
        )
    return {"sources": files}


# --- 0. agentic supervisor input -------------------------------------------

def _candidate_activities(text: str, top_k: int = 5) -> list[dict]:
    """The activities worth offering as clarification options, best first."""
    try:
        match = state.engine.match_event(text, top_k=top_k)
    except Exception:
        return list(state.activities.values())[:top_k]

    ranked = [
        state.activities[c["activity_id"]]
        for c in match.get("candidates", [])
        if c["activity_id"] in state.activities
    ]
    return ranked or list(state.activities.values())[:top_k]


def apply_supervisor_choice(tracked: dict, activity_id: str, supervisor: str) -> None:
    """
    A supervisor who names the activity has not made a suggestion — they have
    answered the question. Their choice overrides the engine's ranking, is
    recorded as positive feedback, and updates the schedule immediately.
    """
    tracked["linked_activity_id"] = activity_id
    tracked["link_state"] = "approved"
    tracked["review"] = {
        "decision": "approve",
        "reviewer": supervisor,
        "activity_id": activity_id,
        "note": "Chosen by the supervisor at input time",
        "reviewed_at": _now(),
    }

    event_text = tracked["event"].get("raw_text") or tracked["event"].get("description", "")
    state.engine.record_feedback(tracked["event_id"], event_text, activity_id, True)

    state.log_audit(
        stage="REVIEW",
        summary=f"{supervisor} confirmed {activity_id} at input time",
        event_id=tracked["event_id"],
        activity_id=activity_id,
        actor=supervisor,
        detail={"engine_proposal": (tracked.get("match") or {}).get("matched_activity_id")},
    )
    state.log_audit(
        stage="LEARN",
        summary=f"Feedback recorded (positive) — "
                f"{len(state.engine.feedback_store)} corrections in store",
        event_id=tracked["event_id"],
        activity_id=activity_id,
        actor=supervisor,
    )
    state.apply_event_to_schedule(tracked, actor=supervisor)


@app.post("/api/supervisor/message", tags=["Supervisor"])
def supervisor_message(req: SupervisorMessageRequest, user: dict = Depends(require_supervisor)) -> dict:
    """
    Agentic clarification at input time.

    If Adithyan's extractor cannot pin the event down, SYNAPSE asks one
    targeted question instead of guessing — the ambiguity dies at the source.
    """
    result = state.extractor.process_text(
        req.text,
        source_id=f"supervisor::{req.supervisor}",
        source_type=SourceType.SUPERVISOR_MESSAGE,
        reference_date=date.today(),
    )
    if not result.events:
        raise HTTPException(422, "Could not read an execution event from that message.")

    event = result.events[0]
    # A supervisor reporting now is reporting about now. Same defensible default
    # as the clarify path, recorded in the audit so it is never mistaken for a
    # date the supervisor actually gave.
    assumed_date = None
    if not event.event_date:
        assumed_date = date.today().isoformat()
        event.event_date = assumed_date

    state.log_audit(
        stage="INGEST",
        summary=f'Supervisor message: "{req.text[:100]}"',
        event_id=event.event_id,
        actor=req.supervisor,
        detail={"channel": "supervisor", "assumed_event_date": assumed_date},
    )

    # Ask Adithyan's clarifier to phrase the question over Amritha's top
    # candidates rather than over all 41 activities. Offering "Fabricate spool"
    # as an option for "erection completed" is not a question worth asking.
    request = generate_clarification(event, _candidate_activities(req.text))
    if request:
        state.pending_clarifications[event.event_id] = {
            "event": event,
            "supervisor": req.supervisor,
            "question": request.question,
            "options": request.options or [],
            "missing_fields": request.missing_fields,
        }
        state.log_audit(
            stage="CLARIFY",
            summary=request.question,
            event_id=event.event_id,
            detail={"missing_fields": request.missing_fields, "options": request.options},
        )
        return {
            "event_id": event.event_id,
            "needs_clarification": True,
            "question": request.question,
            "options": request.options or [],
            "missing_fields": request.missing_fields,
            "raw_text": req.text,
        }

    tracked = track_event(event, source_label=f"Supervisor · {req.supervisor}")
    detect_conflicts()
    return {"event_id": event.event_id, "needs_clarification": False, "event": public_event(tracked)}


@app.post("/api/supervisor/clarify", tags=["Supervisor"])
def supervisor_clarify(req: ClarifyRequest, user: dict = Depends(require_supervisor)) -> dict:
    """Apply the supervisor's answer, then run the now-unambiguous event."""
    pending = state.pending_clarifications.pop(req.event_id, None)
    if pending is None:
        raise HTTPException(404, f"No pending clarification for '{req.event_id}'")

    event: ExecutionEvent = pending["event"]
    answer = req.answer.strip()

    # An option like "PIP-002 — Erect Line 24-XX spool S-101" resolves the
    # asset, discipline and location in one go; free text only fills one field.
    resolved_activity = None
    for activity_id, activity in state.activities.items():
        if answer == activity_id or answer.startswith(f"{activity_id} "):
            resolved_activity = activity
            break

    if resolved_activity:
        event = apply_clarification(event, "asset", resolved_activity["activity_name"])
        if resolved_activity.get("discipline"):
            event.discipline = resolved_activity["discipline"]
        if resolved_activity.get("location"):
            event.location = resolved_activity["location"]
        event.description = f"{event.description} — {resolved_activity['activity_name']}"
    else:
        field = pending["missing_fields"][0] if pending["missing_fields"] else "asset"
        event = apply_clarification(event, field, answer)
        event.description = f"{event.description} ({answer})"

    # A message arriving now is about now — a defensible default, and the audit
    # records that SYNAPSE supplied it. Status gets no such default: guessing
    # "completed" would silently close an activity the supervisor never closed.
    assumed_date = None
    if not event.event_date:
        assumed_date = date.today().isoformat()
        event.event_date = assumed_date

    state.log_audit(
        stage="CLARIFY",
        summary=f'Supervisor answered "{answer}"',
        event_id=event.event_id,
        actor=pending["supervisor"],
        detail={
            "question": pending["question"],
            "answer": answer,
            "resolved_activity": resolved_activity["activity_id"] if resolved_activity else None,
            "assumed_event_date": assumed_date,
        },
    )

    tracked = track_event(event, source_label=f"Supervisor · {pending['supervisor']}")

    # The matcher scores off raw_text, which still reads "Erection completed
    # today." — the clarified fields never reach it. When the supervisor named
    # an activity outright, that answer is authoritative, not a hint.
    if resolved_activity:
        apply_supervisor_choice(tracked, resolved_activity["activity_id"], pending["supervisor"])

    detect_conflicts()
    return {"event_id": event.event_id, "needs_clarification": False, "event": public_event(tracked)}


# --- 1. upload / input ------------------------------------------------------

@app.post("/api/events/extract", tags=["Events"])
def extract_from_text(req: TextIngestRequest, user: dict = Depends(require_supervisor)) -> dict:
    try:
        source_type = SourceType(req.source_type)
    except ValueError:
        raise HTTPException(422, f"Unknown source_type '{req.source_type}'")

    state.log_audit(
        stage="INGEST",
        summary=f"Pasted text ingested ({len(req.text)} chars) as {source_type.value}",
        detail={"source_id": req.source_id},
    )
    result = state.extractor.process_text(
        req.text, source_id=req.source_id, source_type=source_type, reference_date=date.today()
    )
    summary = ingest_events(result.events, source_label=f"Pasted · {req.source_id}")
    summary["warnings"] = result.warnings
    summary["processing_time_ms"] = result.processing_time_ms
    return summary


@app.post("/api/events/upload", tags=["Events"])
async def upload_document(file: UploadFile = File(...), user: dict = Depends(require_supervisor)) -> dict:
    suffix = Path(file.filename or "").suffix.lower()
    if suffix not in UPLOAD_SUFFIXES:
        raise HTTPException(
            415, f"Unsupported file type '{suffix}'. Supported: {', '.join(sorted(UPLOAD_SUFFIXES))}"
        )

    tmp_dir = tempfile.mkdtemp(prefix="synapse_upload_")
    tmp_path = Path(tmp_dir) / (file.filename or f"upload{suffix}")
    try:
        with open(tmp_path, "wb") as handle:
            shutil.copyfileobj(file.file, handle)

        state.log_audit(
            stage="INGEST",
            summary=f"Uploaded {file.filename}",
            detail={"size_bytes": tmp_path.stat().st_size, "suffix": suffix},
        )
        result = state.extractor.process_file(
            str(tmp_path), source_id=tmp_path.stem, reference_date=date.today()
        )
        summary = ingest_events(result.events, source_label=f"Upload · {file.filename}")
        summary["warnings"] = result.warnings
        summary["processing_time_ms"] = result.processing_time_ms
        return summary
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@app.post("/api/events/load-sample", tags=["Events"])
def load_sample(path: str = Query(..., description="Repo-relative path from /api/demo/sources"), user: dict = Depends(require_supervisor)) -> dict:
    target = (ROOT / path).resolve()
    if not str(target).startswith(str(DATA.resolve())) or not target.exists():
        raise HTTPException(404, f"Sample source '{path}' not found")

    state.log_audit(stage="INGEST", summary=f"Sample source loaded: {target.name}")
    result = state.extractor.process_file(
        str(target), source_id=target.stem, reference_date=date.today()
    )
    summary = ingest_events(result.events, source_label=f"Sample · {target.name}")
    summary["warnings"] = result.warnings
    summary["processing_time_ms"] = result.processing_time_ms
    return summary


# --- 2. extracted events ----------------------------------------------------

@app.get("/api/events", tags=["Events"])
def list_events(link_state: Optional[str] = None, discipline: Optional[str] = None) -> dict:
    rows = [public_event(state.events[eid]) for eid in state.event_order]
    if link_state:
        rows = [r for r in rows if r["link_state"] == link_state]
    if discipline:
        rows = [r for r in rows if (r["discipline"] or "").lower() == discipline.lower()]
    return {"events": rows, "count": len(rows)}


@app.get("/api/events/{event_id}", tags=["Events"])
def get_event(event_id: str) -> dict:
    tracked = state.events.get(event_id)
    if not tracked:
        raise HTTPException(404, f"Unknown event '{event_id}'")
    return public_event(tracked)


# --- 3. matching review queue ----------------------------------------------

@app.get("/api/matches/queue", tags=["Review"])
def review_queue() -> dict:
    queue = [
        public_event(state.events[eid])
        for eid in state.event_order
        if state.events[eid]["link_state"] in {"pending_review", "clarification_needed", "unmatched"}
    ]
    queue.sort(key=lambda r: r["match_confidence"] or 0.0, reverse=True)
    return {
        "queue": queue,
        "count": len(queue),
        "auto_threshold": state.engine.auto_threshold,
        "review_threshold": state.engine.review_threshold,
    }


@app.get("/api/activities", tags=["Review"])
def list_activities(q: Optional[str] = None, limit: int = 50) -> dict:
    """Activity picker for the 'Choose another' reviewer action."""
    rows = [
        {
            "activity_id": activity_id,
            "activity_name": activity.get("activity_name", ""),
            "discipline": activity.get("discipline", ""),
            "location": activity.get("location", ""),
            "planned_start": activity.get("planned_start"),
            "planned_finish": activity.get("planned_finish"),
        }
        for activity_id, activity in state.activities.items()
    ]
    if q:
        needle = q.lower()
        rows = [
            r for r in rows
            if needle in r["activity_id"].lower()
            or needle in r["activity_name"].lower()
            or needle in (r["discipline"] or "").lower()
            or needle in (r["location"] or "").lower()
        ]
    return {"activities": rows[:limit], "count": len(rows)}


@app.post("/api/matches/{event_id}/review", tags=["Review"])
def review_match(event_id: str, req: ReviewRequest, user: dict = Depends(require_admin)) -> dict:
    """
    The human decision point — and the active-learning trigger.

    Every approve/reject/reassign is written back into Amritha's feedback store,
    so the same phrasing scores higher (or lower) the next time it arrives.
    """
    tracked = state.events.get(event_id)
    if not tracked:
        raise HTTPException(404, f"Unknown event '{event_id}'")

    decision = req.decision.strip().lower()
    if decision not in {"approve", "reject", "reassign"}:
        raise HTTPException(422, "decision must be approve, reject or reassign")

    match = tracked.get("match") or {}
    if decision == "reassign":
        if not req.activity_id:
            raise HTTPException(422, "reassign requires activity_id")
        if req.activity_id not in state.activities:
            raise HTTPException(404, f"Unknown activity '{req.activity_id}'")
        activity_id = req.activity_id
    else:
        activity_id = match.get("matched_activity_id")
        if decision == "approve" and not activity_id:
            raise HTTPException(422, "Nothing to approve — no candidate matched. Use reassign.")

    approved = decision in {"approve", "reassign"}
    event_text = tracked["event"].get("raw_text") or tracked["event"].get("description", "")

    if activity_id:
        state.engine.record_feedback(event_id, event_text, activity_id, approved)

    tracked["review"] = {
        "decision": decision,
        "reviewer": req.reviewer,
        "activity_id": activity_id,
        "note": req.note,
        "reviewed_at": _now(),
    }
    tracked["link_state"] = "approved" if approved else "rejected"
    tracked["linked_activity_id"] = activity_id if approved else None

    state.log_audit(
        stage="REVIEW",
        summary=f"{req.reviewer} {decision}d {event_id}"
                + (f" → {activity_id}" if activity_id and approved else ""),
        event_id=event_id,
        activity_id=activity_id if approved else None,
        actor=req.reviewer,
        detail={"note": req.note, "previous_decision": match.get("decision")},
    )
    state.log_audit(
        stage="LEARN",
        summary=f"Feedback recorded ({'positive' if approved else 'negative'}) — "
                f"{len(state.engine.feedback_store)} corrections in store",
        event_id=event_id,
        activity_id=activity_id,
        actor=req.reviewer,
    )

    if approved:
        state.apply_event_to_schedule(tracked, actor=req.reviewer)
    detect_conflicts()

    return {"event": public_event(tracked), "feedback_count": len(state.engine.feedback_store)}


# --- 4. schedule / gantt ----------------------------------------------------

@app.get("/api/schedule", tags=["Schedule"])
def get_schedule(discipline: Optional[str] = None, only_touched: bool = False) -> dict:
    rows = [state.schedule_row(activity_id) for activity_id in state.activities]
    if discipline:
        rows = [r for r in rows if (r["discipline"] or "").lower() == discipline.lower()]
    if only_touched:
        rows = [r for r in rows if r["evidence_event_ids"]]
    rows.sort(key=lambda r: (r["planned_start"] or "", r["activity_id"]))

    dates = [
        d
        for r in rows
        for d in (r["planned_start"], r["planned_finish"], r["actual_start"], r["actual_finish"])
        if d
    ]
    return {
        "activities": rows,
        "count": len(rows),
        "window": {"start": min(dates) if dates else None, "end": max(dates) if dates else None},
        "disciplines": sorted({r["discipline"] for r in rows if r["discipline"]}),
    }


@app.get("/api/progress", tags=["Schedule"])
def get_progress() -> dict:
    summary = calculate_project_summary(state.activity_objects())
    rows = [state.schedule_row(a) for a in state.activities]
    variances = [r["variance_days"] for r in rows if r["variance_days"] is not None]

    return {
        "total_activities": summary.total_activities,
        "completed_activities": summary.completed_activities,
        "in_progress_activities": summary.in_progress_activities,
        "delayed_activities": summary.delayed_activities,
        "overall_progress_percent": round(summary.overall_progress * 100, 1),
        "activities_with_actuals": len([r for r in rows if r["evidence_event_ids"]]),
        "average_variance_days": round(sum(variances) / len(variances), 2) if variances else 0.0,
        "worst_variance_days": max(variances) if variances else 0,
        "events_ingested": len(state.events),
        "auto_linked": sum(1 for e in state.events.values() if e["link_state"] == "auto_linked"),
        "approved": sum(1 for e in state.events.values() if e["link_state"] == "approved"),
        "in_review_queue": sum(
            1
            for e in state.events.values()
            if e["link_state"] in {"pending_review", "clarification_needed", "unmatched"}
        ),
        "open_conflicts": sum(1 for c in state.conflicts.values() if not c["resolved"]),
        "corrections_learned": len(state.engine.feedback_store) if state.engine else 0,
    }


# --- 5. audit trail ---------------------------------------------------------

@app.get("/api/audit", tags=["Audit"])
def get_audit(stage: Optional[str] = None, limit: int = 200) -> dict:
    entries = state.audit
    if stage:
        entries = [e for e in entries if e["stage"] == stage.upper()]
    return {"entries": list(reversed(entries))[:limit], "count": len(entries)}


@app.get("/api/audit/event/{event_id}", tags=["Audit"])
def get_audit_chain(event_id: str) -> dict:
    """
    The provenance chain for one event:
        source → extracted event → match → reviewer decision → schedule update.
    """
    tracked = state.events.get(event_id)
    if not tracked:
        raise HTTPException(404, f"Unknown event '{event_id}'")

    entries = [e for e in state.audit if e["event_id"] == event_id]
    activity_id = tracked.get("linked_activity_id")
    return {
        "event_id": event_id,
        "chain": entries,
        "event": public_event(tracked),
        "schedule_state": state.schedule_row(activity_id) if activity_id else None,
    }


# --- 6. conflict resolution -------------------------------------------------

@app.get("/api/conflicts", tags=["Conflicts"])
def list_conflicts(include_resolved: bool = False) -> dict:
    detect_conflicts()
    rows = list(state.conflicts.values())
    if not include_resolved:
        rows = [c for c in rows if not c["resolved"]]
    rows.sort(key=lambda c: (c["severity"] != "HIGH", c["detected_at"]))
    return {"conflicts": rows, "count": len(rows)}


@app.post("/api/conflicts/{conflict_id}/resolve", tags=["Conflicts"])
def resolve_conflict(conflict_id: str, req: ConflictResolveRequest, user: dict = Depends(require_admin)) -> dict:
    conflict = state.conflicts.get(conflict_id)
    if not conflict:
        raise HTTPException(404, f"Unknown conflict '{conflict_id}'")

    if req.action == "investigate":
        conflict["resolution"] = {
            "action": "investigate",
            "reviewer": req.reviewer,
            "note": req.note,
            "decided_at": _now(),
        }
        state.log_audit(
            stage="CONFLICT",
            summary=f"{req.reviewer} flagged {conflict_id} for site investigation",
            activity_id=conflict["activity_id"],
            actor=req.reviewer,
            detail={"note": req.note},
        )
        return conflict

    if not req.trusted_source_id:
        raise HTTPException(422, "trusted_source_id is required when action is 'trust'")

    trusted = [c for c in conflict["claims"] if c["source_id"] == req.trusted_source_id]
    if not trusted:
        raise HTTPException(404, f"'{req.trusted_source_id}' is not a source in this conflict")

    # The planner trusts a *source*, not one sentence from it. If that source
    # contributed several claims, all of them stand — applied in ingestion
    # order, so its latest word is the one the schedule ends up with.
    trusted_claim = trusted[-1]
    trusted_event_ids = {c["event_id"] for c in trusted}
    for claim in conflict["claims"]:
        tracked = state.events.get(claim["event_id"])
        if not tracked:
            continue
        if claim["event_id"] in trusted_event_ids:
            tracked["linked_activity_id"] = conflict["activity_id"]
            tracked["link_state"] = "approved"
            tracked["review"] = {
                "decision": "approve",
                "reviewer": req.reviewer,
                "activity_id": conflict["activity_id"],
                "note": f"Trusted source in {conflict_id}",
                "reviewed_at": _now(),
            }
            state.apply_event_to_schedule(tracked, actor=req.reviewer)
        else:
            tracked["link_state"] = "superseded"
            tracked["review"] = {
                "decision": "superseded",
                "reviewer": req.reviewer,
                "activity_id": conflict["activity_id"],
                "note": f"Not trusted in {conflict_id}",
                "reviewed_at": _now(),
            }

    conflict["resolved"] = True
    conflict["resolution"] = {
        "action": "trust",
        "trusted_source_id": req.trusted_source_id,
        "trusted_status": trusted_claim["status"],
        "reviewer": req.reviewer,
        "note": req.note,
        "decided_at": _now(),
    }
    state.log_audit(
        stage="CONFLICT",
        summary=f"{req.reviewer} trusted {req.trusted_source_id} "
                f"({trusted_claim['status']}) for {conflict['activity_id']}",
        event_id=trusted_claim["event_id"],
        activity_id=conflict["activity_id"],
        actor=req.reviewer,
        detail={
            "rejected_sources": [
                c["source_id"] for c in conflict["claims"] if c["source_id"] != req.trusted_source_id
            ],
            "note": req.note,
        },
    )
    return conflict


# --- 7. risk dashboard ------------------------------------------------------

@app.get("/api/risk", tags=["Risk"])
def risk_dashboard(limit: int = 12, discipline: Optional[str] = None) -> dict:
    """
    Forward-looking risk: Adithyagopan's historical delay intelligence combined
    with the live schedule variance from Adithyanbalu's module.
    """
    rows = []
    for activity_id, activity in state.activities.items():
        if discipline and (activity.get("discipline") or "").lower() != discipline.lower():
            continue
        schedule = state.schedule_row(activity_id)
        if schedule["status"] == ActivityStatus.COMPLETED.value:
            continue

        historical = state.historical_risk(activity_id)
        rows.append(
            {
                "activity_id": activity_id,
                "activity_name": activity.get("activity_name", ""),
                "discipline": activity.get("discipline", ""),
                "location": activity.get("location", ""),
                "planned_start": activity.get("planned_start"),
                "planned_finish": activity.get("planned_finish"),
                "status": schedule["status"],
                "variance_days": schedule["variance_days"],
                "schedule_risk": schedule["schedule_risk"],
                "historical_risk": historical.get("risk_level", "UNKNOWN"),
                "delay_rate_percent": round(historical.get("delay_frequency", 0.0) * 100),
                "avg_variance_days": historical.get("avg_variance_days", 0.0),
                "suggested_buffer_days": historical.get("suggested_buffer_days", 0),
                "historical_matches": historical.get("historical_matches", 0),
                "evidence_confidence": historical.get("confidence", "none"),
                "common_causes": historical.get("common_delay_causes", [])[:3],
            }
        )

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3}
    rows.sort(key=lambda r: (order.get(r["historical_risk"], 3), -r["delay_rate_percent"]))
    return {
        "activities": rows[:limit],
        "count": len(rows),
        "high": sum(1 for r in rows if r["historical_risk"] == "HIGH"),
        "medium": sum(1 for r in rows if r["historical_risk"] == "MEDIUM"),
        "low": sum(1 for r in rows if r["historical_risk"] == "LOW"),
    }


@app.get("/api/risk/{activity_id}/evidence", tags=["Risk"])
def risk_evidence(activity_id: str, limit: int = 8) -> dict:
    """The historical records behind a risk verdict — never assert without evidence."""
    if activity_id not in state.activities:
        raise HTTPException(404, f"Unknown activity '{activity_id}'")

    activity = state.activities[activity_id]
    return {
        "activity_id": activity_id,
        "activity_name": activity.get("activity_name", ""),
        "assessment": state.historical_risk(activity_id),
        "records": _semantic_records(activity.get("activity_name", ""), limit),
    }


@app.get("/api/productivity", tags=["Risk"])
def productivity_benchmarks() -> dict:
    benchmarks = state.productivity.all_benchmarks()
    return {
        "benchmarks": [
            b.model_dump() if hasattr(b, "model_dump") else dict(b.__dict__) for b in benchmarks
        ],
        "count": len(benchmarks),
    }


# --- 8. historical knowledge search ----------------------------------------

def _semantic_records(query: str, limit: int) -> list[dict]:
    """Flatten KnowledgeBase.semantic_search's {"record", "score"} hits into rows."""
    records = []
    for hit in state.kb.semantic_search(query, top_k=limit):
        record = hit["record"]
        payload = record.model_dump() if hasattr(record, "model_dump") else dict(record)
        payload["similarity"] = hit.get("score")
        records.append(payload)
    return records


@app.get("/api/history/search", tags=["History"])
def history_search(q: str = Query(..., min_length=2), limit: int = 10) -> dict:
    """Natural-language query over institutional memory."""
    answer = state.nl_query.query(q)
    state.log_audit(
        stage="HISTORY", summary=f'Historical query: "{q}"', detail={"intent": answer.get("intent")}
    )
    return {
        "question": q,
        "intent": answer.get("intent"),
        "summary": answer.get("summary"),
        "answer": answer.get("answer"),
        "supporting_records": _semantic_records(q, limit),
        "total_records": len(state.kb),
    }


# --- settings ---------------------------------------------------------------

class SettingsUpdate(BaseModel):
    openrouter_api_key: str | None = Field(None, description="OpenRouter API key")
    model: str | None = Field(None, description="Model identifier for LLM extraction")


def _mask_key(key: str | None) -> str | None:
    """Return a masked version of the key, showing only the last 4 characters."""
    if not key:
        return None
    if len(key) <= 4:
        return "****"
    return "*" * (len(key) - 4) + key[-4:]


@app.get("/api/settings", tags=["Settings"])
def get_settings() -> dict:
    """Return current LLM settings (API key is masked)."""
    return {
        "openrouter_api_key": _mask_key(state._openrouter_key),
        "key_configured": bool(state._openrouter_key),
        "model": state._openrouter_model,
    }


@app.post("/api/settings", tags=["Settings"])
def update_settings(body: SettingsUpdate, user: dict = Depends(require_admin)) -> dict:
    """Update LLM settings and re-initialise the extraction pipeline."""
    if body.openrouter_api_key is not None:
        state._openrouter_key = body.openrouter_api_key or None
    if body.model is not None:
        state._openrouter_model = body.model

    try:
        state.extractor = ExtractionPipeline(
            use_llm=bool(state._openrouter_key), llm_api_key=state._openrouter_key
        )
        state.log_audit(
            stage="SYSTEM",
            summary="LLM settings updated",
            detail={"model": state._openrouter_model, "key_set": bool(state._openrouter_key)},
        )
        return {"status": "ok", "key_configured": bool(state._openrouter_key), "model": state._openrouter_model}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to reinitialise extractor: {exc}")


# --- session control --------------------------------------------------------

@app.post("/api/session/reset", tags=["Meta"])
def reset_session(user: dict = Depends(require_admin)) -> dict:
    """Clear ingested events, conflicts and actuals — keeps the loaded schedule."""
    state.events.clear()
    state.event_order.clear()
    state.conflicts.clear()
    state.actuals.clear()
    state.audit.clear()
    state.pending_clarifications.clear()
    if state.engine:
        state.engine.feedback_store.clear()
    state.log_audit(stage="SYSTEM", summary="Session reset — schedule retained")
    return {"status": "reset", "activities_loaded": len(state.activities)}


# --- static frontend --------------------------------------------------------

FRONTEND_DIST = FRONTEND / "dist"

if FRONTEND_DIST.exists():
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_frontend(full_path: str = "") -> FileResponse:
        """SPA catch-all — serve Vite-built React frontend."""
        file_path = FRONTEND_DIST / full_path
        if file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(FRONTEND_DIST / "index.html"))
elif FRONTEND.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(str(FRONTEND / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=False)
