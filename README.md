# Autonomous Marketing Intelligence Hub

**Boyer Law Firm, P.L. · [floridaturkavukat.com](https://floridaturkavukat.com)**

Every weekday morning the marketing team gets a single briefing. It covers what
changed in search, what is trending in short video, whether AI assistants
recommend the firm, and what competitors just did. It ends with a queue of
finished drafts that only need a yes.

The routine runs itself. The team keeps its time for creative work.

[![Tests](https://github.com/kayamelissa/autonomous-marketing-hub/actions/workflows/tests.yml/badge.svg)](https://github.com/kayamelissa/autonomous-marketing-hub/actions/workflows/tests.yml)
![Python](https://img.shields.io/badge/python-3.11%2B-blue)

> 🇹🇷 **Kısaca:** Sistem her sabah beş işi kendisi yapar:
> - Türkçe arama talebini ve Search Console fırsatlarını tarar.
> - Göç, vize ve "Amerika'da yaşam" kısa video trendlerini çıkarır.
> - ChatGPT, Gemini, Perplexity ve Claude'un "Florida'da Türk avukat" gibi sorularda Boyer'i önerip önermediğini ölçer.
> - Gozel, Alaz, Yellow gibi rakip büroların sayfalarını izler.
> - Hepsini 08:30'da ekibe tek bir **Günlük Pazarlama Brifingi** olarak gönderir.
>
> Brifing üç bölümden oluşur: **otomatik yapılanlar**, **onayını bekleyen hazır
> taslaklar** (Florida Barosu reklam kurallarına uygun) ve **sadece senin
> vermen gereken yaratıcı kararlar**.

👉 **See a real example from 24 Nov 2026:** [`sample-daily-briefing.md`](sample-daily-briefing.md)

---

## Why

Turkish-speaking clients find a US lawyer the way everyone now does: they ask
Google, and more and more they ask an AI assistant. On 24 Nov 2026 Google AI Mode
gave these answers:

| Question (Turkish, US location) | Boyer |
|---|---|
| Florida E-2 yatırımcı vizesi Türkçe avukat | **#1** |
| Florida'da Türkçe konuşan boşanma avukatı | #2 |
| Florida'da Türk avukat | #4 |
| Amerika'da Türk avukat | #8 of 9 |
| Amerika'da Türk göçmenlik avukatı | **not mentioned** |

Checking this by hand every day, along with rankings, trends and competitors,
costs the marketing team about two hours each morning. The hub does it before
anyone logs in.

| Daily task | Manual | Hub |
|---|---|---|
| Search demand (TR + US Turkish speakers), rankings, content gaps | ~25 min | automatic |
| Short-video trend scouting (immigration, "life in America") | ~20 min | automatic |
| AI assistant checks (8 prompts × 4 engines) | ~30 min | automatic |
| Competitor firm sites, offers, reviews | ~25 min | automatic |
| Writing the briefing + first drafts | ~20 min | automatic, you approve |
| **Total** | **~2 h / day** | **~10 min review** |

**≈ 10 hours a week back for the marketing manager.** The estimates are the
`manual_minutes` values in [`brand.yaml`](brands/boyer-law-firm/brand.yaml). Each
briefing reports the time it saved that day, counting only the modules that
actually ran.

## How it works

```
                 ┌──────── brands/boyer-law-firm/brand.yaml ─────────┐
                 │ practice areas · 10 competitor firms · 8 AI prompts│
                 │ voice · Florida Bar advertising rules · env names  │
                 └─────────────────────────┬─────────────────────────┘
                                           │
  GitHub Actions cron ──► hub/run_all.py ──┤   each collector = own process;
  (weekdays 08:07 TRT)                     │   one failure never stops the run
                                           ▼
 ┌────────────────┐ ┌────────────────┐ ┌──────────────────┐ ┌────────────────┐
 │  seo-hunter    │ │  viral-radar   │ │ ai-visibility-geo│ │ competitor-spy │
 │ Search Console │ │ YouTube Shorts │ │ ChatGPT · Gemini │ │ site diffs     │
 │ autocomplete   │ │ (TikTok/Reels  │ │ Perplexity ·     │ │ offer & promo  │
 │ TR + US markets│ │  via adapter)  │ │ Claude (APIs w/  │ │ Google reviews │
 │ on-page audit  │ │ outlier ranking│ │ web search)      │ │ Meta Ad Library│
 └───────┬────────┘ └───────┬────────┘ └────────┬─────────┘ └───────┬────────┘
         └──────────────────┴─────────┬─────────┴───────────────────┘
                                      ▼
                     data/<brand>/<date>/<module>.json
                                      │
                                      ▼
                    ┌───────────────────────────────────┐
                    │        content-repurposer         │
                    │ one LLM pass: firm voice + Florida│
                    │ Bar rules → drafts + decisions    │
                    │ humanize (instagram-agent-skill)  │
                    └────────────────┬──────────────────┘
                                     ▼
        reports/<brand>/<date>.md ──► Slack · e-mail · Actions job summary
```

## The briefing

| Section | What's in it | Your effort |
|---|---|---|
| ✅ **Done automatically** | what was scanned and checked | none |
| 📝 **Ready for your approval** | finished drafts, each with a time estimate (see below) | read, say yes |
| 🎨 **Only you can decide** | at most 3 positioning or creative calls, each framed as options | think |
| 📊 **Data** | AI share of voice, quick-win queries, reviews vs competitors, viral videos | glance |

The approval queue can contain:
- Reel scripts built on today's winning formats.
- A page or FAQ brief for the best SEO opening.
- A GEO fix with the exact sentence to add.
- A compliance fix.
- A competitor response.

Every draft follows the firm's compliance rules from `brand.yaml`:
- Include the "Avukat Reklamı / Attorney Advertising" notice.
- Make no outcome promises.
- Never use "uzman" or "specialist". The only exception is Francis M. Boyer's Florida Bar board certification in International Law.
- Never imply Turkish-law services.

Without an LLM key the same sections are filled from rules (no written drafts),
so the briefing is never empty.

## Modules

Every module runs on its own (`python modules/<name>/main.py --brand boyer-law-firm`)
and writes one JSON file. It skips any source whose key is missing and names the
missing key in the briefing's system notes.

| Module | Answers | Sources |
|---|---|---|
| [`seo-hunter`](modules/seo-hunter/main.py) | Which queries are we nearly winning? What are Turkish speakers in Türkiye and the US starting to search? Which topics have no page? What's broken on-page? | Search Console API, Google autocomplete, Google Trends RSS, own sitemap |
| [`viral-radar`](modules/viral-radar/main.py) | Which short videos about visas, Green Cards and life in the US are beating their own account's baseline? Which hook formula and format do they use? | YouTube Data API v3; optional TikTok/Instagram adapters |
| [`ai-visibility-geo`](modules/ai-visibility-geo/main.py) | Do AI assistants recommend Boyer, at what rank, next to which firms, citing which sites? What did we win or lose since yesterday? Are AI crawlers allowed, does `llms.txt` exist? | OpenAI Responses + web search, Gemini + Google Search grounding, Perplexity Sonar, Claude + web search |
| [`competitor-spy`](modules/competitor-spy/main.py) | Which competitor changed offers ("ücretsiz ön görüşme"), fees or services? How do our reviews compare? | Page snapshots + diff, Google Places API, Meta Ad Library API |
| [`content-repurposer`](modules/content-repurposer/main.py) | What should the team ship today? | One LLM call (Anthropic, OpenAI or Gemini) + [`prompt.md`](modules/content-repurposer/prompt.md) |

## Setup

**1. Try it offline (no keys needed, 30 seconds)**

```bash
git clone https://github.com/kayamelissa/autonomous-marketing-hub.git
cd autonomous-marketing-hub
pip install -r requirements.txt
bash scripts/setup_skills.sh   # optional: Claude Code /ig-* skills + hook tools
python -m hub.run_all --brand boyer-law-firm --fixtures tests/fixtures/demo --no-send
cat reports/boyer-law-firm/*.md
```

**2. Run it for real locally**

```bash
cp .env.example .env      # fill in only the keys you have
python -m hub.run_all --brand boyer-law-firm --no-send
```

**3. Automate it in GitHub**

1. *Settings → Secrets and variables → Actions*: add the secrets from [`.env.example`](.env.example) that you use. At minimum, one LLM key and `SLACK_WEBHOOK_URL_BOYER`.
2. *Variables* (optional): `LLM_PROVIDER`, `LLM_MODEL`.
3. *Actions → Daily Marketing Hub → Run workflow* for a first run, then let the weekday schedule take over.

Where to get the keys:
- **Search Console:** create a service account in Google Cloud, enable the *Search Console API*, and add the service-account e-mail as a user on the `floridaturkavukat.com` property.
- **YouTube / Places:** API keys from the same Google Cloud project.
- **Slack:** an *Incoming Webhook* on the marketing channel.

**More sites or brands.** The engine is brand-agnostic. To run it for another site,
such as boyerlawfirm.com (EN) or the Spanish and French sites:
1. Copy `brands/boyer-law-firm/` to a new folder.
2. Edit the YAML.
3. Add a cron line to the workflow.

Each brand runs in its own job, with its own cached history and its own Slack
channel.

## Data sources & terms

| Source | Access | Note |
|---|---|---|
| Search Console, YouTube Data, Places, Meta Ad Library, OpenAI, Gemini, Perplexity, Anthropic | official APIs | subject to each provider's quotas and pricing |
| Google autocomplete, Google Trends RSS | public endpoints | lightweight, once a day |
| Competitor web pages | plain HTTP / optional Playwright | public pages only, honest User-Agent, once a day |
| TikTok, Instagram Reels | **off by default** | no official trends API; the Apify adapters are opt-in and their use is governed by those platforms' terms |
| Meta Ad Library | API returns non-political ads for EU/UK only | US gets direct Ad Library and Google Ads Transparency links |

AI answers via API are close to, but not identical with, what a signed-in user
sees in the consumer apps. Read the trend across days, not a single answer.

## Claude Code skills included

The hub builds on the MIT-licensed
[instagram-agent-skill](https://github.com/Jakeschincariol/instagram-agent-skill)
by Jake Schincariol. [`scripts/setup_skills.sh`](scripts/setup_skills.sh) fetches
it unmodified at a pinned commit (the pipeline also does this on first run). After
running it once, opening this repo in Claude Code gives you `/ig-reel`, `/ig-plan`, `/ig-caption`, `/ig-carousel`,
`/ig-viral`, `/ig-human` and more for turning a briefing item into a finished
post.

The pipeline also calls its Python tools directly:
- `swipe` ranks videos by their multiple over their own account's baseline.
- `humanize` cleans AI tells from every draft.
- `hookscore` is English-tuned, so it is applied only to English-language brands.

## Security

- No secrets in code or YAML. `brand.yaml` holds only env-var **names**. A test fails the build if anything that looks like an API key, Slack webhook or private key is committed.
- `data/` and `reports/` are gitignored. History is kept in `actions/cache`, and briefings go to Slack, e-mail and job artifacts, never to this public repo.
- Workflow permissions are `contents: read`. Manual-run inputs are validated before use.

## Project structure

```
.
├── .github/workflows/      daily-marketing-hub.yml · tests.yml
├── brands/boyer-law-firm/  brand.yaml
├── hub/                    config · storage · http · llm · notify · igkit · run_all
├── modules/
│   ├── seo-hunter/         main.py
│   ├── viral-radar/        main.py
│   ├── ai-visibility-geo/  main.py
│   ├── competitor-spy/     main.py
│   └── content-repurposer/ main.py · prompt.md
├── scripts/                setup_skills.sh (fetches instagram-agent-skill, MIT)
├── tests/                  test_hub.py · fixtures/demo/
├── sample-daily-briefing.md
└── .env.example
```

## Development

```bash
pip install -r requirements.txt pytest
bash scripts/setup_skills.sh
python -m pytest -q
```

## License

MIT for this project (see [LICENSE](LICENSE)).
instagram-agent-skill (fetched into `third_party/`) keeps its own MIT license and copyright.
