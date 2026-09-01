"""
Data Quality Engine for SYNAPSE Schedule Parser.
Validates schedule integrity according to the 7 data-quality rules in 03_YAZEEN_SCHEDULE_PARSER.md:
  1. Missing IDs
  2. Duplicate IDs
  3. Invalid dates
  4. Finish before start
  5. Missing activity names
  6. Missing WBS context
  7. Non-L5/L6 rows
"""

from typing import List, Set, Dict, Optional
from datetime import datetime
from .models import ScheduleActivity, DataQualityIssue, DataQualityReport, QualitySeverity


def validate_schedule(
    activities: List[ScheduleActivity],
    wbs_node_ids: Optional[Set[str]] = None,
    all_read_activities: Optional[List[ScheduleActivity]] = None,
) -> DataQualityReport:
    """
    Run comprehensive data quality inspection across a collection of schedule activities.
    """
    report = DataQualityReport()
    report.total_records_inspected = len(activities)

    seen_ids: Dict[str, int] = {}
    valid_wbs_ids = wbs_node_ids or set()

    for act in activities:
        act_id = act.activity_id

        # 1. Missing Activity ID
        if not act_id or not act_id.strip() or act_id.strip().lower() in ("none", "null", "nan"):
            report.add_issue(
                DataQualityIssue(
                    issue_type="missing_id",
                    severity=QualitySeverity.ERROR,
                    activity_id=act_id,
                    field="activity_id",
                    message=f"Activity has empty or invalid activity ID (name: '{act.activity_name}')",
                )
            )
        else:
            seen_ids[act_id] = seen_ids.get(act_id, 0) + 1

        # 2. Missing Activity Name
        if not act.activity_name or not act.activity_name.strip() or act.activity_name.strip().lower() in ("none", "null", "nan"):
            report.add_issue(
                DataQualityIssue(
                    issue_type="missing_name",
                    severity=QualitySeverity.WARNING,
                    activity_id=act_id,
                    field="activity_name",
                    message=f"Activity '{act_id}' has missing or empty activity name",
                )
            )

        # 3. Invalid Dates
        dt_start: Optional[datetime] = None
        dt_finish: Optional[datetime] = None

        if not act.planned_start:
            report.add_issue(
                DataQualityIssue(
                    issue_type="invalid_date",
                    severity=QualitySeverity.ERROR,
                    activity_id=act_id,
                    field="planned_start",
                    message=f"Activity '{act_id}' is missing planned start date",
                )
            )
        else:
            try:
                dt_start = datetime.strptime(act.planned_start, "%Y-%m-%d")
            except ValueError:
                report.add_issue(
                    DataQualityIssue(
                        issue_type="invalid_date",
                        severity=QualitySeverity.ERROR,
                        activity_id=act_id,
                        field="planned_start",
                        raw_value=act.planned_start,
                        message=f"Activity '{act_id}' has invalid planned start date '{act.planned_start}' (expected YYYY-MM-DD)",
                    )
                )

        if not act.planned_finish:
            report.add_issue(
                DataQualityIssue(
                    issue_type="invalid_date",
                    severity=QualitySeverity.ERROR,
                    activity_id=act_id,
                    field="planned_finish",
                    message=f"Activity '{act_id}' is missing planned finish date",
                )
            )
        else:
            try:
                dt_finish = datetime.strptime(act.planned_finish, "%Y-%m-%d")
            except ValueError:
                report.add_issue(
                    DataQualityIssue(
                        issue_type="invalid_date",
                        severity=QualitySeverity.ERROR,
                        activity_id=act_id,
                        field="planned_finish",
                        raw_value=act.planned_finish,
                        message=f"Activity '{act_id}' has invalid planned finish date '{act.planned_finish}' (expected YYYY-MM-DD)",
                    )
                )

        # 4. Finish Before Start
        if dt_start and dt_finish and dt_finish < dt_start:
            report.add_issue(
                DataQualityIssue(
                    issue_type="finish_before_start",
                    severity=QualitySeverity.ERROR,
                    activity_id=act_id,
                    field="planned_finish",
                    raw_value=f"start={act.planned_start}, finish={act.planned_finish}",
                    message=f"Activity '{act_id}' has planned finish ({act.planned_finish}) prior to planned start ({act.planned_start})",
                )
            )

        # 5. Missing WBS Context
        if not act.wbs_id or not act.wbs_id.strip():
            report.add_issue(
                DataQualityIssue(
                    issue_type="missing_wbs",
                    severity=QualitySeverity.WARNING,
                    activity_id=act_id,
                    field="wbs_id",
                    message=f"Activity '{act_id}' is missing WBS hierarchy context (empty wbs_id)",
                )
            )
        elif valid_wbs_ids and act.wbs_id not in valid_wbs_ids:
            report.add_issue(
                DataQualityIssue(
                    issue_type="missing_wbs",
                    severity=QualitySeverity.INFO,
                    activity_id=act_id,
                    field="wbs_id",
                    raw_value=act.wbs_id,
                    message=f"Activity '{act_id}' references WBS '{act.wbs_id}' which was not found in reconstructed WBS tree",
                )
            )

        # Predecessor self-reference check
        if act_id in act.predecessors:
            report.add_issue(
                DataQualityIssue(
                    issue_type="circular_predecessor",
                    severity=QualitySeverity.WARNING,
                    activity_id=act_id,
                    field="predecessors",
                    message=f"Activity '{act_id}' lists itself as a predecessor",
                )
            )

    # Check for Duplicate IDs across all activities
    for act_id, count in seen_ids.items():
        if count > 1:
            report.add_issue(
                DataQualityIssue(
                    issue_type="duplicate_id",
                    severity=QualitySeverity.ERROR,
                    activity_id=act_id,
                    raw_value=str(count),
                    message=f"Duplicate Activity ID detected: '{act_id}' appears {count} times",
                )
            )

    # 7. Non-L5/L6 Check
    # If all_read_activities was supplied, check for summary rows that were excluded
    if all_read_activities:
        for raw_act in all_read_activities:
            if raw_act.wbs_level < 5 and raw_act.activity_id not in seen_ids:
                report.add_issue(
                    DataQualityIssue(
                        issue_type="non_l5_l6",
                        severity=QualitySeverity.INFO,
                        activity_id=raw_act.activity_id,
                        field="wbs_level",
                        raw_value=str(raw_act.wbs_level),
                        message=f"Row '{raw_act.activity_id}' is a Level {raw_act.wbs_level} summary node, not an L5/L6 execution activity",
                    )
                )

    return report
