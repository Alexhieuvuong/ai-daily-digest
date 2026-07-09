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


WEEKDAYS = ["Thứ Hai", "Thứ Ba", "Thứ Tư", "Thứ Năm", "Thứ Sáu", "Thứ Bảy", "Chủ Nhật"]
REPO_URL = "https://github.com/Alexhieuvuong/ai-daily-digest"
SITE_TITLE = "Bản tin tổng hợp"


# ── CSS ────────────────────────────────────────────────────────────────────────

CSS = """
:root {
  color-scheme: dark;
  --bg: #0d1117;
  --text: #e6edf3;
  --text-muted: #8b949e;
  --text-soft: #c9d1d9;
  --card: #161b22;
  --border: #21262d;
  --border-strong: #30363d;
  --header-bg: rgba(13,17,23,0.95);
  --hover: #1c2230;
}
html[data-theme="light"] {
  color-scheme: light;
  --bg: #ffffff;
  --text: #1f2328;
  --text-muted: #656d76;
  --text-soft: #3d444d;
  --card: #f6f8fa;
  --border: #d8dee4;
  --border-strong: #d0d7de;
  --header-bg: rgba(255,255,255,0.92);
  --hover: #eaeef2;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
  min-height: 100vh;
  line-height: 1.7;
  transition: background .2s, color .2s;
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
  border-bottom: 1px solid var(--border);
  padding: 12px 24px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  position: sticky;
  top: 0;
  background: var(--header-bg);
  backdrop-filter: blur(8px);
  z-index: 100;
}
.site-header .logo {
  font-size: 18px;
  font-weight: 700;
  color: var(--text);
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
  background: var(--card);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  color: var(--text);
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
  background: var(--card);
  border: 1px solid var(--border-strong);
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
  border-bottom: 1px solid var(--border);
  color: inherit;
}
.sr-item:last-child { border-bottom: none; }
.sr-item:hover { background: var(--hover); text-decoration: none; }
.sr-date { font-size: 11px; color: var(--text-muted); }
.sr-title { font-size: 13px; color: var(--text); line-height: 1.4; }
.sr-cat { font-size: 11px; color: #58a6ff; }
.sr-empty, .sr-hint { padding: 14px; font-size: 13px; color: var(--text-muted); text-align: center; }

/* ── Date picker ── */
.date-picker {
  background: var(--card);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  color: var(--text);
  font-size: 13px;
  padding: 6px 10px;
  outline: none;
  cursor: pointer;
}
.date-picker:focus { border-color: #58a6ff; }

.site-header nav { display: flex; gap: 8px; }
.site-header nav a {
  font-size: 13px;
  color: var(--text-muted);
  padding: 6px 10px;
  border-radius: 6px;
  transition: background .15s;
  white-space: nowrap;
}
.site-header nav a:hover { background: var(--border); color: var(--text); text-decoration: none; }

/* ── Theme / language toggle ── */
.theme-toggle, .lang-toggle {
  background: var(--card);
  border: 1px solid var(--border-strong);
  border-radius: 8px;
  color: var(--text);
  font-size: 15px;
  height: 34px;
  line-height: 1;
  cursor: pointer;
  transition: border-color .15s, background .15s;
}
.theme-toggle { width: 34px; }
.lang-toggle { padding: 0 12px; font-size: 13px; font-weight: 600; min-width: 42px; }
.theme-toggle:hover, .lang-toggle:hover { border-color: #58a6ff; }

/* ── Language content toggle ── */
html[data-lang="en"] [data-lang-content="zh"] { display: none; }
html[data-lang="zh"] [data-lang-content="en"] { display: none; }

/* ── Hot words / trends ── */
.trends {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 22px 24px;
  margin: 8px 0 8px;
}
.trends .trends-head {
  display: flex; align-items: baseline; gap: 10px;
  margin-bottom: 16px;
}
.trends .trends-head h2 { font-size: 15px; font-weight: 700; color: var(--text); }
.trends .trends-head .sub { font-size: 12px; color: var(--text-muted); }
.trend-tags { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; }
.trend-tag {
  display: inline-flex; align-items: center; gap: 6px;
  background: var(--bg);
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  padding: 5px 14px;
  color: var(--text);
  cursor: pointer;
  transition: border-color .15s, transform .15s, color .15s;
  user-select: none;
}
.trend-tag:hover { border-color: #58a6ff; color: #58a6ff; transform: translateY(-1px); }
.trend-tag .cnt {
  font-size: 11px; color: #fff;
  background: linear-gradient(135deg, #1f6feb, #bc8cff);
  border-radius: 999px; padding: 1px 7px;
}
.trend-tag.s1 { font-size: 13px; }
.trend-tag.s2 { font-size: 14px; }
.trend-tag.s3 { font-size: 16px; font-weight: 600; }

/* ── Speak (TTS) button ── */
.speak-btn {
  display: inline-flex; align-items: center; gap: 6px;
  margin-top: 16px;
  background: var(--bg);
  border: 1px solid rgba(88,166,255,.35);
  border-radius: 999px;
  color: #58a6ff;
  font-size: 13px;
  padding: 6px 14px;
  cursor: pointer;
  transition: background .15s, border-color .15s;
}
.speak-btn:hover { background: rgba(88,166,255,.1); }
.speak-btn.playing { border-color: #f85149; color: #f85149; }

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
.hero p { color: var(--text-muted); font-size: 16px; }
.hero .stats {
  display: flex;
  justify-content: center;
  gap: 28px;
  margin-top: 24px;
}
.hero .stat .num { font-size: 24px; font-weight: 700; color: var(--text); }
.hero .stat .lbl { font-size: 12px; color: var(--text-muted); }

/* ── Section heading ── */
.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
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
  background: var(--card);
  border: 1px solid var(--border);
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
.date-card .date-label { font-size: 15px; font-weight: 600; color: var(--text); margin-bottom: 4px; }
.date-card .weekday { font-size: 12px; color: var(--text-muted); }
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
  font-size: 13px; color: var(--text-muted);
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
  border-bottom: 1px solid var(--border);
}
.filter-bar .tab {
  font-size: 13px;
  color: var(--text-muted);
  padding: 5px 14px;
  border: 1px solid var(--border-strong);
  border-radius: 999px;
  cursor: pointer;
  transition: all .15s;
  user-select: none;
}
.filter-bar .tab:hover { color: var(--text); border-color: #58a6ff; }
.filter-bar .tab.active { background: #1f6feb; color: #fff; border-color: #1f6feb; }
.filter-bar .star-toggle {
  margin-left: auto;
  font-size: 13px;
  color: #e3b341;
  padding: 5px 14px;
  border: 1px solid var(--border-strong);
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
.cat-line { flex: 1; height: 1px; background: var(--border); }

/* ── Item card ── */
.item-card {
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 20px 24px;
  margin-bottom: 14px;
  transition: border-color .2s;
}
.item-card:hover { border-color: var(--border-strong); }
.item-title { font-size: 15px; font-weight: 600; color: var(--text); line-height: 1.5; margin-bottom: 8px; }
.item-desc { font-size: 14px; color: var(--text-muted); margin-bottom: 14px; line-height: 1.6; }
.item-meta { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
.stars { font-size: 13px; color: #e3b341; letter-spacing: 1px; }
.item-value {
  font-size: 13px; color: #7ee787;
  background: rgba(46,160,67,.1); padding: 2px 10px; border-radius: 999px;
}
.item-sources { font-size: 13px; color: var(--text-muted); margin-left: auto; }
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
.observation p { font-size: 14px; color: var(--text-soft); line-height: 1.8; }

.empty-filter { display: none; color: var(--text-muted); font-size: 14px; text-align: center; padding: 32px; }

/* ── Day nav ── */
.day-nav {
  display: flex; justify-content: space-between;
  margin-top: 48px; padding-top: 24px; border-top: 1px solid var(--border);
}
.nav-btn {
  font-size: 14px; color: #58a6ff;
  padding: 8px 16px; border: 1px solid var(--border); border-radius: 8px;
  transition: background .15s;
}
.nav-btn:hover { background: var(--card); text-decoration: none; }

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
  color: #484f58; font-size: 13px; border-top: 1px solid var(--border);
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
  var DATES = window.AVAILABLE_DATES || [];            // các ngày YYYY-MM-DD (đã sort)
  var SLUG_BY_DATE = window.SLUG_BY_DATE || {};        // ngày -> slug bản tin mới nhất

  function esc(s) {
    return (s || "").replace(/[&<>"]/g, function (c) {
      return {'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c];
    });
  }

  // ── Date picker (chọn ngày -> mở bản tin mới nhất của ngày đó) ──
  var dp = document.getElementById('datePicker');
  if (dp && DATES.length) {
    dp.min = DATES[0];
    dp.max = DATES[DATES.length - 1];
    dp.value = (window.CURRENT_DATE || '').slice(0, 10) || DATES[DATES.length - 1];
    dp.addEventListener('change', function () {
      var v = dp.value;
      if (!SLUG_BY_DATE[v]) {
        var earlier = DATES.filter(function (d) { return d <= v; });
        v = earlier.length ? earlier[earlier.length - 1] : DATES[0];
      }
      var slug = SLUG_BY_DATE[v];
      if (slug) window.location.href = BASE + 'daily/' + slug + '.html';
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
          return (it.title + ' ' + it.desc + ' ' + it.cat)
            .toLowerCase().indexOf(q) !== -1;
        }).slice(0, 25);
        if (!hits.length) {
          sr.innerHTML = '<div class="sr-empty">Không có kết quả</div>';
        } else {
          sr.innerHTML = hits.map(function (h) {
            return '<a class="sr-item" href="' + BASE + 'daily/' + h.date + '.html">' +
                   '<span class="sr-date">' + esc(h.label || h.date) + ' · ' + esc(h.cat) + '</span>' +
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

  // ── Theme toggle ──
  var tt = document.getElementById('themeToggle');
  function curTheme() {
    return document.documentElement.getAttribute('data-theme') === 'light' ? 'light' : 'dark';
  }
  function paintToggle() { if (tt) tt.textContent = curTheme() === 'light' ? '☀️' : '🌙'; }
  paintToggle();
  if (tt) {
    tt.addEventListener('click', function () {
      var next = curTheme() === 'light' ? 'dark' : 'light';
      if (next === 'light') document.documentElement.setAttribute('data-theme', 'light');
      else document.documentElement.removeAttribute('data-theme');
      try { localStorage.setItem('theme', next); } catch (e) {}
      paintToggle();
    });
  }

  // ── Hot-word tags → search ──
  document.querySelectorAll('.trend-tag').forEach(function (tag) {
    tag.addEventListener('click', function () {
      var term = tag.getAttribute('data-term');
      if (si) {
        si.value = term;
        si.focus();
        si.dispatchEvent(new Event('input', { bubbles: true }));
        window.scrollTo({ top: 0, behavior: 'smooth' });
      }
    });
  });

  // ── Voice readout (Web Speech API) ──
  var synth = window.speechSynthesis;
  document.querySelectorAll('.speak-btn').forEach(function (btn) {
    if (!synth) { btn.style.display = 'none'; return; }
    var label = btn.getAttribute('data-label') || '🔊 Đọc to';
    var stop = btn.getAttribute('data-stop') || '⏹ Dừng';
    btn.addEventListener('click', function () {
      if (btn.classList.contains('playing')) {
        synth.cancel();
        return;
      }
      synth.cancel();
      var u = new SpeechSynthesisUtterance(btn.getAttribute('data-text') || '');
      u.lang = btn.getAttribute('data-speak-lang') || 'vi-VN';
      u.rate = 1.0;
      u.onend = u.onerror = function () {
        btn.classList.remove('playing');
        btn.textContent = label;
      };
      btn.classList.add('playing');
      btn.textContent = stop;
      synth.speak(u);
    });
  });
  window.addEventListener('beforeunload', function () { if (synth) synth.cancel(); });
})();
"""


