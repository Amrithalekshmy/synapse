"""
Pure-stdlib fallback implementations of BaseModel and Field.
Only imported by _compat.py when pydantic is not installed.
Never import this module directly — use _compat instead.
"""

from __future__ import annotations

from typing import Any


class BaseModel:
    """Minimal Pydantic-compatible base when pydantic is absent."""

    def __init__(self, **kwargs: Any) -> None:
        # Set class-level defaults first
        for k, val in self.__class__.__dict__.items():
            if (
                not k.startswith("_")
                and not isinstance(val, (property, classmethod, staticmethod))
                and not callable(val)
            ):
                setattr(self, k, val)
        # Then apply caller kwargs (override defaults)
        for k, v in kwargs.items():
            setattr(self, k, v)

    def model_dump(self) -> dict[str, Any]:
        res: dict[str, Any] = {}
        for k, v in self.__dict__.items():
            if k.startswith("_"):
                continue
            if hasattr(v, "model_dump"):
                res[k] = v.model_dump()
            elif isinstance(v, list):
                res[k] = [
                    item.model_dump() if hasattr(item, "model_dump") else item
                    for item in v
                ]
            else:
                res[k] = v
        return res

    def dict(self) -> dict[str, Any]:
        return self.model_dump()


def Field(
    default: Any = None,
    default_factory: Any = None,
    description: Any = None,
    **_: Any,
) -> Any:
    """Pydantic Field() stub — returns the default value."""
    if default_factory is not None:
        return default_factory()
    return default
