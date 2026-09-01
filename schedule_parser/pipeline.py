"""
Main pipeline orchestrator for SYNAPSE Schedule Parser.
Coordinates automatic format detection, parsing, WBS reconstruction, L5/L6 filtering, and quality auditing.
"""

from typing import Optional, List, Dict, Any

from .detector import detect_format, ScheduleFormat
from .models import ScheduleParseResult, ScheduleActivity, DataQualityReport
from .parsers import (
    CSVScheduleParser,
    PrimaveraXERParser,
    MSProjectXMLParser,
    PrimaveraXMLParser,
    JSONScheduleParser,
    BaseScheduleParser,
)


class ScheduleParser:
    """
    Unified entry point for SYNAPSE schedule parsing and normalization.
    Converts Primavera P6, MS Project, and spreadsheet schedules into clean ScheduleActivity collections.
    """

    def __init__(self):
        self._parsers: Dict[str, BaseScheduleParser] = {
            ScheduleFormat.PRIMAVERA_XER: PrimaveraXERParser(),
            ScheduleFormat.PRIMAVERA_XML: PrimaveraXMLParser(),
            ScheduleFormat.MSPROJECT_XML: MSProjectXMLParser(),
            ScheduleFormat.SYNTHETIC_CSV: CSVScheduleParser(),
            ScheduleFormat.PRIMAVERA_CSV: CSVScheduleParser(),
            ScheduleFormat.MSPROJECT_CSV: CSVScheduleParser(),
            ScheduleFormat.STANDARD_CSV: CSVScheduleParser(),
            ScheduleFormat.JSON: JSONScheduleParser(),
        }

    def parse(
        self,
        source: str,
        is_content: bool = False,
        format_hint: Optional[str] = None,
    ) -> ScheduleParseResult:
        """
        Parse a schedule file or content string.
        Automatically detects format if format_hint is omitted.
        """
        detected_fmt = format_hint
        detection_reason = "Explicit format provided"

        if not detected_fmt:
            detected_fmt, detection_reason = detect_format(source, is_content=is_content)

        parser = self._parsers.get(detected_fmt)
        if not parser:
            # Fallback to CSV parser for tabular text
            parser = self._parsers[ScheduleFormat.STANDARD_CSV]

        result = parser.parse(source, is_content=is_content)
        return result

    def parse_to_amritha(self, source: str) -> List[Dict[str, Any]]:
        """
        Convenience method: parses schedule and returns clean activity list
        directly consumable by Amritha's matching engine (SynapseMatchingEngine).
        """
        res = self.parse(source)
        return res.to_amritha_format()

    def parse_to_contract(self, source: str) -> List[Dict[str, Any]]:
        """
        Convenience method: returns activity list conforming to the exact
        contract in 03_YAZEEN_SCHEDULE_PARSER.md.
        """
        res = self.parse(source)
        return res.to_contract_format()

    def audit_quality(self, source: str) -> DataQualityReport:
        """
        Run schedule data-quality audit and return detailed issue report.
        """
        res = self.parse(source)
        return res.quality_report
