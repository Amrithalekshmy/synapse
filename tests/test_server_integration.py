"""
Integration tests for the SYNAPSE API server (Aliadnan's module).

These exercise the seams between modules — the places where one teammate's
output becomes another's input — rather than re-testing logic each module
already covers in its own suite.

The app is expensive to boot (it loads a sentence-transformer and parses the
schedule), so a single module-scoped client is shared and each test resets the
session state instead.
"""

import pytest
from fastapi.testclient import TestClient

import server
from progress_analytics.status import ActivityStatus


@pytest.fixture(scope="module")
def client():
    with TestClient(server.app) as test_client:
        yield test_client


@pytest.fixture(autouse=True)
def clean_session(client):
    client.post("/api/session/reset")
    yield


DPR_28 = "data/daily_reports/DPR_2026_08_28.txt"
DPR_29 = "data/daily_reports/DPR_2026_08_29.txt"
PIPING_SHEET = "data/discipline_report_piping.csv"


def load_sample(client, path):
    response = client.post("/api/events/load-sample", params={"path": path})
    assert response.status_code == 200, response.text
    return response.json()


# ---------------------------------------------------------------- bootstrap

def test_health_reports_every_module_loaded(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert body["activities_loaded"] > 0, "Yazeen's parser produced no activities"
    assert body["historical_records"] > 0, "Adithyagopan's knowledge base is empty"
    assert set(body["modules"]) == {
        "event_extraction", "schedule_parser", "matching_engine",
        "progress_analytics", "knowledge_base",
    }


def test_index_and_static_assets_are_served(client):
    assert client.get("/").status_code == 200
    assert client.get("/static/app.js").status_code == 200
    assert client.get("/static/styles.css").status_code == 200


# ------------------------------------------------------------ ingest → match

def test_daily_report_produces_matched_events(client):
    summary = load_sample(client, DPR_28)

    assert summary["events_detected"] > 0
    assert summary["auto_linked"] > 0, "no event cleared the auto-link threshold"
    assert (
        summary["events_detected"]
        == summary["auto_linked"] + summary["needs_review"]
        + summary["needs_clarification"] + summary["unmatched"]
    ), "every event must land in exactly one routing bucket"

    for event in summary["events"]:
        assert event["raw_text"], "the original text must survive to the UI"
        assert 0.0 <= event["extraction_confidence"] <= 1.0
        assert event["confidence_band"] in {"HIGH", "MEDIUM", "LOW"}


def test_event_dates_stay_within_the_reporting_period(client):
    """
    Regression: normalize_date used to re-read an already-ISO date as d-m-y,
    turning 2026-08-28 into 2028-08-26 and making every variance meaningless.
    """
    summary = load_sample(client, DPR_28)
    dated = [e["event_date"] for e in summary["events"] if e["event_date"]]

    assert dated, "no event carried a date"
    assert all(d.startswith("2026-08") for d in dated), f"dates drifted: {sorted(set(dated))}"


def test_unsupported_upload_is_rejected(client):
    response = client.post(
        "/api/events/upload", files={"file": ("notes.exe", b"binary", "application/octet-stream")}
    )
    assert response.status_code == 415


def test_sample_loader_refuses_paths_outside_the_data_directory(client):
    response = client.post("/api/events/load-sample", params={"path": "../../etc/passwd"})
    assert response.status_code == 404


# --------------------------------------------------------- reviewer decisions

def test_review_queue_only_holds_undecided_events(client):
    load_sample(client, DPR_28)
    queue = client.get("/api/matches/queue").json()

    assert queue["review_threshold"] < queue["auto_threshold"]
    for event in queue["queue"]:
        assert event["link_state"] in {"pending_review", "clarification_needed", "unmatched"}

    scores = [e["match_confidence"] or 0.0 for e in queue["queue"]]
    assert scores == sorted(scores, reverse=True), "queue must lead with the strongest candidate"


def test_approving_a_match_updates_the_schedule_and_teaches_the_matcher(client):
    load_sample(client, DPR_28)
    queue = client.get("/api/matches/queue").json()["queue"]
    reviewable = [e for e in queue if e["proposed_activity_id"]]
    assert reviewable, "expected at least one event with a proposal awaiting review"

    target = reviewable[0]
    before = client.get("/api/progress").json()["corrections_learned"]

    body = client.post(
        f"/api/matches/{target['event_id']}/review",
        json={"decision": "approve", "reviewer": "planner"},
    ).json()

    assert body["event"]["link_state"] == "approved"
    assert body["feedback_count"] == before + 1, "the correction was not fed back to the matcher"

    activity_id = body["event"]["matched_activity_id"]
    row = next(
        r for r in client.get("/api/schedule").json()["activities"]
        if r["activity_id"] == activity_id
    )
    assert target["event_id"] in row["evidence_event_ids"], "the schedule must cite its evidence"
    if target["status"] == "completed":
        assert row["actual_finish"], "an approved completion must produce an actual finish date"
        assert row["status"] == "COMPLETED"


def test_an_approved_completion_sets_the_actual_finish_date(client):
    """
    Drives the completion path explicitly rather than hoping the sample data
    leaves a completed event in the queue — most of them auto-link.
    """
    asked = client.post(
        "/api/supervisor/message", json={"text": "Hydrotest of Line 26 was completed today."}
    ).json()

    if asked["needs_clarification"]:
        asked = client.post(
            "/api/supervisor/clarify", json={"event_id": asked["event_id"], "answer": "PIP-014"}
        ).json()

    event = asked["event"]
    assert event["status"] == "completed"
    activity_id = event["matched_activity_id"]
    assert activity_id, "a clarified completion must end up linked"

    row = next(
        r for r in client.get("/api/schedule").json()["activities"]
        if r["activity_id"] == activity_id
    )
    assert row["status"] == "COMPLETED"
    assert row["actual_finish"] == event["event_date"]
    assert row["variance_days"] is not None
    assert event["event_id"] in row["evidence_event_ids"]


def test_rejecting_a_match_leaves_the_schedule_untouched(client):
    load_sample(client, DPR_28)
    queue = client.get("/api/matches/queue").json()["queue"]
    if not queue:
        pytest.skip("nothing landed in the review queue")

    target = queue[0]
    body = client.post(
        f"/api/matches/{target['event_id']}/review",
        json={"decision": "reject", "reviewer": "planner"},
    ).json()

    assert body["event"]["link_state"] == "rejected"
    assert body["event"]["matched_activity_id"] is None

    touched = client.get("/api/schedule", params={"only_touched": True}).json()
    assert all(target["event_id"] not in r["evidence_event_ids"] for r in touched["activities"])


def test_reassigning_links_the_activity_the_planner_chose(client):
    load_sample(client, DPR_28)
    queue = client.get("/api/matches/queue").json()["queue"]
    if not queue:
        pytest.skip("nothing landed in the review queue")

    chosen = client.get("/api/activities", params={"q": "PIP-013"}).json()["activities"][0]
    body = client.post(
        f"/api/matches/{queue[0]['event_id']}/review",
        json={"decision": "reassign", "activity_id": chosen["activity_id"], "reviewer": "planner"},
    ).json()

    assert body["event"]["matched_activity_id"] == chosen["activity_id"]
    assert body["event"]["link_state"] == "approved"


def test_review_rejects_bad_input(client):
    load_sample(client, DPR_28)
    event_id = client.get("/api/events").json()["events"][0]["event_id"]

    assert client.post(f"/api/matches/{event_id}/review", json={"decision": "maybe"}).status_code == 422
    assert client.post(f"/api/matches/{event_id}/review", json={"decision": "reassign"}).status_code == 422
    assert client.post(
        f"/api/matches/{event_id}/review", json={"decision": "reassign", "activity_id": "NOPE-999"}
    ).status_code == 404
    assert client.post("/api/matches/EVT-NOPE/review", json={"decision": "approve"}).status_code == 404


# ------------------------------------------------------- agentic supervisor

def test_ambiguous_supervisor_message_asks_before_guessing(client):
    body = client.post(
        "/api/supervisor/message", json={"text": "Erection completed today."}
    ).json()

    assert body["needs_clarification"] is True
    assert body["question"]
    assert body["missing_fields"]


def test_clarified_message_resolves_to_a_linked_activity(client):
    asked = client.post(
        "/api/supervisor/message", json={"text": "Erection completed today."}
    ).json()
    assert asked["needs_clarification"] is True

    answered = client.post(
        "/api/supervisor/clarify",
        json={"event_id": asked["event_id"], "answer": "PIP-002"},
    ).json()

    assert answered["needs_clarification"] is False
    assert answered["event"]["matched_activity_id"] == "PIP-002"

    stages = [e["stage"] for e in client.get(f"/api/audit/event/{asked['event_id']}").json()["chain"]]
    assert "CLARIFY" in stages and "MATCH" in stages


def test_clarify_without_a_pending_question_is_rejected(client):
    response = client.post(
        "/api/supervisor/clarify", json={"event_id": "EVT-NOPE", "answer": "PIP-002"}
    )
    assert response.status_code == 404


# ---------------------------------------------------------------- conflicts

def raise_contradiction(client):
    """
    Build a genuine contradiction the way the product does: the DPR records
    PIP-002 as complete, then a supervisor on site reports it blocked.
    Returns the conflict record.
    """
    load_sample(client, DPR_28)
    asked = client.post(
        "/api/supervisor/message",
        json={"text": "Line 24-XX spool erection is blocked, crane not available."},
    ).json()
    if asked.get("needs_clarification"):
        asked = client.post(
            "/api/supervisor/clarify",
            json={"event_id": asked["event_id"], "answer": "PIP-002"},
        ).json()

    conflicts = client.get("/api/conflicts").json()["conflicts"]
    assert conflicts, "a supervisor walking back a completed activity must raise a conflict"
    return conflicts[0]


def test_agreeing_sources_raise_no_conflict(client):
    """
    Regression: 'in progress' from the CSV parser was mapped to NOT_STARTED and
    an unknown status was treated as a NOT_STARTED claim, so two sources that
    actually agreed were reported as contradicting each other.
    """
    load_sample(client, DPR_28)
    load_sample(client, PIPING_SHEET)

    conflicts = client.get("/api/conflicts").json()["conflicts"]
    assert conflicts == [], f"false conflicts raised: {[c['conflict_id'] for c in conflicts]}"


def test_status_vocabularies_from_both_parsers_agree():
    """The text parser says 'in_progress'; the CSV parser passes 'in progress'."""
    assert server.normalize_status("in progress") is ActivityStatus.IN_PROGRESS
    assert server.normalize_status("in_progress") is ActivityStatus.IN_PROGRESS
    assert server.normalize_status("In Progress") is ActivityStatus.IN_PROGRESS
    assert server.normalize_status("not started") is ActivityStatus.NOT_STARTED
    assert server.normalize_status("blocked") is ActivityStatus.ON_HOLD

    # No claim is not a claim of NOT_STARTED.
    assert server.normalize_status("unknown") is None
    assert server.normalize_status("") is None
    assert server.normalize_status(None) is None
    assert server.status_label("unknown") == "UNKNOWN"


def test_an_event_with_no_status_claim_does_not_move_the_schedule(client):
    """An event that never said how far the work got must not imply NOT_STARTED."""
    body = client.post(
        "/api/events/extract",
        json={"text": "Some activity on Line 24-XX.", "source_id": "vague",
              "source_type": "daily_report"},
    ).json()

    for event in body["events"]:
        if event["status"] not in {"completed", "started", "in_progress", "blocked"}:
            activity_id = event["matched_activity_id"]
            if not activity_id:
                continue
            row = next(r for r in client.get("/api/schedule").json()["activities"]
                       if r["activity_id"] == activity_id)
            assert row["actual_finish"] is None, "a vague report set an actual finish date"


def test_supervisor_contradicting_the_record_raises_a_conflict(client):
    conflict = raise_contradiction(client)

    assert conflict["kind"] == "state_regression"
    assert conflict["severity"] == "HIGH"
    statuses = {c["status"] for c in conflict["claims"]}
    assert "COMPLETED" in statuses and "ON_HOLD" in statuses

    # The message must describe source-vs-source, not schedule-vs-execution,
    # and must never read "X vs X".
    for contradiction in conflict["contradictions"]:
        assert contradiction["between"][0] != contradiction["between"][1]
        assert "COMPLETED" in contradiction["message"]


def test_a_planner_can_settle_a_conflict(client):
    conflict = raise_contradiction(client)
    trusted = conflict["claims"][-1]["source_id"]

    resolved = client.post(
        f"/api/conflicts/{conflict['conflict_id']}/resolve",
        json={"action": "trust", "trusted_source_id": trusted, "reviewer": "planner"},
    ).json()

    assert resolved["resolved"] is True
    assert resolved["resolution"]["trusted_source_id"] == trusted

    # The losing claims are superseded, not silently dropped.
    for claim in conflict["claims"]:
        link_state = client.get(f"/api/events/{claim['event_id']}").json()["link_state"]
        assert link_state == ("approved" if claim["source_id"] == trusted else "superseded")

    open_ids = [c["conflict_id"] for c in client.get("/api/conflicts").json()["conflicts"]]
    assert conflict["conflict_id"] not in open_ids


def test_conflict_can_be_sent_for_investigation_and_stays_open(client):
    conflict = raise_contradiction(client)
    body = client.post(
        f"/api/conflicts/{conflict['conflict_id']}/resolve",
        json={"action": "investigate", "reviewer": "planner", "note": "ask the site"},
    ).json()

    assert body["resolved"] is False, "investigating is not deciding"
    assert body["resolution"]["action"] == "investigate"
    still_open = [c["conflict_id"] for c in client.get("/api/conflicts").json()["conflicts"]]
    assert conflict["conflict_id"] in still_open


def test_trusting_requires_a_source_that_is_actually_in_the_conflict(client):
    conflict_id = raise_contradiction(client)["conflict_id"]

    assert client.post(
        f"/api/conflicts/{conflict_id}/resolve", json={"action": "trust"}
    ).status_code == 422
    assert client.post(
        f"/api/conflicts/{conflict_id}/resolve",
        json={"action": "trust", "trusted_source_id": "not_a_source"},
    ).status_code == 404
    assert client.post(
        "/api/conflicts/CFL-NOPE/resolve",
        json={"action": "trust", "trusted_source_id": "x"},
    ).status_code == 404


# --------------------------------------------------------- schedule & risk

def test_schedule_shows_actuals_only_where_evidence_exists(client):
    load_sample(client, DPR_28)
    schedule = client.get("/api/schedule").json()

    assert schedule["count"] > 0
    assert schedule["window"]["start"] <= schedule["window"]["end"]

    for row in schedule["activities"]:
        if row["actual_finish"]:
            assert row["evidence_event_ids"], "an actual date with no cited source"
            assert row["variance_days"] is not None
        else:
            assert row["variance_days"] is None, "variance without an actual finish"


def test_variance_is_plausible_for_a_schedule_of_this_period(client):
    load_sample(client, DPR_28)
    variances = [
        r["variance_days"] for r in client.get("/api/schedule").json()["activities"]
        if r["variance_days"] is not None
    ]
    if not variances:
        pytest.skip("no activity finished")
    assert max(abs(v) for v in variances) < 120, f"implausible variance: {variances}"


def test_progress_counters_agree_with_the_event_list(client):
    load_sample(client, DPR_28)
    progress = client.get("/api/progress").json()
    events = client.get("/api/events").json()["events"]

    assert progress["events_ingested"] == len(events)
    assert progress["auto_linked"] == sum(1 for e in events if e["link_state"] == "auto_linked")
    assert progress["in_review_queue"] == client.get("/api/matches/queue").json()["count"]
    assert 0.0 <= progress["overall_progress_percent"] <= 100.0


def test_risk_dashboard_carries_its_historical_evidence(client):
    risk = client.get("/api/risk").json()
    assert risk["activities"], "no unfinished activity was assessed"

    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "UNKNOWN": 3}
    ranks = [order[a["historical_risk"]] for a in risk["activities"]]
    assert ranks == sorted(ranks), "highest risk must surface first"

    top = risk["activities"][0]
    assert 0 <= top["delay_rate_percent"] <= 100

    evidence = client.get(f"/api/risk/{top['activity_id']}/evidence").json()
    assert evidence["assessment"]["historical_matches"] == top["historical_matches"]
    if top["historical_matches"]:
        assert evidence["records"], "a risk verdict must be openable to its records"


