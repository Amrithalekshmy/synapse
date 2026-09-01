"""
Microsoft Project XML (MSPDI) Parser for SYNAPSE.
Parses standard Microsoft Project XML exports.
Reconstructs tasks, outline hierarchy, durations, and predecessor links.
"""

import time
import re
import xml.etree.ElementTree as ET
from typing import Dict, List, Optional

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


class MSProjectXMLParser(BaseScheduleParser):
    """Parser for Microsoft Project XML (MSPDI) exports."""

    def parse(self, source: str, is_content: bool = False) -> ScheduleParseResult:
        start_time = time.time()
        content, filename = self.read_source(source, is_content)

        # Parse XML tree
        try:
            root = ET.fromstring(content)
        except ET.ParseError as e:
            # Strip XML namespaces if needed or try forgiving parsing
            clean_xml = re.sub(r'\sxmlns="[^"]+"', "", content, count=1)
            root = ET.fromstring(clean_xml)

        # Extract namespace if present
        ns = ""
        if root.tag.startswith("{"):
            ns = root.tag.split("}")[0] + "}"

        project_name = self._find_text(root, f"{ns}Title") or self._find_text(root, f"{ns}Name") or filename
        project_id = filename

        # 1. First pass: Collect all tasks and outline numbers
        raw_tasks: List[Dict[str, Any]] = []
        uid_to_activity_id: Dict[str, str] = {}

        tasks_container = root.find(f"{ns}Tasks")
        task_elements = tasks_container.findall(f"{ns}Task") if tasks_container is not None else root.findall(f".//{ns}Task")

        for t_elem in task_elements:
            uid = self._find_text(t_elem, f"{ns}UID") or ""
            name = self._find_text(t_elem, f"{ns}Name") or ""
            if not uid and not name:
                continue

            wbs = self._find_text(t_elem, f"{ns}WBS") or self._find_text(t_elem, f"{ns}OutlineNumber") or ""
            outline_level_str = self._find_text(t_elem, f"{ns}OutlineLevel") or "1"
            outline_level = int(outline_level_str) if outline_level_str.isdigit() else 1
            is_summary = (self._find_text(t_elem, f"{ns}Summary") == "1")

            # Check if there is an explicit activity ID in custom fields (Text1..Text10 or Name prefix)
            act_id = self._extract_activity_id(t_elem, ns, name, wbs, uid)
            uid_to_activity_id[uid] = act_id

            # Extract predecessor links
            preds: List[str] = []
            for pred_link in t_elem.findall(f"{ns}PredecessorLink"):
                p_uid = self._find_text(pred_link, f"{ns}PredecessorUID")
                if p_uid:
                    preds.append(p_uid)

            raw_tasks.append({
                "elem": t_elem,
                "uid": uid,
                "activity_id": act_id,
                "name": name,
                "wbs": wbs,
                "outline_level": outline_level,
                "is_summary": is_summary,
                "predecessor_uids": preds,
            })

        # 2. Reconstruct WBS Hierarchy
        wbs_tree = WBSTree()
        for t in raw_tasks:
            wbs_code = t["wbs"] or t["uid"]
            wbs_tree.add_node(
                wbs_id=wbs_code,
                code=wbs_code,
                name=t["name"],
                level=t["outline_level"],
            )
        wbs_tree.build_hierarchy()

        # 3. Second pass: Create ScheduleActivity records
        activities: List[ScheduleActivity] = []
        for t in raw_tasks:
            t_elem = t["elem"]
            act_id = t["activity_id"]
            name = t["name"]

            planned_start = normalize_date(self._find_text(t_elem, f"{ns}Start")) or ""
            planned_finish = normalize_date(self._find_text(t_elem, f"{ns}Finish")) or ""
            actual_start = normalize_date(self._find_text(t_elem, f"{ns}ActualStart"))
            actual_finish = normalize_date(self._find_text(t_elem, f"{ns}ActualFinish"))

            # Calculate duration in days
            duration = self._parse_mspdi_duration(self._find_text(t_elem, f"{ns}Duration"))

            # Map predecessor UIDs to resolved Activity IDs
            predecessors = [
                uid_to_activity_id.get(p_uid, p_uid)
                for p_uid in t["predecessor_uids"]
            ]

            # Context from WBS
            wbs_path, inh_disc, inh_loc, computed_lvl = wbs_tree.get_context_for_activity(t["wbs"])
            wbs_level = t["outline_level"] if t["outline_level"] > 1 else computed_lvl

            discipline = inh_disc or normalize_discipline(name)
            location = inh_loc or normalize_location(name)
            status = "completed" if actual_finish else ("in_progress" if actual_start else "planned")

            search_text = build_search_text(
                activity_name=name,
                discipline=discipline,
                location=location,
                wbs_path=wbs_path,
            )

            activities.append(
                ScheduleActivity(
                    activity_id=act_id,
                    activity_name=name,
                    wbs_id=t["wbs"] or f"WBS-{t['uid']}",
                    wbs_level=wbs_level,
                    level=f"L{wbs_level}",
                    discipline=discipline,
                    location=location,
                    planned_start=planned_start,
                    planned_finish=planned_finish,
                    duration_days=duration,
                    predecessors=predecessors,
                    status=status,
                    actual_start=actual_start,
                    actual_finish=actual_finish,
                    wbs_path=wbs_path,
                    search_text=search_text,
                    normalized_name=normalize_text(name),
                    raw_data={"uid": t["uid"], "is_summary": t["is_summary"]},
                )
            )

        # 4. Filter L5/L6 activities
        l5_l6_acts, summary_acts = filter_activities(activities)

        # 5. Validate Quality
        wbs_ids = set(wbs_tree.nodes.keys())
        quality_report = validate_schedule(
            activities=l5_l6_acts,
            wbs_node_ids=wbs_ids,
            all_read_activities=activities,
        )

        elapsed_ms = (time.time() - start_time) * 1000

        return ScheduleParseResult(
            format_detected="msproject_xml",
            project_id=project_id,
            project_name=project_name,
            schedule_version="MS Project XML (MSPDI)",
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

    def _extract_activity_id(self, elem: ET.Element, ns: str, name: str, wbs: str, uid: str) -> str:
        """Extract or synthesize the canonical Activity ID."""
        # 1. Check custom text fields (Text1..Text5)
        for i in range(1, 6):
            val = self._find_text(elem, f"{ns}Text{i}")
            if val and re.match(r"^[A-Z]{2,4}-\d{2,4}", val):
                return val

        # 2. Check prefix in activity name e.g. "PIP-001: Fabricate spool"
        match = re.match(r"^([A-Z]{2,4}-L?\d{1,4}[A-Z0-9\-]*)\b", name)
        if match:
            return match.group(1)

        # 3. Use WBS code if it matches standard EPC code
        if wbs and re.match(r"^[A-Z]{2,4}-", wbs):
            return wbs

        # 4. Fallback to unique task code
        return f"TASK-{uid}" if uid else f"ACT-{hash(name) % 100000:05d}"

    def _parse_mspdi_duration(self, raw_dur: Optional[str]) -> int:
        """Convert ISO 8601 duration (e.g. 'PT40H0M0S') to days."""
        if not raw_dur:
            return 1
        # Example PT40H0M0S
        match = re.search(r"PT(\d+)H", raw_dur)
        if match:
            hours = int(match.group(1))
            return max(1, int(round(hours / 8.0)))
        match_days = re.search(r"P(\d+)D", raw_dur)
        if match_days:
            return max(1, int(match_days.group(1)))
        return 1
