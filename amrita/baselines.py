import re
from difflib import SequenceMatcher


def _normalize_text(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _extract_tokens(text: str) -> set[str]:
    return set(_normalize_text(text).split())


class ExactMatcher:

    def match(self, event_text: str, activities: list[dict], top_k: int = 3) -> list[dict]:
        event_norm = _normalize_text(event_text)
        event_tokens = _extract_tokens(event_text)

        scored = []
        for act in activities:
            act_name = act.get("activity_name", "")
            act_norm = _normalize_text(act_name)

            if event_norm == act_norm:
                scored.append((act, 1.0))
                continue

            act_tokens = _extract_tokens(act_name)
            if not act_tokens:
                scored.append((act, 0.0))
                continue

            overlap = event_tokens & act_tokens
            score = len(overlap) / len(act_tokens)
            scored.append((act, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            {
                "activity_id": a["activity_id"],
                "name": a["activity_name"],
                "score": round(s, 3),
                "method": "exact",
            }
            for a, s in scored[:top_k]
        ]


class FuzzyMatcher:

    def __init__(self, threshold: float = 0.4):
        self.threshold = threshold

    def match(self, event_text: str, activities: list[dict], top_k: int = 3) -> list[dict]:
        event_norm = _normalize_text(event_text)

        scored = []
        for act in activities:
            act_name = act.get("activity_name", "")
            act_norm = _normalize_text(act_name)
            score = SequenceMatcher(None, event_norm, act_norm).ratio()
            scored.append((act, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return [
            {
                "activity_id": a["activity_id"],
                "name": a["activity_name"],
                "score": round(s, 3),
                "method": "fuzzy",
            }
            for a, s in scored[:top_k]
        ]
