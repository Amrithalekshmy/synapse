"""
Field normalization engine for SYNAPSE Schedule Parser.
Standardizes disciplines, locations, dates, and search context.
"""

import re
from datetime import datetime
from typing import Optional, List


# Canonical disciplines in EPC Oil & Gas projects
DISCIPLINE_ALIASES = {
    "piping": ["piping", "pip", "pipe", "pipework", "pipeline", "piping works"],
    "electrical": ["electrical", "elec", "ele", "elect", "e&i", "power", "cable", "substation"],
    "civil": ["civil", "civ", "earthworks", "concrete", "structural", "excavation", "foundation"],
    "mechanical": ["mechanical", "mech", "mec", "static equipment", "rotating equipment", "equipment"],
    "instrumentation": ["instrumentation", "inst", "ins", "telecom", "automation", "scada", "control"],
    "hse": ["hse", "safety", "environmental", "fire"],
}

LOCATION_PATTERNS = [
    (r"\b(?:unit|u)[-\s]*([0-9]+[a-z]?)\b", r"Unit \1"),
    (r"\b(?:area)[-\s]*([a-z0-9]+)\b", r"Area \1"),
    (r"\b(?:fab(?:rication)?)[-\s]*(?:yard)\b", "Fabrication Yard"),
    (r"\b(?:sub[-\s]*station)\b", "Substation"),
    (r"\b(?:tank[-\s]*farm)\b", "Tank Farm"),
]


def normalize_discipline(raw: Optional[str]) -> Optional[str]:
    """Standardize discipline string to canonical EPC discipline."""
    if not raw or not isinstance(raw, str):
        return None
    val = raw.strip().lower()
    for canonical, aliases in DISCIPLINE_ALIASES.items():
        if val == canonical or val in aliases:
            return canonical
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", val):
                return canonical
    return val


def normalize_location(raw: Optional[str]) -> Optional[str]:
    """Standardize location string to canonical EPC area/unit format."""
    if not raw or not isinstance(raw, str):
        return None
    val = raw.strip()
    for pattern, repl in LOCATION_PATTERNS:
        match = re.search(pattern, val, re.IGNORECASE)
        if match:
            # Handle group substitution
            normalized = re.sub(pattern, repl, match.group(0), flags=re.IGNORECASE)
            # Capitalize nicely
            words = normalized.split()
            return " ".join(w.capitalize() if not w.isupper() else w for w in words)
    return val


def normalize_date(raw: Optional[str]) -> Optional[str]:
    """
    Standardize various date formats (Primavera, MS Project, Excel, ISO)
    into standard ISO YYYY-MM-DD.
    Returns None if unparseable.
    """
    if not raw:
        return None
    raw_str = str(raw).strip()
    if not raw_str or raw_str.lower() in ("none", "null", "nan", "nat", ""):
        return None

    # Strip time component if present
    # Examples: '2026-08-20 00:00:00', '2026-08-20T08:00:00', '2026-08-20 08:00'
    date_part = raw_str.split("T")[0].split(" ")[0].strip()

    # List of candidate formats
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%m/%d/%Y",
        "%Y/%m/%d",
        "%d-%b-%Y",
        "%d-%b-%y",
        "%b %d, %Y",
        "%Y%m%d",
    ]

    for fmt in formats:
        try:
            dt = datetime.strptime(date_part, fmt)
            return dt.strftime("%Y-%m-%d")
        except ValueError:
            continue

    # Attempt regex extraction if embedded in longer text
    match = re.search(r"\b(\d{4})[-/](\d{1,2})[-/](\d{1,2})\b", raw_str)
    if match:
        year, month, day = match.groups()
        return f"{int(year):04d}-{int(month):02d}-{int(day):02d}"

    return None


def normalize_status(raw: Optional[str]) -> str:
    """Normalize Primavera/MS Project status strings to canonical status."""
    if not raw:
        return "planned"
    val = str(raw).strip().lower()
    if val in ("tk_notstart", "not started", "not_started", "planned", "inactive"):
        return "planned"
    elif val in ("tk_active", "in progress", "in_progress", "started", "active"):
        return "in_progress"
    elif val in ("tk_complete", "completed", "complete", "finished", "done"):
        return "completed"
    elif val in ("delayed", "overdue"):
        return "delayed"
    elif val in ("suspended", "on hold", "paused"):
        return "suspended"
    return val


def normalize_text(text: Optional[str]) -> str:
    """Clean text by lowercasing and standardizing whitespace."""
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s\-\.]", " ", text)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip().lower()


def build_search_text(
    activity_name: str,
    discipline: Optional[str] = None,
    location: Optional[str] = None,
    wbs_path: Optional[str] = None,
    identifiers: Optional[List[str]] = None,
) -> str:
    """
    Construct enriched text for Amritha's vector & semantic matching engine.
    Embeds activity name, discipline, location, WBS hierarchy, and extracted asset tags.
    """
    parts = [activity_name]
    if discipline:
        parts.append(discipline)
    if location:
        parts.append(location)
    if wbs_path:
        parts.append(wbs_path)
    if identifiers:
        parts.extend(identifiers)

    # Extract asset / line identifiers like 'Line 24', 'P-101', 'F-101', 'S-101'
    extracted = re.findall(
        r"\b(?:[A-Z]{1,4}-\d{2,4}|Line\s+\d+|Unit\s+\d+|Area\s+[A-Z])\b",
        activity_name,
        re.IGNORECASE,
    )
    for ext in extracted:
        if ext not in parts:
            parts.append(ext)

    return " ".join(p.strip() for p in parts if p and p.strip())
