import pandas as pd
from pathlib import Path
from datetime import date
from typing import Optional

from event_extraction.models import ExecutionEvent, ExtractionResult, SourceType


class CSVParser:
    COLUMN_ALIASES = {
        "date": ["date", "report_date", "event_date"],
        "discipline": ["discipline", "dept", "department"],
        "description": ["activity_description", "description", "work_description", "activity", "remarks"],
        "location": ["location", "area", "unit", "zone"],
        "status": ["status", "progress_status", "state"],
        "quantity": ["quantity", "qty", "amount"],
        "unit": ["unit", "uom", "unit_of_measure"],
        "remarks": ["remarks", "notes", "comments"],
    }

    def _resolve_column(self, df: pd.DataFrame, field: str) -> Optional[str]:
        aliases = self.COLUMN_ALIASES.get(field, [field])
        for alias in aliases:
            for col in df.columns:
                if col.strip().lower() == alias.lower():
                    return col
        return None

    def parse(self, file_path: str, source_id: Optional[str] = None) -> ExtractionResult:
        path = Path(file_path)
        if source_id is None:
            source_id = path.stem

        if path.suffix.lower() in (".xlsx", ".xls"):
            df = pd.read_excel(file_path)
            source_type = SourceType.EXCEL_SHEET
        else:
            df = pd.read_csv(file_path)
            source_type = SourceType.DISCIPLINE_REPORT

        col_date = self._resolve_column(df, "date")
        col_discipline = self._resolve_column(df, "discipline")
        col_description = self._resolve_column(df, "description")
        col_location = self._resolve_column(df, "location")
        col_status = self._resolve_column(df, "status")
        col_quantity = self._resolve_column(df, "quantity")
        col_unit = self._resolve_column(df, "unit")
        col_remarks = self._resolve_column(df, "remarks")

        events: list[ExecutionEvent] = []
        warnings: list[str] = []

        if col_description is None:
            warnings.append("No description column found — cannot extract events")
            return ExtractionResult(events=[], source_id=source_id, source_type=source_type, warnings=warnings)

        for idx, row in df.iterrows():
            desc = str(row.get(col_description, "")).strip()
            if not desc or desc.lower() == "nan":
                continue

            raw_parts = [desc]
            if col_location and pd.notna(row.get(col_location)):
                raw_parts.append(str(row[col_location]))
            if col_status and pd.notna(row.get(col_status)):
                raw_parts.append(str(row[col_status]))
            raw_text = ",".join(raw_parts)

            event_date = None
            if col_date and pd.notna(row.get(col_date)):
                raw_date = row[col_date]
                if isinstance(raw_date, date):
                    event_date = raw_date.isoformat()
                else:
                    event_date = str(raw_date).strip()

            discipline = None
            if col_discipline and pd.notna(row.get(col_discipline)):
                discipline = str(row[col_discipline]).strip().lower()

            location = None
            if col_location and pd.notna(row.get(col_location)):
                location = str(row[col_location]).strip()

            status = "unknown"
            if col_status and pd.notna(row.get(col_status)):
                status = str(row[col_status]).strip().lower()

            quantity = None
            if col_quantity and pd.notna(row.get(col_quantity)):
                try:
                    quantity = float(row[col_quantity])
                except (ValueError, TypeError):
                    pass

            unit_val = None
            if col_unit and pd.notna(row.get(col_unit)):
                unit_val = str(row[col_unit]).strip()

            remarks = ""
            if col_remarks and pd.notna(row.get(col_remarks)):
                remarks = str(row[col_remarks]).strip()

            event = ExecutionEvent(
                source_id=source_id,
                source_type=source_type,
                source_reference=f"row_{idx + 2}",
                raw_text=raw_text,
                description=desc,
                discipline=discipline,
                activity_type=None,
                asset=None,
                location=location,
                status=status,
                event_date=event_date,
                quantity=quantity,
                unit=unit_val,
                extraction_confidence=0.0,
            )
            events.append(event)

        return ExtractionResult(events=events, source_id=source_id, source_type=source_type, warnings=warnings)
