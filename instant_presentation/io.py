"""Shared output helpers for CLI and integrations."""

from __future__ import annotations

import json
from pathlib import Path


def serialize_result(result: dict[str, Path | str]) -> dict[str, str]:
    """Convert path-like results into plain strings."""
    serialized: dict[str, str] = {}
    for key, value in result.items():
        serialized[key] = str(value)
    return serialized


def render_result_json(result: dict[str, Path | str]) -> str:
    """Render a stable JSON payload for bot integrations."""
    return json.dumps(serialize_result(result), ensure_ascii=False, indent=2)
