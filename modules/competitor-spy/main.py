"""competitor-spy — competitor site changes, prices, promos, reviews and ads.

Daily, for every competitor in brand.yaml:
  * fetches the tracked pages, stores a text snapshot, and reports what changed
    since the last run (new/removed lines), highlighting price & promo lines
  * Google Places API (official): rating + review count, ours vs theirs
  * Meta Ad Library API (official): active ad texts. NOTE: Meta only returns
    non-political ads delivered in the EU/UK through the API; outside the EU
    the module falls back to Ad Library / Google Ads Transparency links.

Pages that need JavaScript can be rendered with Playwright (``render: true``).
"""
from __future__ import annotations

import difflib
import hashlib
import html as htmllib
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hub.cli import fixture, run_module  # noqa: E402
from hub.config import Brand, env  # noqa: E402
from hub.http import get_json, post_json, session  # noqa: E402
from hub.storage import state_dir  # noqa: E402

MODULE = "competitor-spy"
PRICE = re.compile(r"(₺|\$|€|£|\bTL\b|\bUSD\b)\s?\d|\d[\d.,]*\s?(₺|TL|\$|€)", re.I)
PROMO = re.compile(r"\b(indirim|kampanya|fırsat|bedava|ücretsiz|hediye|yeni|açılış|%\s?\d+|\d+\s?%|"
                   r"sale|discount|free|new|offer|limited|promo|consultation|no fee|award)\b", re.I)


def page_text(html_text: str) -> list[str]:
    t = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html_text)
    t = re.sub(r"(?i)<br\s*/?>|</(p|div|li|h\d|tr|section|article)>", "\n", t)
    t = htmllib.unescape(re.sub(r"<[^>]+>", " ", t))
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in t.splitlines()]
    return [ln for ln in lines if len(ln) > 2]


def fetch(url: str, render: bool) -> str:
    if render:
        from playwright.sync_api import sync_playwright  # optional dependency

        with sync_playwright() as p:
            b = p.chromium.launch()
            pg = b.new_page()
            pg.goto(url, wait_until="networkidle", timeout=45000)
            content = pg.content()
            b.close()
            return content
    r = session().get(url, timeout=30)
    r.raise_for_status()
    return r.text


def diff_page(brand: Brand, comp: str, url: str, lines: list[str]) -> dict:
    sd = state_dir(brand.slug, MODULE)
    key = hashlib.sha1(url.encode()).hexdigest()[:12]
    snap = sd / f"{key}.json"
    prev = json.loads(snap.read_text(encoding="utf-8"))["lines"] if snap.exists() else None
    snap.write_text(json.dumps({"url": url, "competitor": comp, "lines": lines}, ensure_ascii=False), encoding="utf-8")
    if prev is None:
        promo = [x for x in lines if PRICE.search(x) or PROMO.search(x)]
        return {"url": url, "status": "baseline saved", "added": [], "removed": [],
                "price_or_promo_current": promo[:15]}
    added, removed = [], []
    for op in difflib.ndiff(prev, lines):
        if op.startswith("+ "):
            added.append(op[2:])
        elif op.startswith("- "):
            removed.append(op[2:])
    flag = lambda xs: [x for x in xs if PRICE.search(x) or PROMO.search(x)]  # noqa: E731
    return {"url": url, "status": "changed" if added or removed else "no change",
            "added": added[:30], "removed": removed[:30],
            "price_or_promo_added": flag(added)[:15], "price_or_promo_removed": flag(removed)[:15]}


def places(brand: Brand, fx) -> list[dict]:
    rec = fixture(fx, "places")
    if rec is not None:
        return rec
    key = env("GOOGLE_PLACES_API_KEY")
    if not key:
        raise RuntimeError("GOOGLE_PLACES_API_KEY not set")
    out = []
    targets = [{"name": brand.name, "places_query": brand.raw.get("places_query"), "us": True}] + brand.competitors
    for t in targets:
        q = t.get("places_query") or f"{t['name']} {brand.raw.get('city', '')}".strip()
        if "TODO" in q:
            continue
        res = post_json("https://places.googleapis.com/v1/places:searchText",
                        headers={"X-Goog-Api-Key": key,
                                 "X-Goog-FieldMask": "places.displayName,places.rating,places.userRatingCount,places.googleMapsUri"},
                        json={"textQuery": q, "languageCode": brand.language, "maxResultCount": 1})
        p = (res.get("places") or [{}])[0]
        out.append({"name": t["name"], "is_us": bool(t.get("us")), "rating": p.get("rating"),
                    "reviews": p.get("userRatingCount"), "maps": p.get("googleMapsUri")})
    return out


