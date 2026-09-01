"""
Primavera P6 XER Export Parser for SYNAPSE.
Parses proprietary %T, %F, %R relational tables in Primavera P6 XER files.
Reconstructs PROJECT, PROJWBS, TASK, and TASKPRED.
"""

import time
from typing import Dict, List, Any, Optional

from .base import BaseScheduleParser
from ..models import ScheduleActivity, ScheduleParseResult, WBSNode
from ..normalization import (
    normalize_discipline,
    normalize_location,
    normalize_date,
    normalize_status,
    normalize_text,
    build_search_text,
)
from ..wbs import WBSTree
from ..filtering import filter_activities
from ..quality import validate_schedule


class PrimaveraXERParser(BaseScheduleParser):
    """Parser for Oracle Primavera P6 XER files."""

    def parse(self, source: str, is_content: bool = False) -> ScheduleParseResult:
        start_time = time.time()
        content, filename = self.read_source(source, is_content)

        # 1. Parse XER table structures
        tables = self._parse_xer_tables(content)

        # 2. Extract Project info
        project_id = filename
        project_name = filename
        if "PROJECT" in tables and tables["PROJECT"]["records"]:
            proj_rec = tables["PROJECT"]["records"][0]
            project_id = proj_rec.get("proj_short_name") or proj_rec.get("proj_id") or filename
            project_name = proj_rec.get("proj_name") or project_id

        # 3. Reconstruct WBS Hierarchy from PROJWBS
        wbs_tree = WBSTree()
        wbs_id_to_code: Dict[str, str] = {}

        if "PROJWBS" in tables:
            for wbs_rec in tables["PROJWBS"]["records"]:
                raw_wbs_id = str(wbs_rec.get("wbs_id", ""))
                parent_id = str(wbs_rec.get("parent_wbs_id", ""))
                code = wbs_rec.get("wbs_short_name") or raw_wbs_id
                name = wbs_rec.get("wbs_name") or code

                wbs_id_to_code[raw_wbs_id] = code
                wbs_tree.add_node(
                    wbs_id=raw_wbs_id,
                    code=code,
                    name=name,
                    parent_wbs_id=parent_id if parent_id and parent_id != raw_wbs_id else None,
                )

        wbs_tree.build_hierarchy()

        # 4. Map task internal IDs to task codes (Activity IDs)
        task_id_to_code: Dict[str, str] = {}
        if "TASK" in tables:
            for task_rec in tables["TASK"]["records"]:
                t_id = str(task_rec.get("task_id", ""))
                t_code = task_rec.get("task_code") or t_id
                task_id_to_code[t_id] = t_code

        # 5. Extract Predecessors from TASKPRED
        predecessors_map: Dict[str, List[str]] = {}
        successors_map: Dict[str, List[str]] = {}

        if "TASKPRED" in tables:
            for pred_rec in tables["TASKPRED"]["records"]:
                succ_task_id = str(pred_rec.get("task_id", ""))
                pred_task_id = str(pred_rec.get("pred_task_id", ""))

                succ_code = task_id_to_code.get(succ_task_id, succ_task_id)
                pred_code = task_id_to_code.get(pred_task_id, pred_task_id)

                if succ_code and pred_code:
                    predecessors_map.setdefault(succ_code, []).append(pred_code)
                    successors_map.setdefault(pred_code, []).append(succ_code)

        # 6. Parse Tasks into ScheduleActivity objects
        raw_activities: List[ScheduleActivity] = []
        if "TASK" in tables:
            for task_rec in tables["TASK"]["records"]:
                act = self._parse_xer_task(
                    task_rec=task_rec,
                    wbs_tree=wbs_tree,
                    wbs_id_to_code=wbs_id_to_code,
                    predecessors_map=predecessors_map,
                    successors_map=successors_map,
                )
                raw_activities.append(act)

        # Filter L5 / L6 activities
        l5_l6_acts, summary_acts = filter_activities(raw_activities)

        # Validate schedule data quality
        wbs_ids = set(wbs_tree.nodes.keys())
        wbs_ids.update(wbs_id_to_code.values())
        quality_report = validate_schedule(
            activities=l5_l6_acts,
            wbs_node_ids=wbs_ids,
            all_read_activities=raw_activities,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return ScheduleParseResult(
            format_detected="primavera_xer",
            project_id=project_id,
            project_name=project_name,
            schedule_version="P6 XER",
            total_activities_read=len(raw_activities),
            l5_l6_activities_count=len(l5_l6_acts),
            filtered_summary_count=len(summary_acts),
            activities=l5_l6_acts,
            wbs_nodes=wbs_tree.nodes,
            quality_report=quality_report,
            parse_time_ms=round(elapsed_ms, 2),
        )

    def _parse_xer_tables(self, content: str) -> Dict[str, Dict[str, Any]]:
        """Parse %T, %F, %R sections into a structured dictionary."""
        tables: Dict[str, Dict[str, Any]] = {}
        current_table: Optional[str] = None
        current_fields: List[str] = []

        for line in content.splitlines():
            line = line.strip()
            if not line:
                continue

            parts = line.split("\t")
            token = parts[0]

            if token == "%T":
                current_table = parts[1].strip() if len(parts) > 1 else "UNKNOWN"
                tables[current_table] = {"fields": [], "records": []}
                current_fields = []
            elif token == "%F" and current_table:
                current_fields = [p.strip() for p in parts[1:]]
                tables[current_table]["fields"] = current_fields
            elif token == "%R" and current_table:
                values = [p.strip() for p in parts[1:]]
                rec: Dict[str, str] = {}
                for idx, val in enumerate(values):
                    field_name = current_fields[idx] if idx < len(current_fields) else f"field_{idx}"
                    rec[field_name] = val
                tables[current_table]["records"].append(rec)

        return tables

    def _parse_xer_task(
        self,
        task_rec: Dict[str, str],
        wbs_tree: WBSTree,
        wbs_id_to_code: Dict[str, str],
        predecessors_map: Dict[str, List[str]],
        successors_map: Dict[str, List[str]],
    ) -> ScheduleActivity:
        task_code = task_rec.get("task_code") or task_rec.get("task_id") or ""
        task_name = task_rec.get("task_name") or ""
        raw_wbs_id = str(task_rec.get("wbs_id", ""))
        display_wbs_id = wbs_id_to_code.get(raw_wbs_id, raw_wbs_id)

        # Dates
        planned_start = normalize_date(task_rec.get("target_start_date") or task_rec.get("early_start_date")) or ""
        planned_finish = normalize_date(task_rec.get("target_end_date") or task_rec.get("early_end_date")) or ""
        actual_start = normalize_date(task_rec.get("act_start_date"))
        actual_finish = normalize_date(task_rec.get("act_end_date"))

        # Duration in days (P6 exports duration in hours: 8h = 1d)
        duration_days = 1
        hours_str = task_rec.get("target_drtn_hr_cnt") or task_rec.get("remain_drtn_hr_cnt")
        if hours_str:
            try:
                duration_days = max(1, int(round(float(hours_str) / 8.0)))
            except ValueError:
                duration_days = 1

        # WBS Context inheritance
        wbs_path, inh_disc, inh_loc, wbs_level = wbs_tree.get_context_for_activity(raw_wbs_id)

        # Discipline and Location (derive from task_name if not inherited)
        discipline = inh_disc or normalize_discipline(task_name)
        location = inh_loc or normalize_location(task_name)
        status = normalize_status(task_rec.get("status_code"))

        # Predecessors / Successors
        preds = predecessors_map.get(task_code, [])
        succs = successors_map.get(task_code, [])

        # Build search text for NLP matching
        search_text = build_search_text(
            activity_name=task_name,
            discipline=discipline,
            location=location,
            wbs_path=wbs_path,
        )

        return ScheduleActivity(
            activity_id=task_code,
            activity_name=task_name,
            wbs_id=display_wbs_id,
            wbs_level=wbs_level,
            level=f"L{wbs_level}",
            discipline=discipline,
            location=location,
            planned_start=planned_start,
            planned_finish=planned_finish,
            duration_days=duration_days,
            predecessors=preds,
            successors=succs,
            status=status,
            actual_start=actual_start,
            actual_finish=actual_finish,
            wbs_path=wbs_path,
            search_text=search_text,
            normalized_name=normalize_text(task_name),
            raw_data=task_rec,
        )
