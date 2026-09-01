"""
Data models for SYNAPSE Schedule Parser.
Yazeen's module — Primavera & MS Project schedule normalization and standardization.
Fully compatible with Pydantic v2 and standard library fallback.
"""

from enum import Enum
from typing import List, Optional, Dict, Any

try:
    from pydantic import BaseModel, Field
    HAS_PYDANTIC = True
except ImportError:
    HAS_PYDANTIC = False

    class BaseModel:
        """Lightweight fallback when pydantic is not installed."""
        def __init__(self, **kwargs):
            # Apply defaults from class annotations/dict if not a property/method
            for k, val in getattr(self.__class__, "__dict__", {}).items():
                if not k.startswith("_") and not isinstance(val, (property, classmethod, staticmethod)) and not callable(val):
                    setattr(self, k, val)
            for k, v in kwargs.items():
                setattr(self, k, v)

        def model_dump(self) -> Dict[str, Any]:
            res = {}
            for k, v in self.__dict__.items():
                if k.startswith("_"):
                    continue
                if hasattr(v, "model_dump"):
                    res[k] = v.model_dump()
                elif isinstance(v, list):
                    res[k] = [item.model_dump() if hasattr(item, "model_dump") else item for item in v]
                elif isinstance(v, dict):
                    res[k] = {dk: (dv.model_dump() if hasattr(dv, "model_dump") else dv) for dk, dv in v.items()}
                else:
                    res[k] = v
            return res

        def dict(self) -> Dict[str, Any]:
            return self.model_dump()

    def Field(default=None, default_factory=None, description=None, **kwargs):
        if default_factory is not None:
            return default_factory()
        return default


class ScheduleStatus(str, Enum):
    PLANNED = "planned"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    DELAYED = "delayed"
    SUSPENDED = "suspended"
    UNKNOWN = "unknown"


class QualitySeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class WBSNode(BaseModel):
    """Represents a node in the Work Breakdown Structure hierarchy."""
    wbs_id: str = ""
    code: str = ""
    name: str = ""
    parent_wbs_id: Optional[str] = None
    level: int = 1  # 1 to 6
    path: str = ""   # e.g., "Project > Unit 4 > Piping"
    children: List[str] = Field(default_factory=list)
    discipline: Optional[str] = None
    location: Optional[str] = None


class ScheduleActivity(BaseModel):
    """
    Standardized Schedule Activity format for SYNAPSE.
    Feeds directly into Amritha's matching engine.
    """
    activity_id: str = Field(default="", description="Preserved original activity ID")
    activity_name: str = Field(default="", description="Preserved original activity name")
    wbs_id: str = Field(default="", description="Parent WBS ID")
    wbs_level: int = Field(default=6, description="WBS hierarchy level (e.g., 5 or 6)")
    level: str = Field(default="L6", description="Level tag (e.g., 'L5', 'L6')")
    discipline: Optional[str] = Field(default=None, description="Normalized discipline (piping, electrical, etc.)")
    planned_start: str = Field(default="", description="Planned start date in ISO YYYY-MM-DD format")
    planned_finish: str = Field(default="", description="Planned finish date in ISO YYYY-MM-DD format")
    duration_days: int = Field(default=1, description="Planned duration in days")
    predecessors: List[str] = Field(default_factory=list, description="List of predecessor activity IDs")
    successors: List[str] = Field(default_factory=list, description="List of successor activity IDs")
    location: Optional[str] = Field(default=None, description="Normalized location / area / unit")
    status: str = Field(default="planned", description="Activity status")

    # Additional contextual fields for strong version & NLP matching
    normalized_name: Optional[str] = Field(default=None, description="Normalized lowercase title for fuzzy search")
    wbs_path: Optional[str] = Field(default=None, description="Full WBS breadcrumb path")
    search_text: Optional[str] = Field(default=None, description="Enriched text for vector/TF-IDF embeddings")
    actual_start: Optional[str] = Field(default=None, description="Actual start date if recorded in schedule")
    actual_finish: Optional[str] = Field(default=None, description="Actual finish date if recorded in schedule")
    raw_data: Optional[Dict[str, Any]] = Field(default=None, description="Preserved raw source fields")

    def to_contract_dict(self) -> Dict[str, Any]:
        """Convert to the exact dictionary expected in the 03_YAZEEN_SCHEDULE_PARSER.md spec."""
        return {
            "activity_id": self.activity_id,
            "activity_name": self.activity_name,
            "wbs_id": self.wbs_id,
            "wbs_level": self.wbs_level,
            "discipline": self.discipline,
            "planned_start": self.planned_start,
            "planned_finish": self.planned_finish,
            "duration_days": self.duration_days,
            "predecessors": self.predecessors,
            "location": self.location,
            "status": self.status,
        }

    def to_amritha_dict(self) -> Dict[str, Any]:
        """
        Convert to format consumed by Amritha's SynapseMatchingEngine.
        Matches keys in schedule.csv:
        activity_id, activity_name, wbs_id, wbs_level, discipline, location,
        planned_start, planned_finish, duration_days, predecessors, successors
        """
        return {
            "activity_id": self.activity_id,
            "activity_name": self.activity_name,
            "wbs_id": self.wbs_id,
            "wbs_level": self.level or f"L{self.wbs_level}",
            "level": self.level,
            "discipline": self.discipline or "",
            "location": self.location or "",
            "planned_start": self.planned_start,
            "planned_finish": self.planned_finish,
            "duration_days": self.duration_days,
            "predecessors": ",".join(self.predecessors) if isinstance(self.predecessors, list) else str(self.predecessors or ""),
            "successors": ",".join(self.successors) if isinstance(self.successors, list) else str(self.successors or ""),
            "search_text": self.search_text or f"{self.activity_name} {self.discipline or ''} {self.location or ''}".strip(),
            "status": self.status,
        }


