"""viral-radar — daily short-video trends, formats, sounds and hooks.

Platforms
  * YouTube Shorts — official YouTube Data API v3 (YOUTUBE_API_KEY)
  * TikTok / Instagram Reels — optional Apify actors (APIFY_TOKEN). Neither
    platform offers an official trends API; scraping is governed by their terms
    of service, so these adapters are OFF by default and your responsibility to
    enable. Without them the briefing links to TikTok Creative Center instead.

Ranking uses the instagram-agent-skill ``swipe`` logic: a video is
"viral" by its multiple over its own account's baseline, not by raw views.
"""
from __future__ import annotations

import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hub import igkit  # noqa: E402
from hub.cli import fixture, run_module  # noqa: E402
from hub.config import Brand, env  # noqa: E402
from hub.http import get_json, post_json  # noqa: E402

MODULE = "viral-radar"
YT = "https://www.googleapis.com/youtube/v3"
FORMATS = {
    "pov": r"\bpov\b",
    "tutorial / how-to": r"\b(how to|nasıl|tarif|recipe|tutorial|adım adım)\b",
    "day in the life / vlog": r"\b(day in (the|my) life|vlog|bir günüm|günlük)\b",
    "asmr / satisfying": r"\b(asmr|satisfying)\b",
    "review / taste test": r"\b(review|deniyorum|tried|taste test|test ettim|inceleme)\b",
    "versus / comparison": r"\b(vs\.?|versus|karşılaştır)\b",
    "myth / mistake": r"\b(myth|mistake|hata|yanlış|don't|yapmayın|stop)\b",
    "list / ranking": r"\b(top \d+|\d+ (things|ways|tips|şey|ipucu|yer))\b",
    "storytime": r"\b(storytime|story time|başıma gelen)\b",
}
DUR = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")


def seconds(iso: str) -> int:
    m = DUR.fullmatch(iso or "")
    if not m:
        return 0
    h, mi, s = (int(x or 0) for x in m.groups())
    return h * 3600 + mi * 60 + s


def classify_format(text: str) -> list[str]:
    t = text.lower()
    return [name for name, pat in FORMATS.items() if re.search(pat, t)]


# --------------------------------------------------------------------------- YouTube
def youtube(brand: Brand, cfg: dict, day: str, fx) -> list[dict]:
    rec = fixture(fx, "youtube")
    if rec is not None:
        return rec
    key = env("YOUTUBE_API_KEY")
    if not key:
        raise RuntimeError("YOUTUBE_API_KEY not set")
    since = (datetime.now(timezone.utc) - timedelta(hours=int(cfg.get("window_hours", 24)))).strftime("%Y-%m-%dT%H:%M:%SZ")
    ids: list[str] = []
    for topic in brand.ready(cfg.get("topics", [])):
        res = get_json(f"{YT}/search", params={
            "key": key, "part": "snippet", "type": "video", "videoDuration": "short", "order": "viewCount",
            "publishedAfter": since, "q": topic, "regionCode": brand.country,
            "relevanceLanguage": brand.language, "maxResults": int(cfg.get("per_topic", 15))})
        ids += [i["id"]["videoId"] for i in res.get("items", [])]
    ids = list(dict.fromkeys(ids))
    videos, channels = [], {}
    for i in range(0, len(ids), 50):
        res = get_json(f"{YT}/videos", params={"key": key, "part": "snippet,statistics,contentDetails",
                                               "id": ",".join(ids[i:i + 50])})
        videos += res.get("items", [])
    ch_ids = list({v["snippet"]["channelId"] for v in videos})
    for i in range(0, len(ch_ids), 50):
        res = get_json(f"{YT}/channels", params={"key": key, "part": "statistics,snippet", "id": ",".join(ch_ids[i:i + 50])})
        for c in res.get("items", []):
            channels[c["id"]] = c
    now = datetime.now(timezone.utc)
    out = []
    for v in videos:
        if seconds(v["contentDetails"].get("duration")) > 180:
            continue
        sn, st = v["snippet"], v.get("statistics", {})
        ch = channels.get(sn["channelId"], {})
        pub = datetime.fromisoformat(sn["publishedAt"].replace("Z", "+00:00"))
        hours = max((now - pub).total_seconds() / 3600, 1)
        views = int(st.get("viewCount", 0))
        out.append({
            "platform": "youtube_shorts", "account": ch.get("snippet", {}).get("title", sn["channelTitle"]),
            "followers": int(ch.get("statistics", {}).get("subscriberCount", 0) or 0) or None,
            "views": views, "views_per_hour": round(views / hours), "likes": int(st.get("likeCount", 0) or 0),
            "comments": int(st.get("commentCount", 0) or 0), "hook": sn["title"],
            "hashtags": re.findall(r"#(\w+)", sn.get("title", "") + " " + sn.get("description", "")),
            "sound": None, "url": f"https://www.youtube.com/shorts/{v['id']}", "published_at": sn["publishedAt"],
        })
    return out


