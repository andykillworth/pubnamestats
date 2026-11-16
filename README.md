# pubnamestats.co.uk

Programmatic SEO test site: statistics on UK pub names, built from OpenStreetMap.

- `data/pubs.csv` – Overpass export of every UK `amenity=pub` with a name (© OpenStreetMap contributors, ODbL)
- `build.py` – standard-library Python; generates the static site into `dist/`

## Cloudflare (Workers with static assets)

- Build command: `python3 build.py`
- Deploy command: `npx wrangler deploy` (reads `wrangler.jsonc`, serves `dist/`)

## Page types

| Type | URL | Rule |
|---|---|---|
| Name | `/name/red-lion/` | names shared by 2+ pubs |
| Word | `/word/lion/` | words in 5+ names and 10+ pubs |
| Area | `/area/dt-dorchester/` | every postcode area |
| Index | `/names/a/`, `/words/`, `/areas/`, `/most-common-pub-names/` | |

Names shared by only one pub (~14k) are not built yet; reserved for an indexation test cohort.

## Brand

Painted signwriting: gold leaf on Brunswick green, hung against a limewashed wall.

| Token | Hex | Use |
|---|---|---|
| Brunswick green | `#1E3B32` | fascia, signboards, headings |
| Frame green | `#13271F` | board frames, map border |
| Gold leaf | `#D1AB55` | sign lettering, link underlines, map dots |
| Drop shade | `#0B1712` | signwriter's shadow behind gilt letters |
| Limewash | `#E8ECE5` | page background |
| Wrought iron | `#232A28` | sign brackets and chains |

- **Ultra** (Clarendon-style slab) for sign lettering, the wordmark and big counts.
- **Cabin** (humanist sans after Johnston and Gill) for everything else.
- Logo: an iron bracket holding a board painted with a five-bar tally.
- Signature element: each name page opens with a hanging sign painted with that name (`design.sign_svg`), which swings once on load.

Fonts are self-hosted from `static/fonts` under the SIL Open Font Licence.