HEADER_HTML = """
<div id="progressBar"></div>
<header class="site-header">
  <div class="logo"><a href="{base}index.html">📰 Bản tin <span>tổng hợp</span></a></div>
  <div class="header-tools">
    <div class="search-box">
      <input id="searchInput" type="text" placeholder="Tìm trong tất cả bản tin…" autocomplete="off">
      <div id="searchResults" class="search-results"></div>
    </div>
    <input id="datePicker" type="date" class="date-picker" aria-label="Chọn ngày">
    <button id="themeToggle" class="theme-toggle" aria-label="Đổi giao diện" title="Sáng/Tối">🌙</button>
    <nav>
      <a href="{base}index.html">Lưu trữ</a>
      <a href="{repo}" target="_blank">GitHub</a>
    </nav>
  </div>
</header>
"""

FOOTER_HTML = """
<button id="backToTop" aria-label="Lên đầu trang">↑</button>
<footer class="site-footer">
  © Bản tin tổng hợp · Tự động thu thập · Tóm tắt bằng AI · Cập nhật mỗi 6 giờ
</footer>
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <meta name="description" content="{description}">
  <script>
    (function () {{
      try {{
        var t = localStorage.getItem('theme');
        if (!t) t = window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
        if (t === 'light') document.documentElement.setAttribute('data-theme', 'light');
      }} catch (e) {{}}
    }})();
  </script>
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

def cat_type(name: str, emoji: str = "") -> str:
    """Phân loại nhóm theo nhãn category tiếng Việt (bỏ qua emoji)."""
    s = ((name or "") + " " + (emoji or "")).lower()
    if "việt nam" in s:
        return "vietnam"
    if "chứng khoán" in s:        # CafeF — đặt TRƯỚC 'tài chính' để không rơi vào kinh_te
        return "chung_khoan_vn"
    if "🤖" in s or "trí tuệ" in s or re.search(r"\bai\b", s):
        return "ai"
    if "kinh tế" in s or "tài chính" in s:
        return "kinh_te"
    if "công nghệ" in s:
        return "cong_nghe"
    return "other"


CAT_LABELS = [
    ("all", "Tất cả"),
    ("vietnam", "🇻🇳 Việt Nam"),
    ("kinh_te", "💰 Kinh tế"),
    ("chung_khoan_vn", "📈 Chứng khoán VN"),
    ("cong_nghe", "💻 Công nghệ"),
    ("ai", "🤖 AI"),
]


# ── Markdown parser ─────────────────────────────────────────────────────────────

def parse_digest(text: str) -> dict:
    lines = text.splitlines()
    categories = []
    observation_lines = []
    outlook_lines = []
    in_observation = False
    in_outlook = False
    current_cat = None
    current_item = None

    for line in lines:
        # Bắt mọi tiêu đề cấp 2-3 (## hoặc ###), giữ nguyên cả emoji trong tên.
        head_match = re.match(r'^#{2,3}\s+(.+?)\s*$', line)
        name = head_match.group(1).strip() if head_match else None

        if name is not None:
            low = name.lower()
            # Nhận định xu hướng (market_outlook) — kiểm tra TRƯỚC vì tiêu đề chứa
            # "nhận định" sẽ bị nhánh observation bên dưới nuốt mất.
            if "🧭" in name or "xu hướng" in low:
                in_outlook = True
                in_observation = False
                current_cat = None
            elif "quan sát" in low or "nhận định" in low:
                in_observation = True
                in_outlook = False
                current_cat = None
            else:
                in_observation = False
                in_outlook = False
                current_cat = {"emoji": "", "name": name,
                               "type": cat_type(name), "items": []}
                categories.append(current_cat)
                current_item = None
            continue

        if in_outlook:
            # Giữ NGUYÊN dòng (bullet, **đậm**...) — chỉ bỏ footer.
            stripped = line.strip()
            if stripped.startswith('---') or stripped.startswith('*Tạo tự động') or stripped.startswith('*Generated'):
                continue
            outlook_lines.append(line)
            continue

        if in_observation:
            stripped = line.strip()
            if stripped and not stripped.startswith('#') and not stripped.startswith('---') and not stripped.startswith('*Tạo tự động') and not stripped.startswith('*Generated'):
                observation_lines.append(stripped)
            continue

        if current_cat is None:
            continue

        # Tiêu đề mục: số thứ tự có thể nằm trước `**` (định dạng cũ `1. **...**`
        # hoặc `- **...**`) HOẶC nằm trong phần in đậm (`**1. ...**`). Cả hai đều
        # được chấp nhận; số thứ tự bị loại khỏi title vì web hiển thị dạng thẻ.
        item_match = re.match(r'^(?:-|\d+\.)?\s*\*\*\[?(.+?)\]?\*\*\s*[：:]?\s*(.*)', line)
        if item_match:
            title = re.sub(r'^\s*\d+[\.\)]\s*', '', item_match.group(1).strip())
            current_item = {
                "title": title,
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

        star_match = re.match(r'^(?:-\s+)?Quan trọng[：:]\s*(.+)', stripped)
        if star_match:
            raw = star_match.group(1)
            filled = raw.count('★')
            empty = raw.count('☆')
            current_item["stars"] = '★' * filled + '☆' * empty
            current_item["star_count"] = filled
            continue

        val_match = re.match(r'^(?:-\s+)?Vì sao[：:]\s*(.+)', stripped)
        if val_match:
            current_item["value"] = val_match.group(1).strip()
            continue

        src_match = re.match(r'^(?:-\s+)?Nguồn[：:]\s*(.+)', stripped)
        if src_match:
            links = re.findall(r'\[([^\]]+)\]\(([^)]+)\)', src_match.group(1))
            current_item["sources"] = [{"name": n, "url": u} for n, u in links]
            continue

    return {"categories": categories, "observation": " ".join(observation_lines),
            "outlook": "\n".join(outlook_lines).strip()}


# ── HTML builders ───────────────────────────────────────────────────────────────

def attr_escape(s: str) -> str:
    """Escape text for safe use inside an HTML double-quoted attribute."""
    return (
        (s or "")
        .replace("&", "&amp;")
        .replace('"', "&quot;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )


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
      <span class="star-toggle">★ Chỉ tin quan trọng (4+)</span>
    </div>"""


