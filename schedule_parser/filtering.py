"""
L5/L6 Activity filtering engine for SYNAPSE.
Isolates detailed operational work packages and tasks from high-level summaries and milestones.
"""

import re
from typing import List, Tuple
from .models import ScheduleActivity


def parse_level_integer(raw_level: any, default: int = 6) -> int:
    """Extract an integer level from variations like 'L6', 'Level 6', 6, '6'."""
    if raw_level is None:
        return default
    if isinstance(raw_level, int):
        return raw_level
    val_str = str(raw_level).strip()
    match = re.search(r"(\d+)", val_str)
    if match:
        return int(match.group(1))
    return default


def is_l5_or_l6(activity: ScheduleActivity) -> bool:
    """
    Determine if an activity qualifies as an L5 (Work Package Component)
    or L6 (Discrete Execution Task).
    """
    # 1. If marked explicitly as a summary group/milestone, exclude
    if activity.raw_data and activity.raw_data.get("is_summary"):
        return False

    # 2. Direct wbs_level check
    if activity.wbs_level in (5, 6):
        return True

    # 3. WBS ID check (e.g. 'PIP-L5-01', 'L5-PIP-02')
    if activity.wbs_id and re.search(r"L[56]", activity.wbs_id, re.IGNORECASE):
        return True

    # 4. Activity ID check (e.g. 'PIP-L6-024')
    if re.search(r"L[56]", activity.activity_id, re.IGNORECASE):
        return True

    # 5. String level check
    if activity.level:
        lvl = activity.level.upper()
        if "5" in lvl or "6" in lvl or "TASK" in lvl:
            return True
        if any(lvl == prefix for prefix in ("L1", "L2", "L3", "L4")):
            return False

    # 6. Fallback: Leaf tasks with positive duration in execution schedules are L6 operational tasks
    return activity.wbs_level >= 5 or activity.duration_days > 0


def filter_activities(
    activities: List[ScheduleActivity], strict_l5_l6: bool = False
) -> Tuple[List[ScheduleActivity], List[ScheduleActivity]]:
    """
    Split activities into (l5_l6_activities, non_l5_l6_summaries).
    """
    l5_l6: List[ScheduleActivity] = []
    summaries: List[ScheduleActivity] = []

    for act in activities:
        if is_l5_or_l6(act):
            l5_l6.append(act)
        else:
            summaries.append(act)

    return l5_l6, summaries
