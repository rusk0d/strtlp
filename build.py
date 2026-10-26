"""Build a clean, ad-free static reader from the startlap.hu news sitemap.

Only article pages are fetched. Articles already in state.json are not fetched
again, so each run makes requests only for new articles. Output is plain HTML in
./site: one page per article plus an index.
"""
import html
import json
import re
import time
import urllib.request
from pathlib import Path

SITEMAP = "https://www.startlap.hu/uploads/sitemap/www.startlap.hu_news_sitemap.xml"
HERE = Path(__file__).resolve().parent
OUT = HERE / "site"
STATE = HERE / "state.json"
UA = "Mozilla/5.0 (compatible; personal-reader/0.1)"
DELAY_S = 2
KEEP_DAYS = 14


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def sitemap_entries():
    """Return {url: publication_date} from the news sitemap."""
    xml = fetch(SITEMAP)
    entries = {}
    for block in re.findall(r"<url>(.*?)</url>", xml, re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", block)
        date = re.search(r"<news:publication_date>([^<]+)</news:publication_date>", block)
        if loc:
            entries[loc.group(1)] = date.group(1) if date else ""
    return entries


def parse(page):
    ld = re.search(r'<script type="application/ld\+json">(.*?)</script>', page, re.S)
    graph = json.loads(ld.group(1)).get("@graph", []) if ld else []
    news = next((n for n in graph if n.get("@type") == "NewsArticle"), {})
    img = re.search(r'<meta\s+(?:property="og:image"\s+content="([^"]+)"|content="([^"]+)"\s+property="og:image")', page)
    paras = []
    for body in re.findall(r"<p(?:\s[^>]*)?>(.*?)</p>", page, re.S | re.IGNORECASE):
        text = html.unescape(re.sub(r"<[^>]+>", "", body)).strip()
        if len(text) >= 60 and not (re.search(r'\bcookie(?:s)?\b', text, re.IGNORECASE) and len(text) < 200):
            paras.append(body)
    return {
        "title": html.unescape(news.get("headline", "")),
        "lead": html.unescape(news.get("description", "")),
        "date": news.get("datePublished", "")[:10],
        "image": (img.group(1) or img.group(2)) if img else "",
        "paras": paras,
    }


def render(a, url):
    body = "\n".join(f"<p>{p}</p>" for p in a["paras"])
    img_html = f'<div class="hero"><img src="{html.escape(a["image"])}" alt="Cikk képe"></div>' if a["image"] else '<div class="hero-placeholder">📰</div>'
    return f"""<!doctype html><html lang="hu"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(a["title"])}</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{font:17px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:#f5f7fa;color:#2c3e50}}
.back-nav{{position:sticky;top:0;background:white;border-bottom:1px solid #e5e8ec;padding:12px 20px;z-index:100;box-shadow:0 1px 3px rgba(0,0,0,0.04)}}
.back{{display:inline-flex;align-items:center;gap:6px;color:#0066cc;text-decoration:none;font-weight:500;transition:all 0.2s}}
.back:hover{{gap:10px}}
.back::before{{content:"←"}}
.hero{{width:100%;height:400px;background:#e5e8ec;overflow:hidden;display:flex;align-items:center;justify-content:center}}
.hero img{{width:100%;height:100%;object-fit:cover}}
.hero-placeholder{{font-size:120px;color:#bbb}}
article{{max-width:760px;margin:0 auto;background:white;margin-top:-40px;position:relative;border-radius:12px;padding:48px 40px;box-shadow:0 4px 16px rgba(0,0,0,0.08)}}
h1{{font-size:36px;line-height:1.25;margin-bottom:16px;color:#1a1a1a;letter-spacing:-0.5px}}
.meta{{display:flex;gap:12px;align-items:center;margin-bottom:28px;padding-bottom:20px;border-bottom:1px solid #e5e8ec;font-size:13px;color:#7f8c8d;text-transform:uppercase;letter-spacing:0.5px}}
.meta span::before{{content:"📅"}}
.lead{{font-size:20px;font-weight:500;color:#34495e;margin-bottom:32px;line-height:1.6;border-left:4px solid #0066cc;padding-left:16px}}
.content{{color:#2c3e50}}
p{{margin-bottom:20px;text-align:justify}}
p:first-of-type{{font-weight:500;font-size:18px;color:#34495e}}
a{{color:#0066cc;text-decoration:none;border-bottom:1px solid #cce5ff;transition:all 0.2s}}
a:hover{{border-bottom-color:#0066cc;background:#f0f6ff;padding:0 2px}}
.source{{margin-top:40px;padding-top:20px;border-top:2px solid #e5e8ec;text-align:center;font-size:14px}}
.source a{{display:inline-flex;align-items:center;gap:6px;background:#0066cc;color:white;padding:10px 16px;border-radius:6px;border:none}}
.source a:hover{{background:#0052a3;border:none;background-color:#0052a3;padding:10px 16px}}</style>
<nav class="back-nav"><a href="index.html" class="back">Vissza</a></nav>
{img_html}
<article>
<h1>{html.escape(a["title"])}</h1>
<div class="meta"><span>{html.escape(a["date"])}</span></div>
<p class="lead">{html.escape(a["lead"])}</p>
<div class="content">{body}</div>
<div class="source"><a href="{html.escape(url)}" target="_blank">Eredeti cikk olvasása →</a></div>
</article>
"""


HEADER = """<header class="top">
<div class="header-content">
<div class="header-top-row">
<h1 class="title">📰 Hírek</h1>
<div id="weather" class="weather-widget">
<div class="weather-loading">Időjárás…</div>
</div>
</div>
<div class="header-tools">
<form action="https://www.google.com/search" method="get" role="search">
<input type="search" name="q" placeholder="Keresés a Google-ban…" aria-label="Keresés" required>
<button type="submit">🔍</button>
</form>
</div>
</div>
</header>
<script>
(function () {
  var box = document.getElementById("weather");
  var icons = {
    0: "☀️", 1: "🌤", 2: "⛅", 3: "☁️",
    45: "🌫", 48: "🌫", 51: "🌦", 53: "🌦", 55: "🌧",
    61: "🌧", 63: "🌧", 65: "⛈", 71: "❄️", 73: "❄️",
    75: "❄️", 80: "🌦", 81: "⛈", 82: "⛈", 95: "⛈"
  };
  var url = "https://api.open-meteo.com/v1/forecast?latitude=47.4979&longitude=19.0402" +
    "&current=temperature_2m,weather_code&timezone=Europe%2FBudapest";
  fetch(url).then(function (r) { return r.json(); }).then(function (d) {
    var c = d.current;
    var icon = icons[c.weather_code] || "🌡";
    box.innerHTML = '<div class="weather-content"><span class="weather-icon">' + icon + '</span><span class="weather-temp">' + Math.round(c.temperature_2m) + '°</span></div>';
  }).catch(function () { box.innerHTML = '<span class="weather-icon">—</span>'; });
})();
</script>"""


def make_slug(url, existing_slugs):
    """Generate unique slug from URL, avoiding collisions."""
    base = url.rstrip("/").rsplit("/", 1)[-1] or "index"
    slug = base
    counter = 1
    while slug in existing_slugs:
        slug = f"{base}-{counter}"
        counter += 1
    return slug


def write_index(state):
    rows = "\n".join(
        f'<li><a href="{s["slug"]}.html" class="article-link"><span class="title">{html.escape(s["title"])}</span><span class="date">{s["date"]}</span></a></li>'
        for s in sorted(state.values(), key=lambda s: s["date"], reverse=True)
    )
    (OUT / "index.html").write_text(
        f"""<!doctype html><html lang="hu"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hírek</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{font:16px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;background:linear-gradient(135deg,#f5f7fa 0%,#fafbfc 100%);color:#2c3e50}}
.top{{background:white;border-bottom:1px solid #e5e8ec;padding:24px 20px;position:sticky;top:0;z-index:10;box-shadow:0 2px 8px rgba(0,0,0,0.04)}}
.header-content{{max-width:760px;margin:0 auto}}
.header-top-row{{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}}
.title{{font-size:32px;font-weight:800;color:#1a1a1a;letter-spacing:-0.5px}}
.weather-widget{{background:#f0f3f7;border-radius:12px;padding:8px 16px;min-width:90px}}
.weather-content{{display:flex;align-items:center;gap:8px;justify-content:center}}
.weather-icon{{font-size:28px;line-height:1}}
.weather-temp{{font-size:20px;font-weight:700;color:#2c3e50}}
.weather-loading{{color:#999;font-size:12px;text-align:center}}
.header-tools{{display:flex;gap:12px}}
.top form{{display:flex;gap:8px;flex:0 1 320px}}
.top input{{flex:1;padding:10px 14px;border:2px solid #e5e8ec;border-radius:8px;font:inherit;transition:border-color 0.2s}}
.top input:focus{{outline:none;border-color:#0066cc}}
.top button{{padding:10px 14px;background:#0066cc;color:white;border:none;border-radius:8px;cursor:pointer;font-size:18px;transition:background 0.2s}}
.top button:hover{{background:#0052a3}}
.container{{max-width:760px;margin:0 auto;padding:24px 20px}}
ul{{list-style:none}}
li{{margin-bottom:10px}}
.article-link{{display:flex;justify-content:space-between;align-items:center;padding:18px 20px;background:white;border-radius:10px;text-decoration:none;color:inherit;transition:all 0.3s cubic-bezier(0.4,0,0.2,1);border:2px solid transparent;border-left:4px solid transparent}}
.article-link:hover{{background:#f8fafc;border-left-color:#0066cc;border-color:#e5e8ec;box-shadow:0 4px 12px rgba(0,102,204,0.1);transform:translateX(4px)}}
.article-link .title{{font-weight:600;color:#0066cc;flex:1;font-size:16px}}
.article-link .date{{color:#999;font-size:13px;flex-shrink:0;margin-left:16px;letter-spacing:0.3px}}</style>
{HEADER}
<div class="container"><ul>{rows}</ul></div>""",
        encoding="utf-8",
    )


def main():
    OUT.mkdir(exist_ok=True)
    state = json.loads(STATE.read_text(encoding="utf-8")) if STATE.exists() else {}
    existing_slugs = {s["slug"] for s in state.values()}
    fetched = 0
    for url, pub in sitemap_entries().items():
        if url in state:
            continue
        try:
            a = parse(fetch(url))
        except Exception as e:  # keep going if one article fails
            print("skip", url, e)
            continue
        if not a["title"]:
            print("skip", url, "no title")
            continue
        slug = make_slug(url, existing_slugs)
        existing_slugs.add(slug)
        (OUT / f"{slug}.html").write_text(render(a, url), encoding="utf-8")
        state[url] = {"slug": slug, "title": a["title"], "date": a["date"] or pub[:10]}
        fetched += 1
        time.sleep(DELAY_S)
    # drop articles older than KEEP_DAYS so the index and folder stay small
    cutoff = time.strftime("%Y-%m-%d", time.gmtime(time.time() - KEEP_DAYS * 86400))
    for url in [u for u, s in state.items() if s["date"] < cutoff]:
        (OUT / f"{state[url]['slug']}.html").unlink(missing_ok=True)
        del state[url]
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    write_index(state)
    print(f"fetched {fetched} new, {len(state)} articles in index")


if __name__ == "__main__":
    main()
