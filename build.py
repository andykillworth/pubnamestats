#!/usr/bin/env python3
"""Build pubnamestats.co.uk from data/pubs.csv (OpenStreetMap export).

No dependencies beyond the Python standard library. Output goes to dist/.
Cloudflare Pages: build command `python3 build.py`, output directory `dist`.
"""
import csv
import hashlib
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


# ---------------------------------------------------------------- page shell

import sys  # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from design import CSS, FINDER_JS, background_svg, dot_map, favicon_svg, logo_svg, sign_svg  # noqa: E402

NAV = [("Most common", "/most-common-pub-names/"), ("A–Z", "/names/"), ("Areas", "/areas/"), ("Words", "/words/")]


def page(path, title, description, body, breadcrumbs=None, section=None, scripts="", indexable=True):
    canonical = SITE + path
    crumbs_html = ""
    ld = []
    if breadcrumbs:
        items = [("Home", "/")] + breadcrumbs
        crumbs_html = '<nav class="crumbs" aria-label="Breadcrumb">' + " › ".join(
            f'<a href="{u}">{esc(t)}</a>' if i < len(items) - 1 else esc(t)
            for i, (t, u) in enumerate(items)) + "</nav>"
        ld.append({
            "@context": "https://schema.org", "@type": "BreadcrumbList",
            "itemListElement": [
                {"@type": "ListItem", "position": i + 1, "name": t, "item": SITE + u}
                for i, (t, u) in enumerate(items)
            ],
        })
    ld_html = "".join(f'<script type="application/ld+json">{json.dumps(x)}</script>' for x in ld)
    nav = "".join(f'<a href="{u}"{" aria-current=\"page\"" if section == u else ""}>{t}</a>' for t, u in NAV)
    robots_meta = (f'<link rel="canonical" href="{canonical}">' if indexable
                   else '<meta name="robots" content="noindex">')
    doc = f"""<!doctype html>
<html lang="en-GB"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
{robots_meta}
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
<meta name="theme-color" content="#1E3B32">
<meta property="og:type" content="website">
<meta property="og:site_name" content="Pub Name Stats">
<meta property="og:title" content="{esc(title.removesuffix(' | Pub Name Stats'))}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:url" content="{canonical}">
<meta property="og:image" content="{SITE}/og.png">
<meta name="twitter:card" content="summary_large_image">
<link rel="preload" href="/fonts/ultra.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="/style.css">
{ld_html}
</head><body>
<header class="fascia"><div class="wrap"><a class="brand" href="/" aria-label="Pub Name Stats home">{logo_svg()}<span class="wordmark">Pub Name Stats</span></a>
<nav aria-label="Main">{nav}</nav></div></header>
<main class="wrap">{crumbs_html}{body}</main>
<footer><div class="wrap"><p>Pub data © <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>, available under the Open Database Licence. Data updated {DATA_DATE}.</p>
<p>We count “The Red Lion”, “Red Lion” and “Red Lion Inn” as one name. <a href="/about/">How we count</a></p></div></footer>
{scripts}
</body></html>"""
    out = os.path.join(OUT, path.strip("/"), "index.html") if path != "/" else os.path.join(OUT, "index.html")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        f.write(doc)
    if indexable:
        SITEMAP.append(path)
        PAGE_HASH[path] = hashlib.sha1(doc.encode()).hexdigest()


SITEMAP = []
PAGE_HASH = {}


def name_table(rows, show_rank=True):
    """rows: list of (rank, display, slug_or_None, count)"""
    head = "<tr>" + ("<th>Rank</th>" if show_rank else "") + '<th>Name</th><th class="n">Pubs</th></tr>'
    body = "".join(
        "<tr>" + (f'<td class="r">{r}</td>' if show_rank else "")
        + (f'<td><a href="/name/{s}/">{esc(d)}</a></td>' if s else f"<td>{esc(d)}</td>")
        + f'<td class="n">{fmt(c)}</td></tr>'
        for r, d, s, c in rows
    )
    return f"<table>{head}{body}</table>"