# --------------------------------------------------------------------------- Apify (optional)
def _pick(d: dict, *paths, default=None):
    for p in paths:
        cur = d
        for k in p.split("."):
            cur = cur.get(k) if isinstance(cur, dict) else None
        if cur not in (None, ""):
            return cur
    return default


def apify(platform: str, actor_env: str, cfg: dict, fx) -> list[dict]:
    rec = fixture(fx, platform)
    if rec is None:
        token, actor = env("APIFY_TOKEN"), env(actor_env)
        if not (token and actor):
            raise RuntimeError(f"{platform}: APIFY_TOKEN / {actor_env} not set")
        tags = [t.lstrip("#") for t in cfg.get("hashtags", [])]
        payload = ({"hashtags": tags, "resultsPerPage": 30} if platform == "tiktok"
                   else {"hashtags": tags, "resultsLimit": 30, "resultsType": "reels"})
        rec = post_json(f"https://api.apify.com/v2/acts/{actor.replace('/', '~')}/run-sync-get-dataset-items",
                        headers={"Authorization": f"Bearer {token}"}, json=payload, timeout=300)
    out = []
    for it in rec:
        views = int(_pick(it, "playCount", "videoPlayCount", "videoViewCount", "viewCount", default=0) or 0)
        text = _pick(it, "text", "caption", "desc", default="") or ""
        out.append({
            "platform": "tiktok" if platform == "tiktok" else "instagram_reels",
            "account": _pick(it, "authorMeta.name", "ownerUsername", "author.uniqueId", default="?"),
            "followers": _pick(it, "authorMeta.fans", "ownerFollowersCount", "author.followerCount"),
            "views": views, "views_per_hour": None, "likes": _pick(it, "diggCount", "likesCount", default=0),
            "comments": _pick(it, "commentCount", "commentsCount", default=0),
            "hook": text.split("\n")[0][:200], "hashtags": re.findall(r"#(\w+)", text),
            "sound": _pick(it, "musicMeta.musicName", "musicInfo.song_name", "musicInfo.title"),
            "url": _pick(it, "webVideoUrl", "url", default=""), "published_at": _pick(it, "createTimeISO", "timestamp"),
        })
    return out


# --------------------------------------------------------------------------- entry
def collect(brand: Brand, day: str, fx):
    cfg = brand.module(MODULE)
    warnings, items = [], []
    sources = {"youtube_shorts": lambda: youtube(brand, cfg, day, fx)}
    if cfg.get("tiktok_via_apify"):
        sources["tiktok"] = lambda: apify("tiktok", "APIFY_TIKTOK_ACTOR", cfg, fx)
    if cfg.get("instagram_via_apify"):
        sources["instagram_reels"] = lambda: apify("instagram", "APIFY_INSTAGRAM_ACTOR", cfg, fx)
    for name, fn in sources.items():
        try:
            items += fn()
        except Exception as exc:  # noqa: BLE001
            warnings.append(f"{name} skipped: {exc}")

    ranked = igkit.rank_videos([{**i, "median": None} for i in items if i["views"] and i["hook"]]) or {}
    by_url = {i["url"]: i for i in items}
    top = []
    for r in (ranked.get("reels") or sorted(items, key=lambda x: -x["views"]))[: int(cfg.get("top_n", 12))]:
        base = by_url.get(r.get("url"), r)
        top.append({**base, "outlier_multiple": r.get("outlier"), "hook_formula": r.get("formula"),
                    "hook_score": r.get("hook_score"), "formats": classify_format(base["hook"])})
    formats = Counter(f for i in items for f in classify_format(i["hook"]))
    sounds = Counter(i["sound"] for i in items if i.get("sound"))
    tags = Counter(t.lower() for i in items for t in i.get("hashtags", []))
    if brand.language != "en":
        warnings.append("hook_score heuristics are English-tuned; treat scores on non-English hooks as rough")
    return {
        "videos_scanned": len(items),
        "platforms": sorted({i["platform"] for i in items}),
        "top_videos": top,
        "top_hook_formulas": ranked.get("top_formulas", []),
        "formats": formats.most_common(8),
        "sounds": sounds.most_common(8),
        "hashtags": tags.most_common(15),
        "manual_links": {
            "tiktok_creative_center": f"https://ads.tiktok.com/business/creativecenter/inspiration/popular/hashtag/pc/en?region={brand.country}",
            "instagram_reels_trends": "https://www.instagram.com/reels/",
        },
    }, warnings


if __name__ == "__main__":
    raise SystemExit(run_module(MODULE, __doc__.splitlines()[0], collect))
