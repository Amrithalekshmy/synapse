from pathlib import Path
from typing import Optional

from event_extraction.models import ExtractionResult, SourceType
from event_extraction.parsers.text_parser import TextParser


class PDFParser:
    def __init__(self):
        self._text_parser = TextParser()

    def _extract_text(self, file_path: str) -> str:
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("pdfplumber is required for PDF parsing: pip install pdfplumber")

        pages_text: list[str] = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    pages_text.append(text)

                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if row:
                            cleaned = [str(cell).strip() if cell else "" for cell in row]
                            pages_text.append(" | ".join(cleaned))

        return "\n".join(pages_text)

    def parse(self, file_path: str, source_id: Optional[str] = None) -> ExtractionResult:
        path = Path(file_path)
        if source_id is None:
            source_id = path.stem

        text = self._extract_text(file_path)

        if not text.strip():
            return ExtractionResult(
                events=[],
                source_id=source_id,
                source_type=SourceType.PDF_DOCUMENT,
                warnings=["No text extracted from PDF — may be a scanned document requiring OCR"],
            )

        result = self._text_parser.parse(text, source_id=source_id)
        result.source_type = SourceType.PDF_DOCUMENT
        for event in result.events:
            event.source_type = SourceType.PDF_DOCUMENT
        return result
