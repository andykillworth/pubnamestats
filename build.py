#!/usr/bin/env python3
"""Build pubnamestats.co.uk from data/pubs.csv (OpenStreetMap export).

No dependencies beyond the Python standard library. Output goes to dist/.
Cloudflare Pages: build command `python3 build.py`, output directory `dist`.
"""
import csv
import html
import json
import os
import re
import shutil
from collections import Counter, defaultdict
from datetime import date

SITE = "https://pubnamestats.co.uk"
DATA = "data/pubs.csv"
OUT = "dist"
BUILD_DATE = date.today().isoformat()

# Name pages are built for names shared by at least this many pubs.
MIN_NAME_PAGE = 2
# Word pages are built for words appearing in at least this many distinct names.
MIN_WORD_NAMES = 5

POSTCODE_AREAS = {
    "AB": "Aberdeen", "AL": "St Albans", "B": "Birmingham", "BA": "Bath", "BB": "Blackburn",
    "BD": "Bradford", "BH": "Bournemouth", "BL": "Bolton", "BN": "Brighton", "BR": "Bromley",
    "BS": "Bristol", "BT": "Belfast", "CA": "Carlisle", "CB": "Cambridge", "CF": "Cardiff",
    "CH": "Chester", "CM": "Chelmsford", "CO": "Colchester", "CR": "Croydon", "CT": "Canterbury",
    "CV": "Coventry", "CW": "Crewe", "DA": "Dartford", "DD": "Dundee", "DE": "Derby",
    "DG": "Dumfries", "DH": "Durham", "DL": "Darlington", "DN": "Doncaster", "DT": "Dorchester",
    "DY": "Dudley", "E": "East London", "EC": "East Central London", "EH": "Edinburgh",
    "EN": "Enfield", "EX": "Exeter", "FK": "Falkirk", "FY": "Blackpool", "G": "Glasgow",
    "GL": "Gloucester", "GU": "Guildford", "HA": "Harrow", "HD": "Huddersfield", "HG": "Harrogate",
    "HP": "Hemel Hempstead", "HR": "Hereford", "HS": "Outer Hebrides", "HU": "Hull",
    "HX": "Halifax", "IG": "Ilford", "IP": "Ipswich", "IV": "Inverness", "KA": "Kilmarnock",
    "KT": "Kingston upon Thames", "KW": "Kirkwall", "KY": "Kirkcaldy", "L": "Liverpool",
    "LA": "Lancaster", "LD": "Llandrindod Wells", "LE": "Leicester", "LL": "Llandudno",
    "LN": "Lincoln", "LS": "Leeds", "LU": "Luton", "M": "Manchester", "ME": "Medway",
    "MK": "Milton Keynes", "ML": "Motherwell", "N": "North London", "NE": "Newcastle upon Tyne",
    "NG": "Nottingham", "NN": "Northampton", "NP": "Newport", "NR": "Norwich",
    "NW": "North West London", "OL": "Oldham", "OX": "Oxford", "PA": "Paisley", "PE": "Peterborough",
    "PH": "Perth", "PL": "Plymouth", "PO": "Portsmouth", "PR": "Preston", "RG": "Reading",
    "RH": "Redhill", "RM": "Romford", "S": "Sheffield", "SA": "Swansea", "SE": "South East London",
    "SG": "Stevenage", "SK": "Stockport", "SL": "Slough", "SM": "Sutton", "SN": "Swindon",
    "SO": "Southampton", "SP": "Salisbury", "SR": "Sunderland", "SS": "Southend-on-Sea",
    "ST": "Stoke-on-Trent", "SW": "South West London", "SY": "Shrewsbury", "TA": "Taunton",
    "TD": "Galashiels", "TF": "Telford", "TN": "Tonbridge", "TQ": "Torquay", "TR": "Truro",
    "TS": "Cleveland", "TW": "Twickenham", "UB": "Southall", "W": "West London",
    "WA": "Warrington", "WC": "West Central London", "WD": "Watford", "WF": "Wakefield",
    "WN": "Wigan", "WR": "Worcester", "WS": "Walsall", "WV": "Wolverhampton", "YO": "York",
    "ZE": "Lerwick",
}

