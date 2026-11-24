"""Common CLI scaffolding so every module runs standalone the same way::

    python modules/<module>/main.py --brand boyer-law-firm [--date 2026-11-24] [--fixtures DIR]
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from pathlib import Path
from typing import Callable

from .config import Brand, load_brand
from .storage import envelope, write_output

Collector = Callable[[Brand, str, "Path | None"], tuple[dict, list[str]]]


def parser(description: str) -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=description)
    p.add_argument("--brand", required=True, help="brand slug under brands/")
    p.add_argument("--date", help="run date (YYYY-MM-DD); defaults to today in the brand's timezone")
    p.add_argument("--fixtures", type=Path,
                   help="offline mode: read recorded API responses from this folder instead of calling APIs")
    p.add_argument("-v", "--verbose", action="store_true")
    return p


def run_module(module: str, description: str, collect: Collector, argv=None) -> int:
    args = parser(description).parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format=f"%(levelname)s [{module}] %(message)s")
    brand = load_brand(args.brand)
    day = args.date or brand.today()
    if not brand.module_enabled(module):
        logging.info("Disabled for %s in brand.yaml", brand.slug)
        return 0
    todo = brand.todo_fields()
    try:
        payload, warnings = collect(brand, day, args.fixtures)
        status = 0
    except Exception as exc:  # one failing module must not kill the daily run
        logging.error("%s failed: %s", module, exc)
        payload, warnings, status = {"error": str(exc), "trace": traceback.format_exc(limit=3)}, [str(exc)], 1
    if todo:
        warnings.append(f"brand.yaml still has TODO values: {', '.join(todo[:6])}")
    out = write_output(brand.slug, day, module, envelope(module, brand.slug, day, payload, warnings))
    logging.info("Wrote %s", out.relative_to(out.parents[3]))
    if args.verbose:
        json.dump(payload, sys.stdout, ensure_ascii=False, indent=2)
    return status


def fixture(fixtures: Path | None, name: str):
    """Load a recorded response (``<fixtures>/<name>.json``) or None."""
    if not fixtures:
        return None
    p = fixtures / f"{name}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
