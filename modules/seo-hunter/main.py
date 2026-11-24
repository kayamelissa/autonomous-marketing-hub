"""seo-hunter — daily SEO & content opportunities.

Sources
  * Google Search Console API (official): real queries, impressions, position
  * Google autocomplete (public suggest endpoint): what people type right now
  * Google Trends daily trending RSS (public): rising searches in the country
  * The brand's own sitemap: on-page audit + "is this topic already covered?"

Outputs ``data/<brand>/<date>/seo-hunter.json`` with:
  quick_wins      queries ranking 4–20 with real impressions (cheapest gains)
  new_suggestions autocomplete phrases that did not appear yesterday
  content_gaps    demand phrases with no matching page on the site
  trending        trending searches that match the brand's topic words
  site_audit      title / description / H1 / schema issues per page
"""
from __future__ import annotations

import json
import re
import sys
import xml.etree.ElementTree as ET
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hub.cli import fixture, run_module  # noqa: E402
from hub.config import Brand, env  # noqa: E402
from hub.http import session  # noqa: E402
from hub.storage import previous_output  # noqa: E402
from hub.text import fold  # noqa: E402

MODULE = "seo-hunter"
STOP = {"ve", "ile", "en", "iyi", "the", "best", "near", "me", "in", "for", "of", "a", "de", "da",
        "yakın", "yakinimda", "fiyat", "fiyatları", "nedir", "nasıl", "how", "what", "is", "to"}


# --------------------------------------------------------------------------- sources
def autocomplete(brand: Brand, cfg: dict, fx) -> dict[str, list[str]]:
    if (rec := fixture(fx, "suggest")) is not None:
        return rec
    out: dict[str, list[str]] = {}
    s = session()
    for hl, gl in markets(brand, cfg):
        for seed in brand.ready(cfg.get("seed_keywords", [])):
            for mod in cfg.get("modifiers", [""]):
                q = f"{seed}{mod}".strip()
                r = s.get("https://suggestqueries.google.com/complete/search",
                          params={"client": "firefox", "hl": hl, "gl": gl, "q": q}, timeout=20)
                if r.ok:
                    out.setdefault(q, [])
                    out[q] += [x for x in r.json()[1] if fold(x) != fold(q) and x not in out[q]]
    return out


def markets(brand: Brand, cfg: dict) -> list[tuple[str, str]]:
    """(language, country) pairs to watch, e.g. Turkish speakers in TR and in the US."""
    return [tuple(m) for m in cfg.get("markets", [[brand.language, brand.country]])]


def trending(brand: Brand, cfg: dict, fx) -> list[dict]:
    rec = fixture(fx, "trends_rss")
    if rec:
        xmls = [(brand.country, rec["xml"])]
    else:
        xmls = []
        for gl in dict.fromkeys(gl for _, gl in markets(brand, cfg)):
            r = session().get("https://trends.google.com/trending/rss", params={"geo": gl}, timeout=20)
            if r.ok:
                xmls.append((gl, r.text))
    ns = {"ht": "https://trends.google.com/trending/rss"}
    words = [fold(w) for w in cfg.get("topic_words", [])]
    items = []
    for gl, xml in xmls:
        items += _trend_items(ET.fromstring(xml), ns, words, gl)
    return [i for i in items if i["matched_topics"]]


def _trend_items(root, ns, words, gl) -> list[dict]:
    items = []
    for it in root.iter("item"):
        title = (it.findtext("title") or "").strip()
        traffic = it.findtext("ht:approx_traffic", default="", namespaces=ns)
        news = [n.findtext("ht:news_item_title", default="", namespaces=ns)
                for n in it.findall("ht:news_item", ns)]
        blob = fold(" ".join([title, *news]))
        matched = [w for w in words if w in blob]
        items.append({"query": title, "approx_traffic": traffic, "matched_topics": matched, "country": gl})
    return items


def gsc_rows(brand: Brand, cfg: dict, fx, day: str) -> list[dict] | None:
    if (rec := fixture(fx, "gsc")) is not None:
        return rec
    creds_json, prop = env(cfg.get("gsc_credentials_env", "GSC_SERVICE_ACCOUNT_JSON")), (brand.ready([cfg.get("gsc_property")]) or [None])[0]
    if not creds_json or not prop:
        return None
    from google.auth.transport.requests import AuthorizedSession
    from google.oauth2 import service_account

    creds = service_account.Credentials.from_service_account_info(
        json.loads(creds_json), scopes=["https://www.googleapis.com/auth/webmasters.readonly"])
    end = date.fromisoformat(day) - timedelta(days=3)  # GSC data lags ~2-3 days
    body = {"startDate": (end - timedelta(days=27)).isoformat(), "endDate": end.isoformat(),
            "dimensions": ["query", "page"], "rowLimit": 1000}
    from urllib.parse import quote

    url = f"https://searchconsole.googleapis.com/webmasters/v3/sites/{quote(prop, safe='')}/searchAnalytics/query"
    r = AuthorizedSession(creds).post(url, json=body, timeout=60)
    r.raise_for_status()
    return [{"query": x["keys"][0], "page": x["keys"][1], "clicks": x["clicks"],
             "impressions": x["impressions"], "ctr": round(x["ctr"], 4), "position": round(x["position"], 1)}
            for x in r.json().get("rows", [])]


