"""
Generate a static HTML site from daily Markdown digests.
Outputs to docs/ for GitHub Pages.

Features:
- Homepage shows the latest digest inline + an archive grid
- Header date-picker (jump to any day) + full-text search across all digests
- Per-digest category tabs + "only ★★★★+" importance filter
- Keyboard left/right navigation, back-to-top, reading-progress bar
"""

import json
import re
import markdown as md_lib
from pathlib import Path
from datetime import datetime


WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
REPO_URL = "https://github.com/Jimmuji/ai-daily-digest"


# ── CSS ────────────────────────────────────────────────────────────────────────

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

/* ── Reading progress bar ── */
#progressBar {
  position: fixed;
  top: 0; left: 0;
  height: 3px;
  width: 0;
  background: linear-gradient(90deg, #58a6ff, #bc8cff);
  z-index: 200;
  transition: width .1s linear;
}

/* ── Header ── */
.site-header {
  border-bottom: 1px solid #21262d;
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
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
  white-space: nowrap;
}
.site-header .logo a { color: inherit; }
.site-header .logo a:hover { text-decoration: none; }
.site-header .logo span { color: #58a6ff; }

.header-tools {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

/* ── Search ── */
.search-box { position: relative; }
.search-box input {
  width: 220px;
  max-width: 50vw;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  color: #e6edf3;
  font-size: 13px;
  padding: 7px 12px;
  outline: none;
  transition: border-color .15s, width .15s;
}
.search-box input:focus { border-color: #58a6ff; width: 280px; }
.search-results {
  display: none;
  position: absolute;
  top: 110%;
  right: 0;
  width: 360px;
  max-width: 80vw;
  max-height: 420px;
  overflow-y: auto;
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 10px;
  box-shadow: 0 12px 40px rgba(0,0,0,.5);
  z-index: 150;
}
.search-results.active { display: block; }
.sr-item {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: 10px 14px;
  border-bottom: 1px solid #21262d;
  color: inherit;
}
.sr-item:last-child { border-bottom: none; }
.sr-item:hover { background: #1c2230; text-decoration: none; }
.sr-date { font-size: 11px; color: #8b949e; }
.sr-title { font-size: 13px; color: #e6edf3; line-height: 1.4; }
.sr-cat { font-size: 11px; color: #58a6ff; }
.sr-empty, .sr-hint { padding: 14px; font-size: 13px; color: #8b949e; text-align: center; }

/* ── Date picker ── */
.date-picker {
  background: #161b22;
  border: 1px solid #30363d;
  border-radius: 8px;
  color: #e6edf3;
  font-size: 13px;
  padding: 6px 10px;
  outline: none;
  color-scheme: dark;
  cursor: pointer;
}
.date-picker:focus { border-color: #58a6ff; }

.site-header nav { display: flex; gap: 8px; }
.site-header nav a {
  font-size: 13px;
  color: #8b949e;
  padding: 6px 10px;
  border-radius: 6px;
  transition: background .15s;
  white-space: nowrap;
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
  padding: 56px 0 32px;
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
.hero p { color: #8b949e; font-size: 16px; }
.hero .stats {
  display: flex;
  justify-content: center;
  gap: 28px;
  margin-top: 24px;
}
.hero .stat .num { font-size: 24px; font-weight: 700; color: #e6edf3; }
.hero .stat .lbl { font-size: 12px; color: #8b949e; }

/* ── Section heading ── */
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #8b949e;
  text-transform: uppercase;
  letter-spacing: .08em;
  margin: 48px 0 18px;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* ── Date grid (archive) ── */
.date-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  gap: 14px;
}
.date-card {
  background: #161b22;
  border: 1px solid #21262d;
  border-radius: 12px;
  padding: 18px;
  transition: border-color .2s, transform .2s;
  display: block;
  color: inherit;
}
.date-card:hover {
  border-color: #58a6ff;
  transform: translateY(-2px);
  text-decoration: none;
}
.date-card .date-label { font-size: 15px; font-weight: 600; color: #e6edf3; margin-bottom: 4px; }
.date-card .weekday { font-size: 12px; color: #8b949e; }
.date-card .latest-badge {
  display: inline-block;
  font-size: 11px;
  background: #1f6feb;
  color: #fff;
  padding: 2px 8px;
  border-radius: 999px;
  margin-top: 10px;
}

/* ── Day hero ── */
.day-hero { margin-bottom: 24px; }
.day-hero .date-str {
  font-size: 13px; color: #8b949e;
  text-transform: uppercase; letter-spacing: .06em; margin-bottom: 6px;
}
.day-hero h1 { font-size: 28px; font-weight: 700; }

/* ── Filter bar ── */
.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 28px;
  padding-bottom: 20px;
  border-bottom: 1px solid #21262d;
}
.filter-bar .tab {
  font-size: 13px;
  color: #8b949e;
  padding: 5px 14px;
  border: 1px solid #30363d;
  border-radius: 999px;
  cursor: pointer;
  transition: all .15s;
  user-select: none;
}
.filter-bar .tab:hover { color: #e6edf3; border-color: #58a6ff; }
.filter-bar .tab.active { background: #1f6feb; color: #fff; border-color: #1f6feb; }
.filter-bar .star-toggle {
  margin-left: auto;
  font-size: 13px;
  color: #e3b341;
  padding: 5px 14px;
  border: 1px solid #30363d;
  border-radius: 999px;
  cursor: pointer;
  transition: all .15s;
  user-select: none;
}
.filter-bar .star-toggle:hover { border-color: #e3b341; }
.filter-bar .star-toggle.active { background: rgba(227,179,65,.15); border-color: #e3b341; }

/* ── Category section ── */
.category { margin-bottom: 40px; }
.category-header { display: flex; align-items: center; gap: 10px; margin-bottom: 20px; }
.category-header h2 { font-size: 18px; font-weight: 700; }
.cat-line { flex: 1; height: 1px; background: #21262d; }

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
.item-title { font-size: 15px; font-weight: 600; color: #e6edf3; line-height: 1.5; margin-bottom: 8px; }
.item-desc { font-size: 14px; color: #8b949e; margin-bottom: 14px; line-height: 1.6; }
.item-meta { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.stars { font-size: 13px; color: #e3b341; letter-spacing: 1px; }
.item-value {
  font-size: 13px; color: #7ee787;
  background: rgba(46,160,67,.1); padding: 2px 10px; border-radius: 999px;
}
.item-sources { font-size: 13px; color: #8b949e; margin-left: auto; }
.item-sources a { color: #58a6ff; margin-left: 6px; }
.item-sources a:first-child { margin-left: 0; }

/* ── Observation box ── */
.observation {
  background: linear-gradient(135deg, rgba(31,111,235,.12), rgba(188,140,255,.08));
  border: 1px solid rgba(88,166,255,.2);
  border-radius: 12px;
  padding: 24px;
  margin-top: 40px;
}
.observation h2 { font-size: 16px; font-weight: 700; color: #58a6ff; margin-bottom: 12px; }
.observation p { font-size: 14px; color: #c9d1d9; line-height: 1.8; }

.empty-filter { display: none; color: #8b949e; font-size: 14px; text-align: center; padding: 32px; }

/* ── Day nav ── */
.day-nav {
  display: flex; justify-content: space-between;
  margin-top: 48px; padding-top: 24px; border-top: 1px solid #21262d;
}
.nav-btn {
  font-size: 14px; color: #58a6ff;
  padding: 8px 16px; border: 1px solid #21262d; border-radius: 8px;
  transition: background .15s;
}
.nav-btn:hover { background: #161b22; text-decoration: none; }

/* ── Back to top ── */
#backToTop {
  position: fixed;
  right: 24px; bottom: 24px;
  width: 42px; height: 42px;
  border-radius: 50%;
  background: #1f6feb;
  color: #fff;
  border: none;
  font-size: 18px;
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition: opacity .2s, transform .2s;
  box-shadow: 0 6px 20px rgba(0,0,0,.4);
  z-index: 120;
}
#backToTop.visible { opacity: 1; pointer-events: auto; }
#backToTop:hover { transform: translateY(-2px); }

/* ── Footer ── */
.site-footer {
  text-align: center; padding: 24px;
  color: #484f58; font-size: 13px; border-top: 1px solid #21262d;
}

/* ── Responsive ── */
@media (max-width: 680px) {
  .hero h1 { font-size: 28px; }
  .item-meta { flex-direction: column; align-items: flex-start; }
  .item-sources { margin-left: 0; }
  .site-header .logo { font-size: 15px; }
  .search-box input { width: 150px; }
  .search-box input:focus { width: 180px; }
  .filter-bar .star-toggle { margin-left: 0; }
}
"""


# ── JS ─────────────────────────────────────────────────────────────────────────

JS = """
(function () {
  var BASE = window.SITE_BASE || "";
  var DATES = window.AVAILABLE_DATES || [];

  function esc(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }

  // ── Date picker ──
  var dp = document.getElementById('datePicker');
  if (dp && DATES.length) {
    dp.min = DATES[0];
    dp.max = DATES[DATES.length - 1];
    dp.value = window.CURRENT_DATE || DATES[DATES.length - 1];
    dp.addEventListener('change', function () {
      var v = dp.value;
      if (DATES.indexOf(v) === -1) {
        var earlier = DATES.filter(function (d) { return d <= v; });
        v = earlier.length ? earlier[earlier.length - 1] : DATES[0];
      }
      window.location.href = BASE + 'daily/' + v + '.html';
    });
  }

  // ── Search ──
  var si = document.getElementById('searchInput');
  var sr = document.getElementById('searchResults');
  var INDEX = null;
  function loadIndex() {
    if (INDEX) return Promise.resolve(INDEX);
    return fetch(BASE + 'search-index.json')
      .then(function (r) { return r.json(); })
      .then(function (data) { INDEX = data; return data; });
  }
  if (si && sr) {
    si.addEventListener('input', function () {
      var q = si.value.trim().toLowerCase();
      if (q.length < 2) { sr.classList.remove('active'); sr.innerHTML = ''; return; }
      loadIndex().then(function (idx) {
        var hits = idx.filter(function (it) {
          return (it.title + ' ' + it.desc).toLowerCase().indexOf(q) !== -1;
        }).slice(0, 25);
        if (!hits.length) {
          sr.innerHTML = '<div class="sr-empty">没有匹配结果</div>';
        } else {
          sr.innerHTML = hits.map(function (h) {
            return '<a class="sr-item" href="' + BASE + 'daily/' + h.date + '.html">' +
                   '<span class="sr-date">' + h.date + ' · ' + esc(h.cat) + '</span>' +
                   '<span class="sr-title">' + esc(h.title) + '</span></a>';
          }).join('');
        }
        sr.classList.add('active');
      });
    });
    document.addEventListener('click', function (e) {
      if (!e.target.closest('.search-box')) sr.classList.remove('active');
    });
  }

  // ── Filters (category tabs + star toggle), scoped per digest ──
  document.querySelectorAll('.filter-bar').forEach(function (bar) {
    var scope = bar.closest('.digest-scope') || document;
    var tabs = bar.querySelectorAll('.tab');
    var starToggle = bar.querySelector('.star-toggle');
    var curCat = 'all', starsOnly = false;

    function apply() {
      scope.querySelectorAll('.category').forEach(function (catEl) {
        var ct = catEl.getAttribute('data-cat');
        var catMatch = (curCat === 'all') || (ct === curCat);
        var visible = 0;
        catEl.querySelectorAll('.item-card').forEach(function (it) {
          var stars = parseInt(it.getAttribute('data-stars') || '0', 10);
          var show = catMatch && (!starsOnly || stars >= 4);
          it.style.display = show ? '' : 'none';
          if (show) visible++;
        });
        catEl.style.display = (catMatch && visible > 0) ? '' : 'none';
      });
      var anyVisible = Array.prototype.some.call(
        scope.querySelectorAll('.category'),
        function (c) { return c.style.display !== 'none'; }
      );
      var emptyMsg = scope.querySelector('.empty-filter');
      if (emptyMsg) emptyMsg.style.display = anyVisible ? 'none' : 'block';
    }

    tabs.forEach(function (t) {
      t.addEventListener('click', function () {
        tabs.forEach(function (x) { x.classList.remove('active'); });
        t.classList.add('active');
        curCat = t.getAttribute('data-cat');
        apply();
      });
    });
    if (starToggle) {
      starToggle.addEventListener('click', function () {
        starsOnly = !starsOnly;
        starToggle.classList.toggle('active', starsOnly);
        apply();
      });
    }
  });

  // ── Keyboard navigation (day pages) ──
  document.addEventListener('keydown', function (e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
    if (e.key === 'ArrowLeft' && window.PREV_DATE) {
      window.location.href = window.PREV_DATE + '.html';
    } else if (e.key === 'ArrowRight' && window.NEXT_DATE) {
      window.location.href = window.NEXT_DATE + '.html';
    }
  });

  // ── Back to top ──
  var btt = document.getElementById('backToTop');
  if (btt) {
    window.addEventListener('scroll', function () {
      btt.classList.toggle('visible', window.scrollY > 400);
    });
    btt.addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
    });
  }

  // ── Reading progress ──
  var pb = document.getElementById('progressBar');
  if (pb) {
    window.addEventListener('scroll', function () {
      var h = document.documentElement.scrollHeight - window.innerHeight;
      pb.style.width = (h > 0 ? (window.scrollY / h) * 100 : 0) + '%';
    });
  }
})();
"""


HEADER_HTML = """
<div id="progressBar"></div>
<header class="site-header">
  <div class="logo"><a href="{base}index.html">⚡ AI <span>Daily</span> Digest</a></div>
  <div class="header-tools">
    <div class="search-box">
      <input id="searchInput" type="text" placeholder="搜索全部日报…" autocomplete="off">
      <div id="searchResults" class="search-results"></div>
    </div>
    <input id="datePicker" type="date" class="date-picker" aria-label="选择日期">
    <nav>
      <a href="{base}index.html">归档</a>
      <a href="{repo}" target="_blank">GitHub</a>
    </nav>
  </div>
</header>
"""

FOOTER_HTML = """
<button id="backToTop" aria-label="回到顶部">↑</button>
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
  <script>{state}</script>
  <script>{js}</script>
</body>
</html>"""


# ── Category typing ─────────────────────────────────────────────────────────────

def cat_type(name: str, emoji: str) -> str:
    s = (name or "") + (emoji or "")
    if any(k in s for k in ["论文", "paper", "研究", "📄", "📑"]):
        return "paper"
    if any(k in s for k in ["项目", "开源", "工具", "repo", "🔧", "🛠"]):
        return "project"
    if any(k in s for k in ["新闻", "动态", "行业", "资讯", "📰"]):
        return "news"
    return "other"


CAT_LABELS = [("all", "全部"), ("news", "新闻"), ("paper", "论文"), ("project", "项目")]


# ── Markdown parser ─────────────────────────────────────────────────────────────

def parse_digest(text: str) -> dict:
    lines = text.splitlines()
    categories = []
    observation_lines = []
    in_observation = False
    current_cat = None
    current_item = None

    for line in lines:
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
                current_cat = {"emoji": emoji, "name": name,
                               "type": cat_type(name, emoji), "items": []}
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

        item_match = re.match(r'^-\s+\*\*\[?(.+?)\]?\*\*[：:]\s*(.*)', line)
        if item_match:
            current_item = {
                "title": item_match.group(1).strip(),
                "desc": item_match.group(2).strip(),
                "stars": "",
                "star_count": 0,
                "value": "",
                "sources": [],
            }
            current_cat["items"].append(current_item)
            continue

        if current_item is None:
            continue

        stripped = line.strip()

        star_match = re.match(r'^-\s+重要性[：:]\s*(.+)', stripped)
        if star_match:
            raw = star_match.group(1)
            filled = raw.count('★')
            empty = raw.count('☆')
            current_item["stars"] = '★' * filled + '☆' * empty
            current_item["star_count"] = filled
            continue

        val_match = re.match(r'^-\s+核心价值[：:]\s*(.+)', stripped)
        if val_match:
            current_item["value"] = val_match.group(1).strip()
            continue

        src_match = re.match(r'^-\s+来源[：:]\s*(.+)', stripped)
        if src_match:
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', src_match.group(1))
            current_item["sources"] = [{"name": n, "url": u} for n, u in links]
            continue

    return {"categories": categories, "observation": " ".join(observation_lines)}


# ── HTML builders ───────────────────────────────────────────────────────────────

def build_item_html(item: dict) -> str:
    sources_html = ""
    if item["sources"]:
        links = " · ".join(
            f'<a href="{s["url"]}" target="_blank">{s["name"]}</a>'
            for s in item["sources"]
        )
        sources_html = f'<div class="item-sources">{links}</div>'

    value_html = f'<span class="item-value">{item["value"]}</span>' if item["value"] else ""
    stars_html = f'<span class="stars">{item["stars"]}</span>' if item["stars"] else ""

    return f"""
    <div class="item-card" data-stars="{item['star_count']}">
      <div class="item-title">{item["title"]}</div>
      {"<div class='item-desc'>" + item["desc"] + "</div>" if item["desc"] else ""}
      <div class="item-meta">
        {stars_html}
        {value_html}
        {sources_html}
      </div>
    </div>"""


def build_filter_bar(present_types: set) -> str:
    tabs = ""
    for key, label in CAT_LABELS:
        if key != "all" and key not in present_types:
            continue
        active = " active" if key == "all" else ""
        tabs += f'<span class="tab{active}" data-cat="{key}">{label}</span>'
    return f"""
    <div class="filter-bar">
      {tabs}
      <span class="star-toggle">★ 只看重点 (4+)</span>
    </div>"""


def build_digest_body(digest: dict) -> str:
    """Filter bar + categories + observation, wrapped in a .digest-scope."""
    present_types = {c["type"] for c in digest["categories"] if c["items"]}
    filter_bar = build_filter_bar(present_types)

    cats_html = ""
    for cat in digest["categories"]:
        if not cat["items"]:
            continue
        items_html = "".join(build_item_html(i) for i in cat["items"])
        cats_html += f"""
        <div class="category" data-cat="{cat['type']}">
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

    return f"""
    <div class="digest-scope">
      {filter_bar}
      {cats_html}
      <div class="empty-filter">该筛选条件下没有内容。</div>
      {obs_html}
    </div>"""


def weekday_of(date_str: str) -> str:
    try:
        return WEEKDAYS[datetime.strptime(date_str, "%Y-%m-%d").weekday()]
    except Exception:
        return ""


def state_script(dates: list[str], current: str | None,
                 prev_date: str | None, next_date: str | None, base: str) -> str:
    parts = [
        f'window.SITE_BASE={json.dumps(base)};',
        f'window.AVAILABLE_DATES={json.dumps(dates)};',
    ]
    if current:
        parts.append(f'window.CURRENT_DATE={json.dumps(current)};')
    if prev_date:
        parts.append(f'window.PREV_DATE={json.dumps(prev_date)};')
    if next_date:
        parts.append(f'window.NEXT_DATE={json.dumps(next_date)};')
    return "".join(parts)


def build_day_html(date_str: str, digest: dict, dates: list[str],
                   prev_date: str | None, next_date: str | None) -> str:
    weekday = weekday_of(date_str)
    body = f"""
    <div class="container">
      <div class="day-hero">
        <div class="date-str">{weekday} · {date_str}</div>
        <h1>AI 每日简报</h1>
      </div>
      {build_digest_body(digest)}
      <div class="day-nav">
        {f'<a class="nav-btn" href="{prev_date}.html">← {prev_date}</a>' if prev_date else '<span></span>'}
        {f'<a class="nav-btn" href="{next_date}.html">{next_date} →</a>' if next_date else '<span></span>'}
      </div>
    </div>"""

    return PAGE_TEMPLATE.format(
        title=f"AI Daily Digest · {date_str}",
        description=f"AI领域{date_str}每日简报，涵盖行业新闻、重要论文与开源项目。",
        css=CSS,
        header=HEADER_HTML.format(base="../", repo=REPO_URL),
        body=body,
        footer=FOOTER_HTML,
        state=state_script(dates, date_str, prev_date, next_date, base="../"),
        js=JS,
    )


def build_index_html(dates: list[str], latest_digest: dict) -> str:
    latest = dates[-1] if dates else ""
    weekday = weekday_of(latest)

    # Archive grid (newest first)
    cards = ""
    for i, d in enumerate(reversed(dates)):
        badge = '<div class="latest-badge">最新</div>' if i == 0 else ""
        cards += f"""
        <a class="date-card" href="daily/{d}.html">
          <div class="date-label">{d}</div>
          <div class="weekday">{weekday_of(d)}</div>
          {badge}
        </a>"""

    latest_section = ""
    if latest_digest:
        latest_section = f"""
      <div class="section-title">📅 最新一期 · {latest} {weekday}</div>
      {build_digest_body(latest_digest)}"""

    body = f"""
    <div class="container">
      <div class="hero">
        <h1>AI Daily Digest</h1>
        <p>每天 5 分钟 · 掌握 AI 领域最新动态 · 全自动采集 · 智能筛选</p>
        <div class="stats">
          <div class="stat"><div class="num">{len(dates)}</div><div class="lbl">期日报</div></div>
          <div class="stat"><div class="num">12+</div><div class="lbl">数据源</div></div>
          <div class="stat"><div class="num">每日</div><div class="lbl">自动更新</div></div>
        </div>
      </div>
      {latest_section}
      <div class="section-title">🗂 历史归档</div>
      <div class="date-grid">{cards}</div>
    </div>"""

    return PAGE_TEMPLATE.format(
        title="AI Daily Digest · AI 领域每日简报",
        description="AI Daily Digest 每日自动采集 AI 领域最新资讯，涵盖行业新闻、重要论文与开源项目。",
        css=CSS,
        header=HEADER_HTML.format(base="", repo=REPO_URL),
        body=body,
        footer=FOOTER_HTML,
        state=state_script(dates, latest, None, None, base=""),
        js=JS,
    )


def build_search_index(parsed_by_date: dict) -> list:
    """Flat list of every item for client-side search."""
    index = []
    for date_str, digest in parsed_by_date.items():
        for cat in digest["categories"]:
            for item in cat["items"]:
                index.append({
                    "date": date_str,
                    "title": item["title"],
                    "desc": item["desc"],
                    "cat": cat["name"],
                    "stars": item["star_count"],
                })
    # newest first
    index.sort(key=lambda x: x["date"], reverse=True)
    return index


# ── Main ────────────────────────────────────────────────────────────────────────

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

    parsed_by_date = {}
    for md_file in md_files:
        parsed_by_date[md_file.stem] = parse_digest(md_file.read_text(encoding="utf-8"))

    for i, date_str in enumerate(dates):
        digest = parsed_by_date[date_str]
        prev_date = dates[i - 1] if i > 0 else None
        next_date = dates[i + 1] if i < len(dates) - 1 else None
        html = build_day_html(date_str, digest, dates, prev_date, next_date)
        (docs_daily_dir / f"{date_str}.html").write_text(html, encoding="utf-8")

    # Index with latest digest inline
    latest_digest = parsed_by_date[dates[-1]] if dates else {}
    (docs_dir / "index.html").write_text(
        build_index_html(dates, latest_digest), encoding="utf-8")

    # Search index
    (docs_dir / "search-index.json").write_text(
        json.dumps(build_search_index(parsed_by_date), ensure_ascii=False),
        encoding="utf-8")

    # 404 → back to index
    (docs_dir / "404.html").write_text(
        '<!DOCTYPE html><meta charset="UTF-8">'
        '<meta http-equiv="refresh" content="0;url=/ai-daily-digest/index.html">',
        encoding="utf-8")

    print(f"Site generated → {docs_dir}")


if __name__ == "__main__":
    generate_site()
