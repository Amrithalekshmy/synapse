"""
WBS (Work Breakdown Structure) hierarchy reconstruction engine.
Reconstructs multi-level WBS trees, resolves breadcrumbs, and propagates context.
"""

import re
from typing import Dict, List, Optional, Tuple
from .models import WBSNode
from .normalization import normalize_discipline, normalize_location


class WBSTree:
    """Manages and reconstructs WBS hierarchies for schedule activities."""

    def __init__(self):
        self.nodes: Dict[str, WBSNode] = {}
        self.root_ids: List[str] = []

    def add_node(
        self,
        wbs_id: str,
        code: str,
        name: str,
        parent_wbs_id: Optional[str] = None,
        level: Optional[int] = None,
        discipline: Optional[str] = None,
        location: Optional[str] = None,
    ) -> WBSNode:
        """Add or update a WBS node in the tree."""
        # Derive discipline or location from name/code if not provided
        derived_discipline = discipline or normalize_discipline(name) or normalize_discipline(code)
        derived_location = location or normalize_location(name) or normalize_location(code)

        node = WBSNode(
            wbs_id=str(wbs_id),
            code=str(code or wbs_id),
            name=str(name or code or wbs_id),
            parent_wbs_id=str(parent_wbs_id) if parent_wbs_id else None,
            level=level or 1,
            path="",
            children=[],
            discipline=derived_discipline,
            location=derived_location,
        )
        self.nodes[node.wbs_id] = node
        return node

    def build_hierarchy(self):
        """Build parent-child relationships, calculate levels, and compute full paths."""
        # Clear children lists
        for node in self.nodes.values():
            node.children = []

        self.root_ids = []

        # Connect children to parents
        for wbs_id, node in self.nodes.items():
            if node.parent_wbs_id and node.parent_wbs_id in self.nodes and node.parent_wbs_id != wbs_id:
                parent = self.nodes[node.parent_wbs_id]
                if wbs_id not in parent.children:
                    parent.children.append(wbs_id)
            else:
                self.root_ids.append(wbs_id)

        # Compute depth levels and full path recursively
        def _traverse(node_id: str, current_level: int, current_path: str):
            node = self.nodes[node_id]
            node.level = current_level
            node_path = f"{current_path} > {node.name}" if current_path else node.name
            node.path = node_path

            for child_id in node.children:
                _traverse(child_id, current_level + 1, node_path)

        for root_id in self.root_ids:
            _traverse(root_id, 1, "")

    def get_context_for_activity(
        self, wbs_id: Optional[str]
    ) -> Tuple[Optional[str], Optional[str], Optional[str], int]:
        """
        Given a wbs_id, returns:
        (wbs_path, inherited_discipline, inherited_location, wbs_level)
        """
        if not wbs_id or str(wbs_id) not in self.nodes:
            # Check if wbs_id itself indicates a level e.g. 'PIP-L5-01' -> level 5
            level = 6
            if wbs_id:
                m = re.search(r"L(\d)", str(wbs_id), re.IGNORECASE)
                if m:
                    level = int(m.group(1))
            return None, None, None, level

        node = self.nodes[str(wbs_id)]
        path = node.path
        discipline = node.discipline
        location = node.location
        level = node.level

        # Walk up tree to inherit discipline/location if missing
        curr = node
        visited = set()
        while (not discipline or not location) and curr.parent_wbs_id:
            if curr.parent_wbs_id in visited or curr.parent_wbs_id not in self.nodes:
                break
            visited.add(curr.parent_wbs_id)
            curr = self.nodes[curr.parent_wbs_id]
            if not discipline and curr.discipline:
                discipline = curr.discipline
            if not location and curr.location:
                location = curr.location

        return path, discipline, location, level

    @classmethod
    def from_outline_numbers(cls, tasks: List[Dict]) -> "WBSTree":
        """
        Reconstruct WBS tree from MS Project tasks having OutlineNumber or WBS codes (e.g. '1.2.3').
        """
        tree = cls()
        outline_map: Dict[str, str] = {}

        for task in tasks:
            task_id = str(task.get("id") or task.get("UID") or task.get("activity_id"))
            outline = str(task.get("outline_number") or task.get("OutlineNumber") or task.get("WBS") or "")
            name = str(task.get("name") or task.get("activity_name") or "")

            if not outline:
                continue

            outline_map[outline] = task_id
            level = len(outline.split("."))

            # Find parent outline (e.g. '1.2' is parent of '1.2.1')
            parent_id = None
            if "." in outline:
                parent_outline = outline.rsplit(".", 1)[0]
                parent_id = outline_map.get(parent_outline)

            tree.add_node(
                wbs_id=task_id,
                code=outline,
                name=name,
                parent_wbs_id=parent_id,
                level=level,
            )

        tree.build_hierarchy()
        return tree
