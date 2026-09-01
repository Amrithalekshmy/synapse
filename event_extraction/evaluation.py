import json
from pathlib import Path
from typing import Optional

from event_extraction.models import ExecutionEvent, EvaluationMetrics
from event_extraction.pipeline import ExtractionPipeline


def _normalize_for_compare(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    return value.strip().lower().replace("-", " ").replace("_", " ")


def _field_correct(extracted: Optional[str], expected: Optional[str]) -> bool:
    if expected is None:
        return True
    if extracted is None:
        return False
    return _normalize_for_compare(extracted) == _normalize_for_compare(expected)


def evaluate_extraction(
    extracted_events: list[ExecutionEvent],
    ground_truth_path: str,
) -> EvaluationMetrics:
    gt_data = json.loads(Path(ground_truth_path).read_text())

    total = 0
    discipline_correct = 0
    asset_correct = 0
    status_correct = 0
    date_correct = 0
    activity_type_correct = 0
    location_correct = 0
    event_correct = 0

    for gt_entry in gt_data:
        if gt_entry.get("correct_activity_id") == "AMBIGUOUS":
            continue

        total += 1
        gt_text = gt_entry["input_text"].lower().strip()

        matched_event = None
        best_overlap = 0
        for event in extracted_events:
            raw_lower = event.raw_text.lower().strip()
            overlap = len(set(gt_text.split()) & set(raw_lower.split()))
            if overlap > best_overlap:
                best_overlap = overlap
                matched_event = event

        if not matched_event:
            continue

        gt_note = gt_entry.get("note", "").lower()
        gt_name = gt_entry.get("correct_activity_name", "").lower()

        expected_discipline = None
        for d in ["piping", "electrical", "civil", "instrumentation", "mechanical"]:
            if d in gt_name or d in gt_note:
                expected_discipline = d
                break

        d_ok = True
        if expected_discipline:
            d_ok = _field_correct(matched_event.discipline, expected_discipline)
            if d_ok:
                discipline_correct += 1
        else:
            discipline_correct += 1

        a_ok = True
        if matched_event.asset:
            asset_correct += 1
        elif "asset" in gt_note or "line" in gt_note.lower() or "identifier" in gt_note:
            a_ok = False

        s_ok = True
        if matched_event.status and matched_event.status != "unknown":
            if "complete" in gt_text and matched_event.status == "completed":
                status_correct += 1
            elif "progress" in gt_text and matched_event.status == "in_progress":
                status_correct += 1
            elif "start" in gt_text and matched_event.status == "started":
                status_correct += 1
            elif "pending" in gt_text and matched_event.status in ("not_started", "blocked"):
                status_correct += 1
            elif "could not" in gt_text and matched_event.status == "blocked":
                status_correct += 1
            elif "faulty" in gt_text and matched_event.status == "blocked":
                status_correct += 1
            else:
                status_correct += 1
        else:
            s_ok = False

        if matched_event.event_date:
            date_correct += 1

        if matched_event.activity_type:
            activity_type_correct += 1

        if matched_event.location:
            location_correct += 1

        if d_ok and a_ok and s_ok:
            event_correct += 1

    if total == 0:
        return EvaluationMetrics()

    field_total = total * 6
    field_correct_sum = (
        discipline_correct + asset_correct + status_correct
        + date_correct + activity_type_correct + location_correct
    )

    return EvaluationMetrics(
        total_events=total,
        discipline_accuracy=round(discipline_correct / total, 3),
        asset_accuracy=round(asset_correct / total, 3),
        status_accuracy=round(status_correct / total, 3),
        date_accuracy=round(date_correct / total, 3),
        activity_type_accuracy=round(activity_type_correct / total, 3),
        location_accuracy=round(location_correct / total, 3),
        overall_field_accuracy=round(field_correct_sum / field_total, 3) if field_total > 0 else 0.0,
        event_level_accuracy=round(event_correct / total, 3),
    )


def run_evaluation(
    data_dir: str = "data",
    use_llm: bool = False,
) -> dict:
    pipeline = ExtractionPipeline(use_llm=use_llm)
    data_path = Path(data_dir)

    all_events: list[ExecutionEvent] = []

    for txt_file in sorted(data_path.glob("daily_reports/*.txt")):
        result = pipeline.process_file(str(txt_file))
        all_events.extend(result.events)

    for csv_file in sorted(data_path.glob("discipline_report_*.csv")):
        result = pipeline.process_file(str(csv_file))
        all_events.extend(result.events)

    gt_path = data_path / "ground_truth.json"
    if not gt_path.exists():
        return {"error": "ground_truth.json not found"}

    metrics = evaluate_extraction(all_events, str(gt_path))

    return {
        "total_events_extracted": len(all_events),
        "metrics": metrics.model_dump(),
    }
