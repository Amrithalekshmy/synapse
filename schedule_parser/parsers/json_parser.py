"""
JSON Schedule Parser for SYNAPSE.
Handles JSON exports and REST API ingest payloads.
"""

import json
import time
from typing import Dict, List, Any, Optional

from .base import BaseScheduleParser
from ..models import ScheduleActivity, ScheduleParseResult
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


class JSONScheduleParser(BaseScheduleParser):
    """Parser for JSON schedule representations."""

    def parse(self, source: str, is_content: bool = False) -> ScheduleParseResult:
        start_time = time.time()
        content, filename = self.read_source(source, is_content)

        data = json.loads(content)
        raw_list = data if isinstance(data, list) else data.get("activities", [])
        project_id = filename if isinstance(data, list) else data.get("project_id", filename)
        project_name = filename if isinstance(data, list) else data.get("project_name", project_id)

        wbs_tree = WBSTree()
        activities: List[ScheduleActivity] = []

        for item in raw_list:
            act_id = item.get("activity_id") or item.get("id") or ""
            act_name = item.get("activity_name") or item.get("name") or ""
            wbs_id = item.get("wbs_id") or item.get("wbs") or ""
            raw_lvl = item.get("wbs_level") or item.get("level")
            wbs_level = parse_level_integer(raw_lvl, default=6)

            if wbs_id:
                wbs_tree.add_node(wbs_id=wbs_id, code=wbs_id, name=wbs_id, level=wbs_level - 1 if wbs_level > 1 else 1)

            planned_start = normalize_date(item.get("planned_start") or item.get("start")) or ""
            planned_finish = normalize_date(item.get("planned_finish") or item.get("finish")) or ""
            duration = int(item.get("duration_days") or item.get("duration") or 1)

            preds = item.get("predecessors") or []
            if isinstance(preds, str):
                preds = [p.strip() for p in preds.split(",") if p.strip()]

            succs = item.get("successors") or []
            if isinstance(succs, str):
                succs = [s.strip() for s in succs.split(",") if s.strip()]

            discipline = normalize_discipline(item.get("discipline"))
            location = normalize_location(item.get("location"))
            status = normalize_status(item.get("status"))

            activities.append(
                ScheduleActivity(
                    activity_id=act_id,
                    activity_name=act_name,
                    wbs_id=wbs_id,
                    wbs_level=wbs_level,
                    level=f"L{wbs_level}",
                    discipline=discipline,
                    location=location,
                    planned_start=planned_start,
                    planned_finish=planned_finish,
                    duration_days=duration,
                    predecessors=preds,
                    successors=succs,
                    status=status,
                    normalized_name=normalize_text(act_name),
                    raw_data=item,
                )
            )

        wbs_tree.build_hierarchy()

        for act in activities:
            path, disc, loc, _ = wbs_tree.get_context_for_activity(act.wbs_id)
            if path:
                act.wbs_path = path
            if not act.discipline and disc:
                act.discipline = disc
            if not act.location and loc:
                act.location = loc
            act.search_text = build_search_text(
                activity_name=act.activity_name,
                discipline=act.discipline,
                location=act.location,
                wbs_path=act.wbs_path,
            )

        l5_l6_acts, summary_acts = filter_activities(activities)
        wbs_ids = set(wbs_tree.nodes.keys())
        quality_report = validate_schedule(
            activities=l5_l6_acts,
            wbs_node_ids=wbs_ids,
            all_read_activities=activities,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return ScheduleParseResult(
            format_detected="json",
            project_id=project_id,
            project_name=project_name,
            schedule_version="JSON",
            total_activities_read=len(activities),
            l5_l6_activities_count=len(l5_l6_acts),
            filtered_summary_count=len(summary_acts),
            activities=l5_l6_acts,
            wbs_nodes=wbs_tree.nodes,
            quality_report=quality_report,
            parse_time_ms=round(elapsed_ms, 2),
        )
