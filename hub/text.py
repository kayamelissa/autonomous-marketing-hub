"""Text helpers shared by modules (brand matching, normalisation)."""
from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlparse

_TR_MAP = str.maketrans({"İ": "i", "I": "ı", "Ş": "ş", "Ğ": "ğ", "Ü": "ü", "Ö": "ö", "Ç": "ç"})


def fold(s: str) -> str:
    """Case/diacritic-insensitive form, Turkish-aware (İ/ı) and ASCII-folded."""
    s = s.translate(_TR_MAP).lower().replace("ı", "i")
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def first_position(text: str, names: list[str]) -> int | None:
    """Character offset of the first mention of any alias, or None."""
    t = fold(text)
    hits = []
    for n in names:
        m = re.search(r"(?<![a-z0-9])" + re.escape(fold(n)) + r"(?![a-z0-9])", t)
        if m:
            hits.append(m.start())
    return min(hits) if hits else None


def domain_of(url: str) -> str:
    host = urlparse(url).netloc.lower()
    return host[4:] if host.startswith("www.") else host
