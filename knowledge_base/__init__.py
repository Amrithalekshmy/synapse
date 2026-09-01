"""
SYNAPSE Knowledge Base — Adithyagopan's module.

Institutional memory and delay risk intelligence for SIH26122 SYNAPSE.

Exposes:
  KnowledgeBase        — in-memory store (minimum version, no PostgreSQL required)
  DelayRiskEngine      — forward-looking risk scoring for current activities
  ProductivityTracker  — discipline-level productivity benchmarking
  NLQueryEngine        — natural-language query layer over historical records
  router               — FastAPI router (strong version)
"""

from .models import HistoricalRecord, DelayRiskResult, ProductivityBenchmark, RecordQuality
from .store import KnowledgeBase
from .risk import DelayRiskEngine
from .productivity import ProductivityTracker
from .queries import run_builtin_queries
from .nlquery import NLQueryEngine

__all__ = [
    "HistoricalRecord",
    "DelayRiskResult",
    "ProductivityBenchmark",
    "RecordQuality",
    "KnowledgeBase",
    "DelayRiskEngine",
    "ProductivityTracker",
    "run_builtin_queries",
    "NLQueryEngine",
]
