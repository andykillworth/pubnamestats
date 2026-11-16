"""Visual identity for Pub Name Stats: signwriting, fascia board, gold leaf on Brunswick green.

Everything presentational lives here so build.py stays about data.
"""
import html
import math
import re

GREEN = "#1E3B32"      # Brunswick green signboard paint
GREEN_DEEP = "#13271F"  # board frame / shadowed timber
GILT = "#D1AB55"       # gold leaf
SHADE = "#0B1712"      # signwriter's drop shade
LIME = "#E8ECE5"       # limewashed wall
IRON = "#232A28"       # wrought-iron bracket
INK = "#1F2B27"


def esc(s) -> str:
    return html.escape(str(s), quote=True)


# ---------------------------------------------------------------- the hanging sign

def _split_lines(text: str, max_chars: int = 11):
    words = text.split()
    lines, cur = [], ""
    for w in words:
        if cur and len(cur) + 1 + len(w) > max_chars:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip()
    if cur:
        lines.append(cur)
    # Too many lines: rebalance with a longer measure.
    if len(lines) > 3:
        return _split_lines(text, max_chars + 5)
    return lines


def sign_svg(display: str, *, bracket: bool = True, swing: bool = False, cls: str = "sign") -> str:
    """A hanging pub sign painted with `display` (e.g. "The Red Lion")."""
    has_the = display.lower().startswith("the ")
    name = display[4:] if has_the else display
    name = re.sub(r"\s+", " ", name).upper()
    lines = _split_lines(name)
    longest = max(len(l) for l in lines)

    bx, bw = (40, 340) if bracket else (4, 340)   # board x and width
    W = 420 if bracket else bw + 8
    inner_w = bw - 56
    size = min(50.0, inner_w / (max(longest, 4) * 0.80))
    lh = size * 1.08
    top = 34 if not has_the else 58
    board_h = top + lh * len(lines) + 30
    by = 66 if bracket else 34
    H = by + board_h + 6

    out = [f'<svg class="{cls}" viewBox="0 0 {W} {H:.0f}" role="img" aria-label="Pub sign reading {esc(display)}">']
    if bracket:
        out.append(
            f'<g fill="none" stroke="{IRON}" stroke-linecap="round">'
            f'<rect x="6" y="2" width="14" height="84" rx="3" fill="{IRON}" stroke="none"/>'
            f'<path d="M14 15 H392" stroke-width="7"/>'
            f'<circle cx="398" cy="15" r="6" fill="{IRON}" stroke="none"/>'
            f'<path d="M20 74 C70 72 130 56 190 19" stroke-width="4.5"/>'
            f'<path d="M20 74 C32 74 40 64 34 56 C29 50 21 55 25 60" stroke-width="3.5"/>'
            f'<path d="M150 40 C160 46 172 44 176 36" stroke-width="2.5"/>'
            f'</g>'
        )
        hook_top = 19
    else:
        hook_top = 0
    # Chains: two links each side.
    for cx in (bx + 46, bx + bw - 46):
        y = hook_top
        out.append(f'<g fill="none" stroke="{IRON}" stroke-width="2.6">')
        n = 3 if bracket else 2
        step = (by - y) / n
        for i in range(n):
            out.append(f'<ellipse cx="{cx}" cy="{y + step * (i + .5):.1f}" rx="{3.2 if i % 2 else 4.6}" ry="{step / 2 + 1.5:.1f}"/>')
        out.append("</g>")

    swing_cls = ' class="swing"' if swing else ""
    out.append(f'<g{swing_cls}>')
    out.append(f'<rect x="{bx}" y="{by}" width="{bw}" height="{board_h:.1f}" rx="4" fill="{GREEN_DEEP}"/>')
    out.append(f'<rect x="{bx + 7}" y="{by + 7}" width="{bw - 14}" height="{board_h - 14:.1f}" rx="2" fill="{GREEN}" stroke="{GILT}" stroke-width="2"/>')
    out.append(f'<rect x="{bx + 14}" y="{by + 14}" width="{bw - 28}" height="{board_h - 28:.1f}" fill="none" stroke="{GILT}" stroke-opacity=".45" stroke-width=".8"/>')
    # Corner flourishes: small gilt diamonds.
    for x, y in ((bx + 14, by + 14), (bx + bw - 14, by + 14), (bx + 14, by + board_h - 14), (bx + bw - 14, by + board_h - 14)):
        out.append(f'<path d="M{x} {y - 4} L{x + 4} {y} L{x} {y + 4} L{x - 4} {y} Z" fill="{GILT}"/>')
    cx = bx + bw / 2
    if has_the:
        ty = by + 42
        out.append(f'<path d="M{cx - 58} {ty - 5} H{cx - 30} M{cx + 30} {ty - 5} H{cx + 58}" stroke="{GILT}" stroke-width="1.4"/>')
        out.append(f'<text x="{cx}" y="{ty}" text-anchor="middle" class="sign-the" fill="{GILT}">THE</text>')
    for i, line in enumerate(lines):
        y = by + top + lh * (i + 1) - lh * 0.18
        fit = ""
        if len(line) * size * 0.80 > inner_w:
            fit = f' textLength="{inner_w}" lengthAdjust="spacingAndGlyphs"'
        for dx, fill in ((2.4, SHADE), (0, GILT)):
            out.append(f'<text x="{cx + dx}" y="{y + dx:.1f}" text-anchor="middle" class="sign-name" '
                       f'font-size="{size:.1f}" fill="{fill}"{fit}>{esc(line)}</text>')
    out.append("</g></svg>")
    return "".join(out)


