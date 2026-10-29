# Torino e Cultura — the public site

Static site for *Torino e Cultura*, Carlo De Marchis's video-interview project on
Turin's cultural scene. Lives at **https://torinoecultura.it** (GitHub Pages, served
from `docs/` on `main`, repo `carlodemarchis-stack/torinoecultura-site`).

There is **no CMS here**. The content is the JSON + photos of the sibling project
`../torinoecultura-data/` (edited with its `tec_ui.py` on http://127.0.0.1:8765);
this repo only reads them and renders pages.

```
torinoecultura-site/
├── build.py        renders docs/ with jinja2 + resizes images with Pillow into WebP
├── site.json       settings: data folder, base URL / domain, Umami id, social links, category labels
├── templates/      base, index, episodes, episode, about, 404, _card (jinja2)
├── static/         style.css, site.js, logo, icons, og-default.jpg → copied into docs/
└── docs/           the generated site — what GitHub Pages serves
```

## Publish a change

1. Edit episodes / people in `tec_ui.py` (the data project). Only episodes with
   status `Published` are rendered; `candidates` are never read.
2. Build and push:

```bash
python3 build.py
```

```bash
git add -A && git commit -m "content: …" && git push
```

`build.py` reads `<data_dir>/data/torino_e_cultura.json` and
`<data_dir>/data/photos/{episodes,people}/` (`data_dir` is in `site.json`, or pass
`--data PATH`). Every image becomes WebP at 2000 / 1200 / 900 / 480 px (quality 82,
cached: only new or changed sources are re-encoded) plus a 1200 px JPEG for
`og:image`, since LinkedIn and X do not read WebP. `--no-images` skips that step for
a quick template-only rebuild. Pages: `/`, `/episodi/` (category filter in the URL
hash, restored on reload), `/episodi/<n>/`, `/progetto/`, `404.html`, plus
`sitemap.xml`, `robots.txt`, `.nojekyll` and `CNAME`.

## What the pages show

- **Episode page**: still image that turns into the YouTube embed on click
  (youtube-nocookie, nothing loaded before the click), description, YouTube /
  Spotify / LinkedIn / Substack / reel buttons, the guest box (photo, category, bio
  and link from the `people` record when the guest is linked to one; plain name
  otherwise), location, previous / next episode.
- **People have no pages of their own** (every episode *is* its person). A person
  record only enriches the guest box of their episodes, so linking a guest to a
  person in `tec_ui.py` is what adds the photo and bio there. The build prints the
  guests that have no person record.
- The description gets a light clean-up at build time: a first line that repeats the
  title and pasted YouTube header lines (`YouTube video:`, `Spotify podcast:`,
  `Torino e Cultura`, `27 minuti fa`) are dropped; descriptions without blank lines
  are split into one paragraph per line.
- Category labels can be localised in `site.json` (`Other` → `Altro`,
  `Education` → `Formazione`); the categories themselves come from the data.

## Analytics

Umami (self-hosted at m.aguywithascarf.com), website id in `site.json`. Every page
carries the standard `?noumami` opt-out line; add it to the URL whenever you open
the live site in something that runs JavaScript so the visit is not counted.

## Requirements

macOS system `python3` with `jinja2` and `Pillow` (`pip3 install --user pillow`
otherwise). No node, no build tool.
