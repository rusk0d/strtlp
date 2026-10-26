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
    img_html = f'<img class="hero-img" src="{html.escape(a["image"])}" alt="Cikk képe">' if a["image"] else '<div class="hero-placeholder">📰</div>'
    return f"""<!doctype html><html lang="hu"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(a["title"])}</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{font:14px/1.6 Arial,sans-serif;background:#a8c5dd;color:#333}}
.header{{background:#6b92c1;padding:12px 20px}}
.back{{color:#fff;text-decoration:none;font-weight:bold;font-size:13px}}
.back:hover{{text-decoration:underline}}
.container{{max-width:800px;margin:20px auto;padding:0 20px}}
.hero-img{{width:100%;max-height:400px;object-fit:cover;border-radius:4px;margin-bottom:20px}}
.hero-placeholder{{width:100%;height:300px;background:#e0e0e0;border-radius:4px;display:flex;align-items:center;justify-content:center;font-size:80px;margin-bottom:20px}}
article{{background:white;padding:28px;border-radius:4px;margin-bottom:20px}}
h1{{font-size:26px;font-weight:bold;color:#333;margin-bottom:12px;line-height:1.3}}
.meta{{display:flex;gap:12px;margin-bottom:20px;padding-bottom:12px;border-bottom:1px solid #ddd;font-size:12px;color:#999}}
.lead{{font-size:15px;font-weight:bold;color:#333;margin-bottom:20px;line-height:1.6;padding:12px;background:#f5f5f5;border-left:3px solid #f39200}}
.content{{color:#333;font-size:14px}}
.content p{{margin-bottom:16px;text-align:justify}}
a{{color:#0066cc;text-decoration:none}}
a:hover{{text-decoration:underline}}
.source{{margin-top:24px;padding-top:12px;border-top:1px solid #ddd;text-align:center}}
.source a{{display:inline-block;background:#f39200;color:white;padding:10px 16px;border-radius:3px;font-weight:bold;text-decoration:none;font-size:13px}}
.source a:hover{{background:#e08700;text-decoration:none}}</style>
<div class="header"><a href="index.html" class="back">← Vissza a hírlistához</a></div>
<div class="container">
{img_html}
<article>
<h1>{html.escape(a["title"])}</h1>
<div class="meta"><span>📅 {html.escape(a["date"])}</span></div>
<p class="lead">{html.escape(a["lead"])}</p>
<div class="content">{body}</div>
</article>
<div class="source"><a href="{html.escape(url)}" target="_blank">Eredeti cikk a Starlapnál →</a></div>
</div>
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
    articles = sorted(state.values(), key=lambda s: s["date"], reverse=True)
    featured = articles[:3] if articles else []
    rest = articles[3:] if len(articles) > 3 else []

    featured_html = "\n".join(
        f'<li class="featured-item"><a href="{a["slug"]}.html"><span class="label">Kiemelt</span><h3>{html.escape(a["title"])}</h3><span class="date">{a["date"]}</span></a></li>'
        for a in featured
    )

    grid_html = "\n".join(
        f'<li class="grid-item"><a href="{a["slug"]}.html"><div class="thumb">📰</div><h4>{html.escape(a["title"][:60])}</h4><span class="date">{a["date"]}</span></a></li>'
        for a in rest
    )

    (OUT / "index.html").write_text(
        f"""<!doctype html><html lang="hu"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hírek - Startlap</title>