# Suffixes stripped when grouping names ("Red Lion Inn" -> "red lion").
SUFFIXES = ["public house", "inn", "tavern", "hotel", "pub", "bar"]
# Don't strip a suffix if what remains is one of these on its own ("New Inn" stays "new inn").
KEEP_SUFFIX_IF_LEFT = {
    "new", "old", "top", "bottom", "halfway", "half way", "first", "last", "central",
    "little", "great", "village", "county", "royal", "kings", "queens", "station", "union",
    "market", "bridge", "end", "corner", "cross", "hill", "town", "city", "country", "travellers",
}
# Words not worth a word page.
STOPWORDS = {
    "and", "the", "of", "in", "at", "on", "a", "to", "st", "ye", "de", "y", "le", "la", "an",
    "n", "s", "by", "for", "with", "old", "new", "inn", "bar", "pub", "hotel", "tavern", "house",
    "public", "club", "lounge", "kitchen", "dining", "room", "rooms", "&",
}


def normalise(name: str) -> str:
    s = name.lower().replace("&", " and ").replace("’", "'").replace("`", "'")
    s = s.replace("'", "")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"^(the|ye)\s+", "", s)
    s = re.sub(r"\bolde\b", "old", s)
    s = re.sub(r"\bsaint\b", "st", s)
    for suf in SUFFIXES:
        if s.endswith(" " + suf):
            rest = s[: -len(suf) - 1].strip()
            if rest and rest not in KEEP_SUFFIX_IF_LEFT:
                s = rest
            break
    return s


def slugify(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def postcode_area(pc: str):
    m = re.match(r"([A-Z]{1,2})\d", pc.strip().upper())
    return m.group(1) if m and m.group(1) in POSTCODE_AREAS else None


def esc(s) -> str:
    return html.escape(str(s), quote=True)


def fmt(n: int) -> str:
    return f"{n:,}"


def ordinal(n: int) -> str:
    suf = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suf}"


# ---------------------------------------------------------------- load data

def load():
    pubs = []
    with open(DATA, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row["name"].strip()
            if not name:
                continue
            key = normalise(name)
            if not key:
                continue
            pubs.append({
                "osm": f'{row["@type"]}/{row["@id"]}',
                "lat": float(row["@lat"]),
                "lon": float(row["@lon"]),
                "name": name,
                "key": key,
                "postcode": row["addr:postcode"].strip().upper(),
                "area": postcode_area(row["addr:postcode"]),
                "town": row["addr:city"].strip(),
                "operator": row["operator"].strip(),
            })
    return pubs


# ---------------------------------------------------------------- map (SVG)

LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 49.85, 60.9, -8.2, 1.8
MAP_W = 300


def project(lat, lon):
    # Simple equirectangular with latitude correction; good enough for a dot map.
    import math
    k = math.cos(math.radians(54.5))
    x = (lon - LON_MIN) * k
    y = LAT_MAX - lat
    w = (LON_MAX - LON_MIN) * k
    scale = MAP_W / w
    return x * scale, y * scale


MAP_H = round(project(LAT_MIN, LON_MIN)[1])


def background_svg(pubs):
    cells = set()
    for p in pubs:
        x, y = project(p["lat"], p["lon"])
        cells.add((round(x), round(y)))
    dots = "".join(f'<rect x="{x}" y="{y}" width="1" height="1"/>' for x, y in sorted(cells))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {MAP_W} {MAP_H}">'
            f'<g fill="#d6d0c4">{dots}</g></svg>')


def dot_map(points, label):
    dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="2.2"/>'
        for x, y in (project(p["lat"], p["lon"]) for p in points)
    )
    return (f'<figure class="map"><svg viewBox="0 0 {MAP_W} {MAP_H}" role="img" aria-label="{esc(label)}">'
            f'<image href="/uk-pubs.svg" width="{MAP_W}" height="{MAP_H}"/>'
            f'<g fill="#9b2c1f" fill-opacity="0.75">{dots}</g></svg>'
            f'<figcaption>{esc(label)}. Grey dots show every pub in the UK.</figcaption></figure>')


# ---------------------------------------------------------------- page shell

