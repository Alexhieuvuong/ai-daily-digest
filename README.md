<div align="center">

# 📡 Bản tin tổng hợp — Personal Vietnamese News Digest

**A personal news agent that collects, de-duplicates, and summarizes the news in Vietnamese — four times a day, fully automated.**

Auto-collected · AI-curated & summarized · Importance scored · Runs on GitHub Actions (zero server)

[![Daily Digest](https://github.com/Alexhieuvuong/ai-daily-digest/actions/workflows/daily.yml/badge.svg)](https://github.com/Alexhieuvuong/ai-daily-digest/actions/workflows/daily.yml)
![GitHub last commit](https://img.shields.io/github/last-commit/Alexhieuvuong/ai-daily-digest)

</div>

---

## 🤔 Why this exists

Reading the news across many sites takes time. This is a **personal** agent (not a multi-user product) that does the reading for me: it pulls articles from a few trusted feeds, removes duplicates across runs, groups them into sections (Vietnam, finance, VN markets, tech, AI), and writes a short Vietnamese summary with an importance rating and a link back to the original.

It's a customized fork of [`Jimmuji/ai-daily-digest`](https://github.com/Jimmuji/ai-daily-digest) (MIT). The upstream pipeline (collect → summarize with an LLM → save → GitHub Pages) is reused; the sources, language, categories, schedule, and cross-run de-duplication are mine.

---

## ✨ What it does

```
📥 Collect (RSS via feedparser)
 │
 ├── 🇻🇳 Việt Nam               ← VnExpress (Thời sự, Thế giới)
 ├── 💰 Kinh tế / Tài chính     ← CNBC (Top News / Economy / Finance) + VnExpress Kinh doanh
 ├── 📈 Chứng khoán VN          ← CafeF (Chứng khoán, TC quốc tế, TC-Ngân hàng, Vĩ mô)
 ├── 💻 Công nghệ               ← TechCrunch
 └── 🤖 AI                      ← The Verge AI
 │
 ▼
🧹 De-duplicate across runs (data/sent_state.json — 24h sliding window)
 │   Running multiple times a day would repeat the same stories, so a
 │   multi-layer (URL / content-hash / near-dup) watermark is persisted
 │   to the repo and only NEW items pass through.
 │
 ▼
🧠 Summarize in Vietnamese (DeepSeek by default; any OpenAI-compatible API)
 │
 ├── Group items by the categories above
 ├── Up to 3 items for Việt Nam, 7 for each other category, merging same-topic articles
 ├── 2-3 Vietnamese sentences each, with "why it matters" + source link
 ├── Importance rating: ★☆☆☆☆ – ★★★★★
 └── A "Quan sát hôm nay" (today's take) trend note
 │
 ▼
📤 Publish
 │
 ├── Markdown → daily/{YYYY-MM-DD}-{HHMM}.md   (timestamped, never overwritten)
 ├── Raw input JSON → data/ (for traceability)
 └── Static site rebuilt → docs/ (GitHub Pages, Vietnamese UI)
```

---

## 🚀 Quick start

### 1. Fork / clone

This repo already contains the customization. To run your own copy, fork it.

### 2. Configure the API key

**Settings → Secrets and variables → Actions → New repository secret:**

| Secret | Value | Notes |
|--------|-------|-------|
| `API_KEY` | your API key | Defaults to [DeepSeek](https://platform.deepseek.com/) (`deepseek-chat`) |

To use a different provider, add repository **Variables**:

| Variable | Example | For |
|----------|---------|-----|
| `API_BASE_URL` | `https://openrouter.ai/api/v1` | OpenRouter / OpenAI-compatible |
| `API_MODEL` | `anthropic/claude-sonnet-4-6` | model id on that provider |

> The Claude (Anthropic) native API is **not** OpenAI-compatible. To use Claude, go through OpenRouter (`API_BASE_URL=https://openrouter.ai/api/v1`, `API_MODEL=anthropic/...`).

### 3. Enable Actions, then Pages

- **Actions** tab → enable workflows → optionally **Run workflow** once to verify.
- After the first run creates `docs/`, set **Settings → Pages** → source = `main` / `/docs`.

The workflow runs on `cron: 0 4,10,16,22 * * *` — four times a day at 06:00 / 12:00 / 18:00 / 00:00 in UTC+2 (i.e. UTC 04/10/16/22). Dates in the digest use Vietnam time (UTC+7).

---

## 🏗️ Project structure

```
ai-daily-digest/
├── .github/workflows/
│   └── daily.yml            # GitHub Actions — 4×/day (6h), commits daily/ data/ docs/
├── scripts/
│   ├── main.py              # load_state → fetch_all → filter_new → summarize → save
│   ├── sources.py           # feeds grouped by category, fetch_all()
│   ├── dedup.py             # cross-run de-duplication (data/sent_state.json, 24h window)
│   ├── summarize.py         # Vietnamese editor prompt; retry/backoff on 429/5xx
│   └── generate_site.py     # static Vietnamese site → docs/
├── PROJECT_CONTEXT.md       # design decisions & rationale
├── ADAPTATION_GUIDE.md      # how the fork was customized
├── requirements.txt
└── README.md
```

`daily/`, `data/`, and `docs/` are generated at runtime and committed by the workflow.

---

## 🔧 Customizing

### Add or change sources
Edit `scripts/sources.py` — add `(url, "Display name")` tuples under the relevant category in `CATEGORIES`:

```python
CATEGORIES = {
    "vietnam": {"label": "🇻🇳 Việt Nam", "max_items": 3, "feeds": [
        ("https://vnexpress.net/rss/thoi-su.rss", "VnExpress Thời sự"),
        # ("https://your-source.com/rss", "New Source"),  ← add here
    ]},
    ...
}
```

`max_items` caps how many items that category contributes to the digest (default 7). When a category has more than one source, `summarize.py` round-robins + caps per source so no single outlet dominates.

### Change the schedule
Edit the cron in `.github/workflows/daily.yml` (default `0 4,10,16,22 * * *` — 4×/day).

### Change the model
Set `API_BASE_URL` / `API_MODEL` repository Variables (see Quick start).

### Email brief (optional)
After each run with new items, the digest can be emailed via [Resend](https://resend.com). It's **opt-in** — without `RESEND_API_KEY` the step is skipped and nothing else changes.

| Secret / Variable | Value | Notes |
|---|---|---|
| `RESEND_API_KEY` (secret) | your Resend API key | enables sending |
| `EMAIL_TO` (variable) | recipient address | default `hieuvuongforwork@gmail.com` |
| `EMAIL_FROM` (variable) | sender address | default `onboarding@resend.dev` (Resend test sender; use a verified-domain address to send to others) |

---

## 📄 License

MIT — based on [`Jimmuji/ai-daily-digest`](https://github.com/Jimmuji/ai-daily-digest). Free to use; please keep attribution.
