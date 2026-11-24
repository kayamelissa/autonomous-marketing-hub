"""Brand profile + environment loading.

Every brand lives in ``brands/<slug>/brand.yaml``. The YAML only ever holds the
*names* of environment variables (e.g. ``slack_webhook_env: SLACK_WEBHOOK_URL_BOYER``),
never secret values. Secrets come from the process environment, a local ``.env``
file (gitignored) or GitHub Actions secrets.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import yaml

ROOT = Path(__file__).resolve().parent.parent
BRANDS_DIR = ROOT / "brands"

try:  # optional: local development convenience
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass


class ConfigError(RuntimeError):
    pass


@dataclass
class Brand:
    slug: str
    raw: dict[str, Any] = field(repr=False)

    # --- convenience accessors -------------------------------------------------
    @property
    def name(self) -> str:
        return self.raw["name"]

    @property
    def language(self) -> str:
        return self.raw.get("language", "en")

    @property
    def country(self) -> str:
        return self.raw.get("country", "US")

    @property
    def timezone(self) -> str:
        return self.raw.get("timezone", "UTC")

    @property
    def domain(self) -> str | None:
        return self.raw.get("domain")

    @property
    def aliases(self) -> list[str]:
        return [self.name, *self.raw.get("aliases", [])]

    @property
    def domain_ready(self) -> bool:
        return bool(self.domain) and "TODO" not in self.domain

    @property
    def competitors(self) -> list[dict[str, Any]]:
        return self.ready(self.raw.get("competitors", []) or [])

    def module(self, name: str) -> dict[str, Any]:
        """Per-module settings block (``modules.<name>`` in brand.yaml)."""
        return (self.raw.get("modules", {}) or {}).get(name, {}) or {}

    def module_enabled(self, name: str) -> bool:
        return bool(self.module(name).get("enabled", True))

    def today(self) -> str:
        return datetime.now(ZoneInfo(self.timezone)).strftime("%Y-%m-%d")

    @staticmethod
    def ready(values: list) -> list:
        """Drop placeholder entries (anything containing 'TODO') from a list."""
        return [v for v in values or [] if "TODO" not in (v if isinstance(v, str) else str(v.get("name", "")))]

    def todo_fields(self) -> list[str]:
        """Return dotted paths of values still set to the TODO placeholder."""
        out: list[str] = []

        def walk(node: Any, path: str) -> None:
            if isinstance(node, dict):
                for k, v in node.items():
                    walk(v, f"{path}.{k}" if path else k)
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    walk(v, f"{path}[{i}]")
            elif isinstance(node, str) and node.strip().upper().startswith("TODO"):
                out.append(path)

        walk(self.raw, "")
        return out


def list_brands() -> list[str]:
    return sorted(p.name for p in BRANDS_DIR.iterdir() if (p / "brand.yaml").exists())


def load_brand(slug: str) -> Brand:
    path = BRANDS_DIR / slug / "brand.yaml"
    if not path.exists():
        raise ConfigError(f"Unknown brand '{slug}'. Available: {', '.join(list_brands())}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("name", "language", "timezone"):
        if key not in raw:
            raise ConfigError(f"{path}: missing required key '{key}'")
    return Brand(slug=slug, raw=raw)


def env(name: str | None, default: str | None = None) -> str | None:
    """Read an env var; empty strings count as missing."""
    if not name:
        return default
    val = os.environ.get(name, "").strip()
    return val or default
