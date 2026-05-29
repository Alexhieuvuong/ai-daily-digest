"""
Generate a static HTML site from daily Markdown digests.
Outputs to docs/ for GitHub Pages.
"""

import re
import markdown as md_lib
from pathlib import Path
from datetime import datetime


# ── HTML template ─────────────────────────────────────────────────────────────

CSS = """
* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #0d1117;
  color: #e6edf3;
  min-height: 100vh;
  line-height: 1.7;
}

a { color: #58a6ff; text-decoration: none; }
a:hover { text-decoration: underline; }

/* ── Header ── */
.site-header {
  border-bottom: 1px solid #21262d;
  padding: 16px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  position: sticky;
  top: 0;
  background: rgba(13,17,23,0.95);
  backdrop-filter: blur(8px);
  z-index: 100;
}
.site-header .logo {
  font-size: 18px;
  font-weight: 700;
  color: #e6edf3;
  display: flex;
  align-items: center;
  gap: 8px;
}
.site-header .logo span { color: #58a6ff; }
.site-header nav { display: flex; gap: 12px; }
.site-header nav a {
  font-size: 13px;
  color: #8b949e;
  padding: 4px 10px;
  border-radius: 6px;
  transition: background .15s;
}
.site-header nav a:hover { background: #21262d; color: #e6edf3; text-decoration: none; }

/* ── Layout ── */
.container {
  max-width: 860px;
  margin: 0 auto;
  padding: 40px 24px 80px;
}

/* ── Hero ── */
.hero {
  text-align: center;
  padding: 60px 0 48px;
}
.hero h1 {
  font-size: 40px;
  font-weight: 800;
  background: linear-gradient(135deg, #58a6ff, #bc8cff);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
  margin-bottom: 12px;
}
.hero p {
  color: #8b949e;
  font-size: 16px;
}

/* ── Date grid (index) ── */
.date-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 16px;
  margin-top: 32px;
}
.date-card {
  background: #161b22;
  border: 1px solid #21262d;
  border-radius: 12px;
  padding: 20px;
  transition: border-color .2s, transform .2s;
  display: block;
  color: inherit;
}
.date-card:hover {
  border-color: #58a6ff;
  transform: translateY(-2px);
  text-decoration: none;
}
.date-card .date-label {
  font-size: 15px;
  font-weight: 600;
  color: #e6edf3;
  margin-bottom: 4px;
}
.date-card .weekday {
  font-size: 12px;
  color: #8b949e;
}
.date-card .latest-badge {
  display: inline-block;
  font-size: 11px;
  background: #1f6feb;
  color: #fff;
  padding: 2px 8px;
  border-radius: 999px;
  margin-top: 10px;
}

/* ── Day page date heading ── */
.day-hero {
  margin-bottom: 40px;
  padding-bottom: 24px;
  border-bottom: 1px solid #21262d;
}
.day-hero .date-str {
  font-size: 13px;
  color: #8b949e;
  text-transform: uppercase;
  letter-spacing: .06em;
  margin-bottom: 6px;
}
.day-hero h1 {
  font-size: 28px;
  font-weight: 700;
}

/* ── Category section ── */
.category {
  margin-bottom: 40px;
}
.category-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 20px;
}
.category-header h2 {
  font-size: 18px;
  font-weight: 700;
}
.cat-line {
  flex: 1;
  height: 1px;
  background: #21262d;
}

/* ── Item card ── */
.item-card {
  background: #161b22;
  border: 1px solid #21262d;
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 14px;
  transition: border-color .2s;
}
.item-card:hover { border-color: #30363d; }

.item-title {
  font-size: 15px;
  font-weight: 600;
  color: #e6edf3;
  line-height: 1.5;
  margin-bottom: 8px;
}
.item-desc {
  font-size: 14px;
  color: #8b949e;
  margin-bottom: 14px;
  line-height: 1.6;
}
.item-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: center;
}
.stars {
  font-size: 13px;
  color: #e3b341;
  letter-spacing: 1px;
}
.item-value {
  font-size: 13px;
  color: #7ee787;
  background: rgba(46,160,67,.1);
  padding: 2px 10px;
  border-radius: 999px;
}
.item-sources {
  font-size: 13px;
  color: #8b949e;
  margin-left: auto;
}
.item-sources a {
  color: #58a6ff;
  margin-left: 6px;
}
.item-sources a:first-child { margin-left: 0; }

/* ── Observation box ── */
.observation {
  background: linear-gradient(135deg, rgba(31,111,235,.12), rgba(188,140,255,.08));
  border: 1px solid rgba(88,166,255,.2);
  border-radius: 12px;
  padding: 24px;
  margin-top: 40px;
}
.observation h2 {
  font-size: 16px;
  font-weight: 700;
  color: #58a6ff;
  margin-bottom: 12px;
}
.observation p {
  font-size: 14px;
  color: #c9d1d9;
  line-height: 1.8;
}

/* ── Day nav ── */
.day-nav {
  display: flex;
  justify-content: space-between;
  margin-top: 48px;
  padding-top: 24px;
  border-top: 1px solid #21262d;
}
.nav-btn {
  font-size: 14px;
  color: #58a6ff;
  padding: 8px 16px;
  border: 1px solid #21262d;
  border-radius: 8px;
  transition: background .15s;
}
.nav-btn:hover { background: #161b22; text-decoration: none; }

/* ── Footer ── */
.site-footer {
  text-align: center;
  padding: 24px;
  color: #484f58;
  font-size: 13px;
  border-top: 1px solid #21262d;
}

/* ── Responsive ── */
@media (max-width: 600px) {
  .hero h1 { font-size: 28px; }
  .item-meta { flex-direction: column; align-items: flex-start; }
  .item-sources { margin-left: 0; }
  .site-header .logo { font-size: 15px; }
}
"""

