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
    img = f'<img src="{html.escape(a["image"])}" alt="">' if a["image"] else ""
    return f"""<!doctype html><html lang="hu"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(a["title"])}</title>
<style>body{{font:18px/1.6 system-ui,sans-serif;max-width:680px;margin:auto;padding:16px}}
img{{max-width:100%;height:auto}}a{{color:#0a58ca}}</style>
<p><a href="index.html">← Vissza</a></p>
<h1>{html.escape(a["title"])}</h1>
<p><em>{html.escape(a["date"])}</em></p>
<p><strong>{html.escape(a["lead"])}</strong></p>
{img}
{body}
<p><a href="{html.escape(url)}">Eredeti cikk</a></p>
"""


HEADER = """<header class="top">
<form action="https://www.google.com/search" method="get" role="search">
<input type="search" name="q" placeholder="Keresés a Google-ban" aria-label="Keresés" required>
<button type="submit">Keresés</button>
</form>
<div id="weather" class="weather">Időjárás betöltése…</div>
</header>
<script>
(function () {
  var box = document.getElementById("weather");
  var names = {0: "derült", 1: "túlnyomóan derült", 2: "részben felhős", 3: "borult",
    45: "köd", 48: "zúzmarás köd", 51: "gyenge szitálás", 53: "szitálás", 55: "erős szitálás",
    61: "gyenge eső", 63: "eső", 65: "erős eső", 71: "gyenge havazás", 73: "havazás",
    75: "erős havazás", 80: "zápor", 81: "erős zápor", 82: "heves zápor", 95: "zivatar"};
  // Budapest; change latitude/longitude for another town
  var url = "https://api.open-meteo.com/v1/forecast?latitude=47.4979&longitude=19.0402" +
    "&current=temperature_2m,weather_code&timezone=Europe%2FBudapest";
  fetch(url).then(function (r) { return r.json(); }).then(function (d) {
    var c = d.current;
    box.textContent = "Budapest: " + Math.round(c.temperature_2m) + " °C, " +
      (names[c.weather_code] || "");
  }).catch(function () { box.textContent = "Az időjárás most nem elérhető."; });
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
        f'<li><a href="{s["slug"]}.html">{html.escape(s["title"])}</a> <small>{s["date"]}</small></li>'
        for s in sorted(state.values(), key=lambda s: s["date"], reverse=True)
    )
    (OUT / "index.html").write_text(
        f"""<!doctype html><html lang="hu"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hírek</title>
<style>body{{font:18px/1.5 system-ui,sans-serif;max-width:680px;margin:auto;padding:16px}}li{{margin:.6em 0}}
.top{{display:flex;flex-direction:column;gap:10px;margin-bottom:24px}}
.top form{{display:flex;gap:8px}}.top input{{flex:1;font:inherit;padding:8px}}
.top button{{font:inherit;padding:8px 14px}}.weather{{color:#555;font-size:16px}}</style>
{HEADER}
<h1>Hírek</h1><ul>{rows}</ul>""",
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
