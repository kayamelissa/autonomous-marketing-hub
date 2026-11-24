"""Run the whole daily pipeline for one brand (or all brands).

    python -m hub.run_all --brand boyer-law-firm
    python -m hub.run_all --brand all --no-send
    python -m hub.run_all --brand boyer-law-firm --fixtures tests/fixtures/demo   # offline demo

Each collector runs in its own process, so one failure never blocks the
others; the briefing is always produced from whatever succeeded.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

from .config import ROOT, list_brands, load_brand

COLLECTORS = ["seo-hunter", "viral-radar", "ai-visibility-geo", "competitor-spy"]


def run_brand(slug: str, args) -> int:
    brand = load_brand(slug)
    day = args.date or brand.today()
    failures = 0
    for m in COLLECTORS:
        if args.only and m not in args.only:
            continue
        cmd = [sys.executable, str(ROOT / "modules" / m / "main.py"), "--brand", slug, "--date", day]
        if args.fixtures:
            cmd += ["--fixtures", str(args.fixtures)]
        t0 = time.time()
        rc = subprocess.call(cmd, cwd=ROOT)
        print(f"[{slug}] {m}: {'ok' if rc == 0 else f'failed ({rc})'} in {time.time() - t0:.1f}s", flush=True)
        failures += rc != 0
    cmd = [sys.executable, str(ROOT / "modules" / "content-repurposer" / "main.py"), "--brand", slug, "--date", day]
    if args.no_send:
        cmd.append("--no-send")
    if args.report_url:
        cmd += ["--report-url", args.report_url]
    rc = subprocess.call(cmd, cwd=ROOT)
    return 1 if rc else 0  # collectors degrade gracefully; only a missing briefing fails the run


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Run the daily marketing hub pipeline")
    p.add_argument("--brand", required=True, help="brand slug, or 'all'")
    p.add_argument("--date")
    p.add_argument("--fixtures", help="offline mode: folder of recorded responses")
    p.add_argument("--only", nargs="*", help="run only these collectors")
    p.add_argument("--no-send", action="store_true")
    p.add_argument("--report-url")
    args = p.parse_args(argv)
    slugs = list_brands() if args.brand == "all" else [args.brand]
    return max(run_brand(s, args) for s in slugs)


if __name__ == "__main__":
    raise SystemExit(main())
