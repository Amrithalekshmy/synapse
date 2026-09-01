"""
Data models for the SYNAPSE Knowledge Base.
Adithyagopan's module — institutional memory & delay risk intelligence.

Uses Pydantic v2 with a stdlib fallback (see _compat.py).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional

from ._compat import BaseModel, Field


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------

class RecordQuality(str, Enum):
    """Data quality / trust level of a historical record."""
    VERIFIED    = "verified"
    PROVISIONAL = "provisional"
    REJECTED    = "rejected"


class Discipline(str, Enum):
    PIPING          = "piping"
    ELECTRICAL      = "electrical"
    CIVIL           = "civil"
    INSTRUMENTATION = "instrumentation"
    MECHANICAL      = "mechanical"
    UNKNOWN         = "unknown"


# ---------------------------------------------------------------------------
# Core record — one completed execution history entry
# ---------------------------------------------------------------------------

class HistoricalRecord(BaseModel):
    """
    One row in the SYNAPSE institutional memory.

    Captures everything that happened during a single planned activity on a
    completed EPC project so that future projects can learn from it.
    """
    # Identity
    record_id:            str = Field(default="", description="Unique record identifier (UUID or slug)")
    project_id:           str = Field(default="", description="Source project identifier")
    activity_id:          str = Field(default="", description="Original schedule activity ID")
    activity_description: str = Field(default="", description="Activity description")

    # Classification
    discipline:    str = Field(default="unknown", description="Discipline (piping, electrical, civil, ...)")
    activity_type: str = Field(default="",        description="Action type: erection, welding, installation, ...")
    location_type: str = Field(default="",        description="Location descriptor: unit, area, substation, ...")

    # Planned vs actual
    planned_start:  Optional[str] = Field(default=None, description="Planned start date (YYYY-MM-DD)")
    planned_finish: Optional[str] = Field(default=None, description="Planned finish date (YYYY-MM-DD)")
    actual_start:   Optional[str] = Field(default=None, description="Actual start date (YYYY-MM-DD)")
    actual_finish:  Optional[str] = Field(default=None, description="Actual finish date (YYYY-MM-DD)")

    # Duration & variance
    planned_duration_days: int = Field(default=0, description="Planned duration in calendar days")
    actual_duration_days:  int = Field(default=0, description="Actual duration in calendar days")
    variance_days:         int = Field(default=0, description="Actual - Planned (positive = delayed)")

    # Delay intelligence
    delayed:     bool          = Field(default=False, description="Whether the activity was delayed")
    delay_cause: Optional[str] = Field(default=None,  description="Primary cause of delay, if delayed")

    # Productivity
    productivity_rate: Optional[float] = Field(default=None, description="Measured unit rate e.g. spools/day")
    productivity_unit: Optional[str]   = Field(default=None, description="Unit of productivity")

    # Provenance
    source_reference: Optional[str]   = Field(default=None, description="Source document or report")
    match_confidence: Optional[float] = Field(default=None, description="Confidence of the original match decision")
    reviewer_status:  Optional[str]   = Field(default=None, description="approved / rejected / auto")
    record_quality:   str             = Field(default="provisional", description="verified | provisional | rejected")


# ---------------------------------------------------------------------------
# Delay risk — returned to Adithyanbalu's risk scoring engine
# ---------------------------------------------------------------------------

class DelayCause(BaseModel):
    cause:     str   = Field(default="")
    frequency: float = Field(default=0.0, description="Proportion of matched records with this cause [0-1]")
    count:     int   = Field(default=0)


class DelayRiskResult(BaseModel):
    """
    Forward-looking risk profile for a *current* activity, derived from
    historically similar completed activities.

    Primary output consumed by Adithyanbalu's risk engine.
    """
    query_activity:           str              = Field(default="")
    discipline:               str              = Field(default="")
    activity_type:            str              = Field(default="")
    historical_matches:       int              = Field(default=0)
    avg_planned_duration_days: float           = Field(default=0.0)
    avg_actual_duration_days:  float           = Field(default=0.0)
    avg_variance_days:         float           = Field(default=0.0)
    delay_frequency:           float           = Field(default=0.0, description="Proportion delayed [0-1]")
    common_delay_causes:       list[DelayCause] = Field(default_factory=list)
    suggested_buffer_days:     int             = Field(default=0)
    risk_level:                str             = Field(default="LOW", description="HIGH / MEDIUM / LOW")
    confidence:                str             = Field(default="low", description="high | medium | low")


# ---------------------------------------------------------------------------
# Productivity benchmark
# ---------------------------------------------------------------------------

class ProductivityBenchmark(BaseModel):
    """Discipline + activity_type level productivity statistics."""
    discipline:        str            = Field(default="")
    activity_type:     str            = Field(default="")
    sample_count:      int            = Field(default=0)
    avg_rate:          Optional[float] = Field(default=None)
    best_rate:         Optional[float] = Field(default=None)
    worst_rate:        Optional[float] = Field(default=None)
    productivity_unit: Optional[str]  = Field(default=None)
    avg_planned_days:  float          = Field(default=0.0)
    avg_actual_days:   float          = Field(default=0.0)
    avg_variance_days: float          = Field(default=0.0)
    delay_frequency:   float          = Field(default=0.0)
