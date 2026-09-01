"""
Automatic format detection for schedule export files.
Detects Primavera P6 XER, Primavera P6 XML, MS Project XML, CSV, and JSON.
"""

import os
import re
from typing import Tuple, Optional


class ScheduleFormat:
    PRIMAVERA_XER = "primavera_xer"
    PRIMAVERA_XML = "primavera_xml"
    MSPROJECT_XML = "msproject_xml"
    SYNTHETIC_CSV = "synthetic_csv"
    PRIMAVERA_CSV = "primavera_csv"
    MSPROJECT_CSV = "msproject_csv"
    STANDARD_CSV = "standard_csv"
    JSON = "json"
    UNKNOWN = "unknown"


def detect_format(file_path_or_content: str, is_content: bool = False) -> Tuple[str, Optional[str]]:
    """
    Detect the schedule format from a file path or raw string content.
    Returns (format_name, reason).
    """
    sample = ""
    ext = ""

    if not is_content and os.path.exists(file_path_or_content):
        _, ext = os.path.splitext(file_path_or_content)
        ext = ext.lower()
        try:
            with open(file_path_or_content, "r", encoding="utf-8", errors="ignore") as f:
                sample = f.read(4096)
        except Exception as e:
            return ScheduleFormat.UNKNOWN, f"Could not read file: {e}"
    else:
        sample = file_path_or_content[:4096]

    sample_lower = sample.lower().strip()

    # 1. Primavera P6 XER Check
    if sample.startswith("ERMHDR") or "%T PROJECT" in sample or "%T TASK" in sample or "%T PROJWBS" in sample or ext == ".xer":
        return ScheduleFormat.PRIMAVERA_XER, "Found Primavera XER header / table tokens (%T)"

    # 2. XML detection
    if "<" in sample and ">" in sample:
        if "primaveraxml" in sample_lower or "p6xml" in sample_lower:
            return ScheduleFormat.PRIMAVERA_XML, "Found Primavera XML namespace or root element"
        if "schemas.microsoft.com/project" in sample_lower or ("<project" in sample_lower and "<tasks>" in sample_lower):
            return ScheduleFormat.MSPROJECT_XML, "Found Microsoft Project XML schema / Task elements"
        if "<project" in sample_lower and "<activity" in sample_lower:
            return ScheduleFormat.PRIMAVERA_XML, "Found Project and Activity XML elements"

    # 3. JSON detection
    if sample_lower.startswith("{") or sample_lower.startswith("["):
        if '"activity_id"' in sample_lower or '"activities"' in sample_lower:
            return ScheduleFormat.JSON, "Found JSON format with activity structure"

    # 4. CSV detection
    first_line = sample.split("\n")[0].lower() if sample else ""

    # Synthetic / Project schema check (matches synapse/data/schedule.csv)
    if "activity_id" in first_line and "activity_name" in first_line:
        return ScheduleFormat.SYNTHETIC_CSV, "Found SYNAPSE synthetic CSV headers (activity_id, activity_name)"

    # Primavera spreadsheet export
    if "activity id" in first_line and ("activity name" in first_line or "activity status" in first_line):
        return ScheduleFormat.PRIMAVERA_CSV, "Found Primavera P6 spreadsheet CSV headers (Activity ID, Activity Name)"

    # MS Project spreadsheet export
    if ("task name" in first_line or "name" in first_line) and ("outline level" in first_line or "wbs" in first_line or "predecessors" in first_line):
        return ScheduleFormat.MSPROJECT_CSV, "Found MS Project CSV headers (Task Name, Outline Level/WBS)"

    if ext in (".csv", ".tsv", ".txt") and ("," in first_line or "\t" in first_line or ";" in first_line):
        return ScheduleFormat.STANDARD_CSV, "Delimited text file with tabular headers"

    return ScheduleFormat.UNKNOWN, "Format could not be confidently determined"
