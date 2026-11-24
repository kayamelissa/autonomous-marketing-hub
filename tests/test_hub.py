import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIX = ROOT / "tests" / "fixtures" / "demo"

from hub import igkit  # noqa: E402
from hub.config import load_brand  # noqa: E402
from hub.text import first_position, fold  # noqa: E402


def mod(name):
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), ROOT / "modules" / name / "main.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


seo, viral, geo, spy, rep = (mod(n) for n in
                             ["seo-hunter", "viral-radar", "ai-visibility-geo", "competitor-spy", "content-repurposer"])


# ----------------------------------------------------------------- text
def test_fold_is_turkish_aware():
    assert fold("GÖÇMENLİK İşlemleri") == "gocmenlik islemleri"
    assert first_position("Önerim BOYER hukuk", ["Boyer Hukuk"]) == 7
    assert first_position("Boyerlaw değil", ["Boyer"]) is None  # whole-word only


# ----------------------------------------------------------------- ai-visibility-geo
def test_answer_ranking_and_citations():
    brand = load_brand("boyer-law-firm")
    r = geo.analyse_answer("Önce Gozel Law Firm, sonra Boyer Law Firm ve Alaz Law.",
                           ["https://www.floridaturkavukat.com/", "https://www.avvo.com/x"], brand)
    assert r["mentioned"] and r["rank"] == 2
    assert r["brands_ranked"][:3] == ["Gozel Law Firm", "Boyer Hukuk Bürosu", "Alaz Law"]
    assert r["own_domain_cited"] and "avvo.com" in r["cited_domains"]


def test_alias_catches_turkish_firm_name():
    brand = load_brand("boyer-law-firm")
    r = geo.analyse_answer("Sema Yıldırım aile hukukunda; Boyer Hukuk Bürosu ise E-2'de.", [], brand)
    assert r["brands_ranked"] == ["Law Offices of Sema Yildirim", "Boyer Hukuk Bürosu"]


def test_robots_blocked_bots():
    robots = "User-agent: *\nAllow: /\n\nUser-agent: GPTBot\nDisallow: /\n"
    assert geo.blocked_bots(robots) == ["GPTBot"]


def test_geo_deltas():
    prev = {"results": [{"engine": "openai", "prompt": "q", "mentioned": False}]}
    now = [{"engine": "openai", "prompt": "q", "mentioned": True}]
    assert geo.deltas(now, prev)["won"] == ["openai: q"]


# ----------------------------------------------------------------- seo-hunter
def test_quick_wins_and_gaps():
    rows = json.loads((FIX / "gsc.json").read_text())
    wins = seo.quick_wins(rows, {"quick_win_positions": [4, 20], "quick_win_min_impressions": 15})
    assert [w["query"] for w in wins] == ["e2 vizesi şartları", "amerikada boşanma türkiyede geçerli mi"]
    pages = json.loads((FIX / "site.json").read_text())
    assert seo.content_gaps(["green card çekilişi 2027", "e2 yatırımcı vizesi"], pages) == ["green card çekilişi 2027"]


def test_audit_flags_thin_meta_and_missing_schema():
    pages = json.loads((FIX / "site.json").read_text())
    issues = {i["url"]: i["issues"] for i in seo.audit(pages)}
    e2 = "https://floridaturkavukat.com/avukatlik-alanlari/amerika-gocmenlik-avukati/yatirim-vizesi/e-2-yatirimci-vize/"
    assert any("meta description" in x for x in issues[e2])
    assert any("JSON-LD" in x for x in issues["https://floridaturkavukat.com/uluslararasi-bosanma-avukati-boyer-hukuk-burosu/"])


# ----------------------------------------------------------------- competitor-spy
def test_page_text_and_promo():
    lines = spy.page_text("<p>Kış menüsü</p><script>x=1</script><p>Latte'lerde %20 indirim</p>")
    assert lines == ["Kış menüsü", "Latte'lerde %20 indirim"]
    assert spy.PROMO.search(lines[1]) and not spy.PROMO.search(lines[0])


# ----------------------------------------------------------------- instagram-agent-skill toolkit
def test_igkit_ranks_by_outlier_not_views():
    ranked = igkit.rank_videos([
        {"account": "big", "followers": 2_000_000, "median": None, "views": 400_000, "hook": "Big account day"},
        {"account": "small", "followers": 4_000, "median": None, "views": 100_000, "hook": "Stop doing this on your visa form"},
    ])
    assert ranked["reels"][0]["account"] == "small"


def test_humanize_strips_machine_tells():
    clean, _ = igkit.humanize("Bu harika​ — gerçekten")
    assert "​" not in clean and "—" not in clean


# ----------------------------------------------------------------- content-repurposer
def test_briefing_with_llm_scores_english_hooks(monkeypatch, tmp_path):
    brand = load_brand("boyer-law-firm")
    brand.raw["language"] = "en"  # hook scores are shown for English brands only
    outputs = {"viral-radar": {"warnings": [], "top_videos": [], "videos_scanned": 0, "platforms": []}}
    fake = "## 📝 Ready for your approval\n- **Reel**\n  Hook: I lost $18,000 on one missing contract\n\n## 🎨 Only you can decide\n- A?"
    monkeypatch.setattr(rep.llm, "complete", lambda *a, **k: fake)
    md = rep.build(brand, "2026-11-24", outputs)
    assert "hook score" in md and "Ready for your approval" in md


def test_offline_pipeline(tmp_path):
    for slug in ("boyer-law-firm",):
        rc = subprocess.call([sys.executable, "-m", "hub.run_all", "--brand", slug, "--fixtures", str(FIX),
                              "--no-send", "--date", "2099-01-01"], cwd=ROOT,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        assert rc == 0
        report = ROOT / "reports" / slug / "2099-01-01.md"
        assert report.exists() and report.read_text().startswith("# ")
        report.unlink()
    import shutil

    for slug in ("boyer-law-firm",):
        shutil.rmtree(ROOT / "data" / slug / "2099-01-01", ignore_errors=True)


# ----------------------------------------------------------------- security
SECRET = re.compile(r"(sk-[A-Za-z0-9]{20,}|sk-ant-[A-Za-z0-9-]{20,}|AIza[0-9A-Za-z_-]{30,}|xox[bpa]-[0-9A-Za-z-]{10,}"
                    r"|hooks\.slack\.com/services/T[A-Z0-9]+|ghp_[A-Za-z0-9]{30,}|-----BEGIN (RSA |EC )?PRIVATE KEY)")


@pytest.mark.parametrize("path", [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts
                                  and p.suffix in {".py", ".yaml", ".yml", ".md", ".json", ".txt", ".example"}])
def test_no_hardcoded_secrets(path):
    assert not SECRET.search(path.read_text(encoding="utf-8", errors="ignore")), path


def test_turkish_briefing_skips_hook_scores(monkeypatch):
    brand = load_brand("boyer-law-firm")
    fake = "## 📝 Onayına hazır taslaklar\n- Hook: Green Card mülakatında bu soruya dikkat\n## 🎨 Sadece senin kararın\n- ?"
    monkeypatch.setattr(rep.llm, "complete", lambda *a, **k: fake)
    md = rep.build(brand, "2026-11-24", {"viral-radar": {"warnings": [], "top_videos": []}})
    assert "hook score" not in md and "Onayına hazır" in md


def test_brand_profile_has_no_placeholders():
    assert load_brand("boyer-law-firm").todo_fields() == []
