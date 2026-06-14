<div align="center">

# 📡 Bản tin tổng hợp — Personal Vietnamese News Digest

**A personal news agent that collects, de-duplicates, and summarizes the news in Vietnamese — every 4 hours, fully automated.**

Auto-collected · AI-curated & summarized · Importance scored · Runs on GitHub Actions (zero server)

[![Daily Digest](https://github.com/Alexhieuvuong/ai-daily-digest/actions/workflows/daily.yml/badge.svg)](https://github.com/Alexhieuvuong/ai-daily-digest/actions/workflows/daily.yml)
![GitHub last commit](https://img.shields.io/github/last-commit/Alexhieuvuong/ai-daily-digest)

</div>

---

## 🤔 Why this exists

Reading the news across many sites takes time. This is a **personal** agent (not a multi-user product) that does the reading for me: it pulls articles from a few trusted feeds, removes duplicates across runs, groups them into three sections, and writes a short Vietnamese summary with an importance rating and a link back to the original.

It's a customized fork of [`Jimmuji/ai-daily-digest`](https://github.com/Jimmuji/ai-daily-digest) (MIT). The upstream pipeline (collect → summarize with an LLM → save → GitHub Pages) is reused; the sources, language, categories, schedule, and cross-run de-duplication are mine.

---

## ✨ What it does

```
📥 Collect (RSS via feedparser)
 │
 ├── 🇻🇳 Việt Nam     ← VnExpress (Thời sự, Thế giới)
 ├── 💰 Kinh tế        ← CNBC (Top News / Economy / Finance) + VnExpress Kinh doanh
 └── 💻 Công nghệ      ← TechCrunch + CNBC Tech
 │
 ▼
🧹 De-duplicate across runs (data/seen.json)
 │   Running every 4h would repeat the same stories, so a URL-hash
 │   watermark is persisted to the repo and only NEW items pass through.
 │
 ▼
🧠 Summarize in Vietnamese (DeepSeek by default; any OpenAI-compatible API)
 │
 ├── Group items by the 3 categories above
 ├── Up to 5 items per category, merging same-topic articles
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

The workflow runs on `cron: 0 */4 * * *` (every 4 hours). Dates in the digest use Vietnam time (UTC+7).

---

## 🏗️ Project structure

```
ai-daily-digest/
├── .github/workflows/
│   └── daily.yml            # GitHub Actions — every 4h, commits daily/ data/ docs/
├── scripts/
│   ├── main.py              # load_state → fetch_all → filter_new → summarize → save
│   ├── sources.py           # feeds grouped by category, fetch_all()
│   ├── dedup.py             # cross-run de-duplication (data/seen.json watermark)
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
    "vietnam": {"label": "🇻🇳 Việt Nam", "feeds": [
        ("https://vnexpress.net/rss/thoi-su.rss", "VnExpress Thời sự"),
        # ("https://your-source.com/rss", "New Source"),  ← add here
    ]},
    ...
}
```

### Change the schedule
Edit the cron in `.github/workflows/daily.yml` (default `0 */4 * * *`).

### Change the model
Set `API_BASE_URL` / `API_MODEL` repository Variables (see Quick start).

---

## 📄 License

MIT — based on [`Jimmuji/ai-daily-digest`](https://github.com/Jimmuji/ai-daily-digest). Free to use; please keep attribution.
