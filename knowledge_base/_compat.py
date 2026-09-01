"""
Pydantic v2 compatibility shim for the SYNAPSE Knowledge Base.
Adithyagopan's module.

Try pydantic; fall back to the pure-stdlib shim in _fallback.py.
Import BaseModel and Field from here — never import pydantic directly
in the rest of the knowledge_base package.
"""

from __future__ import annotations

try:
    from pydantic import BaseModel, Field  # type: ignore  # noqa: F401
except ImportError:
    from ._fallback import BaseModel, Field  # type: ignore[no-redef]  # noqa: F401

__all__ = ["BaseModel", "Field"]
