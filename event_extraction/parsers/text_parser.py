import re
from datetime import date
from typing import Optional
from dateutil import parser as dateutil_parser

from event_extraction.models import ExecutionEvent, ExtractionResult, SourceType


class TextParser:
    DISCIPLINE_HEADER = re.compile(r'^={2,}\s*(.+?)\s*={2,}\s*$', re.MULTILINE)
    DATE_HEADER = re.compile(
        r'[Dd]ate:\s*(\d{1,2}\s+\w+\s+\d{4}|\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})',
    )

    def _extract_report_date(self, text: str) -> Optional[date]:
        match = self.DATE_HEADER.search(text)
        if match:
            try:
                return dateutil_parser.parse(match.group(1), dayfirst=True).date()
            except (ValueError, OverflowError):
                pass
        return None

    def _split_into_sections(self, text: str) -> list[tuple[Optional[str], str]]:
        headers = list(self.DISCIPLINE_HEADER.finditer(text))
        if not headers:
            return [(None, text)]

        sections: list[tuple[Optional[str], str]] = []

        if headers[0].start() > 0:
            preamble = text[: headers[0].start()].strip()
            if preamble:
                sections.append((None, preamble))

        for i, header in enumerate(headers):
            discipline = header.group(1).strip().lower()
            start = header.end()
            end = headers[i + 1].start() if i + 1 < len(headers) else len(text)
            body = text[start:end].strip()
            if body:
                sections.append((discipline, body))

        return sections

    def _split_into_sentences(self, text: str) -> list[str]:
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        sentences: list[str] = []
        for line in lines:
            parts = re.split(r'(?<=[.!])\s+', line)
            for part in parts:
                cleaned = part.strip()
                if cleaned and len(cleaned) > 5:
                    sentences.append(cleaned)
        return sentences

    def _is_meta_line(self, line: str) -> bool:
        meta_patterns = [
            r'^daily\s+progress\s+report',
            r'^project:',
            r'^date:',
            r'^prepared\s+by:',
            r'^report\s+no',
            r'^page\s+\d',
        ]
        line_lower = line.strip().lower()
        return any(re.match(p, line_lower) for p in meta_patterns)

    def parse(self, text: str, source_id: Optional[str] = None) -> ExtractionResult:
        if source_id is None:
            source_id = "text_input"

        report_date = self._extract_report_date(text)
        sections = self._split_into_sections(text)

        events: list[ExecutionEvent] = []
        warnings: list[str] = []

        for discipline, section_text in sections:
            sentences = self._split_into_sentences(section_text)
            for sentence in sentences:
                if self._is_meta_line(sentence):
                    continue

                event_date_str = report_date.isoformat() if report_date else None

                event = ExecutionEvent(
                    source_id=source_id,
                    source_type=SourceType.DAILY_REPORT,
                    source_reference=f"section_{discipline or 'preamble'}",
                    raw_text=sentence,
                    description=sentence,
                    discipline=discipline if discipline and discipline != "issues / delays" else None,
                    status="unknown",
                    event_date=event_date_str,
                    extraction_confidence=0.0,
                )
                events.append(event)

        return ExtractionResult(events=events, source_id=source_id, source_type=SourceType.DAILY_REPORT, warnings=warnings)

    def parse_file(self, file_path: str, source_id: Optional[str] = None) -> ExtractionResult:
        from pathlib import Path

        path = Path(file_path)
        if source_id is None:
            source_id = path.stem

        text = path.read_text(encoding="utf-8")
        result = self.parse(text, source_id=source_id)
        return result
