"""
Primavera P6 XML Parser for SYNAPSE.
Parses Primavera P6 XML export schemas containing <Project>, <WBS>, and <Activity> elements.
"""

import time
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional, Any

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
from ..filtering import filter_activities
from ..quality import validate_schedule


class PrimaveraXMLParser(BaseScheduleParser):
    """Parser for Oracle Primavera P6 XML exports."""

    def parse(self, source: str, is_content: bool = False) -> ScheduleParseResult:
        start_time = time.time()
        content, filename = self.read_source(source, is_content)

        try:
            root = ET.fromstring(content)
        except ET.ParseError:
            clean_xml = re.sub(r'\sxmlns="[^"]+"', "", content, count=1)
            root = ET.fromstring(clean_xml)

        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        project_elem = root.find(f".//{ns}Project") or root
        project_id = self._find_text(project_elem, f"{ns}Id") or filename
        project_name = self._find_text(project_elem, f"{ns}Name") or project_id

        # 1. Parse WBS Elements
        wbs_tree = WBSTree()
        wbs_id_to_name: Dict[str, str] = {}

        wbs_elements = root.findall(f".//{ns}WBS")
        for w_elem in wbs_elements:
            w_id = self._find_text(w_elem, f"{ns}ObjectId") or self._find_text(w_elem, f"{ns}Id") or ""
            w_code = self._find_text(w_elem, f"{ns}Code") or w_id
            w_name = self._find_text(w_elem, f"{ns}Name") or w_code
            parent_id = self._find_text(w_elem, f"{ns}ParentObjectId")

            wbs_id_to_name[w_id] = w_name
            wbs_tree.add_node(
                wbs_id=w_id,
                code=w_code,
                name=w_name,
                parent_wbs_id=parent_id,
            )

        wbs_tree.build_hierarchy()

        # 2. Parse Activities
        activities: List[ScheduleActivity] = []
        activity_elements = root.findall(f".//{ns}Activity")

        for act_elem in activity_elements:
            act_id = self._find_text(act_elem, f"{ns}Id") or ""
            act_name = self._find_text(act_elem, f"{ns}Name") or ""
            wbs_ref = self._find_text(act_elem, f"{ns}WBSObjectId") or self._find_text(act_elem, f"{ns}WBSCode") or ""

            planned_start = normalize_date(self._find_text(act_elem, f"{ns}PlannedStartDate")) or ""
            planned_finish = normalize_date(self._find_text(act_elem, f"{ns}PlannedFinishDate")) or ""
            actual_start = normalize_date(self._find_text(act_elem, f"{ns}ActualStartDate"))
            actual_finish = normalize_date(self._find_text(act_elem, f"{ns}ActualFinishDate"))

            # Duration in days (P6 exports in hours)
            duration_days = 1
            raw_dur = self._find_text(act_elem, f"{ns}PlannedDuration")
            if raw_dur:
                try:
                    duration_days = max(1, int(round(float(raw_dur) / 8.0)))
                except ValueError:
                    duration_days = 1

            status = normalize_status(self._find_text(act_elem, f"{ns}Status"))

            # WBS Context
            wbs_path, inh_disc, inh_loc, wbs_lvl = wbs_tree.get_context_for_activity(wbs_ref)
            discipline = inh_disc or normalize_discipline(act_name)
            location = inh_loc or normalize_location(act_name)

            search_text = build_search_text(
                activity_name=act_name,
                discipline=discipline,
                location=location,
                wbs_path=wbs_path,
            )

            activities.append(
                ScheduleActivity(
                    activity_id=act_id,
                    activity_name=act_name,
                    wbs_id=wbs_ref,
                    wbs_level=wbs_lvl,
                    level=f"L{wbs_lvl}",
                    discipline=discipline,
                    location=location,
                    planned_start=planned_start,
                    planned_finish=planned_finish,
                    duration_days=duration_days,
                    predecessors=[],
                    status=status,
                    actual_start=actual_start,
                    actual_finish=actual_finish,
                    wbs_path=wbs_path,
                    search_text=search_text,
                    normalized_name=normalize_text(act_name),
                )
            )

        # 3. Filter L5/L6
        l5_l6_acts, summary_acts = filter_activities(activities)

        # 4. Quality Audit
        wbs_ids = set(wbs_tree.nodes.keys())
        quality_report = validate_schedule(
            activities=l5_l6_acts,
            wbs_node_ids=wbs_ids,
            all_read_activities=activities,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return ScheduleParseResult(
            format_detected="primavera_xml",
            project_id=project_id,
            project_name=project_name,
            schedule_version="P6 XML",
            total_activities_read=len(activities),
            l5_l6_activities_count=len(l5_l6_acts),
            filtered_summary_count=len(summary_acts),
            activities=l5_l6_acts,
            wbs_nodes=wbs_tree.nodes,
            quality_report=quality_report,
            parse_time_ms=round(elapsed_ms, 2),
        )

    def _find_text(self, elem: ET.Element, tag: str) -> Optional[str]:
        node = elem.find(tag)
        return node.text.strip() if node is not None and node.text else None