HEADER_HTML = """
<header class="site-header">
  <div class="logo">⚡ AI <span>Daily</span> Digest</div>
  <nav>
    <a href="{index_href}">归档</a>
    <a href="https://github.com/Jimmuji/ai-daily-digest" target="_blank">GitHub</a>
  </nav>
</header>
"""

FOOTER_HTML = """
<footer class="site-footer">
  © AI Daily Digest · 全自动采集 · DeepSeek 智能筛选 · 每日更新
</footer>
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-Hans">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <style>{css}</style>
</head>
<body>
  {header}
  {body}
  {footer}
</body>
</html>"""


# ── Markdown parser ───────────────────────────────────────────────────────────

def parse_digest(text: str) -> dict:
    """
    Parse the digest Markdown into structured data.
    Returns { categories: [{name, emoji, items}], observation: str }
    """
    lines = text.splitlines()
    categories = []
    observation_lines = []
    in_observation = False
    current_cat = None
    current_item = None

    for line in lines:
        # Category header: ## 📰 行业新闻  or  ## 今日观察
        cat_match = re.match(r'^##\s+([\U00010000-\U0010ffff☀-⛿✀-➿])\s*(.+)', line)
        plain_match = re.match(r'^##\s+([^#\U00010000-\U0010ffff].+)', line) if not cat_match else None
        if cat_match:
            emoji = cat_match.group(1)
            name = cat_match.group(2).strip()
        elif plain_match:
            emoji = ""
            name = plain_match.group(1).strip()
        else:
            emoji = name = None

        if name is not None:
            if "观察" in name or "洞察" in name:
                in_observation = True
                current_cat = None
            else:
                in_observation = False
                current_cat = {"emoji": emoji, "name": name, "items": []}
                categories.append(current_cat)
                current_item = None
            continue

        if in_observation:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('---') and not stripped.startswith('*Generated'):
                observation_lines.append(stripped)
            continue

        if current_cat is None:
            continue

        # Item title: - **[Title]**: desc  or  - **Title**: desc
        item_match = re.match(r'^-\s+\*\*\[?(.+?)\]?\*\*[：:]\s*(.*)', line)
        if item_match:
            current_item = {
                "title": item_match.group(1).strip(),
                "desc": item_match.group(2).strip(),
                "stars": "",
                "value": "",
                "sources": [],
            }
            current_cat["items"].append(current_item)
            continue

        if current_item is None:
            continue

        stripped = line.strip()

        # Star rating
        star_match = re.match(r'^-\s+重要性[：:]\s*(.+)', stripped)
        if star_match:
            raw = star_match.group(1)
            filled = raw.count('★')
            empty = raw.count('☆')
            current_item["stars"] = '★' * filled + '☆' * empty
            continue

        # Core value
        val_match = re.match(r'^-\s+核心价值[：:]\s*(.+)', stripped)
        if val_match:
            current_item["value"] = val_match.group(1).strip()
            continue

        # Sources — may contain multiple [Name](URL) separated by |
        src_match = re.match(r'^-\s+来源[：:]\s*(.+)', stripped)
        if src_match:
            raw_sources = src_match.group(1)
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', raw_sources)
            current_item["sources"] = [{"name": n, "url": u} for n, u in links]
            continue

    observation_text = " ".join(observation_lines)

    return {"categories": categories, "observation": observation_text}


# ── HTML builders ─────────────────────────────────────────────────────────────

def build_item_html(item: dict) -> str:
    sources_html = ""
    if item["sources"]:
        links = " · ".join(
            f'<a href="{s["url"]}" target="_blank">{s["name"]}</a>'
            for s in item["sources"]
        )
        sources_html = f'<div class="item-sources">{links}</div>'

    value_html = (
        f'<span class="item-value">{item["value"]}</span>' if item["value"] else ""
    )
    stars_html = (
        f'<span class="stars">{item["stars"]}</span>' if item["stars"] else ""
    )

    return f"""
    <div class="item-card">
      <div class="item-title">{item["title"]}</div>
      {"<div class='item-desc'>" + item["desc"] + "</div>" if item["desc"] else ""}
      <div class="item-meta">
        {stars_html}
        {value_html}
        {sources_html}
      </div>
    </div>"""