<style>*{{margin:0;padding:0;box-sizing:border-box}}
body{{font:14px/1.5 Arial,sans-serif;background:#a8c5dd;color:#333}}
.header{{background:#6b92c1;padding:16px 20px;text-align:center}}
.logo{{font-size:24px;font-weight:bold;color:#fff;margin-bottom:12px}}
.nav-tabs{{background:#5a7fa8;display:flex;gap:2px;padding:0 20px;overflow-x:auto}}
.nav-tabs a{{padding:10px 14px;color:#fff;text-decoration:none;font-size:12px;font-weight:bold;background:#5a7fa8;border-right:1px solid #4a6f98}}
.nav-tabs a:hover{{background:#4a6f98}}
.wrapper{{max-width:1200px;margin:0 auto;display:grid;grid-template-columns:1fr 280px;gap:20px;padding:20px;background:#a8c5dd;min-height:100vh}}
.main{{display:flex;flex-direction:column;gap:20px}}
.featured{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px}}
.featured-item{{list-style:none;background:white;border-radius:4px;overflow:hidden;transition:transform 0.2s}}
.featured-item a{{text-decoration:none;color:inherit;display:flex;flex-direction:column;height:100%;padding:12px}}
.featured-item .label{{font-size:11px;color:#f39200;font-weight:bold;margin-bottom:8px}}
.featured-item h3{{font-size:14px;font-weight:bold;color:#333;line-height:1.4;flex:1;margin-bottom:8px}}
.featured-item .date{{font-size:11px;color:#999}}
.featured-item:hover{{transform:scale(1.02);box-shadow:0 2px 8px rgba(0,0,0,0.15)}}
.grid-section{{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;background:white;padding:12px;border-radius:4px}}
.grid-item{{list-style:none;text-align:center;transition:all 0.2s}}
.grid-item a{{text-decoration:none;color:inherit;display:flex;flex-direction:column;padding:8px}}
.grid-item .thumb{{font-size:40px;height:60px;display:flex;align-items:center;justify-content:center;background:#f0f0f0;border-radius:3px;margin-bottom:8px}}
.grid-item h4{{font-size:12px;font-weight:bold;color:#333;line-height:1.3;text-align:left}}
.grid-item .date{{font-size:10px;color:#999;margin-top:4px;text-align:left}}
.grid-item:hover{{background:#f9f9f9;padding:8px}}
.sidebar{{background:white;border-radius:4px;padding:12px;height:fit-content;position:sticky;top:20px}}
.sidebar-title{{font-size:13px;font-weight:bold;color:#333;margin-bottom:12px;padding-bottom:8px;border-bottom:2px solid #f39200}}
.weather-box{{background:#f0f0f0;padding:12px;border-radius:3px;text-align:center;margin-bottom:12px}}
.weather-content{{display:flex;flex-direction:column;align-items:center;gap:6px}}
.weather-icon{{font-size:32px}}
.weather-temp{{font-size:18px;font-weight:bold;color:#333}}
.sidebar-section{{margin-bottom:16px}}
.sidebar-item{{font-size:11px;line-height:1.4;margin-bottom:8px;padding-bottom:8px;border-bottom:1px solid #eee}}
.sidebar-item a{{color:#0066cc;text-decoration:none}}
.sidebar-item a:hover{{text-decoration:underline}}</style>
<div class="header">
<div class="logo">Startlap Hírek</div>
</div>
<div class="nav-tabs">
<a href="#friss">FRISS</a>
<a href="#buzar">Buzár</a>
<a href="#sport">Sport</a>
<a href="#utzas">Utazás</a>
<a href="#tech">Tech</a>
<a href="#eletmod">Életmód</a>
</div>
<div class="wrapper">
<div class="main">
<section class="featured">
{featured_html}
</section>
<section class="grid-section">
{grid_html}
</section>
</div>
<aside class="sidebar">
<div class="sidebar-title">🌦 BUDAPEST</div>
<div class="weather-box">
<div class="weather-content">
<div id="weather" class="weather-widget">
<div class="weather-loading">Betöltés…</div>
</div>
</div>
</div>
<div class="sidebar-title">Kedvelt Cikkek</div>
<div class="sidebar-section">
{chr(10).join(f'<div class="sidebar-item"><a href="{a["slug"]}.html">→ {html.escape(a["title"][:35])}</a></div>' for a in rest[:5])}
</div>
</aside>
</div>
<script>
(function () {{
  var box = document.querySelector('.weather-widget');
  var icons = {{
    0: "☀️", 1: "🌤", 2: "⛅", 3: "☁️",
    45: "🌫", 48: "🌫", 51: "🌦", 53: "🌦", 55: "🌧",
    61: "🌧", 63: "🌧", 65: "⛈", 71: "❄️", 73: "❄️",
    75: "❄️", 80: "🌦", 81: "⛈", 82: "⛈", 95: "⛈"
  }};
  var url = "https://api.open-meteo.com/v1/forecast?latitude=47.4979&longitude=19.0402" +
    "&current=temperature_2m,weather_code&timezone=Europe%2FBudapest";
  fetch(url).then(function (r) {{ return r.json(); }}).then(function (d) {{
    var c = d.current;
    var icon = icons[c.weather_code] || "🌡";
    box.innerHTML = '<div class="weather-icon">' + icon + '</div><div class="weather-temp">' + Math.round(c.temperature_2m) + '°</div>';
  }}).catch(function () {{ box.innerHTML = '<div class="weather-icon">—</div>'; }});
}})();
</script>""",
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

    # regenerate all article pages (in case they were deleted or it's first build of new design)
    for url in state:
        slug = state[url]["slug"]
        if not (OUT / f"{slug}.html").exists():
            try:
                a = parse(fetch(url))
                if a["title"]:
                    (OUT / f"{slug}.html").write_text(render(a, url), encoding="utf-8")
                    time.sleep(0.5)
            except Exception:
                pass

    write_index(state)
    print(f"fetched {fetched} new, {len(state)} articles in index")


if __name__ == "__main__":
    main()