CSS = """
:root{--ink:#2a211b;--muted:#6f6357;--bg:#faf7f1;--card:#fff;--accent:#9b2c1f;--rule:#e6dfd3}
*{box-sizing:border-box}body{margin:0;font:17px/1.6 Georgia,'Times New Roman',serif;color:var(--ink);background:var(--bg)}
a{color:var(--accent)}header,main,footer{max-width:860px;margin:0 auto;padding:0 20px}
header{padding-top:18px;display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px}
header .brand{font-weight:bold;font-size:20px;text-decoration:none;color:var(--ink)}
header nav a{margin-left:14px;font-size:15px}
h1{font-size:32px;line-height:1.2;margin:28px 0 8px}h2{font-size:22px;margin-top:36px;border-top:1px solid var(--rule);padding-top:20px}
.lede{font-size:20px}.big{font-size:54px;font-weight:bold;color:var(--accent);line-height:1}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:20px 0}
.stat{background:var(--card);border:1px solid var(--rule);padding:12px 14px}.stat b{display:block;font-size:26px}
.stat span{color:var(--muted);font-size:14px}
table{border-collapse:collapse;width:100%;background:var(--card);font-size:15px}
th,td{text-align:left;padding:6px 10px;border-bottom:1px solid var(--rule)}th{font-size:13px;color:var(--muted);text-transform:uppercase;letter-spacing:.04em}
td.n{text-align:right;font-variant-numeric:tabular-nums}
.map{margin:6px 0 20px 24px;width:300px;float:right}@media(max-width:700px){.map{float:none;margin:20px auto}}h2{clear:both}.map svg{width:100%;height:auto;background:var(--card);border:1px solid var(--rule)}
figcaption{font-size:13px;color:var(--muted)}
.cols{columns:3 200px;font-size:15px}.cols a{display:block}
.az a{display:inline-block;margin:0 6px 6px 0;padding:2px 8px;border:1px solid var(--rule);background:var(--card);text-decoration:none}
footer{margin-top:60px;padding-bottom:40px;font-size:13px;color:var(--muted);border-top:1px solid var(--rule);padding-top:16px}
"""


def page(path, title, description, body, breadcrumbs=None):
    canonical = SITE + path
    crumbs_html = ""
    ld = []
    if breadcrumbs:
        items = [("Home", "/")] + breadcrumbs
        crumbs_html = '<p style="font-size:14px;margin-top:20px">' + " › ".join(
            f'<a href="{u}">{esc(t)}</a>' if i < len(items) - 1 else esc(t)
            for i, (t, u) in enumerate(items)) + "</p>"
        ld.append({
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": t, "item": SITE + u}
                for i, (t, u) in enumerate(items)
            ],
        })
    ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in ld)
    doc = f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<link rel="canonical" href="{canonical}">