# ---------------------------------------------------------------- lastmod + sitemaps

LASTMOD_FILE = "data/lastmod.json"
try:
    with open(LASTMOD_FILE) as f:
        LASTMOD = json.load(f)
except FileNotFoundError:
    LASTMOD = {}


def _file_hash(path):
    with open(path, "rb") as f:
        return hashlib.sha1(f.read()).hexdigest()


def lastmod_for(key, digest):
    """Keep a page's lastmod unless its content has actually changed."""
    old = LASTMOD.get(key)
    if old and old[0] == digest:
        return old[1]
    LASTMOD[key] = [digest, BUILD_DATE]
    return BUILD_DATE


DATA_DATE = lastmod_for("__data__", _file_hash(DATA))

# Separate sitemaps per page type, so Search Console reports indexing for each one.
SITEMAP_GROUPS = [
    ("names", lambda p: p.startswith("/name/")),
    ("words", lambda p: p.startswith("/word/")),
    ("areas", lambda p: p.startswith("/area/")),
    ("pages", lambda p: True),
]


def write_sitemaps_and_robots():
    # Pages are hashed with the build date stripped, so a rebuild alone doesn't bump lastmod.
    groups = {name: [] for name, _ in SITEMAP_GROUPS}
    for path in SITEMAP:
        for name, test in SITEMAP_GROUPS:
            if test(path):
                groups[name].append(path)
                break
    entries = []
    for name, paths in groups.items():
        dates = []
        with open(os.path.join(OUT, f"sitemap-{name}.xml"), "w") as f:
            f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
            for p in paths:
                d = lastmod_for(p, PAGE_HASH[p])
                dates.append(d)
                f.write(f"<url><loc>{SITE}{p}</loc><lastmod>{d}</lastmod></url>\n")
            f.write("</urlset>\n")
        entries.append((name, max(dates)))
    with open(os.path.join(OUT, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n')
        for name, d in entries:
            f.write(f"<sitemap><loc>{SITE}/sitemap-{name}.xml</loc><lastmod>{d}</lastmod></sitemap>\n")
        f.write("</sitemapindex>\n")
    # Drop pages that no longer exist from the manifest.
    live = set(PAGE_HASH) | {"__data__"}
    for k in list(LASTMOD):
        if k not in live:
            del LASTMOD[k]
    with open(LASTMOD_FILE, "w") as f:
        json.dump(LASTMOD, f, indent=0, sort_keys=True)
    with open(os.path.join(OUT, "robots.txt"), "w") as f:
        f.write("# Everything is open to every crawler, including AI crawlers.\n"
                "User-agent: *\n"
                "Disallow: /names.json\n"
                "Allow: /\n\n"
                f"Sitemap: {SITE}/sitemap.xml\n")


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
    shutil.copytree("static", OUT)
    with open(os.path.join(OUT, "style.css"), "w") as f:
        f.write(CSS)
    with open(os.path.join(OUT, "uk-pubs.svg"), "w") as f:
        f.write(background_svg(pubs))
    with open(os.path.join(OUT, "favicon.svg"), "w") as f:
        f.write(favicon_svg())
    with open(os.path.join(OUT, "names.json"), "w") as f:
        json.dump([[disp[k], slug[k], len(by_key[k])] for k in page_keys], f, separators=(",", ":"))

    def tie_ranked(pairs):
        rows, prev, r = [], None, 0
        for i, (k, n) in enumerate(pairs, 1):
            if n != prev:
                r, prev = i, n
            rows.append((r, disp[k], slug.get(k), n))
        return rows

    def plural(n, one, many):
        return one if n == 1 else many

    # ---- name pages
    for k in page_keys:
        ps = by_key[k]
        n = len(ps)
        d = disp[k]
        rank = rank_of[k]
        joint = sum(1 for x in ranked if len(by_key[x]) == n) > 1
        share = n / total * 100
        variants = Counter(p["name"] for p in ps).most_common()
        areas = area_share[k].most_common()
        top_area = areas[0] if areas else None
        towns = Counter(p["town"] for p in ps if p["town"]).most_common(10)
        ops = Counter(p["operator"] for p in ps if p["operator"]).most_common(5)
        north = max(ps, key=lambda p: p["lat"])
        south = min(ps, key=lambda p: p["lat"])

        def where(p):
            return p["town"] or (POSTCODE_AREAS[p["area"]] + " area" if p["area"] else None)

        rank_text = ("the most common pub name of all" if rank == 1
                     else f"{'joint ' if joint else ''}{ordinal(rank)} on the list of the UK's most common pub names")
        answer = (f"There are {fmt(n)} pubs called {esc(d)} in the UK. That makes it {rank_text}, "
                  f"with {share:.2f}% of the {fmt(total)} named pubs we've counted.")
        facts = [(f"{'=' if joint else ''}{ordinal(rank)}", "most common name"),
                 (str(len(variants)), plural(len(variants), "way of writing it", "ways of writing it")),
                 (str(len(areas)), plural(len(areas), "postcode area", "postcode areas"))]
        if top_area and top_area[1] > 1:
            facts.append((POSTCODE_AREAS[top_area[0]], f"has the most ({top_area[1]})"))
        body = [
            '<section class="hero">',
            sign_svg(d, swing=True),
            "<div>",
            f"<h1>How many pubs are called {esc(d)}?</h1>",
            f'<p class="answer">{fmt(n)}<small>{plural(n, "pub", "pubs")}</small></p>',
            f'<p class="lede">{answer}</p>',
            '<dl class="facts">' + "".join(f"<div><dt>{esc(b)}</dt><dd>{esc(a)}</dd></div>" for a, b in facts) + "</dl>",
            "</div></section>",
        ]

        left = []
        if n > 1 and where(north) and where(south) and where(north) != where(south):
            left.append(f"<p>The most northerly {esc(d)} is in {esc(where(north))}. "
                        f"The most southerly is in {esc(where(south))}.</p>")
        if areas:
            left.append(f"<h2>Where they are</h2>")
            left.append('<table><tr><th>Postcode area</th><th class="n">Pubs</th></tr>' + "".join(
                f'<tr><td><a href="/area/{area_slug[a]}/">{esc(POSTCODE_AREAS[a])}</a> ({a})</td><td class="n">{c}</td></tr>'
                for a, c in areas[:15]) + "</table>")
            if len(areas) > 15:
                left.append(f"<p>Plus {len(areas) - 15} more postcode {plural(len(areas) - 15, 'area', 'areas')}, listed in full below.</p>")
            missing = n - sum(c for _, c in areas)
            if missing:
                left.append(f"<p>{missing} {plural(missing, 'pub has', 'pubs have')} no postcode recorded.</p>")
        left.append("<h2>How the name is written</h2>")
        left.append('<table><tr><th>On the sign</th><th class="n">Pubs</th></tr>' + "".join(
            f'<tr><td>{esc(v)}</td><td class="n">{c}</td></tr>' for v, c in variants) + "</table>")
        if towns and towns[0][1] > 1:
            left.append("<h2>Towns with more than one</h2><ul>" + "".join(
                f"<li>{esc(t)}: {c}</li>" for t, c in towns if c > 1) + "</ul>")
        if ops:
            left.append("<h2>Who runs them</h2><p>Where OpenStreetMap records an operator: " + ", ".join(
                f"{esc(o)} ({c})" for o, c in ops) + ".</p>")
        body.append('<div class="split"><div>' + "".join(left) + "</div>"
                    + dot_map(ps, f"Every pub called {d}") + "</div>")

        body.append(f"<h2>Every {esc(d)} in the UK</h2>")
        rows = sorted(ps, key=lambda p: (p["area"] or "ZZ", p["town"], p["postcode"]))
        body.append('<div class="scroll"><table><tr><th>Name</th><th>Town</th><th>Postcode</th><th>Map</th></tr>' + "".join(
            f'<tr><td>{esc(p["name"])}</td><td>{esc(p["town"])}</td><td>{esc(p["postcode"])}</td>'
            f'<td><a href="https://www.openstreetmap.org/{p["osm"]}" rel="nofollow">View</a></td></tr>'
            for p in rows) + "</table></div>")

        related = Counter()
        for w in k.split():
            if w in word_names and w not in STOPWORDS:
                for other in sorted(word_names[w]):
                    if other != k and other in has_page:
                        related[other] = len(by_key[other])
        if related:
            body.append("<h2>Similar names</h2><ul class='cols'>" + "".join(
                f"<li>{link(o)} <span class='c'>{len(by_key[o])}</span></li>" for o in sorted(related, key=lambda o: (-related[o], o))[:24]) + "</ul>")
        word_links = [w for w in k.split() if w in words]
        if word_links:
            body.append("<p>See every pub with " + " or ".join(
                f'<a href="/word/{w}/">{esc(w.title())}</a>' for w in word_links) + " in the name.</p>")

        title = f"How Many Pubs Are Called {d}? {fmt(n)} in the UK | Pub Name Stats"
        desc = f"There are {fmt(n)} pubs called {d} in the UK, the {ordinal(rank)} most common pub name. See where they are, how the name is written and the full list."
        page(f"/name/{slug[k]}/", title, desc, "".join(body),
             [("Pub names A–Z", "/names/"), (d, f"/name/{slug[k]}/")], section="/names/")

    # ---- word pages
    for w in words:
        ks = sorted(word_names[w], key=lambda k: (-len(by_key[k]), k))
        n_pubs = word_pubs[w]
        rows = [(rank_of[k], disp[k], slug.get(k), len(by_key[k])) for k in ks]
        body = (f"<h1>Pubs with {esc(w.title())} in the name</h1>"
                f'<p class="answer">{fmt(n_pubs)}<small>pubs</small></p>'
                f"<p class='lede'>{fmt(n_pubs)} UK pubs have {esc(w.title())} in their name, spread across "
                f"{fmt(len(ks))} different names. The most common is {link(ks[0])}, with {fmt(len(by_key[ks[0]]))}.</p>"
                + '<div class="split"><div><h2>Every name</h2>' + name_table(rows, show_rank=False) + "</div>"
                + dot_map([p for k in ks for p in by_key[k]], f"Pubs with {w.title()} in the name") + "</div>")
        page(f"/word/{w}/", f"Pubs With {w.title()} in the Name: {fmt(n_pubs)} in the UK | Pub Name Stats",
             f"{fmt(n_pubs)} UK pubs have {w.title()} in the name, across {len(ks)} different names. See them all ranked.",
             body, [("Words", "/words/"), (w.title(), f"/word/{w}/")], section="/words/")

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
        left = ("<h2>Most common names</h2>"
                + name_table(tie_ranked(top)))
        if over:
            left += ("<h2>Unusually common here</h2><p>Names that turn up far more often here than in the rest of the UK.</p><ul>"
                     + "".join(f"<li>{link(k)}: {c[k]} here, {len(by_key[k])} across the UK</li>" for k in over) + "</ul>")
        if only_here:
            left += (f"<h2>Only found in {esc(name)}</h2><p>Names shared by more than one pub, none of them outside the {a} area.</p><ul>"
                     + "".join(f"<li>{link(k)} ({len(by_key[k])})</li>" for k in only_here[:20]) + "</ul>")
        body = (f"<h1>Pub names in {esc(name)} ({a})</h1>"
                f'<p class="lede">We\'ve counted {fmt(len(ps))} pubs in the {a} postcode area, with '
                f"{fmt(len(c))} different names between them. The most common is {link(top[0][0])}, with {top[0][1]}.</p>"
                + '<div class="split"><div>' + left + "</div>"
                + dot_map(ps, f"Pubs in the {a} postcode area") + "</div>")
        page(f"/area/{area_slug[a]}/", f"Most Common Pub Names in {name} ({a}) | Pub Name Stats",
             f"The most common pub names in the {a} ({name}) postcode area, from {fmt(len(ps))} pubs. Plus names you'll only find there.",
             body, [("Areas", "/areas/"), (f"{name} ({a})", f"/area/{area_slug[a]}/")], section="/areas/")

    # ---- index pages
    top500 = [(rank_of[k], disp[k], slug.get(k), len(by_key[k])) for k in ranked[:500]]
    page("/most-common-pub-names/", "The 500 Most Common Pub Names in the UK | Pub Name Stats",
         f"The most common pub names in the UK, ranked from {fmt(total)} pubs. The Red Lion, The Crown and The Royal Oak lead the list.",
         f"<h1>The most common pub names in the UK</h1><p class='lede'>The top 500, ranked from {fmt(total)} named pubs. Names with the same count share a rank.</p>"
         + name_table(top500), [("Most common pub names", "/most-common-pub-names/")], section="/most-common-pub-names/")

    letters = defaultdict(list)
    for k in page_keys:
        first = disp[k].removeprefix("The ")[0].upper()
        letters[first if first.isalpha() else "#"].append(k)

    def az(current=None):
        return "<ul class='az'>" + "".join(
            f'<li><a href="/names/{l.lower() if l != "#" else "0-9"}/"{" aria-current=\"page\"" if l == current else ""}>{l}</a></li>'
            for l in sorted(letters)) + "</ul>"

    for l, ks in letters.items():
        ks.sort(key=lambda k: disp[k].removeprefix("The ").lower())
        ls = l.lower() if l != "#" else "0-9"
        page(f"/names/{ls}/", f"Pub Names Beginning With {l} | Pub Name Stats",
             f"Every UK pub name beginning with {l} that's shared by more than one pub, with counts.",
             f"<h1>Pub names beginning with {l}</h1>{az(l)}<ul class='cols'>"
             + "".join(f'<li><a href="/name/{slug[k]}/">{esc(disp[k])}</a> <span class="c">{len(by_key[k])}</span></li>' for k in ks) + "</ul>",
             [("Pub names A–Z", "/names/"), (l, f"/names/{ls}/")], section="/names/")
    page("/names/", "UK Pub Names A–Z | Pub Name Stats",
         "Browse every UK pub name shared by more than one pub, A to Z.",
         f"<h1>Pub names A–Z</h1><p class='lede'>{fmt(len(page_keys))} names are shared by two or more pubs. "
         f"Another {fmt(unique_count)} belong to a single pub.</p>{az()}", [("Pub names A–Z", "/names/")], section="/names/")

    page("/words/", "Most Common Words in UK Pub Names | Pub Name Stats",
         "The words that appear most often in UK pub names: Arms, Head, Horse, Lion, Crown and more.",
         "<h1>The most common words in pub names</h1><p class='lede'>How many pubs use each word, and in how many different names.</p>"
         '<table><tr><th>Word</th><th class="n">Pubs</th><th class="n">Names</th></tr>'
         + "".join(f'<tr><td><a href="/word/{w}/">{esc(w.title())}</a></td><td class="n">{fmt(word_pubs[w])}</td>'
                   f'<td class="n">{len(word_names[w])}</td></tr>' for w in words) + "</table>",
         [("Words", "/words/")], section="/words/")

    page("/areas/", "Pub Names by Postcode Area | Pub Name Stats",
         "The most common pub names in every UK postcode area.",
         "<h1>Pub names by postcode area</h1><p class='lede'>The most common name in each of the UK's postcode areas.</p>"
         '<table><tr><th>Area</th><th class="n">Pubs</th><th>Most common name</th></tr>'
         + "".join(f'<tr><td><a href="/area/{area_slug[a]}/">{esc(POSTCODE_AREAS[a])}</a> ({a})</td>'
                   f'<td class="n">{fmt(len(by_area[a]))}</td><td>{link(Counter(p["key"] for p in by_area[a]).most_common(1)[0][0])}</td></tr>'
                   for a in sorted(by_area, key=lambda a: POSTCODE_AREAS[a])) + "</table>",
         [("Areas", "/areas/")], section="/areas/")

    page("/about/", "How Pub Name Stats Counts Pub Names", "How Pub Name Stats counts and groups UK pub names.",
         f"""<h1>How we count</h1>
<p class="lede">We count the names of {fmt(total)} UK pubs, taken from <a href="https://www.openstreetmap.org/">OpenStreetMap</a>,
the map built by volunteers. Some pubs will be missing, some will have closed and some details will be out of date.</p>
<h2>Grouping names</h2>
<p>Small differences shouldn't split a count, so we ignore capitals and punctuation, a leading “The” or “Ye”,
and a trailing “Inn”, “Tavern”, “Hotel”, “Pub” or “Bar”. “The Red Lion”, “Red Lion” and “Red Lion Inn” are one name.
Where dropping the word would leave something odd, it stays: “New Inn” isn't counted as “New”.</p>
<h2>Postcode areas</h2>
<p>Area pages use the letters at the start of each pub's postcode. Pubs without a postcode count towards UK totals
but don't appear on area pages.</p>
<h2>Using the data</h2>
<p>Pub data © OpenStreetMap contributors, available under the Open Database Licence. Data last updated {DATA_DATE}.</p>""",
         [("How we count", "/about/")])

    beam = "".join(
        f'<li><a href="/name/{slug[k]}/">{sign_svg(disp[k], bracket=False, cls="mini")}'
        f'<span class="count">{fmt(len(by_key[k]))} pubs</span></a></li>'
        for k in ranked[:5])
    top20 = [(rank_of[k], disp[k], slug.get(k), len(by_key[k])) for k in ranked[:20]]
    page("/", "Pub Name Stats: How Many UK Pubs Share Your Pub's Name?",
         f"Statistics on {fmt(total)} UK pub names. Find out how many pubs are called The Red Lion, The Crown or your local, and where they are.",
         f"""<h1>How many pubs share your local's name?</h1>
<p class="lede">We've counted the names of {fmt(total)} UK pubs. Between them there are {fmt(len(ranked))} different names,
and {fmt(unique_count)} of those are painted on just one sign.</p>
<ul class="beam" aria-label="The five most common pub names">{beam}</ul>
<form class="finder" role="search"><label for="q">Find a pub name</label>
<input id="q" name="q" type="search" autocomplete="off" placeholder="Try Fox and Hounds">
<ul id="results" aria-live="polite"></ul></form>
<h2>The 20 most common pub names</h2>{name_table(top20)}
<p>Keep going with the <a href="/most-common-pub-names/">top 500</a>, browse names <a href="/names/">A to Z</a>,
or look them up <a href="/areas/">by postcode area</a> or <a href="/words/">by word</a>.</p>""",
         scripts=f"<script>{FINDER_JS}</script>")

    # ---- 404 (noindex, not in sitemap)
    page("/404/", "Page not found | Pub Name Stats", "Page not found.",
         "<h1>We couldn't find that page</h1><p>Try the <a href='/names/'>A–Z of pub names</a> or the <a href='/most-common-pub-names/'>most common names</a>.</p>",
         indexable=False)
    os.replace(os.path.join(OUT, "404", "index.html"), os.path.join(OUT, "404.html"))
    os.rmdir(os.path.join(OUT, "404"))

    write_sitemaps_and_robots()

    print(f"pubs={total} names={len(ranked)} name_pages={len(page_keys)} word_pages={len(words)} "
          f"area_pages={len(by_area)} total_pages={len(SITEMAP)}")

    import checks
    checks.run(OUT, SITE, SITEMAP)


if __name__ == "__main__":
    main()
