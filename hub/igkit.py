"""Bridge to the instagram-agent-skill toolkit (MIT, Jake Schincariol).

``scripts/setup_skills.sh`` fetches it at a pinned commit into ``third_party/``
(run automatically on first use). Its Python tools are pure, offline text
utilities; we load them by path so the upstream code stays unmodified:

* ``swipe.analyse``   – rank short videos by multiple over the account baseline
* ``hookscore.run``   – score a hook on five text heuristics (English-tuned)
* ``humanize``        – strip invisible chars / em dashes / slop words from a draft
"""
from __future__ import annotations

import importlib.util
import logging
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

from .config import ROOT

KIT = ROOT / "third_party" / "instagram-agent-skill" / "skills"


@lru_cache(maxsize=None)
def ensure() -> bool:
    """Fetch the toolkit once if it is missing (needs git + network)."""
    if not KIT.exists():
        try:
            subprocess.run(["bash", str(ROOT / "scripts" / "setup_skills.sh")], check=True,
                           capture_output=True, timeout=120)
        except Exception as exc:  # noqa: BLE001 - pipeline degrades gracefully without it
            logging.getLogger(__name__).warning("instagram-agent-skill unavailable: %s", exc)
    return KIT.exists()


@lru_cache(maxsize=None)
def _load(rel: str, name: str):
    ensure()
    path = KIT / rel
    if not path.exists():
        return None
    sys.path.insert(0, str(path.parent))  # swipe.py imports hookscore from ../ig-reel
    sys.path.insert(0, str(KIT / "ig-reel"))
    spec = importlib.util.spec_from_file_location(f"igkit_{name}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


def available() -> bool:
    return ensure()


def rank_videos(rows: list[dict]) -> dict | None:
    """rows: dicts with account, followers, median (optional), views, hook."""
    swipe = _load("ig-viral/swipe.py", "swipe")
    if not swipe or not rows:
        return None
    formulas = swipe.load_formulas(str(KIT / "ig-reel" / "hooks.json"))
    return swipe.analyse([dict(r) for r in rows], formulas)


def score_hook(text: str) -> dict | None:
    hs = _load("ig-reel/hookscore.py", "hookscore")
    if not hs:
        return None
    results, overall, verdict, flags = hs.run(text)
    return {"score": round(overall, 1), "verdict": verdict, "flags": flags,
            "weakest": min(results, key=lambda k: results[k][0])}


def humanize(text: str) -> tuple[str, dict]:
    hz = _load("ig-human/humanize.py", "humanize")
    if not hz:
        return text, {}
    return hz.humanize(text, hz.load_lexicon())