<link rel="stylesheet" href="/style.css">
{ld_html}
</head><body>
<header><a class="brand" href="/">Pub Name Stats</a>
<nav><a href="/most-common-pub-names/">Most common</a><a href="/names/">A–Z</a><a href="/areas/">Areas</a><a href="/words/">Words</a></nav></header>
<main>{crumbs_html}{body}</main>
<footer>Pub data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, available under the Open Database Licence. Names are grouped so that “The Red Lion”, “Red Lion” and “Red Lion Inn” count as one name. Data updated {BUILD_DATE}. <a href="/about/">About and methodology</a>.</footer>
</body></html>"""
    out = os.path.join(OUT, path.strip("/"), "index.html") if path != "/" else os.path.join(OUT, "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    SITEMAP.append(path)


SITEMAP = []


def name_table(rows, show_rank=True):
    """rows: list of (rank, display, slug_or_None, count)"""
    head = "<tr>" + ("<th>Rank</th>" if show_rank else "") + "<th>Name</th><th>Pubs</th></tr>"
    body = "".join(
        "<tr>" + (f'<td class="n">{r}</td>' if show_rank else "")
        + (f'<td><a href="/name/{s}/">{esc(d)}</a></td>' if s else f"<td>{esc(d)}</td>")
        + f'<td class="n">{fmt(c)}</td></tr>'
        for r, d, s, c in rows
    )
    return f"<table>{head}{body}</table>"


# ---------------------------------------------------------------- build

def main():
    pubs = load()
    total = len(pubs)

    by_key = defaultdict(list)
    for p in pubs:
        by_key[p["key"]].append(p)

    # Display name = the most common way the name is written, minus a leading "The".
    def display(key):
        variants = Counter(p["name"] for p in by_key[key])
        best = variants.most_common(1)[0][0]
        best = re.sub(r"^the\s+", "", best, flags=re.I)
        return "The " + best if not re.match(r"^(ye|y)\b", best, re.I) else best

    ranked = sorted(by_key, key=lambda k: (-len(by_key[k]), k))
    rank_of = {}
    prev, rnk = None, 0
    for i, k in enumerate(ranked, 1):
        if len(by_key[k]) != prev:
            rnk, prev = i, len(by_key[k])
        rank_of[k] = rnk
    disp = {k: display(k) for k in ranked}
    page_keys = [k for k in ranked if len(by_key[k]) >= MIN_NAME_PAGE]
    has_page = set(page_keys)
    slug = {k: slugify(k) for k in page_keys}
    unique_count = sum(1 for k in ranked if len(by_key[k]) == 1)

    def link(k):
        return f'<a href="/name/{slug[k]}/">{esc(disp[k])}</a>' if k in has_page else esc(disp[k])

    # Words
    word_names = defaultdict(set)
    for k in ranked:
        for w in set(k.split()):
            if w not in STOPWORDS and not w.isdigit() and len(w) > 1:
                word_names[w].add(k)
    word_pubs = {w: sum(len(by_key[k]) for k in ks) for w, ks in word_names.items()}
    words = sorted((w for w, ks in word_names.items() if len(ks) >= MIN_WORD_NAMES and word_pubs[w] >= 10),
                   key=lambda w: (-word_pubs[w], w))

    # Areas
    by_area = defaultdict(list)
    for p in pubs:
        if p["area"]:
            by_area[p["area"]].append(p)
    area_slug = {a: f"{a.lower()}-{slugify(POSTCODE_AREAS[a])}" for a in by_area}
    area_share = {}  # key -> Counter(area)
    for k in ranked:
        area_share[k] = Counter(p["area"] for p in by_key[k] if p["area"])

    if os.path.exists(OUT):
        shutil.rmtree(OUT)
    os.makedirs(OUT)
    with open(os.path.join(OUT, "style.css"), "w") as f:
        f.write(CSS)
    with open(os.path.join(OUT, "uk-pubs.svg"), "w") as f:
        f.write(background_svg(pubs))

    # ---- name pages
    for k in page_keys:
        ps = by_key[k]
        n = len(ps)
        d = disp[k]
        rank = rank_of[k]
        share = n / total * 100
        variants = Counter(p["name"] for p in ps).most_common()
        areas = area_share[k].most_common()
        top_area = areas[0] if areas else None
        towns = Counter(p["town"] for p in ps if p["town"]).most_common(10)
        ops = Counter(p["operator"] for p in ps if p["operator"]).most_common(5)
        north = max(ps, key=lambda p: p["lat"])
        south = min(ps, key=lambda p: p["lat"])

        answer = (f"There are <strong>{fmt(n)}</strong> pubs called {esc(d)} in the UK, "
                  + ("making it the most common pub name" if rank == 1 else f"making it the {ordinal(rank)} most common pub name")
                  + (" (joint)" if sum(1 for x in ranked if len(by_key[x]) == n) > 1 else "")
                  + f". That's {share:.2f}% of the {fmt(total)} named pubs we track.")
        body = [f"<h1>How many pubs are called {esc(d)}?</h1>",
                f'<p class="big">{fmt(n)}</p><p class="lede">{answer}</p>',
                '<div class="stats">',
                f'<div class="stat"><b>{ordinal(rank)}</b><span>most common UK pub name</span></div>',
                f'<div class="stat"><b>{len(variants)}</b><span>ways of writing it</span></div>',
                f'<div class="stat"><b>{len(areas)}</b><span>postcode areas</span></div>']
        if top_area:
            a = top_area[0]
            body.append(f'<div class="stat"><b>{esc(POSTCODE_AREAS[a])}</b><span>area with the most ({top_area[1]})</span></div>')
        body.append("</div>")
        body.append(dot_map(ps, f"Map of every pub called {d}"))
        def where(p):
            return p["town"] or (POSTCODE_AREAS[p["area"]] + " area" if p["area"] else None)
        if n > 1 and where(north) and where(south):
            body.append(f"<p>The most northerly {esc(d)} is in {esc(where(north))}, "
                        f"and the most southerly is in {esc(where(south))}.</p>")

        body.append("<h2>How the name is written</h2>")
        body.append("<table><tr><th>As written on the sign</th><th>Pubs</th></tr>" + "".join(
            f'<tr><td>{esc(v)}</td><td class="n">{c}</td></tr>' for v, c in variants) + "</table>")

        if areas:
            body.append(f"<h2>Where the {esc(d)} pubs are</h2>")
            body.append("<table><tr><th>Postcode area</th><th>Pubs</th></tr>" + "".join(
                f'<tr><td><a href="/area/{area_slug[a]}/">{esc(POSTCODE_AREAS[a])} ({a})</a></td><td class="n">{c}</td></tr>'
                for a, c in areas) + "</table>")
            missing = n - sum(c for _, c in areas)
            if missing:
                body.append(f"<p><small>{missing} pub{'s have' if missing != 1 else ' has'} no postcode recorded.</small></p>")
        if towns and towns[0][1] > 1:
            body.append("<h2>Towns with more than one</h2><ul>" + "".join(
                f"<li>{esc(t)}: {c}</li>" for t, c in towns if c > 1) + "</ul>")
        if ops:
            body.append("<h2>Who runs them</h2><p>Where an operator is recorded: " + ", ".join(
                f"{esc(o)} ({c})" for o, c in ops) + ".</p>")

        body.append(f"<h2>Every {esc(d)} in the UK</h2>")
        rows = sorted(ps, key=lambda p: (p["area"] or "ZZ", p["town"], p["postcode"]))
        body.append("<table><tr><th>Name</th><th>Town</th><th>Postcode</th><th>Map</th></tr>" + "".join(
            f'<tr><td>{esc(p["name"])}</td><td>{esc(p["town"])}</td><td>{esc(p["postcode"])}</td>'
            f'<td><a href="https://www.openstreetmap.org/{p["osm"]}" rel="nofollow">OSM</a></td></tr>'
            for p in rows) + "</table>")

        # related names via shared words
        related = Counter()
        for w in k.split():
            if w in word_names and w not in STOPWORDS:
                for other in word_names[w]:
                    if other != k and other in has_page:
                        related[other] = len(by_key[other])
        if related:
            body.append("<h2>Similar pub names</h2><div class='cols'>" + "".join(
                link(o) for o, _ in related.most_common(24)) + "</div>")
        word_links = [w for w in k.split() if w in words]
        if word_links:
            body.append("<p>More pubs with " + ", ".join(
                f'<a href="/word/{w}/">“{esc(w.title())}” in the name</a>' for w in word_links) + ".</p>")

        title = f"How Many Pubs Are Called {d}? {fmt(n)} in the UK | Pub Name Stats"
        desc = f"There are {fmt(n)} pubs called {d} in the UK, the {ordinal(rank)} most common pub name. See where they are, how the name is written and the full list."
        page(f"/name/{slug[k]}/", title, desc, "".join(body),
             [("Pub names A–Z", "/names/"), (d, f"/name/{slug[k]}/")])

    # ---- word pages
    for w in words:
        ks = sorted(word_names[w], key=lambda k: (-len(by_key[k]), k))
        n_pubs = word_pubs[w]
        rows = [(rank_of[k], disp[k], slug.get(k), len(by_key[k])) for k in ks]
        body = (f"<h1>Pubs with “{esc(w.title())}” in the name</h1>"
                f'<p class="big">{fmt(n_pubs)}</p>'
                f"<p class='lede'>{fmt(n_pubs)} UK pubs have “{esc(w.title())}” in their name, across "
                f"{fmt(len(ks))} different pub names. The most common is {link(ks[0])} ({fmt(len(by_key[ks[0]]))}).</p>"
                + dot_map([p for k in ks for p in by_key[k]], f"Map of pubs with {w.title()} in the name")
                + "<h2>Every name</h2>" + name_table(rows, show_rank=False))
        page(f"/word/{w}/", f"Pubs With “{w.title()}” in the Name: {fmt(n_pubs)} in the UK | Pub Name Stats",
             f"{fmt(n_pubs)} UK pubs have {w.title()} in the name, across {len(ks)} different names. See them all ranked.",
             body, [("Words", "/words/"), (w.title(), f"/word/{w}/")])

    # ---- area pages
    for a, ps in by_area.items():
        name = POSTCODE_AREAS[a]
        c = Counter(p["key"] for p in ps)
        top = c.most_common(30)
        only_here = sorted([k for k in c if len(by_key[k]) >= 2 and area_share[k].get(a) == len(by_key[k])],
                           key=lambda k: -len(by_key[k]))
        over = sorted(
            [k for k in c if c[k] >= 3],
            key=lambda k: -(c[k] / len(ps)) / (len(by_key[k]) / total))[:10]
        body = (f"<h1>Pub names in {esc(name)} ({a})</h1>"
                f'<p class="lede">We track <strong>{fmt(len(ps))}</strong> pubs in the {a} postcode area, with '
                f"{fmt(len(c))} different names. The most common is {link(top[0][0])} ({top[0][1]}).</p>"
                + dot_map(ps, f"Pubs in the {a} postcode area")
                + "<h2>Most common names</h2>"
                + name_table([(i, disp[k], slug.get(k), n) for i, (k, n) in enumerate(top, 1)]))
        if over:
            body += ("<h2>Names that are unusually common here</h2><p>Compared with the rest of the UK:</p><ul>"
                     + "".join(f"<li>{link(k)}: {c[k]} here, {len(by_key[k])} UK-wide</li>" for k in over) + "</ul>")
        if only_here:
            body += ("<h2>Names you'll only find here</h2><p>Shared by more than one pub, but none outside " + esc(name) + ":</p><ul>"
                     + "".join(f"<li>{link(k)} ({len(by_key[k])})</li>" for k in only_here[:20]) + "</ul>")
        page(f"/area/{area_slug[a]}/", f"Most Common Pub Names in {name} ({a}) | Pub Name Stats",
             f"The most common pub names in the {a} ({name}) postcode area, from {fmt(len(ps))} pubs. Plus names you'll only find there.",
             body, [("Areas", "/areas/"), (f"{name} ({a})", f"/area/{area_slug[a]}/")])

    # ---- index pages
    top500 = [(rank_of[k], disp[k], slug.get(k), len(by_key[k])) for k in ranked[:500]]
    page("/most-common-pub-names/", "The 500 Most Common Pub Names in the UK | Pub Name Stats",
         f"The most common pub names in the UK, ranked from {fmt(total)} pubs. The Red Lion, The Crown and The Royal Oak lead the list.",
         f"<h1>The most common pub names in the UK</h1><p class='lede'>Ranked from {fmt(total)} named pubs.</p>"
         + name_table(top500), [("Most common pub names", "/most-common-pub-names/")])

    letters = defaultdict(list)
    for k in page_keys:
        letters[disp[k].removeprefix("The ")[0].upper() if disp[k].removeprefix("The ")[0].isalpha() else "#"].append(k)
    az = "<p class='az'>" + "".join(f'<a href="/names/{l.lower() if l != "#" else "0-9"}/">{l}</a>' for l in sorted(letters)) + "</p>"
    for l, ks in letters.items():
        ks.sort(key=lambda k: disp[k].removeprefix("The ").lower())
        ls = l.lower() if l != "#" else "0-9"
        page(f"/names/{ls}/", f"Pub Names Beginning With {l} | Pub Name Stats",
             f"Every UK pub name beginning with {l} that's shared by more than one pub, with counts.",
             f"<h1>Pub names beginning with {l}</h1>{az}<div class='cols'>"
             + "".join(f'<a href="/name/{slug[k]}/">{esc(disp[k])} ({len(by_key[k])})</a>' for k in ks) + "</div>",
             [("Pub names A–Z", "/names/"), (l, f"/names/{ls}/")])
    page("/names/", "UK Pub Names A–Z | Pub Name Stats",
         "Browse every UK pub name shared by more than one pub, A to Z.",
         f"<h1>Pub names A–Z</h1><p>{fmt(len(page_keys))} names shared by more than one pub. "
         f"Another {fmt(unique_count)} names belong to just one pub.</p>{az}", [("Pub names A–Z", "/names/")])

    page("/words/", "Most Common Words in UK Pub Names | Pub Name Stats",
         "The words that appear most often in UK pub names: Arms, Head, Horse, Lion, Crown and more.",
         "<h1>The most common words in pub names</h1><table><tr><th>Word</th><th>Pubs</th><th>Names</th></tr>"
         + "".join(f'<tr><td><a href="/word/{w}/">{esc(w.title())}</a></td><td class="n">{fmt(word_pubs[w])}</td>'
                   f'<td class="n">{len(word_names[w])}</td></tr>' for w in words) + "</table>",
         [("Words", "/words/")])

    page("/areas/", "Pub Names by Postcode Area | Pub Name Stats",
         "The most common pub names in every UK postcode area.",
         "<h1>Pub names by postcode area</h1><table><tr><th>Area</th><th>Pubs</th><th>Most common name</th></tr>"
         + "".join(f'<tr><td><a href="/area/{area_slug[a]}/">{esc(POSTCODE_AREAS[a])} ({a})</a></td>'
                   f'<td class="n">{fmt(len(by_area[a]))}</td><td>{esc(disp[Counter(p["key"] for p in by_area[a]).most_common(1)[0][0]])}</td></tr>'
                   for a in sorted(by_area)) + "</table>", [("Areas", "/areas/")])

    page("/about/", "About Pub Name Stats", "How Pub Name Stats counts and groups UK pub names.",
         f"""<h1>About and methodology</h1>