def meta_ads(brand: Brand, comp: dict, fx) -> list[dict] | None:
    rec = fixture(fx, f"meta_ads_{comp['name']}")
    if rec is not None:
        return rec
    token, page_id = env("META_AD_LIBRARY_TOKEN"), comp.get("facebook_page_id")
    if not (token and page_id) or brand.country not in EU_UK:
        return None
    data = get_json("https://graph.facebook.com/v21.0/ads_archive", params={
        "access_token": token, "search_page_ids": page_id, "ad_reached_countries": json.dumps([brand.country]),
        "ad_active_status": "ACTIVE", "fields": "ad_creative_bodies,ad_delivery_start_time,ad_snapshot_url", "limit": 25})
    return [{"text": (a.get("ad_creative_bodies") or [""])[0][:300], "since": a.get("ad_delivery_start_time"),
             "snapshot": a.get("ad_snapshot_url")} for a in data.get("data", [])]


EU_UK = {"AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR", "DE", "GR", "HU", "IE", "IT", "LV", "LT",
         "LU", "MT", "NL", "PL", "PT", "RO", "SK", "SI", "ES", "SE", "GB"}


def ad_links(brand: Brand, comp: dict) -> dict:
    n = quote_plus(comp["name"])
    links = {"meta_ad_library": f"https://www.facebook.com/ads/library/?active_status=active&ad_type=all"
                                f"&country={brand.country}&q={n}&search_type=keyword_unordered"}
    if comp.get("url"):
        from hub.text import domain_of

        links["google_ads_transparency"] = f"https://adstransparency.google.com/?region={brand.country}&domain={domain_of(comp['url'])}"
    return links


def collect(brand: Brand, day: str, fx):
    warnings: list[str] = []
    recorded_pages = fixture(fx, "competitor_pages")  # {url: html}
    competitors = []
    for comp in brand.competitors:
        entry = {"name": comp["name"], "pages": [], "ads": None, "ad_links": ad_links(brand, comp)}
        for url in [u for u in [comp.get("url"), *comp.get("track_pages", [])] if u]:
            try:
                html_text = recorded_pages[url] if recorded_pages else fetch(url, comp.get("render", False))
                entry["pages"].append(diff_page(brand, comp["name"], url, page_text(html_text)))
            except Exception as exc:  # noqa: BLE001
                entry["pages"].append({"url": url, "status": f"error: {str(exc)[:150]}"})
        try:
            entry["ads"] = meta_ads(brand, comp, fx)
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"Meta Ad Library for {comp['name']}: {exc}")
        if not comp.get("url"):
            warnings.append(f"{comp['name']}: no website set in brand.yaml (only reviews/ads tracked)")
        competitors.append(entry)
    reviews = []
    try:
        reviews = places(brand, fx)
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"reviews skipped: {exc}")
    us = next((r for r in reviews if r["is_us"]), None)
    gap = None
    if us and us.get("reviews") is not None:
        others = [r["reviews"] for r in reviews if not r["is_us"] and r.get("reviews")]
        if others:
            from statistics import median

            gap = {"our_reviews": us["reviews"], "competitor_median": round(median(others)),
                   "leader": max((r for r in reviews if not r["is_us"] and r.get("reviews")), key=lambda r: r["reviews"])["name"]}
    changed = [p for c in competitors for p in c["pages"] if p.get("status") == "changed"]
    return {"competitors": competitors, "reviews": reviews, "review_gap": gap,
            "pages_changed": len(changed)}, warnings


if __name__ == "__main__":
    raise SystemExit(run_module(MODULE, __doc__.splitlines()[0], collect))