def build_day_html(date_str: str, digest: dict,
                   prev_date: str | None, next_date: str | None,
                   index_href: str) -> str:
    weekdays = ["周一","周二","周三","周四","周五","周六","周日"]
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        weekday = weekdays[dt.weekday()]
    except Exception:
        weekday = ""

    cats_html = ""
    for cat in digest["categories"]:
        if not cat["items"]:
            continue
        items_html = "".join(build_item_html(i) for i in cat["items"])
        cats_html += f"""
        <div class="category">
          <div class="category-header">
            <h2>{cat["emoji"]} {cat["name"]}</h2>
            <div class="cat-line"></div>
          </div>
          {items_html}
        </div>"""

    obs_html = ""
    if digest["observation"]:
        obs_html = f"""
        <div class="observation">
          <h2>💡 今日观察</h2>
          <p>{digest["observation"]}</p>
        </div>"""

    nav_prev = (
        f'<a class="nav-btn" href="{prev_date}.html">← {prev_date}</a>'
        if prev_date else '<span></span>'
    )
    nav_next = (
        f'<a class="nav-btn" href="{next_date}.html">{next_date} →</a>'
        if next_date else '<span></span>'
    )

    body = f"""
    <div class="container">
      <div class="day-hero">
        <div class="date-str">{weekday} · {date_str}</div>
        <h1>AI 每日简报</h1>
      </div>
      {cats_html}
      {obs_html}
      <div class="day-nav">{nav_prev}{nav_next}</div>
    </div>"""

    return PAGE_TEMPLATE.format(
        title=f"AI Daily Digest · {date_str}",
        description=f"AI领域{date_str}每日简报，涵盖行业新闻、重要论文与开源项目。",
        css=CSS,
        header=HEADER_HTML.format(index_href=index_href),
        body=body,
        footer=FOOTER_HTML,
    )


def build_index_html(dates: list[str]) -> str:
    cards = ""
    for i, d in enumerate(reversed(dates)):
        try:
            dt = datetime.strptime(d, "%Y-%m-%d")
            weekdays = ["周一","周二","周三","周四","周五","周六","周日"]
            weekday = weekdays[dt.weekday()]
        except Exception:
            weekday = ""

        badge = '<div class="latest-badge">最新</div>' if i == 0 else ""
        cards += f"""
        <a class="date-card" href="daily/{d}.html">
          <div class="date-label">{d}</div>
          <div class="weekday">{weekday}</div>
          {badge}
        </a>"""

    body = f"""
    <div class="container">
      <div class="hero">
        <h1>AI Daily Digest</h1>
        <p>每天 5 分钟 · 掌握 AI 领域最新动态 · 全自动采集 · 智能筛选</p>
      </div>
      <div class="date-grid">{cards}</div>
    </div>"""

    return PAGE_TEMPLATE.format(
        title="AI Daily Digest · AI 领域每日简报",
        description="AI Daily Digest 每日自动采集 AI 领域最新资讯，涵盖行业新闻、重要论文与开源项目。",
        css=CSS,
        header=HEADER_HTML.format(index_href="index.html"),
        body=body,
        footer=FOOTER_HTML,
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def generate_site(root: Path | None = None) -> None:
    if root is None:
        root = Path(__file__).parent.parent

    daily_dir = root / "daily"
    docs_dir = root / "docs"
    docs_daily_dir = docs_dir / "daily"
    docs_daily_dir.mkdir(parents=True, exist_ok=True)

    md_files = sorted(daily_dir.glob("*.md"))
    dates = [f.stem for f in md_files]

    print(f"Generating site for {len(dates)} days...")

    for i, md_file in enumerate(md_files):
        date_str = md_file.stem
        text = md_file.read_text(encoding="utf-8")
        digest = parse_digest(text)

        prev_date = dates[i - 1] if i > 0 else None
        next_date = dates[i + 1] if i < len(dates) - 1 else None

        html = build_day_html(date_str, digest, prev_date, next_date,
                              index_href="../index.html")
        out = docs_daily_dir / f"{date_str}.html"
        out.write_text(html, encoding="utf-8")

    # Index
    index_html = build_index_html(dates)
    (docs_dir / "index.html").write_text(index_html, encoding="utf-8")

    # GitHub Pages: copy latest day as root redirect
    if dates:
        latest = dates[-1]
        redirect = f'<!DOCTYPE html><meta charset="UTF-8"><meta http-equiv="refresh" content="0;url=daily/{latest}.html"><title>Redirecting...</title>'
        # Just link to index from 404
        (docs_dir / "404.html").write_text(
            f'<!DOCTYPE html><meta charset="UTF-8"><meta http-equiv="refresh" content="0;url=/ai-daily-digest/index.html">',
            encoding="utf-8"
        )

    print(f"Site generated → {docs_dir}")


if __name__ == "__main__":
    generate_site()
