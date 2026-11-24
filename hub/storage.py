"""Run output + persistent state on disk.

Layout (all gitignored)::

    data/<brand>/<YYYY-MM-DD>/<module>.json   daily module output
    data/<brand>/state/<module>/...           state carried between runs (snapshots)
    reports/<brand>/<YYYY-MM-DD>.md           the daily briefing

In GitHub Actions, ``data/<brand>/state`` is persisted with ``actions/cache``
so nothing private is ever committed to the (public) repository.
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .config import ROOT

DATA_DIR = ROOT / "data"
REPORTS_DIR = ROOT / "reports"


def run_dir(brand: str, day: str) -> Path:
    p = DATA_DIR / brand / day
    p.mkdir(parents=True, exist_ok=True)
    return p


def state_dir(brand: str, module: str) -> Path:
    p = DATA_DIR / brand / "state" / module
    p.mkdir(parents=True, exist_ok=True)
    return p


def envelope(module: str, brand: str, day: str, payload: dict[str, Any],
             warnings: list[str] | None = None) -> dict[str, Any]:
    return {
        "module": module,
        "brand": brand,
        "date": day,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "warnings": warnings or [],
        **payload,
    }


def write_output(brand: str, day: str, module: str, data: dict[str, Any]) -> Path:
    path = run_dir(brand, day) / f"{module}.json"
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def read_output(brand: str, day: str, module: str) -> dict[str, Any] | None:
    path = DATA_DIR / brand / day / f"{module}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def previous_output(brand: str, day: str, module: str, lookback: int = 7) -> dict[str, Any] | None:
    """Most recent output before ``day`` (used for day-over-day deltas)."""
    d = date.fromisoformat(day)
    for i in range(1, lookback + 1):
        prev = read_output(brand, (d - timedelta(days=i)).isoformat(), module)
        if prev:
            return prev
    return None


def write_report(brand: str, day: str, markdown: str) -> Path:
    p = REPORTS_DIR / brand
    p.mkdir(parents=True, exist_ok=True)
    path = p / f"{day}.md"
    path.write_text(markdown, encoding="utf-8")
    return path