# ---------------------------------------------------------------- logo + favicon

def logo_svg() -> str:
    """Bracket holding a small board painted with a five-bar tally."""
    return (
        f'<svg class="logo" viewBox="0 0 64 54" aria-hidden="true">'
        f'<g fill="none" stroke="{GILT}" stroke-linecap="round">'
        f'<path d="M3 2 V30" stroke-width="3"/><path d="M3 6 H60" stroke-width="3"/>'
        f'<path d="M3 26 C14 26 24 18 30 8" stroke-width="2"/>'
        f'<path d="M20 6 V16 M50 6 V16" stroke-width="1.6"/></g>'
        f'<rect x="12" y="16" width="46" height="34" rx="2" fill="{GREEN_DEEP}" stroke="{GILT}" stroke-width="1.6"/>'
        f'<g stroke="{GILT}" stroke-width="3" stroke-linecap="round">'
        f'<path d="M22 24 V42 M29 24 V42 M36 24 V42 M43 24 V42"/><path d="M18 39 L48 27"/></g>'
        f'</svg>'
    )


def favicon_svg() -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">'
        f'<rect width="64" height="64" rx="10" fill="{GREEN}"/>'
        f'<rect x="6" y="6" width="52" height="52" rx="5" fill="none" stroke="{GILT}" stroke-width="2.5"/>'
        f'<g stroke="{GILT}" stroke-width="5" stroke-linecap="round">'
        f'<path d="M18 17 V47 M27 17 V47 M36 17 V47 M45 17 V47"/><path d="M12 42 L52 22"/></g></svg>'
    )


# ---------------------------------------------------------------- dot map

LAT_MIN, LAT_MAX, LON_MIN, LON_MAX = 49.85, 60.9, -8.2, 1.8
MAP_W = 300
_K = math.cos(math.radians(54.5))
_SCALE = MAP_W / ((LON_MAX - LON_MIN) * _K)
MAP_H = round((LAT_MAX - LAT_MIN) * _SCALE)


def project(lat, lon):
    return (lon - LON_MIN) * _K * _SCALE, (LAT_MAX - lat) * _SCALE