def site_pages(brand: Brand, cfg: dict, fx) -> list[dict]:
    if (rec := fixture(fx, "site")) is not None:
        return rec
    if not brand.domain_ready:
        return []
    s = session()
    r = s.get(f"https://{brand.domain}/sitemap.xml", timeout=20)
    if not r.ok:
        return []
    urls = re.findall(r"<loc>\s*([^<]+?)\s*</loc>", r.text)[: int(cfg.get("max_audit_pages", 40))]
    pages = []
    for u in urls:
        try:
            p = s.get(u, timeout=20)
        except Exception as exc:  # noqa: BLE001
            pages.append({"url": u, "status": None, "error": str(exc)})
            continue
        pages.append({"url": u, "status": p.status_code, **parse_page(p.text)})
    return pages


# --------------------------------------------------------------------------- analysis
def parse_page(html_text: str) -> dict:
    def one(pattern):
        m = re.search(pattern, html_text, re.I | re.S)
        return re.sub(r"\s+", " ", m.group(1)).strip() if m else None

    types = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html_text, re.S | re.I):
        types += re.findall(r'"@type"\s*:\s*"([^"]+)"', block)
    return {
        "title": one(r"<title[^>]*>(.*?)</title>"),
        "description": one(r'<meta[^>]+name=["\']description["\'][^>]+content=["\'](.*?)["\']'),
        "canonical": one(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\'](.*?)["\']'),
        "h1_count": len(re.findall(r"<h1[\s>]", html_text, re.I)),
        "schema_types": sorted(set(types)),
    }


def audit(pages: list[dict]) -> list[dict]:
    issues = []
    for p in pages:
        found = []
        if p.get("status") and p["status"] >= 400:
            found.append(f"HTTP {p['status']}")
        t, d = p.get("title") or "", p.get("description") or ""
        if not t:
            found.append("missing <title>")
        elif len(t) > 70:
            found.append(f"title {len(t)} chars (Google truncates ~60–70)")
        if not d:
            found.append("missing meta description")
        elif not 70 <= len(d) <= 170:
            found.append(f"meta description {len(d)} chars")
        if p.get("h1_count", 1) != 1:
            found.append(f"{p.get('h1_count')} <h1> tags")
        if not p.get("schema_types"):
            found.append("no JSON-LD structured data")
        if found:
            issues.append({"url": p["url"], "issues": found})
    return issues


def quick_wins(rows: list[dict], cfg: dict) -> list[dict]:
    lo, hi = cfg.get("quick_win_positions", [4, 20])
    min_imp = cfg.get("quick_win_min_impressions", 20)
    wins = [r for r in rows if lo <= r["position"] <= hi and r["impressions"] >= min_imp]
    return sorted(wins, key=lambda r: -r["impressions"])[:25]


def tokens(s: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", fold(s)) if w not in STOP and len(w) > 2}


def content_gaps(phrases: list[str], pages: list[dict]) -> list[str]:
    covered = set()
    for p in pages:
        covered |= tokens(" ".join(filter(None, [p.get("title"), p.get("description"), p.get("url")])))
    gaps = []
    for ph in phrases:
        tk = tokens(ph)
        if tk and not (tk & covered):
            gaps.append(ph)
    return sorted(set(gaps))


# --------------------------------------------------------------------------- entry
def collect(brand: Brand, day: str, fx):
    cfg = brand.module(MODULE)
    warnings: list[str] = []
    sugg = {}
    try:
        sugg = autocomplete(brand, cfg, fx)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"autocomplete unavailable: {exc}")
    all_sugg = sorted({x for v in sugg.values() for x in v})
    prev = previous_output(brand.slug, day, MODULE) or {}
    prev_set = set(prev.get("all_suggestions", []))
    new = [x for x in all_sugg if x not in prev_set] if prev_set else []

    trend = []
    try:
        trend = trending(brand, cfg, fx)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"trends unavailable: {exc}")

    rows = None
    try:
        rows = gsc_rows(brand, cfg, fx, day)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Search Console unavailable: {exc}")
    if rows is None:
        warnings.append(f"Search Console not configured ({cfg.get('gsc_credentials_env', 'GSC_SERVICE_ACCOUNT_JSON')} + gsc_property)")

    pages = []
    try:
        pages = site_pages(brand, cfg, fx)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"site crawl failed: {exc}")

    totals = None
    if rows:
        totals = {"clicks": sum(r["clicks"] for r in rows), "impressions": sum(r["impressions"] for r in rows)}
    return {
        "gsc_totals_28d": totals,
        "quick_wins": quick_wins(rows or [], cfg),
        "new_suggestions": new[:40],
        "all_suggestions": all_sugg,
        "content_gaps": content_gaps(all_sugg + [t["query"] for t in trend], pages)[:30] if pages else [],
        "trending": trend[:15],
        "site_audit": audit(pages),
        "pages_checked": len(pages),
    }, warnings


if __name__ == "__main__":
    raise SystemExit(run_module(MODULE, __doc__.splitlines()[0], collect))
