# pubnamestats.co.uk

Programmatic SEO test site: statistics on UK pub names, built from OpenStreetMap.

- `data/pubs.csv` – Overpass export of every UK `amenity=pub` with a name (© OpenStreetMap contributors, ODbL)
- `build.py` – standard-library Python; generates the static site into `dist/`

## Cloudflare Pages settings

- Framework preset: None
- Build command: `python3 build.py`
- Build output directory: `dist`

## Page types

| Type | URL | Rule |
|---|---|---|
| Name | `/name/red-lion/` | names shared by 2+ pubs |
| Word | `/word/lion/` | words in 5+ names and 10+ pubs |
| Area | `/area/dt-dorchester/` | every postcode area |
| Index | `/names/a/`, `/words/`, `/areas/`, `/most-common-pub-names/` | |

Names shared by only one pub (~14k) are not built yet; reserved for an indexation test cohort.