def background_svg(pubs) -> str:
    cells = {(round(x), round(y)) for x, y in (project(p["lat"], p["lon"]) for p in pubs)}
    dots = "".join(f'<rect x="{x}" y="{y}" width="1.1" height="1.1"/>' for x, y in sorted(cells))
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {MAP_W} {MAP_H}">'
            f'<g fill="#5E8676" fill-opacity=".55">{dots}</g></svg>')


def dot_map(points, label: str, note: str = "Faint dots show every pub in the UK.") -> str:
    r = 2.8 if len(points) < 60 else 2.3 if len(points) < 600 else 1.7
    dots = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}"/>'
                   for x, y in (project(p["lat"], p["lon"]) for p in points))
    return (f'<figure class="map"><svg viewBox="0 0 {MAP_W} {MAP_H}" role="img" aria-label="{esc(label)}">'
            f'<image href="/uk-pubs.svg" width="{MAP_W}" height="{MAP_H}"/>'
            f'<g fill="{GILT}" stroke="{SHADE}" stroke-width=".5">{dots}</g></svg>'
            f'<figcaption>{esc(label)}. {esc(note)}</figcaption></figure>')


# ---------------------------------------------------------------- stylesheet

CSS = f"""
@font-face{{font-family:Ultra;src:url(/fonts/ultra.woff2) format("woff2");font-display:swap}}
@font-face{{font-family:Cabin;src:url(/fonts/cabin-400.woff2) format("woff2");font-weight:400;font-display:swap}}
@font-face{{font-family:Cabin;src:url(/fonts/cabin-400-italic.woff2) format("woff2");font-weight:400;font-style:italic;font-display:swap}}
@font-face{{font-family:Cabin;src:url(/fonts/cabin-700.woff2) format("woff2");font-weight:700;font-display:swap}}
:root{{--green:{GREEN};--deep:{GREEN_DEEP};--gilt:{GILT};--shade:{SHADE};--lime:{LIME};--ink:{INK};--iron:{IRON};
--soft:#5B6A64;--line:#C9D1C6;--wash:#DCE3DA}}
*{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:var(--lime);color:var(--ink);font:400 1.0625rem/1.55 Cabin,"Gill Sans","Trebuchet MS",sans-serif}}
.wrap{{max-width:62rem;margin:0 auto;padding:0 1.25rem}}
a{{color:var(--green);text-decoration-color:var(--gilt);text-decoration-thickness:2px;text-underline-offset:3px}}
a:hover{{background:rgba(209,171,85,.22)}}
:focus-visible{{outline:3px solid var(--gilt);outline-offset:2px}}

/* Fascia: the painted board above a pub's front windows */
.fascia{{background:var(--green);border-bottom:5px solid var(--deep);box-shadow:inset 0 -2px 0 var(--gilt)}}
.fascia .wrap{{display:flex;align-items:center;justify-content:space-between;gap:1rem;flex-wrap:wrap;padding-top:.7rem;padding-bottom:.8rem}}
.brand{{display:flex;align-items:center;gap:.7rem;text-decoration:none;color:var(--gilt)}}
.brand:hover{{background:none}}
.logo{{width:3.1rem;height:auto;flex:none}}
.wordmark{{font-family:Ultra,Georgia,serif;font-size:1.55rem;line-height:1;letter-spacing:.01em;text-shadow:2px 2px 0 var(--shade)}}
.fascia nav{{display:flex;gap:1.1rem;flex-wrap:wrap}}
.fascia nav a{{color:#EADFBE;text-decoration:none;font-weight:700;font-size:.98rem;padding:.15rem 0;border-bottom:2px solid transparent}}
.fascia nav a:hover{{background:none;border-bottom-color:var(--gilt)}}
.fascia nav a[aria-current]{{border-bottom-color:var(--gilt)}}

.crumbs{{font-size:.9rem;color:var(--soft);margin:1.1rem 0 0}}
main>h1:first-child{{margin-top:2.2rem}}
.crumbs a{{color:var(--soft)}}

h1,h2,h3{{color:var(--green);font-weight:700;line-height:1.15}}
h1{{font-size:clamp(1.9rem,4.2vw,2.75rem);margin:.6rem 0 .8rem;letter-spacing:-.01em;max-width:22ch}}
h2{{font-size:1.45rem;margin:2.6rem 0 .8rem}}
p,li{{max-width:66ch}}
.lede{{font-size:1.2rem;line-height:1.5}}

/* Name page hero: sign on the left, answer on the right */
.hero{{display:grid;grid-template-columns:minmax(0,25rem) minmax(0,1fr);gap:2.5rem;align-items:center;margin:1rem 0 1.5rem}}
.hero .sign{{width:100%;height:auto;display:block}}
.answer{{font-family:Ultra,Georgia,serif;color:var(--green);font-size:clamp(4rem,11vw,7rem);line-height:.9;margin:.2rem 0 .4rem;text-shadow:3px 3px 0 var(--gilt)}}
.answer small{{font-family:Cabin,sans-serif;font-weight:700;font-size:1.4rem;text-shadow:none;margin-left:.5rem;letter-spacing:0}}
.sign-name{{font-family:Ultra,Georgia,serif}}
.sign-the{{font-family:Cabin,sans-serif;font-weight:700;font-size:15px;letter-spacing:.32em}}
.swing{{transform-box:view-box;transform-origin:50% 0;animation:swing 2.8s cubic-bezier(.3,.1,.3,1) .2s both}}
@keyframes swing{{0%{{transform:rotate(4deg)}}30%{{transform:rotate(-2.6deg)}}55%{{transform:rotate(1.4deg)}}78%{{transform:rotate(-.6deg)}}100%{{transform:rotate(0)}}}}
@media (prefers-reduced-motion:reduce){{.swing{{animation:none}}}}

/* Facts read as a sentence-like ledger, not a grid of cards */
.facts{{display:flex;flex-wrap:wrap;gap:.6rem 1.7rem;margin:1.2rem 0 0;padding:0}}
.facts div{{display:flex;flex-direction:column}}
.facts dt{{order:2;color:var(--soft);font-size:.92rem}}
.facts dd{{order:1;margin:0;font-weight:700;font-size:1.25rem;color:var(--green)}}

.split{{display:grid;grid-template-columns:minmax(0,1fr) 18.5rem;gap:2.5rem;align-items:start}}
.split>.map{{position:sticky;top:1rem}}
.map{{margin:0}}
.map svg{{display:block;width:100%;height:auto;background:var(--green);border:6px solid var(--deep);box-shadow:inset 0 0 0 1px var(--gilt);border-radius:3px}}
figcaption{{font-size:.85rem;color:var(--soft);margin-top:.4rem}}

table{{border-collapse:collapse;width:100%;font-size:.98rem;font-variant-numeric:tabular-nums}}
th{{text-align:left;font-weight:700;color:var(--green);padding:.45rem .6rem .45rem 0;border-bottom:2px solid var(--green)}}
td{{padding:.42rem .6rem .42rem 0;border-bottom:1px solid var(--line);vertical-align:top}}
td.n,th.n{{text-align:right;padding-right:0}}
td.r{{color:var(--soft);width:3.2rem}}
.scroll{{overflow-x:auto}}

.cols{{columns:3 13rem;column-gap:2rem;margin:0;padding:0;list-style:none}}
.cols li{{break-inside:avoid;padding:.12rem 0}}
.cols .c{{color:var(--soft);font-size:.9rem}}

/* A–Z as a row of tiny painted boards */
.az{{display:flex;flex-wrap:wrap;gap:.4rem;margin:1rem 0 1.6rem;padding:0;list-style:none}}
.az a{{display:grid;place-items:center;width:2.3rem;height:2.3rem;background:var(--green);color:var(--gilt);font-family:Ultra,Georgia,serif;
text-decoration:none;border:2px solid var(--deep);box-shadow:inset 0 0 0 1px var(--gilt);border-radius:2px}}
.az a:hover,.az a[aria-current]{{background:var(--gilt);color:var(--green)}}

/* Home: signs hanging from a beam */
.beam{{margin:1.6rem 0 0;padding:0;list-style:none;display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:1rem;
border-top:16px solid #3A2A1E;position:relative;padding-top:0}}
.beam::before{{content:"";position:absolute;left:0;right:0;top:-16px;height:4px;background:#5A4231}}
.beam li{{text-align:center}}
.beam a{{text-decoration:none;display:block}}
.beam a:hover{{background:none}}
.beam a:hover .mini{{transform:rotate(-2deg)}}
.mini{{width:100%;height:auto;display:block;transform-origin:50% 0;transition:transform .4s cubic-bezier(.3,.1,.3,1)}}
@media (prefers-reduced-motion:reduce){{.mini{{transition:none}}}}
.beam .count{{display:block;font-weight:700;color:var(--green);margin-top:.15rem}}
.finder{{margin:2.2rem 0 0;max-width:34rem;position:relative}}
.finder label{{display:block;font-weight:700;color:var(--green);margin-bottom:.35rem;font-size:1.1rem}}
.finder input{{width:100%;font:inherit;font-size:1.2rem;padding:.7rem .9rem;border:2px solid var(--green);border-radius:3px;background:#fff;color:var(--ink)}}
.finder ul{{list-style:none;margin:.3rem 0 0;padding:0;background:#fff;border:2px solid var(--green);border-radius:3px;position:absolute;left:0;right:0;z-index:5}}
.finder ul:empty{{display:none}}
.finder li a{{display:flex;justify-content:space-between;padding:.45rem .9rem;text-decoration:none}}
.finder li a span{{color:var(--soft)}}
.finder .none{{padding:.45rem .9rem;color:var(--soft)}}

footer{{margin-top:4.5rem;background:var(--wash);border-top:3px solid var(--green);font-size:.9rem;color:var(--soft)}}
footer .wrap{{padding-top:1.4rem;padding-bottom:2.4rem}}
footer p{{max-width:70ch;margin:.3rem 0}}
footer a{{color:var(--ink)}}

@media (max-width:760px){{
.hero{{grid-template-columns:1fr;gap:.8rem}}
.hero .sign{{max-width:22rem;margin:0 auto}}
.split{{grid-template-columns:1fr}}
.split>.map{{position:static;max-width:20rem}}
.beam{{grid-template-columns:repeat(3,minmax(0,1fr))}}
.beam li:nth-child(n+4){{display:none}}
.wordmark{{font-size:1.3rem}}
}}
"""


