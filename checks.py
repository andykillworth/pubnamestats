"""Technical SEO checks run at the end of every build. Any failure stops the deploy.

- every indexable page has exactly one self-referencing absolute canonical
- every page has exactly one <h1>, a title and a meta description
- titles are unique across indexable pages
- every internal link points at a page or file that exists, in its canonical form
- the sitemaps list every indexable page, and nothing else
- robots.txt points at the sitemap index and blocks nothing indexable
"""
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter

NS = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _path_for(out, file):
    rel = os.path.relpath(file, out).replace(os.sep, "/")
    if rel == "index.html":
        return "/"
    if rel.endswith("/index.html"):
        return "/" + rel[: -len("index.html")]
    return "/" + rel


def _resolves(out, href_path):
    if href_path.endswith("/"):
        return os.path.isfile(os.path.join(out, href_path.strip("/"), "index.html")) or href_path == "/"
    return os.path.isfile(os.path.join(out, href_path.lstrip("/")))


def run(out, site, sitemap_paths):
    errors, warnings = [], []
    titles = {}
    pages = {}
    inbound = Counter()

    for root, _, files in os.walk(out):
        for name in files:
            if not name.endswith(".html"):
                continue
            file = os.path.join(root, name)
            path = _path_for(out, file)
            html = open(file, encoding="utf-8").read()
            pages[path] = html
            noindex = 'name="robots" content="noindex"' in html
            canon = re.findall(r'<link rel="canonical" href="([^"]+)"', html)

            if noindex:
                if canon:
                    errors.append(f"{path}: noindex page has a canonical")
            else:
                if len(canon) != 1:
                    errors.append(f"{path}: expected 1 canonical, found {len(canon)}")
                elif canon[0] != site + path:
                    errors.append(f"{path}: canonical {canon[0]} doesn't match the page URL")
                t = re.search(r"<title>(.*?)</title>", html, re.S)
                if t:
                    titles.setdefault(t.group(1), []).append(path)
            if html.count("<h1") != 1:
                errors.append(f"{path}: expected 1 <h1>, found {html.count('<h1')}")
            if not re.search(r"<title>.+?</title>", html, re.S):
                errors.append(f"{path}: missing <title>")
            if not re.search(r'<meta name="description" content=".+?">', html):
                errors.append(f"{path}: missing meta description")

            markup = re.sub(r"<script\b.*?</script>", "", html, flags=re.S)
            for href in re.findall(r'href="(/[^"#]*)', markup):
                target = href.split("?")[0]
                if not _resolves(out, target):
                    errors.append(f"{path}: broken internal link {href}")
                elif "." not in target.rsplit("/", 1)[-1] and not target.endswith("/"):
                    errors.append(f"{path}: link {href} is missing its trailing slash")
                elif target != target.lower():
                    errors.append(f"{path}: link {href} isn't lowercase")
                if target != path:
                    inbound[target] += 1

    for title, paths in titles.items():
        if len(paths) > 1:
            errors.append(f"duplicate title on {len(paths)} pages: {title[:60]} ({', '.join(paths[:3])})")

    # Sitemaps
    index = ET.parse(os.path.join(out, "sitemap.xml")).getroot()
    listed = []
    for loc in index.findall("sm:sitemap/sm:loc", NS):
        child = loc.text.removeprefix(site).lstrip("/")
        urls = ET.parse(os.path.join(out, child)).getroot().findall("sm:url/sm:loc", NS)
        if len(urls) > 50000:
            errors.append(f"{child}: more than 50,000 URLs")
        listed += [u.text for u in urls]
    dupes = [u for u, c in Counter(listed).items() if c > 1]
    if dupes:
        errors.append(f"sitemap lists {len(dupes)} URLs more than once, e.g. {dupes[0]}")
    indexable = {p for p, h in pages.items() if 'content="noindex"' not in h}
    in_sitemap = {u.removeprefix(site) for u in listed}
    for p in sorted(in_sitemap - indexable):
        errors.append(f"sitemap lists {p}, which isn't an indexable page")
    for p in sorted(indexable - in_sitemap):
        errors.append(f"indexable page {p} is missing from the sitemap")
    if set(sitemap_paths) != in_sitemap:
        errors.append("sitemap contents don't match the pages the build generated")

    # robots.txt
    robots = open(os.path.join(out, "robots.txt")).read()
    if f"Sitemap: {site}/sitemap.xml" not in robots:
        errors.append("robots.txt doesn't reference the sitemap index")
    for rule in re.findall(r"^Disallow:\s*(\S+)", robots, re.M):
        blocked = [p for p in indexable if p.startswith(rule)]
        if blocked:
            errors.append(f"robots.txt Disallow {rule} blocks indexable pages, e.g. {blocked[0]}")

    orphans = [p for p in indexable if p != "/" and inbound[p] == 0]
    if orphans:
        warnings.append(f"{len(orphans)} indexable pages have no internal links, e.g. {orphans[:3]}")

    for w in warnings:
        print("SEO check warning:", w)
    if errors:
        for e in errors[:50]:
            print("SEO check failed:", e)
        if len(errors) > 50:
            print(f"...and {len(errors) - 50} more")
        sys.exit(1)
    print(f"SEO checks passed: {len(pages)} HTML files, {len(in_sitemap)} URLs in sitemaps")
