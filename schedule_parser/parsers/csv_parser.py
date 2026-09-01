"""
CSV and Delimited Spreadsheet Parser for SYNAPSE.
Handles synthetic schedule formats (synapse/data/schedule.csv) and general spreadsheet exports.
"""

import csv
import io
import time
from datetime import datetime
from typing import List, Dict, Any, Optional

from .base import BaseScheduleParser
from ..models import ScheduleActivity, ScheduleParseResult, ScheduleStatus
from ..normalization import (
    normalize_discipline,
    normalize_location,
    normalize_date,
    normalize_status,
    normalize_text,
    build_search_text,
)
from ..wbs import WBSTree
from ..filtering import filter_activities, parse_level_integer
from ..quality import validate_schedule


# Common column name aliases for flexible ingestion
COLUMN_ALIASES = {
    "activity_id": ["activity_id", "activity id", "task_id", "task id", "task_code", "act_id", "id"],
    "activity_name": ["activity_name", "activity name", "task_name", "task name", "name", "description", "activity description"],
    "wbs_id": ["wbs_id", "wbs id", "wbs", "wbs_code", "wbs code", "outline_number", "outline number"],
    "wbs_level": ["wbs_level", "wbs level", "level", "outline_level", "outline level"],
    "discipline": ["discipline", "disc", "trade", "department"],
    "location": ["location", "area", "unit", "work area", "plant area", "zone"],
    "planned_start": ["planned_start", "planned start", "start", "start date", "target_start_date", "target start"],
    "planned_finish": ["planned_finish", "planned finish", "finish", "finish date", "target_end_date", "target finish"],
    "duration_days": ["duration_days", "duration", "planned duration", "original duration", "target_drtn_hr_cnt"],
    "predecessors": ["predecessors", "predecessor", "pred", "preds", "predecessor_ids"],
    "successors": ["successors", "successor", "succ", "succs", "successor_ids"],
    "status": ["status", "activity status", "activity_status", "status_code"],
    "actual_start": ["actual_start", "act start", "actual start", "act_start_date"],
    "actual_finish": ["actual_finish", "act finish", "actual finish", "act_end_date"],
}


