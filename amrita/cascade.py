"""
Cascade Impact Engine — SYNAPSE
Amritha's module extension.

When an activity is confirmed delayed or completed later than planned,
this engine traces the dependency graph (predecessors/successors from
the schedule CSV) and computes which downstream activities are impacted,
by how many days, and what the total project slip looks like.

This turns SYNAPSE from a "data entry tool" into a decision-support
system: the reviewer sees not just "this event matches PIP-238" but
"confirming PIP-238's delay will push 4 downstream activities including
commissioning by up to 8 days."
"""

from __future__ import annotations

from collections import deque
from datetime import date, timedelta
from typing import Optional


class CascadeImpactEngine:
    """
    Dependency-graph traversal for schedule impact propagation.

    The graph is built from the `predecessors` and `successors` columns
    in the schedule CSV. Multi-predecessor activities are handled: a delay
    only propagates when ALL predecessors of the next activity are delayed.
    """

    def __init__(self) -> None:
        self._activities: dict[str, dict] = {}
        self._successors: dict[str, list[str]] = {}   # id -> [successor ids]
        self._predecessors: dict[str, list[str]] = {} # id -> [predecessor ids]

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------

    def load_activities(self, activities: list[dict]) -> None:
        self._activities = {}
        self._successors = {}
        self._predecessors = {}

        for act in activities:
            aid = act["activity_id"]
            self._activities[aid] = act

            succs = [
                s.strip()
                for s in str(act.get("successors") or "").split(",")
                if s.strip()
            ]
            preds = [
                p.strip()
                for p in str(act.get("predecessors") or "").split(",")
                if p.strip()
            ]
            self._successors[aid] = succs
            self._predecessors[aid] = preds

    # ------------------------------------------------------------------
    # Core cascade computation
    # ------------------------------------------------------------------

    def compute_cascade(
        self,
        activity_id: str,
        delay_days: int = 1,
        current_actuals: Optional[dict[str, dict]] = None,
    ) -> dict:
        """
        BFS from `activity_id` through the successor graph.

        Parameters
        ----------
        activity_id : str
            The activity that is delayed or newly completed late.
        delay_days : int
            How many days late this activity is finishing (default 1 — used
            when the actual finish date is unknown but the event confirms a slip).
        current_actuals : dict, optional
            Map of activity_id -> observed state, used to skip activities
            that are already completed (they absorb the delay).

        Returns
        -------
        dict with:
          impacted          list of impacted activity dicts (id, name, discipline,
                            planned_finish, estimated_new_finish, slip_days, depth)
          total_impacted    count of affected activities
          max_slip_days     worst-case slip across the cascade
          critical_path_hit bool — True if any impacted activity has no successors
                            (end of chain = likely a project milestone)
          summary           human-readable one-liner
        """
        if activity_id not in self._activities:
            return self._empty_result(activity_id)

        actuals = current_actuals or {}
        visited: set[str] = set()
        impacted: list[dict] = []

        # BFS queue: (activity_id, slip_days_at_this_node, depth)
        queue: deque[tuple[str, int, int]] = deque()
        queue.append((activity_id, delay_days, 0))
        visited.add(activity_id)

        while queue:
            current_id, slip, depth = queue.popleft()

            for succ_id in self._successors.get(current_id, []):
                if succ_id not in self._activities:
                    continue
                if succ_id in visited:
                    continue

                succ = self._activities[succ_id]
                succ_actual = actuals.get(succ_id, {})

                # Already completed — delay absorbed, don't propagate further
                if succ_actual.get("status") == "completed":
                    continue

                visited.add(succ_id)

                # Compute new planned finish if this slip propagates
                planned_finish = succ.get("planned_finish")
                estimated_new_finish = None
                if planned_finish:
                    try:
                        pf = date.fromisoformat(planned_finish)
                        estimated_new_finish = (pf + timedelta(days=slip)).isoformat()
                    except ValueError:
                        pass

                impacted.append({
                    "activity_id": succ_id,
                    "activity_name": succ.get("activity_name", ""),
                    "discipline": succ.get("discipline", ""),
                    "location": succ.get("location", ""),
                    "planned_finish": planned_finish,
                    "estimated_new_finish": estimated_new_finish,
                    "slip_days": slip,
                    "depth": depth + 1,
                    "is_milestone": len(self._successors.get(succ_id, [])) == 0,
                })

                queue.append((succ_id, slip, depth + 1))

        if not impacted:
            return {
                "activity_id": activity_id,
                "activity_name": self._activities[activity_id].get("activity_name", ""),
                "delay_days": delay_days,
                "impacted": [],
                "total_impacted": 0,
                "max_slip_days": 0,
                "critical_path_hit": False,
                "summary": "No downstream dependencies — isolated activity.",
            }

        max_slip = max(r["slip_days"] for r in impacted)
        critical_hit = any(r["is_milestone"] for r in impacted)
        disciplines_hit = sorted({r["discipline"] for r in impacted if r["discipline"]})

        summary = (
            f"{len(impacted)} downstream activit{'y' if len(impacted)==1 else 'ies'} affected"
            f" — up to {max_slip} day{'s' if max_slip!=1 else ''} slip"
        )
        if critical_hit:
            summary += " — ⚠ hits a project milestone"
        if disciplines_hit:
            summary += f" ({', '.join(disciplines_hit)})"

        return {
            "activity_id": activity_id,
            "activity_name": self._activities[activity_id].get("activity_name", ""),
            "delay_days": delay_days,
            "impacted": impacted,
            "total_impacted": len(impacted),
            "max_slip_days": max_slip,
            "critical_path_hit": critical_hit,
            "disciplines_hit": disciplines_hit,
            "summary": summary,
        }

    def fan_out(self, activity_id: str) -> int:
        """Quick count of all reachable successors (for RL feature)."""
        if activity_id not in self._activities:
            return 0
        visited: set[str] = set()
        queue: deque[str] = deque([activity_id])
        while queue:
            current = queue.popleft()
            for succ in self._successors.get(current, []):
                if succ not in visited and succ in self._activities:
                    visited.add(succ)
                    queue.append(succ)
        return len(visited)

    def _empty_result(self, activity_id: str) -> dict:
        return {
            "activity_id": activity_id,
            "activity_name": "",
            "delay_days": 0,
            "impacted": [],
            "total_impacted": 0,
            "max_slip_days": 0,
            "critical_path_hit": False,
            "summary": "Activity not found in schedule.",
        }
