"""ai-visibility-geo — does AI recommend us? Daily GEO check.

Asks a fixed prompt set to search-grounded AI engines through their official
APIs and records, per engine and prompt: whether the brand is mentioned, its
rank among tracked brands, which competitors appear, and which domains the
answer cites.

Engines (each enabled when its key exists)
  openai      Responses API + web_search tool        OPENAI_API_KEY
  gemini      generateContent + google_search tool   GEMINI_API_KEY
  perplexity  Sonar chat completions                 PERPLEXITY_API_KEY
  claude      Messages API + web_search tool         ANTHROPIC_API_KEY

Caveat: API answers are close to, but not identical with, what a logged-in
consumer sees in ChatGPT / Gemini apps (personalisation, location, model
version). Use the trend over days, not a single answer.

Also checks GEO hygiene on the brand's site: llms.txt present, AI crawlers
allowed in robots.txt.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hub.cli import fixture, run_module  # noqa: E402
from hub.config import Brand, env  # noqa: E402
from hub.http import post_json, session  # noqa: E402
from hub.storage import previous_output  # noqa: E402
from hub.text import domain_of, first_position  # noqa: E402

MODULE = "ai-visibility-geo"
AI_BOTS = ["OAI-SearchBot", "ChatGPT-User", "GPTBot", "PerplexityBot", "Claude-SearchBot",
           "ClaudeBot", "Google-Extended", "Bingbot"]


# --------------------------------------------------------------------------- engines
def ask_openai(q: str, brand: Brand) -> dict:
    data = post_json("https://api.openai.com/v1/responses",
                     headers={"Authorization": f"Bearer {env('OPENAI_API_KEY')}"},
                     json={"model": env("GEO_OPENAI_MODEL", "gpt-4.1"), "input": q,
                           "tools": [{"type": "web_search", "user_location": _loc(brand)}]})
    text, cites = [], []
    for item in data.get("output", []):
        for c in item.get("content", []) or []:
            if c.get("type") == "output_text":
                text.append(c.get("text", ""))
                cites += [a["url"] for a in c.get("annotations", []) if a.get("type") == "url_citation"]
    return {"answer": "".join(text), "citations": cites}


def ask_gemini(q: str, brand: Brand) -> dict:
    model = env("GEO_GEMINI_MODEL", "gemini-2.5-flash")
    data = post_json(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                     headers={"x-goog-api-key": env("GEMINI_API_KEY")},
                     json={"contents": [{"role": "user", "parts": [{"text": q}]}],
                           "tools": [{"google_search": {}}]})
    cand = (data.get("candidates") or [{}])[0]
    text = "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []))
    chunks = cand.get("groundingMetadata", {}).get("groundingChunks", [])
    # Gemini returns redirect URIs; the chunk title is the source domain
    cites = [c["web"].get("title") or c["web"].get("uri") for c in chunks if "web" in c]
    return {"answer": text, "citations": cites}


def ask_perplexity(q: str, brand: Brand) -> dict:
    data = post_json("https://api.perplexity.ai/chat/completions",
                     headers={"Authorization": f"Bearer {env('PERPLEXITY_API_KEY')}"},
                     json={"model": env("GEO_PERPLEXITY_MODEL", "sonar"),
                           "messages": [{"role": "user", "content": q}],
                           "web_search_options": {"user_location": {"country": brand.country}}})
    text = data["choices"][0]["message"]["content"]
    cites = data.get("citations") or [r.get("url") for r in data.get("search_results", [])]
    return {"answer": text, "citations": [c for c in cites if c]}


def ask_claude(q: str, brand: Brand) -> dict:
    data = post_json("https://api.anthropic.com/v1/messages",
                     headers={"x-api-key": env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"},
                     json={"model": env("GEO_CLAUDE_MODEL", "claude-sonnet-5-5"), "max_tokens": 1500,
                           "messages": [{"role": "user", "content": q}],
                           "tools": [{"type": "web_search_20250305", "name": "web_search", "max_uses": 4,
                                      "user_location": _loc(brand)}]})
    text, cites = [], []
    for b in data.get("content", []):
        if b.get("type") == "text":
            text.append(b.get("text", ""))
            cites += [c.get("url") for c in b.get("citations", []) or [] if c.get("url")]
        elif b.get("type") == "web_search_tool_result" and isinstance(b.get("content"), list):
            cites += [r.get("url") for r in b["content"] if r.get("url")]
    return {"answer": "".join(text), "citations": list(dict.fromkeys(cites))}


ENGINES = {"openai": ("OPENAI_API_KEY", ask_openai), "gemini": ("GEMINI_API_KEY", ask_gemini),
           "perplexity": ("PERPLEXITY_API_KEY", ask_perplexity), "claude": ("ANTHROPIC_API_KEY", ask_claude)}


def _loc(brand: Brand) -> dict:
    loc = {"type": "approximate", "country": brand.country}
    if brand.raw.get("city"):
        loc["city"] = brand.raw["city"]
    return loc


# --------------------------------------------------------------------------- analysis
def analyse_answer(answer: str, citations: list[str], brand: Brand) -> dict:
    tracked = {brand.name: brand.aliases}
    for c in brand.competitors:
        tracked[c["name"]] = [c["name"], *c.get("aliases", [])]
    positions = {n: first_position(answer, al) for n, al in tracked.items()}
    order = sorted((p, n) for n, p in positions.items() if p is not None)
    ranks = {n: i + 1 for i, (_, n) in enumerate(order)}
    domains = [domain_of(c) if c.startswith("http") else c.lower() for c in citations]
    pos = positions[brand.name]
    snippet = None
    if pos is not None:
        snippet = re.sub(r"\s+", " ", answer[max(0, pos - 60): pos + 160]).strip()
    own = brand.domain_ready and any(brand.domain in d for d in domains)
    return {
        "mentioned": pos is not None,
        "rank": ranks.get(brand.name),
        "brands_ranked": [n for _, n in order],
        "competitors_mentioned": [n for _, n in order if n != brand.name],
        "cited_domains": list(dict.fromkeys(domains)),
        "own_domain_cited": bool(own),
        "snippet": snippet,
    }


def summarise(results: list[dict]) -> dict:
    by_engine: dict[str, dict] = {}
    for r in results:
        if "error" in r:
            continue
        e = by_engine.setdefault(r["engine"], {"prompts": 0, "mentioned": 0, "ranks": []})
        e["prompts"] += 1
        e["mentioned"] += r["mentioned"]
        if r["rank"]:
            e["ranks"].append(r["rank"])
    for e in by_engine.values():
        e["share_of_voice"] = round(e["mentioned"] / e["prompts"], 2) if e["prompts"] else 0
        e["avg_rank"] = round(sum(e["ranks"]) / len(e["ranks"]), 1) if e["ranks"] else None
        del e["ranks"]
    comp: dict[str, int] = {}
    doms: dict[str, int] = {}
    for r in results:
        for c in r.get("competitors_mentioned", []):
            comp[c] = comp.get(c, 0) + 1
        for d in r.get("cited_domains", []):
            doms[d] = doms.get(d, 0) + 1
    return {"by_engine": by_engine,
            "competitor_mentions": sorted(comp.items(), key=lambda kv: -kv[1]),
            "top_cited_domains": sorted(doms.items(), key=lambda kv: -kv[1])[:15]}


def deltas(results: list[dict], prev: dict | None) -> dict:
    if not prev:
        return {"won": [], "lost": []}
    key = lambda r: (r["engine"], r["prompt"])  # noqa: E731
    before = {key(r): r.get("mentioned") for r in prev.get("results", []) if "error" not in r}
    won, lost = [], []
    for r in results:
        if "error" in r or key(r) not in before:
            continue
        if r["mentioned"] and not before[key(r)]:
            won.append(f"{r['engine']}: {r['prompt']}")
        elif not r["mentioned"] and before[key(r)]:
            lost.append(f"{r['engine']}: {r['prompt']}")
    return {"won": won, "lost": lost}


def site_hygiene(brand: Brand, fx) -> dict:
    rec = fixture(fx, "site_hygiene")
    if rec is not None:
        return rec
    if not brand.domain_ready:
        return {}
    s = session()
    out = {}
    try:
        r = s.get(f"https://{brand.domain}/llms.txt", timeout=15)
        out["llms_txt"] = r.ok and len(r.text) > 50
        robots = s.get(f"https://{brand.domain}/robots.txt", timeout=15).text
        out["blocked_ai_bots"] = blocked_bots(robots)
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out


def blocked_bots(robots: str) -> list[str]:
    """Bots that are fully disallowed (``Disallow: /``) by a named or * group."""
    groups, agents, rules = [], [], []
    for raw in robots.splitlines():
        line = raw.split("#")[0].strip()
        if not line or ":" not in line:
            continue
        k, v = (x.strip() for x in line.split(":", 1))
        if k.lower() == "user-agent":
            if rules:
                groups.append((agents, rules))
                agents, rules = [], []
            agents.append(v.lower())
        elif k.lower() in ("allow", "disallow"):
            rules.append((k.lower(), v))
    if agents:
        groups.append((agents, rules))
    blocked = []
    for bot in AI_BOTS:
        named = [g for g in groups if bot.lower() in g[0]]
        group = named or [g for g in groups if "*" in g[0]]
        if any(("disallow", "/") in g[1] and ("allow", "/") not in g[1] for g in group):
            blocked.append(bot)
    return blocked


# --------------------------------------------------------------------------- entry
def collect(brand: Brand, day: str, fx):
    cfg = brand.module(MODULE)
    warnings, results = [], []
    recorded = fixture(fx, "ai_answers")  # {engine: {prompt: {answer, citations}}}
    engines = cfg.get("engines", list(ENGINES))
    active = [e for e in engines if (recorded and e in recorded) or (not recorded and env(ENGINES[e][0]))]
    for e in engines:
        if e not in active:
            warnings.append(f"{e} skipped: {ENGINES[e][0]} not set")
    for prompt in brand.ready(cfg.get("prompts", [])):
        for e in active:
            if recorded and prompt not in recorded.get(e, {}):
                continue
            try:
                res = recorded[e][prompt] if recorded else ENGINES[e][1](prompt, brand)
                results.append({"engine": e, "prompt": prompt, **analyse_answer(res["answer"], res["citations"], brand)})
            except Exception as exc:  # noqa: BLE001
                results.append({"engine": e, "prompt": prompt, "error": str(exc)[:300]})
    prev = previous_output(brand.slug, day, MODULE)
    return {"results": results, "summary": summarise(results), "delta_vs_previous": deltas(results, prev),
            "site_hygiene": site_hygiene(brand, fx)}, warnings


if __name__ == "__main__":
    raise SystemExit(run_module(MODULE, __doc__.splitlines()[0], collect))
