"""
FastAPI router endpoint for SYNAPSE schedule ingestion.
Implements POST /schedule/import as outlined in SIH26122 architecture.
"""

from typing import Optional, List, Dict, Any
from .pipeline import ScheduleParser
from .models import ScheduleParseResult

# Optional FastAPI support
try:
    from fastapi import APIRouter, UploadFile, File, Form, HTTPException
    HAS_FASTAPI = True
except ImportError:
    HAS_FASTAPI = False


def create_schedule_router():
    """Create and return FastAPI router for schedule endpoints."""
    if not HAS_FASTAPI:
        raise RuntimeError("FastAPI is not installed in the current environment.")

    router = APIRouter(prefix="/schedule", tags=["Schedule Parser (Yazeen)"])
    parser = ScheduleParser()

    @router.post("/import")
    async def import_schedule(
        file: UploadFile = File(...),
        format_hint: Optional[str] = Form(None),
    ) -> Dict[str, Any]:
        """
        Upload and standardize an enterprise schedule export (P6 XER/XML, MS Project, CSV).
        Returns standardized ScheduleActivity list and Data Quality Audit.
        """
        try:
            content_bytes = await file.read()
            content_str = content_bytes.decode("utf-8", errors="replace")

            result = parser.parse(content_str, is_content=True, format_hint=format_hint)

            return {
                "status": "success",
                "filename": file.filename,
                "format_detected": result.format_detected,
                "is_valid": result.is_valid,
                "total_read": result.total_activities_read,
                "l5_l6_count": result.l5_l6_activities_count,
                "filtered_summary_count": result.filtered_summary_count,
                "parse_time_ms": result.parse_time_ms,
                "quality_summary": {
                    "total_issues": result.quality_report.total_issues,
                    "errors": result.quality_report.error_count,
                    "warnings": result.quality_report.warning_count,
                },
                "activities": result.to_contract_format(),
                "amritha_format": result.to_amritha_format(),
            }
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Schedule parsing failed: {str(e)}")

    return router