class CSVScheduleParser(BaseScheduleParser):
    """Parser for CSV / TSV format schedule files."""

    def parse(self, source: str, is_content: bool = False) -> ScheduleParseResult:
        start_time = time.time()
        content, filename = self.read_source(source, is_content)

        # Detect delimiter
        first_line = content.split("\n")[0] if content else ""
        delimiter = "\t" if "\t" in first_line and "," not in first_line else ","

        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        raw_rows = list(reader)

        # Map column headers
        col_map = self._map_columns(reader.fieldnames or [])

        activities: List[ScheduleActivity] = []
        wbs_tree = WBSTree()

        for row in raw_rows:
            act = self._parse_row(row, col_map, wbs_tree)
            activities.append(act)

        # Reconstruct WBS
        wbs_tree.build_hierarchy()

        # Enrich activities with WBS hierarchy context & inherited properties
        for act in activities:
            path, disc, loc, level = wbs_tree.get_context_for_activity(act.wbs_id)
            if path:
                act.wbs_path = path
            if not act.discipline and disc:
                act.discipline = disc
            if not act.location and loc:
                act.location = loc
            # Enrich search text
            act.search_text = build_search_text(
                activity_name=act.activity_name,
                discipline=act.discipline,
                location=act.location,
                wbs_path=act.wbs_path,
            )

        # Filter L5 / L6 activities
        l5_l6_acts, summary_acts = filter_activities(activities)

        # Run quality validation
        wbs_ids = set(wbs_tree.nodes.keys())
        quality_report = validate_schedule(
            activities=l5_l6_acts,
            wbs_node_ids=wbs_ids,
            all_read_activities=activities,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return ScheduleParseResult(
            format_detected="synthetic_csv" if "activity_id" in col_map else "standard_csv",
            project_id=filename,
            project_name=filename,
            total_activities_read=len(activities),
            l5_l6_activities_count=len(l5_l6_acts),
            filtered_summary_count=len(summary_acts),
            activities=l5_l6_acts,
            wbs_nodes=wbs_tree.nodes,
            quality_report=quality_report,
            parse_time_ms=round(elapsed_ms, 2),
        )

    def _map_columns(self, fieldnames: List[str]) -> Dict[str, str]:
        col_map = {}
        for canonical, aliases in COLUMN_ALIASES.items():
            for name in fieldnames:
                cleaned = name.strip().lower()
                if cleaned in aliases or cleaned.replace(" ", "_") in aliases:
                    col_map[canonical] = name
                    break
        return col_map

    def _parse_row(self, row: Dict[str, str], col_map: Dict[str, str], wbs_tree: WBSTree) -> ScheduleActivity:
        def get_val(key: str) -> Optional[str]:
            col = col_map.get(key)
            if col and col in row and row[col] is not None:
                val = str(row[col]).strip()
                return val if val != "" else None
            return None

        # 1. Identity
        activity_id = get_val("activity_id") or ""
        activity_name = get_val("activity_name") or ""

        # 2. WBS & Level
        wbs_id = get_val("wbs_id") or ""
        raw_level = get_val("wbs_level")
        wbs_level = parse_level_integer(raw_level, default=6)
        level_str = f"L{wbs_level}" if raw_level is None else str(raw_level)
        if not level_str.startswith("L") and level_str.isdigit():
            level_str = f"L{level_str}"

        # Register WBS node in tree if provided
        if wbs_id:
            wbs_tree.add_node(
                wbs_id=wbs_id,
                code=wbs_id,
                name=wbs_id,
                level=wbs_level - 1 if wbs_level > 1 else 1,
            )

        # 3. Dates
        planned_start = normalize_date(get_val("planned_start")) or ""
        planned_finish = normalize_date(get_val("planned_finish")) or ""
        actual_start = normalize_date(get_val("actual_start"))
        actual_finish = normalize_date(get_val("actual_finish"))

        # 4. Duration
        duration = 1
        raw_dur = get_val("duration_days")
        if raw_dur:
            try:
                # Handle hours (if ends with 'h' or large number from P6) or plain days
                dur_float = float(str(raw_dur).replace("h", "").replace("d", "").strip())
                duration = max(0, int(round(dur_float)))
            except ValueError:
                duration = 1
        elif planned_start and planned_finish:
            try:
                d1 = datetime.strptime(planned_start, "%Y-%m-%d")
                d2 = datetime.strptime(planned_finish, "%Y-%m-%d")
                duration = max(0, (d2 - d1).days + 1)
            except ValueError:
                duration = 1

        # 5. Predecessors / Successors
        predecessors: List[str] = []
        raw_preds = get_val("predecessors")
        if raw_preds:
            for p in raw_preds.replace(";", ",").split(","):
                p_clean = p.strip()
                if p_clean:
                    predecessors.append(p_clean)

        successors: List[str] = []
        raw_succs = get_val("successors")
        if raw_succs:
            for s in raw_succs.replace(";", ",").split(","):
                s_clean = s.strip()
                if s_clean:
                    successors.append(s_clean)

        # 6. Metadata
        discipline = normalize_discipline(get_val("discipline"))
        location = normalize_location(get_val("location"))
        status = normalize_status(get_val("status"))
        normalized_name = normalize_text(activity_name)

        return ScheduleActivity(
            activity_id=activity_id,
            activity_name=activity_name,
            wbs_id=wbs_id,
            wbs_level=wbs_level,
            level=level_str,
            discipline=discipline,
            location=location,
            planned_start=planned_start,
            planned_finish=planned_finish,
            duration_days=duration,
            predecessors=predecessors,
            successors=successors,
            status=status,
            actual_start=actual_start,
            actual_finish=actual_finish,
            normalized_name=normalized_name,
            raw_data=dict(row),
        )