def _inline_md(s: str) -> str:
    """**đậm** → <strong>, _nghiêng_ → <em> (đủ cho định dạng của outlook)."""
    s = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', s)
    s = re.sub(r'(?<![\w_])_([^_]+)_(?![\w_])', r'<em>\1</em>', s)
    return s


def build_outlook_html(outlook_md: str) -> str:
    """Render section 'Nhận định xu hướng' (shape đã biết: đoạn + bullet) thành card.

    Dùng lại class .observation nên không cần CSS mới.
    """
    if not outlook_md:
        return ""
    parts = []
    bullets = []
    for raw in outlook_md.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith('- '):
            bullets.append(f"<li>{_inline_md(line[2:].strip())}</li>")
            continue
        if bullets:
            parts.append("<ul>" + "".join(bullets) + "</ul>")
            bullets = []
        parts.append(f"<p>{_inline_md(line)}</p>")
    if bullets:
        parts.append("<ul>" + "".join(bullets) + "</ul>")
    body = "".join(parts)
    return f"""
        <div class="observation outlook">
          <h2>🧭 Nhận định xu hướng</h2>
          {body}
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
            <h2>{cat["name"]}</h2>
            <div class="cat-line"></div>
          </div>
          {items_html}
        </div>"""

    empty_msg = "Không có mục nào khớp bộ lọc này."

    obs_html = ""
    if digest["observation"]:
        speak_text = attr_escape(digest["observation"])
        obs_html = f"""
        <div class="observation">
          <h2>💡 Quan sát hôm nay</h2>
          <p>{digest["observation"]}</p>
          <button class="speak-btn" data-label="🔊 Đọc to" data-stop="⏹ Dừng" data-speak-lang="vi-VN" data-text="{speak_text}">🔊 Đọc to</button>
        </div>"""

    outlook_html = build_outlook_html(digest.get("outlook", ""))

    return f"""
    <div class="digest-scope">
      {filter_bar}
      {cats_html}
      <div class="empty-filter">{empty_msg}</div>
      {obs_html}
      {outlook_html}
    </div>"""