# ---------------------------------------------------------------- search script (home page)

FINDER_JS = """
(function(){
var input=document.getElementById('q'),list=document.getElementById('results'),names=null;
function norm(s){return s.toLowerCase().replace(/&/g,' and ').replace(/['’]/g,'').replace(/[^a-z0-9 ]/g,' ').replace(/^(the|ye) /,'').replace(/\\s+/g,' ').trim();}
function render(){
  var q=norm(input.value);list.innerHTML='';if(!q||!names)return;
  var hits=[];for(var i=0;i<names.length&&hits.length<8;i++){if(names[i][3].indexOf(q)>-1)hits.push(names[i]);}
  if(!hits.length){list.innerHTML='<li class="none">No pub name shared by two or more pubs matches that.</li>';return;}
  list.innerHTML=hits.map(function(h){return '<li><a href="/name/'+h[1]+'/">'+h[0].replace(/</g,'&lt;')+' <span>'+h[2].toLocaleString('en-GB')+' pubs</span></a></li>';}).join('');
}
input.addEventListener('focus',function(){if(names)return;fetch('/names.json').then(function(r){return r.json();}).then(function(d){names=d.map(function(n){return n.concat([norm(n[0])]);});render();});},{once:true});
input.addEventListener('input',render);
input.form.addEventListener('submit',function(e){e.preventDefault();var a=list.querySelector('a');if(a)location.href=a.href;});
})();
"""
