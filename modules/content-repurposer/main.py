"""content-repurposer — turns the day's intelligence into the 08:30 briefing.

Reads every module's JSON for the day, passes a compact digest through one LLM
call with the brand's voice + compliance rules, and produces a briefing built
around the marketing manager's time:

  1. Done automatically       — nothing to do
  2. Ready for your approval  — drafts you only need to say yes to
  3. Only you can decide      — max 3 creative calls

Post-processing uses the instagram-agent-skill tools: every Reel hook
gets a hook score (English brands only; the heuristics are English-tuned) and the whole draft is passed through ``humanize`` (strips
invisible characters, em dashes and stock AI phrasing).

Without an LLM key the briefing still renders from a deterministic template.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from hub import igkit, llm, notify  # noqa: E402
from hub.config import load_brand  # noqa: E402
from hub.storage import read_output, write_report  # noqa: E402

MODULES = ["seo-hunter", "viral-radar", "ai-visibility-geo", "competitor-spy"]
PROMPT_PATH = Path(__file__).with_name("prompt.md")
L = {
    "tr": {"title": "Günlük Pazarlama Brifingi", "done": "✅ Otomatik yapıldı",
           "approve": "📝 Onayına hazır taslaklar", "decide": "🎨 Sadece senin kararın",
           "data": "📊 Veriler", "warn": "⚠️ Sistem notları", "saved": "Bu rapor bugün tahminen {m} dk elle çalışma yerine geçti.",
           "nollm": "LLM anahtarı tanımlı değil: taslak metinler yerine kurala dayalı aksiyon listesi gösteriliyor."},
    "en": {"title": "Daily Marketing Briefing", "done": "✅ Done automatically",
           "approve": "📝 Ready for your approval", "decide": "🎨 Only you can decide",
           "data": "📊 Data", "warn": "⚠️ System notes", "saved": "This briefing replaced an estimated {m} min of manual work today.",
           "nollm": "No LLM key configured: showing a rule-based action list instead of written drafts."},
}


def did_work(module: str, o: dict) -> bool:
    """True when a collector actually gathered data (drives the time-saved line)."""
    return bool({
        "seo-hunter": o.get("all_suggestions") or o.get("pages_checked") or o.get("gsc_totals_28d"),
        "viral-radar": o.get("videos_scanned"),
        "ai-visibility-geo": [r for r in o.get("results", []) if "error" not in r],
        "competitor-spy": o.get("reviews") or any(p.get("status", "").startswith(("changed", "no change", "baseline"))
                                                  for c in o.get("competitors", []) for p in c.get("pages", [])),
    }.get(module))


# --------------------------------------------------------------------------- digest
def digest(outputs: dict[str, dict]) -> dict:
    """Trim module outputs to what the LLM needs (keeps the prompt small)."""
    d: dict = {}
    if s := outputs.get("seo-hunter"):
        d["seo"] = {k: s.get(k) for k in ("gsc_totals_28d", "quick_wins", "new_suggestions",
                                          "content_gaps", "trending", "site_audit")}
        d["seo"]["quick_wins"] = (s.get("quick_wins") or [])[:10]
        d["seo"]["site_audit"] = (s.get("site_audit") or [])[:8]
    if v := outputs.get("viral-radar"):
        d["viral"] = {"top_videos": [{k: x.get(k) for k in ("platform", "account", "views", "outlier_multiple",
                                                            "hook", "hook_formula", "formats", "sound", "url")}
                                     for x in (v.get("top_videos") or [])[:8]],
                      "formats": v.get("formats"), "sounds": v.get("sounds"), "hashtags": (v.get("hashtags") or [])[:10],
                      "top_hook_formulas": v.get("top_hook_formulas")}
    if a := outputs.get("ai-visibility-geo"):
        d["ai"] = {"summary": a.get("summary"), "delta": a.get("delta_vs_previous"),
                   "site_hygiene": a.get("site_hygiene"),
                   "results": [{k: r.get(k) for k in ("engine", "prompt", "mentioned", "rank", "brands_ranked",
                                                      "cited_domains", "own_domain_cited")}
                               for r in a.get("results", []) if "error" not in r][:40]}
    if c := outputs.get("competitor-spy"):
        d["competitors"] = {"review_gap": c.get("review_gap"), "reviews": c.get("reviews"),
                            "changes": [{"competitor": x["name"], **p} for x in c.get("competitors", [])
                                        for p in x.get("pages", []) if p.get("status") == "changed"][:10],
                            "ads": {x["name"]: x["ads"] for x in c.get("competitors", []) if x.get("ads")}}
    return d


def automatic_lines(outputs: dict[str, dict], lang: str) -> list[str]:
    tr = lang == "tr"
    lines = []
    if s := outputs.get("seo-hunter"):
        gsc = bool(s.get("gsc_totals_28d"))
        lines.append((f"{len(s.get('all_suggestions', []))} arama önerisi ve {s.get('pages_checked', 0)} sayfa tarandı"
                      + (", Search Console verisi çekildi" if gsc else "") if tr else
                      f"Scanned {len(s.get('all_suggestions', []))} search suggestions and {s.get('pages_checked', 0)} pages"
                      + (", pulled Search Console" if gsc else "")))
    if v := outputs.get("viral-radar"):
        lines.append((f"{v.get('videos_scanned', 0)} kısa video ({', '.join(v.get('platforms', [])) or '-'}) hesabın kendi ortalamasına göre sıralandı"
                      if tr else f"Ranked {v.get('videos_scanned', 0)} short videos ({', '.join(v.get('platforms', [])) or '-'}) by multiple over account baseline"))
    if a := outputs.get("ai-visibility-geo"):
        n = len([r for r in a.get("results", []) if "error" not in r])
        lines.append(f"{n} AI cevabı test edildi" if tr else f"Tested {n} AI answers")
    if c := outputs.get("competitor-spy"):
        pages = sum(len(x.get("pages", [])) for x in c.get("competitors", []))
        lines.append((f"{len(c.get('competitors', []))} rakibin {pages} sayfası ve yorum sayıları kontrol edildi" if tr
                      else f"Checked {pages} pages and review counts for {len(c.get('competitors', []))} competitors"))
    return lines


# --------------------------------------------------------------------------- rule-based fallback
def fallback_actions(outputs: dict[str, dict], lang: str, t: dict, brand_review_ask: str | None = None) -> str:
    """Approval queue + decisions without an LLM: deterministic, data-only."""
    tr = lang == "tr"
    todo, decide = [], []
    s = outputs.get("seo-hunter") or {}
    for q in (s.get("quick_wins") or [])[:2]:
        todo.append((f"**Sayfa güncelle** · \"{q['query']}\" {q['position']}. sırada, {q['impressions']} gösterim. "
                     f"`{q['page'].split('//')[-1]}` başlığına ve ilk paragrafına bu ifadeyi ekle (~15 dk)") if tr else
                    (f"**Update page** · \"{q['query']}\" ranks {q['position']} with {q['impressions']} impressions. "
                     f"Add the phrase to the title and first paragraph of `{q['page'].split('//')[-1]}` (~15 min)"))
    for g in (s.get("content_gaps") or [])[:2]:
        todo.append((f"**Yeni içerik** · \"{g}\" aranıyor ama sitede karşılığı yok: SSS maddesi ya da kısa sayfa (~30 dk)") if tr else
                    (f"**New content** · \"{g}\" has demand but no matching page: add an FAQ or short page (~30 min)"))
    a = outputs.get("ai-visibility-geo") or {}
    missing = [r for r in a.get("results", []) if "error" not in r and not r.get("mentioned")]
    if missing:
        r = missing[0]
        doms = ", ".join(r.get("cited_domains", [])[:3]) or "—"
        todo.append((f"**GEO düzeltmesi** · {r['engine']} \"{r['prompt']}\" cevabında yokuz. Bu soruyu ilgili sayfada "
                     f"birebir SSS olarak cevapla; cevabın dayandığı kaynaklar: {doms} (~20 dk)") if tr else
                    (f"**GEO fix** · Missing from {r['engine']} for \"{r['prompt']}\". Answer this exact question as an FAQ "
                     f"on the matching page; sources it relied on: {doms} (~20 min)"))
    c = outputs.get("competitor-spy") or {}
    for comp in c.get("competitors", []):
        for p in comp.get("pages", []):
            promo = p.get("price_or_promo_added") or p.get("price_or_promo_current") or []
            if promo:
                decide.append((f"**{comp['name']}**: \"{promo[0]}\". Karşılık verecek miyiz? (a) benzer kampanya "
                               f"(b) farklılaşan teklif (c) beklemek") if tr else
                              (f"**{comp['name']}**: \"{promo[0]}\". Respond? (a) match (b) differentiate (c) wait"))
    if gap := c.get("review_gap"):
        ask = brand_review_ask or ("Memnun müşterilere kısa bir Google yorum bağlantısı gönder" if tr
                                   else "Send happy clients a short Google review link")
        todo.append((f"**Yorum toplama** · {gap['our_reviews']} yorumumuz var, rakiplerin ortancası {gap['competitor_median']} "
                     f"(lider: {gap['leader']}). {ask} (~10 dk)") if tr else
                    (f"**Review drive** · We have {gap['our_reviews']} reviews vs competitor median {gap['competitor_median']} "
                     f"(leader: {gap['leader']}). {ask} (~10 min)"))
    v = outputs.get("viral-radar") or {}
    if v.get("top_videos"):
        x = v["top_videos"][0]
        decide.append((f"Bu haftanın Reel konsepti: \"{x['hook']}\" ({x.get('outlier_multiple')}x) formatını kendi "
                       f"hizmetimize uyarlayalım mı? `/ig-reel` ile senaryo 2 dakikada çıkar") if tr else
                      (f"Reel concept this week: adapt \"{x['hook']}\" ({x.get('outlier_multiple')}x) to our offer? "
                       f"`/ig-reel` drafts the script in two minutes"))
    out = [f"## {t['approve']}", *([f"- {x}" for x in todo] or ["- —"]), "", f"## {t['decide']}",
           *([f"- {x}" for x in decide[:3]] or ["- —"])]
    return "\n".join(out)


# --------------------------------------------------------------------------- rendering
def data_tables(outputs: dict[str, dict], lang: str) -> str:
    tr = lang == "tr"
    md: list[str] = []
    a = outputs.get("ai-visibility-geo")
    if a and a.get("summary", {}).get("by_engine"):
        md += ["", "**AI görünürlüğü**" if tr else "**AI visibility**", "",
               "| Motor | Görünme oranı | Ort. sıra |" if tr else "| Engine | Share of voice | Avg rank |", "|---|---|---|"]
        for e, s in a["summary"]["by_engine"].items():
            md.append(f"| {e} | {int(s['share_of_voice'] * 100)}% ({s['mentioned']}/{s['prompts']}) | {s['avg_rank'] or '—'} |")
    s = outputs.get("seo-hunter")
    if s and s.get("quick_wins"):
        md += ["", "**Hızlı kazanımlar (Search Console, 4–20. sıra)**" if tr else "**Quick wins (Search Console, positions 4–20)**", "",
               "| Sorgu | Gösterim | Sıra | Sayfa |" if tr else "| Query | Impressions | Position | Page |", "|---|---|---|---|"]
        for q in s["quick_wins"][:8]:
            md.append(f"| {q['query']} | {q['impressions']} | {q['position']} | {q['page'].split('//')[-1]} |")
    c = outputs.get("competitor-spy")
    if c and c.get("reviews"):
        md += ["", "**Google yorumları**" if tr else "**Google reviews**", "",
               "| İşletme | Puan | Yorum |" if tr else "| Business | Rating | Reviews |", "|---|---|---|"]
        for r in sorted(c["reviews"], key=lambda r: -(r.get("reviews") or 0)):
            name = f"**{r['name']}**" if r.get("is_us") else r["name"]
            md.append(f"| {name} | {r.get('rating') or '—'} | {r.get('reviews') or '—'} |")
    v = outputs.get("viral-radar")
    if v and v.get("top_videos"):
        md += ["", "**Viral kısa videolar (hesap ortalamasının kaç katı)**" if tr else "**Viral short videos (multiple over account baseline)**", "",
               "| Kat | Platform | Hook | Format |" if tr else "| Multiple | Platform | Hook | Format |", "|---|---|---|---|"]
        for x in v["top_videos"][:6]:
            mult = f"{x['outlier_multiple']}x" if x.get("outlier_multiple") else "—"
            md.append(f"| {mult} | {x['platform']} | [{x['hook'][:70]}]({x['url']}) | {', '.join(x.get('formats') or []) or x.get('hook_formula') or '—'} |")
    return "\n".join(md)


def score_hooks(md: str) -> str:
    """Append instagram-agent-skill's hookscore next to every 'Hook:' line the LLM wrote."""
    def repl(m):
        hook = m.group(2).strip().strip('"“”')
        s = igkit.score_hook(hook)
        return f"{m.group(0)}  _(hook score {s['score']:.0f}/100, {s['verdict']})_" if s else m.group(0)

    return re.sub(r"(?im)^(\s*[-*]?\s*\**hook\**\s*:\**\s*)(.+)$", repl, md)


