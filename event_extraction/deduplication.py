import re
from difflib import SequenceMatcher
from typing import Optional

from event_extraction.models import ExecutionEvent, DuplicateGroup


def _normalize_for_comparison(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[^\w\s]', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    return text


def _field_match(a: Optional[str], b: Optional[str]) -> bool:
    if a is None or b is None:
        return False
    return a.strip().lower() == b.strip().lower()


def compute_similarity(a: ExecutionEvent, b: ExecutionEvent) -> float:
    score = 0.0
    total_weight = 0.0

    if a.asset and b.asset:
        total_weight += 3.0
        if _field_match(a.asset, b.asset):
            score += 3.0

    if a.discipline and b.discipline:
        total_weight += 1.0
        if _field_match(a.discipline, b.discipline):
            score += 1.0

    if a.activity_type and b.activity_type:
        total_weight += 2.0
        if _field_match(a.activity_type, b.activity_type):
            score += 2.0

    if a.event_date and b.event_date:
        total_weight += 1.5
        if a.event_date == b.event_date:
            score += 1.5

    if a.status and b.status:
        total_weight += 1.0
        if a.status == b.status:
            score += 1.0

    norm_a = _normalize_for_comparison(a.description)
    norm_b = _normalize_for_comparison(b.description)
    text_sim = SequenceMatcher(None, norm_a, norm_b).ratio()
    total_weight += 1.5
    score += 1.5 * text_sim

    if total_weight == 0:
        return 0.0

    return round(score / total_weight, 3)


def find_duplicates(events: list[ExecutionEvent], threshold: float = 0.80) -> list[DuplicateGroup]:
    n = len(events)
    visited: set[int] = set()
    groups: list[DuplicateGroup] = []

    for i in range(n):
        if i in visited:
            continue
        duplicates: list[str] = []
        max_sim = 0.0
        for j in range(i + 1, n):
            if j in visited:
                continue
            sim = compute_similarity(events[i], events[j])
            if sim >= threshold:
                duplicates.append(events[j].event_id)
                max_sim = max(max_sim, sim)
                visited.add(j)
        if duplicates:
            visited.add(i)
            groups.append(DuplicateGroup(
                primary_event_id=events[i].event_id,
                duplicate_event_ids=duplicates,
                similarity_score=max_sim,
            ))

    return groups