class DataQualityIssue(BaseModel):
    """Represents a data quality warning or error flagged during parsing."""
    issue_type: str = Field(default="", description="Issue code (e.g. missing_id, invalid_date)")
    severity: QualitySeverity = Field(default=QualitySeverity.WARNING)
    activity_id: Optional[str] = None
    message: str = Field(default="", description="Human readable description of the issue")
    field: Optional[str] = None
    raw_value: Optional[str] = None


class DataQualityReport(BaseModel):
    """Aggregated report of data quality findings."""
    total_records_inspected: int = 0
    total_issues: int = 0
    error_count: int = 0
    warning_count: int = 0
    info_count: int = 0
    issues: List[DataQualityIssue] = Field(default_factory=list)
    issue_counts_by_type: Dict[str, int] = Field(default_factory=dict)

    def add_issue(self, issue: DataQualityIssue):
        self.issues.append(issue)
        self.total_issues += 1
        if issue.severity == QualitySeverity.ERROR:
            self.error_count += 1
        elif issue.severity == QualitySeverity.WARNING:
            self.warning_count += 1
        else:
            self.info_count += 1

        self.issue_counts_by_type[issue.issue_type] = (
            self.issue_counts_by_type.get(issue.issue_type, 0) + 1
        )


class ScheduleParseResult(BaseModel):
    """Output container for a complete schedule parsing operation."""
    format_detected: str = Field(default="", description="Detected file format (primavera_xer, msproject_xml, csv, etc.)")
    project_id: Optional[str] = None
    project_name: Optional[str] = None
    schedule_version: Optional[str] = None
    total_activities_read: int = 0
    l5_l6_activities_count: int = 0
    filtered_summary_count: int = 0
    activities: List[ScheduleActivity] = Field(default_factory=list)
    wbs_nodes: Dict[str, WBSNode] = Field(default_factory=dict)
    quality_report: DataQualityReport = Field(default_factory=DataQualityReport)
    parse_time_ms: float = 0.0

    @property
    def is_valid(self) -> bool:
        """Schedule is considered valid if there are zero blocking errors."""
        return self.quality_report.error_count == 0

    def to_amritha_format(self) -> List[Dict[str, Any]]:
        """Direct list of activity dicts for Amritha's matching engine."""
        return [act.to_amritha_dict() for act in self.activities]

    def to_contract_format(self) -> List[Dict[str, Any]]:
        """List of activity dicts matching exact 03_YAZEEN_SCHEDULE_PARSER.md JSON contract."""
        return [act.to_contract_dict() for act in self.activities]
