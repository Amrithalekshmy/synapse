import time
from datetime import date
from pathlib import Path
from typing import Optional

from event_extraction.models import (
    ExecutionEvent,
    ExtractionResult,
    SourceType,
    ClarificationRequest,
    DuplicateGroup,
)
from event_extraction.parsers.csv_parser import CSVParser
from event_extraction.parsers.text_parser import TextParser
from event_extraction.parsers.pdf_parser import PDFParser
from event_extraction.extraction.hybrid import HybridExtractor
from event_extraction.confidence import score_confidence
from event_extraction.deduplication import find_duplicates
from event_extraction.clarification import needs_clarification, generate_clarification


class ExtractionPipeline:
    def __init__(self, use_llm: bool = False, llm_api_key: Optional[str] = None):
        self._csv_parser = CSVParser()
        self._text_parser = TextParser()
        self._pdf_parser = PDFParser()
        self._extractor = HybridExtractor(use_llm=use_llm, llm_api_key=llm_api_key)

    def process_file(
        self,
        file_path: str,
        source_id: Optional[str] = None,
        reference_date: Optional[date] = None,
    ) -> ExtractionResult:
        start = time.time()
        path = Path(file_path)
        suffix = path.suffix.lower()

        if suffix in (".csv",):
            result = self._csv_parser.parse(file_path, source_id)
        elif suffix in (".xlsx", ".xls"):
            result = self._csv_parser.parse(file_path, source_id)
        elif suffix == ".pdf":
            result = self._pdf_parser.parse(file_path, source_id)
        elif suffix in (".txt", ".text", ".md"):
            result = self._text_parser.parse_file(file_path, source_id)
        else:
            return ExtractionResult(
                events=[],
                source_id=source_id or path.stem,
                source_type=SourceType.DAILY_REPORT,
                warnings=[f"Unsupported file format: {suffix}"],
            )

        result = self._enrich_events(result, reference_date)
        result.processing_time_ms = round((time.time() - start) * 1000, 2)
        return result

    def process_text(
        self,
        text: str,
        source_id: str = "text_input",
        source_type: SourceType = SourceType.SUPERVISOR_MESSAGE,
        reference_date: Optional[date] = None,
    ) -> ExtractionResult:
        start = time.time()

        if source_type == SourceType.SUPERVISOR_MESSAGE:
            event = ExecutionEvent(
                source_id=source_id,
                source_type=source_type,
                raw_text=text,
                description=text,
                status="unknown",
            )
            result = ExtractionResult(
                events=[event],
                source_id=source_id,
                source_type=source_type,
            )
        else:
            result = self._text_parser.parse(text, source_id)

        result = self._enrich_events(result, reference_date)
        result.processing_time_ms = round((time.time() - start) * 1000, 2)
        return result

    def _enrich_events(
        self,
        result: ExtractionResult,
        reference_date: Optional[date] = None,
    ) -> ExtractionResult:
        enriched: list[ExecutionEvent] = []

        for event in result.events:
            event = self._extractor.extract(event, reference_date)
            event.extraction_confidence = score_confidence(event)
            enriched.append(event)

        result.events = enriched
        return result

    def find_duplicates(
        self,
        events: list[ExecutionEvent],
        threshold: float = 0.80,
    ) -> list[DuplicateGroup]:
        return find_duplicates(events, threshold)

    def get_clarification_requests(
        self,
        events: list[ExecutionEvent],
        active_activities: Optional[list[dict]] = None,
    ) -> list[ClarificationRequest]:
        requests: list[ClarificationRequest] = []
        for event in events:
            if needs_clarification(event):
                req = generate_clarification(event, active_activities)
                if req:
                    requests.append(req)
        return requests
