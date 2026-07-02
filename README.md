<div align="center">

# 📡 Bản tin tổng hợp — Personal Vietnamese News Digest

**A personal news agent that collects, de-duplicates, and summarizes the news in Vietnamese — three times a day, fully automated.**

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
 ├── 🇻🇳 Việt Nam               ← Người Quan Sát (nguoiquansat.vn via Google News RSS proxy)
 ├── 💰 Kinh tế / Tài chính     ← CNBC (Top News / Economy / Finance) + VnExpress Kinh doanh
 ├── 📈 Chứng khoán VN          ← CafeF (Chứng khoán, TC quốc tế, TC-Ngân hàng, Vĩ mô)
 ├── 💻 Công nghệ               ← TechCrunch + CNBC Tech
 └── 🤖 AI                      ← The Verge AI + TechCrunch AI
 │
 ▼
🧹 De-duplicate across runs + accumulate into a buffer (data/sent_state.json,
 │   data/pending.json)
 │   Six runs a day would repeat the same stories, so a multi-layer
 │   (URL / content-hash / near-dup) watermark is persisted to the repo and
 │   only NEW items pass through, buffered in data/pending.json until a send.
 │
 ▼
🧠 Summarize in Vietnamese (DeepSeek by default; any OpenAI-compatible API)
 │   Only runs on a real send (see Schedule below) — off-slot ticks just buffer.
 │
 ├── Group items by the categories above
 ├── Up to 6 items for Việt Nam, 7 for each other category, merging same-topic articles
 ├── 2-3 Vietnamese sentences each, with "why it matters" + source link
 ├── Importance rating: ★☆☆☆☆ – ★★★★★
 └── A "Quan sát hôm nay" (today's take) trend note
 │
 ▼
📤 Publish
 │
 ├── Markdown → daily/{YYYY-MM-DD}-{HHMM}.md   (committed, timestamped, never overwritten)
 ├── State → data/pending.json + data/sent_state.json (committed); raw input
 │   dump data/{slug}.raw.json is gitignored (local debug only)
 ├── Email via Resend (optional)
 └── Static site rebuilt → docs/ on the runner → deployed to GitHub Pages via
     actions/deploy-pages (Vietnamese UI, NOT committed)
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
- **Settings → Pages** → Build and deployment → **Source: GitHub Actions** (the site is deployed by `daily.yml`, not served from a branch). One-off via CLI:
  ```bash
  gh api -X POST repos/<owner>/ai-daily-digest/pages -f build_type=workflow
  ```
  Do this **before** the first send, otherwise that run's deploy job fails with "Not Found".

The workflow sends **3×/day at ~07:00 / 13:00 / 22:00 Rome local time, year-round**. GitHub cron is fixed UTC and doesn't follow DST, so it fires **6 ticks** as 3 DST-proof pairs (`cron: 0 5,6,11,12,20,21 * * *` = Rome summer 05/11/20 + winter 06/12/21). Every tick fetches and de-duplicates, but a **slot valve** (`SLOTS` + `sent_slots` in `scripts/dedup.py`, persisted to `data/pending.json`) lets each Rome slot send **exactly once per day** — the second tick of a pair, and any tick below `DIGEST_MIN_ITEMS`, just buffers and skips the LLM. A dropped/late tick is covered by its pair partner, so you never get more than 3 sends and rarely fewer. `workflow_dispatch` sends immediately (`DIGEST_FORCE_SEND=1`) without consuming a slot. Dates in the digest use Vietnam time (UTC+7).

---

## 🏗️ Project structure

```
ai-daily-digest/
├── .github/workflows/
│   ├── daily.yml            # 6 ticks/day (Rome-slot valve); commits daily/ + data/,
│   │                        #   deploys docs/ as a Pages artifact on each send
│   └── keepalive.yml        # daily canary (alerts if yesterday had no digest) +
│                            #   empty commit only if the repo is idle 45+ days
├── scripts/
│   ├── main.py              # load state/buffer → fetch_all → dedup → slot-gated send
│   ├── sources.py           # feeds grouped by category, fetch_all() (per-feed guarded)
│   ├── dedup.py             # cross-run de-dup + pending buffer + Rome slot valve
│   ├── summarize.py         # Vietnamese editor prompt; retry/backoff on 429/5xx/timeout
│   ├── generate_site.py     # static Vietnamese site → docs/
│   ├── email_brief.py       # Markdown → HTML → Resend (optional)
│   └── notify_failure.py    # failure/canary alert email (optional)
├── PROJECT_CONTEXT.md       # design decisions & rationale
├── ADAPTATION_GUIDE.md      # how the fork was customized
├── requirements.txt
└── README.md
```

`daily/` and `data/` (`pending.json`, `sent_state.json`) are committed by the workflow. `docs/` is generated at runtime and deployed as a Pages artifact — **not** committed.

---

## 🔧 Customizing

### Add or change sources
Edit `scripts/sources.py` — add `(url, "Display name")` tuples under the relevant category in `CATEGORIES`:

```python
CATEGORIES = {
    "vietnam": {"label": "🇻🇳 Việt Nam", "max_items": 6, "feeds": [
        ("https://news.google.com/rss/search?q=site:nguoiquansat.vn&hl=vi&gl=VN&ceid=VN:vi", "Người Quan Sát"),
        # ("https://your-source.com/rss", "New Source"),  ← add here
    ]},
    ...
}
```

`max_items` caps how many items that category contributes to the digest (default 7). When a category has more than one source, `summarize.py` round-robins + caps per source so no single outlet dominates.

### Change the schedule
Edit the cron in `.github/workflows/daily.yml` (default `0 5,6,11,12,20,21 * * *` — DST-proof 6 ticks as 3 pairs at 07/13/22 Rome time) **and** the `SLOTS` definition in `scripts/dedup.py`, which decides how ticks map to send windows. The slot valve — not the cron alone — is what guarantees exactly one send per window per day.

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

## 🏛️ Architecture: the two workflows

**`daily.yml`** (6 ticks/day) is the pipeline. Each tick: fetch every feed → de-duplicate against the 24h window and the pending buffer → accumulate new items into `data/pending.json`. If the current Rome slot has not sent today and the buffer has ≥ `DIGEST_MIN_ITEMS`, it summarizes with the LLM, writes `daily/{slug}.md`, rebuilds the site into `docs/`, emails via Resend, marks the slot sent, and clears the buffer. It then commits `daily/` + `data/`; on a send it uploads `docs/` as a Pages artifact and a dependent `deploy` job publishes it. Any run failure triggers a Resend alert (`notify_failure.py`).

**`keepalive.yml`** (once/day, 09:00 VN) is insurance, not part of the pipeline. It checks whether *yesterday* (VN) produced any `daily/*.md`; if not, it emails a canary alert (it does **not** re-trigger `daily.yml` — the 6-tick pairs already self-heal, and a forced off-slot send used to cause duplicate emails). Separately, it makes an empty commit **only if** `main` has been idle 45+ days, purely to keep GitHub from auto-disabling the schedule after 60 days of inactivity.

## 🧹 Shrinking git history (one-time, manual — KHÔNG tự chạy)

`docs/` is no longer committed, but its historical blobs (~124 MiB raw) and old `data/*.raw.json` (~7 MiB) still live in git history. To reclaim that space you must **rewrite history** — do it deliberately, never automatically:

```bash
pip install git-filter-repo          # hoặc: brew install git-filter-repo
cd /tmp
git clone https://github.com/Alexhieuvuong/ai-daily-digest.git adg-rewrite
cd adg-rewrite
git filter-repo --invert-paths --path docs/ --path-glob 'data/*.raw.json'
git remote add origin https://github.com/Alexhieuvuong/ai-daily-digest.git
git push --force --all origin
git push --force --tags origin
```

⚠️ **Before running:** pause Actions (Settings → Actions, or disable the workflows) so no in-flight run's rebase+push resurrects the old history. **After running:** every existing clone must be re-cloned or hard-reset — old commit SHAs and links change. GitHub may keep cached objects until its GC runs. (There are no `*.mp3` blobs in this fork's history; that was an upstream-only artifact.)

---

## 📄 License

MIT — based on [`Jimmuji/ai-daily-digest`](https://github.com/Jimmuji/ai-daily-digest). Free to use; please keep attribution.
