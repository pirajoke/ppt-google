"""Simple file-based presentation storage. MVP — no DB needed."""

import os
from pathlib import Path

STORE_DIR = Path(os.environ.get("STORE_DIR", "/tmp/ppt-google-store"))


def _path(pres_id: str) -> Path:
    STORE_DIR.mkdir(parents=True, exist_ok=True)
    return STORE_DIR / f"{pres_id}.html"


def save_presentation(pres_id: str, html: str) -> None:
    _path(pres_id).write_text(html, encoding="utf-8")


def load_presentation(pres_id: str) -> str | None:
    p = _path(pres_id)
    if not p.exists():
        return None
    return p.read_text(encoding="utf-8")
