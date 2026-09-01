from datetime import date

from progress_analytics.matched_event import MatchedEvent


def match_result_to_event(result: dict) -> MatchedEvent:
    """
    Convert Amritha's MatchResult dictionary into
    the internal MatchedEvent model.
    """
    if result.get("matched_activity_id") is None:
        raise ValueError("MatchResult has no matched activity.")

    return MatchedEvent(
        event_id=result["event_id"],
        activity_id=result["matched_activity_id"],
        event_date=date.fromisoformat(result["date"]),
        confidence=result["confidence"],
        decision=result["decision"],
        status_hint=result.get("status_hint", "unknown"),
        original_text=result["original_text"],
    )