def test_completed_activities_drop_out_of_the_risk_list(client):
    load_sample(client, DPR_28)
    completed = {
        r["activity_id"] for r in client.get("/api/schedule").json()["activities"]
        if r["status"] == "COMPLETED"
    }
    if not completed:
        pytest.skip("nothing completed")
    listed = {a["activity_id"] for a in client.get("/api/risk", params={"limit": 100}).json()["activities"]}
    assert not (completed & listed)


def test_risk_evidence_404s_for_an_unknown_activity(client):
    assert client.get("/api/risk/NOPE-999/evidence").status_code == 404


# ------------------------------------------------------- history & audit

def test_history_search_answers_and_cites(client):
    body = client.get(
        "/api/history/search", params={"q": "what causes piping erection delays"}
    ).json()

    assert body["summary"]
    assert body["intent"]
    assert body["supporting_records"]
    assert all("similarity" in r for r in body["supporting_records"])


def test_audit_trail_records_the_full_chain_for_an_event(client):
    load_sample(client, DPR_28)
    auto = [
        e for e in client.get("/api/events").json()["events"]
        if e["link_state"] == "auto_linked"
    ]
    assert auto, "expected at least one auto-linked event"

    chain = client.get(f"/api/audit/event/{auto[0]['event_id']}").json()
    stages = [entry["stage"] for entry in chain["chain"]]

    assert stages.index("EXTRACT") < stages.index("MATCH") < stages.index("SCHEDULE_UPDATE")
    assert chain["schedule_state"]["activity_id"] == auto[0]["matched_activity_id"]


