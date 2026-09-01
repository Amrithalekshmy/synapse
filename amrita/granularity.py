from typing import Optional


class GranularityTracker:

    def __init__(self):
        self.event_to_activities: dict[str, list[str]] = {}
        self.activity_to_events: dict[str, list[str]] = {}
        self.activity_progress: dict[str, dict] = {}

    def record_link(self, event_id: str, activity_id: str, confidence: float, status_hint: str = "unknown"):
        self.event_to_activities.setdefault(event_id, [])
        if activity_id not in self.event_to_activities[event_id]:
            self.event_to_activities[event_id].append(activity_id)

        self.activity_to_events.setdefault(activity_id, [])
        if event_id not in self.activity_to_events[activity_id]:
            self.activity_to_events[activity_id].append(event_id)

        self._update_progress(activity_id, event_id, confidence, status_hint)

    def _update_progress(self, activity_id: str, event_id: str, confidence: float, status_hint: str):
        if activity_id not in self.activity_progress:
            self.activity_progress[activity_id] = {
                "events": [],
                "latest_status": "not_started",
                "event_count": 0,
            }

        prog = self.activity_progress[activity_id]
        prog["events"].append({"event_id": event_id, "confidence": confidence, "status": status_hint})
        prog["event_count"] = len(prog["events"])
        prog["latest_status"] = status_hint if status_hint != "unknown" else prog["latest_status"]

    def get_activity_events(self, activity_id: str) -> list[str]:
        return self.activity_to_events.get(activity_id, [])

    def get_event_activities(self, event_id: str) -> list[str]:
        return self.event_to_activities.get(event_id, [])

    def is_one_to_many(self, event_id: str) -> bool:
        return len(self.event_to_activities.get(event_id, [])) > 1

    def is_many_to_one(self, activity_id: str) -> bool:
        return len(self.activity_to_events.get(activity_id, [])) > 1

    def get_progress_summary(self, activity_id: str) -> Optional[dict]:
        return self.activity_progress.get(activity_id)

    def get_all_links(self) -> list[dict]:
        links = []
        for event_id, act_ids in self.event_to_activities.items():
            for act_id in act_ids:
                links.append({"event_id": event_id, "activity_id": act_id})
        return links