def build(brand, day: str, outputs: dict[str, dict]) -> str:
    lang = "tr" if brand.language == "tr" else "en"
    t = L[lang]
    warnings, seen = [], set()
    for m, o in outputs.items():
        for w in o.get("warnings", []):
            key = w if not w.startswith("brand.yaml still has TODO") else "todo"
            if key not in seen:
                seen.add(key)
                warnings.append(f"{m}: {w[:180]}")
    worked = [m for m, o in outputs.items() if did_work(m, o)]
    minutes = sum(int(brand.module(m).get("manual_minutes", 0)) for m in worked)
    if worked:
        minutes += int(brand.module("content-repurposer").get("manual_minutes", 0))

    system = PROMPT_PATH.read_text(encoding="utf-8")
    brief_ctx = {k: brand.raw.get(k) for k in ("name", "description", "city", "language", "voice", "compliance", "offers")}
    prompt = (f"BRAND:\n{json.dumps(brief_ctx, ensure_ascii=False, indent=1)}\n\nDATE: {day}\n\n"
              f"SECTION HEADINGS (use exactly): ## {t['approve']}\n## {t['decide']}\n\n"
              f"DATA:\n{json.dumps(digest(outputs), ensure_ascii=False)}")
    body = llm.complete(prompt, system=system)

    parts = [f"# {t['title']} — {brand.name} · {day}", ""]
    parts += [f"## {t['done']}", *[f"- {x}" for x in automatic_lines(outputs, lang)], ""]
    if body:
        body, _ = igkit.humanize(body)
        # hookscore heuristics are English-tuned; on other languages they mislead
        parts += [score_hooks(body.strip()) if brand.language == "en" else body.strip(), ""]
    else:
        parts += [f"> {t['nollm']}", "", fallback_actions(outputs, lang, t, brand.raw.get("review_ask")), ""]
    parts += [f"## {t['data']}", data_tables(outputs, lang), ""]
    if warnings:
        parts += [f"<details><summary>{t['warn']} ({len(warnings)})</summary>", "",
                  *[f"- {w}" for w in warnings], "", "</details>", ""]
    if minutes:
        parts.append(f"_{t['saved'].format(m=minutes)}_")
    return "\n".join(parts).rstrip() + "\n"


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--brand", required=True)
    p.add_argument("--date")
    p.add_argument("--no-send", action="store_true", help="write the report but do not post to Slack/e-mail")
    p.add_argument("--report-url", help="link added to Slack (e.g. the Actions run)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s [content-repurposer] %(message)s")
    brand = load_brand(args.brand)
    day = args.date or brand.today()
    outputs = {m: o for m in MODULES if (o := read_output(brand.slug, day, m))}
    if not outputs:
        logging.error("No module output for %s on %s — run the collectors first.", brand.slug, day)
        return 1
    md = build(brand, day, outputs)
    path = write_report(brand.slug, day, md)
    logging.info("Briefing written to %s", path)
    if not args.no_send:
        title = f"{L['tr' if brand.language == 'tr' else 'en']['title']} — {brand.name} · {day}"
        notify.send_slack(brand, title, md, args.report_url)
        notify.send_email(brand, title, md)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
