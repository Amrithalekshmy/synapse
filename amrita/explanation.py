import re


def generate_explanation(event_text: str, activity: dict, score_breakdown: dict) -> dict:
    evidence = []

    if score_breakdown.get("discipline_match"):
        evidence.append({
            "signal": "discipline",
            "matched": True,
            "detail": f"Event discipline '{score_breakdown.get('event_discipline', '')}' matches activity discipline '{activity.get('discipline', '')}'",
            "boost": 0.15,
        })

    if score_breakdown.get("location_match"):
        evidence.append({
            "signal": "location",
            "matched": True,
            "detail": f"Location match: '{score_breakdown.get('event_location', '')}' in '{activity.get('location', '')}'",
            "boost": 0.10,
        })

    if score_breakdown.get("identifier_match"):
        evidence.append({
            "signal": "identifier",
            "matched": True,
            "detail": f"Asset identifier found in both event and activity",
            "boost": 0.20,
        })

    if score_breakdown.get("wbs_boost", 0) > 0:
        evidence.append({
            "signal": "wbs_context",
            "matched": True,
            "detail": f"WBS proximity: activities share WBS lineage",
            "boost": score_breakdown["wbs_boost"],
        })

    if score_breakdown.get("temporal_boost", 0) > 0:
        evidence.append({
            "signal": "temporal",
            "matched": True,
            "detail": f"Event date falls within activity's planned window",
            "boost": score_breakdown["temporal_boost"],
        })

    if score_breakdown.get("dependency_boost", 0) > 0:
        evidence.append({
            "signal": "dependency",
            "matched": True,
            "detail": f"Predecessor activities completed — activity is ready",
            "boost": score_breakdown["dependency_boost"],
        })

    if score_breakdown.get("feedback_boost", 0) > 0:
        evidence.append({
            "signal": "active_learning",
            "matched": True,
            "detail": f"Past feedback supports this match",
            "boost": score_breakdown["feedback_boost"],
        })

    semantic_score = score_breakdown.get("semantic_score", 0)
    evidence.append({
        "signal": "semantic_similarity",
        "matched": semantic_score > 0.3,
        "detail": f"Cosine similarity: {semantic_score:.3f}",
        "boost": semantic_score,
    })

    total_boost = sum(e["boost"] for e in evidence if e["signal"] != "semantic_similarity" and e["matched"])

    return {
        "evidence": evidence,
        "semantic_score": round(semantic_score, 3),
        "total_boost": round(total_boost, 3),
        "final_score": round(semantic_score + total_boost, 3),
        "matched_signals": sum(1 for e in evidence if e["matched"]),
        "total_signals": len(evidence),
    }