<p>Pub Name Stats counts the names of {fmt(total)} pubs in the UK, using pubs tagged <code>amenity=pub</code> in
<a href="https://www.openstreetmap.org/">OpenStreetMap</a>. OpenStreetMap is mapped by volunteers, so some pubs are missing,
some have closed and some details are out of date.</p>
<h2>How names are grouped</h2>
<p>Names are grouped so that small differences don't split the count. We ignore capitals and punctuation, a leading
“The” or “Ye”, and a trailing “Inn”, “Tavern”, “Hotel”, “Pub” or “Bar”. So “The Red Lion”, “Red Lion” and “Red Lion Inn” are one name.
Where removing the word would leave something meaningless (“New Inn”), it stays.</p>
<h2>Postcode areas</h2>
<p>Area pages use the first letters of each pub's recorded postcode. Pubs without a postcode are counted UK-wide but don't appear on area pages.</p>
<p>Data © OpenStreetMap contributors, available under the Open Database Licence. Last updated {BUILD_DATE}.</p>""",
         [("About", "/about/")])

    top10 = [(rank_of[k], disp[k], slug.get(k), len(by_key[k])) for k in ranked[:20]]
    page("/", "Pub Name Stats: How Many UK Pubs Share Your Pub's Name?",
         f"Statistics on {fmt(total)} UK pub names. Find out how many pubs are called The Red Lion, The Crown or your local, and where they are.",
         f"""<h1>How many pubs share your pub's name?</h1>
