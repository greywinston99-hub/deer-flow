"""CER authoring runtime.

This package is intentionally separate from ``deerflow.runtime.cer_review``.
Authoring writes CER draft work products; review evaluates existing CERs.
"""

from __future__ import annotations

from typing import Any

__all__ = ["build_cer_authoring_graph"]


def __getattr__(name: str) -> Any:
    if name == "build_cer_authoring_graph":
        from .graph import build_cer_authoring_graph

        return build_cer_authoring_graph
    raise AttributeError(name)
