"""
Base class for format-specific schedule parsers.
"""

from abc import ABC, abstractmethod
import os
from typing import Tuple
from ..models import ScheduleParseResult


class BaseScheduleParser(ABC):
    """Abstract interface for format-specific schedule parsers."""

    @abstractmethod
    def parse(self, source: str, is_content: bool = False) -> ScheduleParseResult:
        """Parse source file path or string content into ScheduleParseResult."""
        pass

    @staticmethod
    def read_source(source: str, is_content: bool = False) -> Tuple[str, str]:
        """
        Read source and return (content, filename_or_name).
        """
        if is_content or not os.path.exists(source):
            return source, "in_memory"
        with open(source, "r", encoding="utf-8", errors="replace") as f:
            content = f.read()
        return content, os.path.basename(source)