<p class="lede">We've counted the names of <strong>{fmt(total)}</strong> UK pubs. There are {fmt(len(ranked))} different names,
and {fmt(unique_count)} of them belong to just one pub.</p>
<div class="stats"><div class="stat"><b>{fmt(total)}</b><span>pubs</span></div>
<div class="stat"><b>{fmt(len(ranked))}</b><span>different names</span></div>
<div class="stat"><b>{fmt(len(by_key[ranked[0]]))}</b><span>called {esc(disp[ranked[0]])}</span></div></div>
<h2>The 20 most common pub names</h2>{name_table(top10)}
<p><a href="/most-common-pub-names/">See the top 500</a> · <a href="/names/">Browse A–Z</a> · <a href="/areas/">By postcode area</a> · <a href="/words/">By word</a></p>""")

    # ---- sitemap / robots / headers
    with open(os.path.join(OUT, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for p in SITEMAP:
            f.write(f"<url><loc>{SITE}{p}</loc><lastmod>{BUILD_DATE}</lastmod></url>\n")
        f.write("</urlset>\n")
    with open(os.path.join(OUT, "robots.txt"), "w") as f:
        f.write(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")

    print(f"pubs={total} names={len(ranked)} name_pages={len(page_keys)} word_pages={len(words)} "
          f"area_pages={len(by_area)} total_pages={len(SITEMAP)}")


if __name__ == "__main__":
    main()