def test_audit_can_be_filtered_by_stage(client):
    load_sample(client, DPR_28)
    entries = client.get("/api/audit", params={"stage": "MATCH"}).json()["entries"]
    assert entries
    assert all(entry["stage"] == "MATCH" for entry in entries)


def test_audit_chain_404s_for_an_unknown_event(client):
    assert client.get("/api/audit/event/EVT-NOPE").status_code == 404


# -------------------------------------------------------- the full demo run

def test_end_to_end_demo_flow(client):
    """The story told to the judges, start to finish, in one pass."""
    # 1 · an ambiguous supervisor message is clarified, not guessed at
    asked = client.post("/api/supervisor/message", json={"text": "Erection completed today."}).json()
    assert asked["needs_clarification"]
    client.post("/api/supervisor/clarify", json={"event_id": asked["event_id"], "answer": "PIP-002"})

    # 2 · a planner uploads two sources covering the same day
    load_sample(client, DPR_28)
    load_sample(client, PIPING_SHEET)

    # 3 · a supervisor contradicts the written record, and the planner settles it
    blocked = client.post(
        "/api/supervisor/message",
        json={"text": "Line 24-XX spool erection is blocked, crane not available."},
    ).json()
    if blocked.get("needs_clarification"):
        client.post("/api/supervisor/clarify",
                    json={"event_id": blocked["event_id"], "answer": "PIP-002"})
    assert client.get("/api/conflicts").json()["count"] > 0

    for conflict in client.get("/api/conflicts").json()["conflicts"]:
        client.post(
            f"/api/conflicts/{conflict['conflict_id']}/resolve",
            json={
                "action": "trust",
                "trusted_source_id": conflict["claims"][0]["source_id"],
                "reviewer": "planner",
            },
        )
    assert client.get("/api/conflicts").json()["count"] == 0

    # 4 · the planner clears the review queue, teaching the matcher as they go.
    #     An ambiguous event has candidates but no proposal — it must be
    #     reassigned to a chosen candidate, not "approved".
    for event in client.get("/api/matches/queue").json()["queue"]:
        if event["proposed_activity_id"]:
            body = {"decision": "approve"}
        elif event["candidates"]:
            body = {"decision": "reassign", "activity_id": event["candidates"][0]["activity_id"]}
        else:
            body = {"decision": "reject"}
        client.post(f"/api/matches/{event['event_id']}/review",
                    json={**body, "reviewer": "planner"})
    assert client.get("/api/matches/queue").json()["count"] == 0

    # 5 · the schedule moved, and every change can be traced to its source
    progress = client.get("/api/progress").json()
    assert progress["activities_with_actuals"] > 0
    assert progress["corrections_learned"] > 0
    assert progress["open_conflicts"] == 0

    touched = client.get("/api/schedule", params={"only_touched": True}).json()["activities"]
    assert touched
    for row in touched:
        assert row["evidence_event_ids"]

    # 6 · risk intelligence still speaks for the unfinished work
    assert client.get("/api/risk").json()["activities"]