def render_digest(digest: dict) -> str:
    """Render a single Vietnamese digest body."""
    return build_digest_body(digest)


def date_of(slug: str) -> str:
    """Phần ngày YYYY-MM-DD của một slug (slug có thể là YYYY-MM-DD hoặc YYYY-MM-DD-HHMM)."""
    return slug[:10]


def time_of(slug: str) -> str:
    """Giờ HH:MM nếu slug có hậu tố -HHMM, ngược lại rỗng."""
    m = re.match(r'^\d{4}-\d{2}-\d{2}-(\d{2})(\d{2})$', slug)
    return f"{m.group(1)}:{m.group(2)}" if m else ""


def label_of(slug: str) -> str:
    """Nhãn hiển thị: 'YYYY-MM-DD' hoặc 'YYYY-MM-DD · HH:MM'."""
    t = time_of(slug)
    return f"{date_of(slug)} · {t}" if t else date_of(slug)


def weekday_of(slug: str) -> str:
    try:
        idx = datetime.strptime(date_of(slug), "%Y-%m-%d").weekday()
        return WEEKDAYS[idx]
    except Exception:
        return ""


def state_script(dates: list[str], current: str | None,
                 prev_date: str | None, next_date: str | None, base: str) -> str:
    # Map ngày YYYY-MM-DD -> slug mới nhất trong ngày (cho date picker, vì 1 ngày
    # có thể có nhiều bản tin theo giờ). dates đã sort tăng dần -> lần gán sau là mới nhất.
    slug_by_date: dict[str, str] = {}
    for s in dates:
        slug_by_date[date_of(s)] = s
    parts = [
        f'window.SITE_BASE={json.dumps(base)};',
        f'window.AVAILABLE_DATES={json.dumps(sorted(slug_by_date.keys()))};',
        f'window.SLUG_BY_DATE={json.dumps(slug_by_date)};',
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
    weekday = f"{weekday_of(date_str)} · {label_of(date_str)}"
    body = f"""
    <div class="container">
      <div class="day-hero">
        <div class="date-str">{weekday}</div>
        <h1>{SITE_TITLE}</h1>
      </div>
      {render_digest(digest)}
      <div class="day-nav">
        {f'<a class="nav-btn" href="{prev_date}.html">← {label_of(prev_date)}</a>' if prev_date else '<span></span>'}
        {f'<a class="nav-btn" href="{next_date}.html">{label_of(next_date)} →</a>' if next_date else '<span></span>'}
      </div>
    </div>"""

    return PAGE_TEMPLATE.format(
        title=f"{SITE_TITLE} · {label_of(date_str)}",
        description=f"Bản tin tổng hợp ngày {label_of(date_str)}: Việt Nam, Tài chính, Chứng khoán, Công nghệ, AI.",
        css=CSS,
        header=HEADER_HTML.format(base="../", repo=REPO_URL),
        body=body,
        footer=FOOTER_HTML,
        state=state_script(dates, date_str, prev_date, next_date, base="../"),
        js=JS,
    )


# ── Trends / hot words ──────────────────────────────────────────────────────────

# (display label, search term, [match patterns — lowercase])
TREND_GROUPS = [
    ("Lạm phát", "lạm phát", ["lạm phát", "cpi", "giá cả"]),
    ("Lãi suất", "lãi suất", ["lãi suất", "ngân hàng nhà nước", "fed", "ecb"]),
    ("Chứng khoán", "chứng khoán", ["chứng khoán", "cổ phiếu", "vn-index", "nasdaq", "ipo"]),
    ("Bất động sản", "bất động sản", ["bất động sản", "nhà ở", "căn hộ", "chung cư"]),
    ("Tiền số", "tiền số", ["bitcoin", "tiền số", "crypto", "blockchain"]),
    ("AI", "AI", ["ai", "trí tuệ nhân tạo", "anthropic", "openai", "claude", "chatgpt"]),
    ("Công nghệ", "công nghệ", ["công nghệ", "phần mềm", "ứng dụng", "startup"]),
    ("Năng lượng", "năng lượng", ["dầu", "xăng", "điện", "năng lượng", "khí đốt"]),
    ("Thời tiết", "thời tiết", ["mưa", "bão", "nắng nóng", "el nino", "thời tiết", "ngập"]),
    ("Giao thông", "giao thông", ["giao thông", "tai nạn", "cao tốc", "đường sắt", "sân bay"]),
    ("Y tế", "y tế", ["y tế", "bệnh", "dịch", "bệnh viện", "sức khỏe"]),
    ("Giáo dục", "giáo dục", ["giáo dục", "thi", "học sinh", "tuyển sinh", "đại học"]),
    ("Du lịch", "du lịch", ["du lịch", "khách quốc tế", "tour", "lễ hội"]),
    ("Chính sách", "chính sách", ["thủ tướng", "quốc hội", "nghị định", "chính phủ", "luật"]),
    ("Quốc tế", "quốc tế", ["nga", "ukraine", "mỹ", "trung quốc", "iran", "chiến tranh"]),
]


def compute_trends(parsed_by_date: dict, dates: list[str], window: int = 7, top: int = 12) -> list:
    """Count keyword-group mentions across the most recent `window` digests."""
    recent = dates[-window:] if len(dates) > window else dates
    counts = {label: 0 for label, _, _ in TREND_GROUPS}
    for d in recent:
        digest = parsed_by_date.get(d)
        if not digest:
            continue
        for cat in digest["categories"]:
            for item in cat["items"]:
                text = (item["title"] + " " + item["desc"]).lower()
                for label, _term, patterns in TREND_GROUPS:
                    if any(p in text for p in patterns):
                        counts[label] += 1
    term_of = {label: term for label, term, _ in TREND_GROUPS}
    ranked = [(lbl, c, term_of[lbl]) for lbl, c in counts.items() if c >= 2]
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked[:top]


def build_trends_html(trends: list, window: int) -> str:
    if not trends:
        return ""
    top_count = trends[0][1]
    tags = ""
    for label, count, term in trends:
        ratio = count / top_count if top_count else 0
        size = "s3" if ratio >= 0.66 else ("s2" if ratio >= 0.33 else "s1")
        tags += (
            f'<span class="trend-tag {size}" data-term="{attr_escape(term)}">'
            f'{label}<span class="cnt">{count}</span></span>'
        )
    return f"""
      <div class="trends">
        <div class="trends-head">
          <h2>🔥 Chủ đề nóng · {window} kỳ gần nhất</h2>
          <span class="sub">Xếp theo tần suất · bấm để tìm bản tin liên quan</span>
        </div>
        <div class="trend-tags">{tags}</div>
      </div>"""


def build_index_html(dates: list[str], latest_digest: dict,
                     trends_html: str = "") -> str:
    latest = dates[-1] if dates else ""

    # Archive grid (newest first)
    cards = ""
    for i, d in enumerate(reversed(dates)):
        badge = ('<div class="latest-badge">Mới nhất</div>' if i == 0 else "")
        cards += f"""
        <a class="date-card" href="daily/{d}.html">
          <div class="date-label">{label_of(d)}</div>
          <div class="weekday">{weekday_of(d)}</div>
          {badge}
        </a>"""

    latest_section = ""
    if latest_digest:
        latest_label = f"📅 Bản tin mới nhất · {label_of(latest)} {weekday_of(latest)}"
        latest_section = f"""
      <div class="section-title">{latest_label}</div>
      {render_digest(latest_digest)}"""

    body = f"""
    <div class="container">
      <div class="hero">
        <h1>{SITE_TITLE}</h1>
        <p>Việt Nam · Tài chính · Chứng khoán · Công nghệ · AI — tự động thu thập, tóm tắt bằng AI, cập nhật mỗi 6 giờ</p>
        <div class="stats">
          <div class="stat"><div class="num">{len(dates)}</div><div class="lbl">kỳ bản tin</div></div>
          <div class="stat"><div class="num">3</div><div class="lbl">chuyên mục</div></div>
          <div class="stat"><div class="num">4h</div><div class="lbl">tự cập nhật</div></div>
        </div>
      </div>
      {trends_html}
      {latest_section}
      <div class="section-title">🗂 Lưu trữ</div>
      <div class="date-grid">{cards}</div>
    </div>"""

    return PAGE_TEMPLATE.format(
        title=f"{SITE_TITLE} · Việt Nam · Tài chính · Chứng khoán · Công nghệ · AI",
        description="Bản tin tổng hợp tự động: Việt Nam, Tài chính, Chứng khoán, Công nghệ, AI — tóm tắt bằng AI, cập nhật mỗi 6 giờ.",
        css=CSS,
        header=HEADER_HTML.format(base="", repo=REPO_URL),
        body=body,
        footer=FOOTER_HTML,
        state=state_script(dates, latest, None, None, base=""),
        js=JS,
    )


def build_search_index(parsed_by_date: dict) -> list:
    """Flat list of every item for client-side search (Vietnamese only)."""
    index = []
    for slug, digest in parsed_by_date.items():
        for cat in digest["categories"]:
            for item in cat["items"]:
                index.append({
                    "date": slug,
                    "label": label_of(slug),
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

    # Mỗi file .md (kể cả dạng {date}-{HHmm}.md) là một kỳ bản tin riêng.
    # Bỏ qua *.en.md cũ của repo gốc nếu còn sót.
    md_files = sorted(f for f in daily_dir.glob("*.md")
                      if not f.name.endswith(".en.md"))
    dates = [f.stem for f in md_files]  # "dates" ở đây là các slug, sort tăng dần

    print(f"Generating site for {len(dates)} digests...")

    parsed_by_date = {}
    for md_file in md_files:
        slug = md_file.stem
        parsed_by_date[slug] = parse_digest(md_file.read_text(encoding="utf-8"))

    for i, slug in enumerate(dates):
        digest = parsed_by_date[slug]
        prev_date = dates[i - 1] if i > 0 else None
        next_date = dates[i + 1] if i < len(dates) - 1 else None
        html = build_day_html(slug, digest, dates, prev_date, next_date)
        (docs_daily_dir / f"{slug}.html").write_text(html, encoding="utf-8")

    # Index with latest digest inline + trending hot words
    latest_digest = parsed_by_date[dates[-1]] if dates else {}
    trend_window = 7
    trends = compute_trends(parsed_by_date, dates, window=trend_window)
    trends_html = build_trends_html(trends, trend_window)
    (docs_dir / "index.html").write_text(
        build_index_html(dates, latest_digest, trends_html),
        encoding="utf-8")

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
