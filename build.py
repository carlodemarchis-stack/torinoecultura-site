#!/usr/bin/env python3
"""Render the Torino e Cultura site from the torinoecultura-data JSON into docs/ (GitHub Pages).

  python3 build.py                 full build (images are cached; only new/changed sources are resized)
  python3 build.py --no-images     skip image derivatives (fast template-only rebuild)
  python3 build.py --data PATH     data folder (default: "data_dir" in site.json, relative to this file)

Reads  <data>/data/torino_e_cultura.json  and  <data>/data/photos/{people,episodes}/.
People have no pages of their own: a person record adds photo, bio and link to the guest box of their episodes.
`candidates` in that file is a private pipeline and is never read.
Needs: python3 with jinja2 and Pillow (both in the system python on this Mac).
"""
import hashlib
import html
import json
import os
import re
import shutil
import sys
import unicodedata
from html.parser import HTMLParser
from datetime import date

from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup
from PIL import Image, ImageOps

ROOT = os.path.dirname(os.path.abspath(__file__))
DOCS = os.path.join(ROOT, "docs")
IMG = os.path.join(DOCS, "img")
SIZES = {"url": 2000, "medium": 1200, "thumb": 900, "small": 480}   # key -> longest side (px)
SUFFIX = {"url": "", "medium": "-m", "thumb": "-s", "small": "-xs"}
WEBP_QUALITY = 82
OG_SIZE, OG_QUALITY = 1200, 85            # JPEG copy for og:image (LinkedIn/X do not read WebP)
Image.MAX_IMAGE_PIXELS = None

SITE = json.load(open(os.path.join(ROOT, "site.json")))
NO_IMAGES = "--no-images" in sys.argv
DATA = SITE["data_dir"]
if "--data" in sys.argv:
    DATA = sys.argv[sys.argv.index("--data") + 1]
DATA = os.path.abspath(os.path.join(ROOT, os.path.expanduser(DATA)))


# ---------------------------------------------------------------- images
def load_source(src):
    im = Image.open(src)
    im = ImageOps.exif_transpose(im)
    if im.mode in ("RGBA", "LA", "P"):
        im = im.convert("RGBA")
        bg = Image.new("RGB", im.size, (0, 0, 0))
        bg.paste(im, mask=im.split()[-1])
        im = bg
    elif im.mode != "RGB":
        im = im.convert("RGB")
    return im


def derive_all(src, targets):
    """targets: {path: longest_side}. Decode once, write every missing/stale file. Returns number written."""
    stale = {p: n for p, n in targets.items()
             if not (os.path.exists(p) and os.path.getmtime(p) >= os.path.getmtime(src))}
    if not stale:
        return 0
    try:
        im = load_source(src)
    except Exception as e:
        print(f"  ! cannot read {src}: {e}")
        return 0
    os.makedirs(os.path.dirname(next(iter(stale))), exist_ok=True)
    for path, n in sorted(stale.items(), key=lambda kv: -kv[1]):
        out = im.copy()
        out.thumbnail((n, n), Image.LANCZOS)
        if path.endswith(".webp"):
            out.save(path, "WEBP", quality=WEBP_QUALITY, method=5)
        else:
            out.save(path, "JPEG", quality=OG_QUALITY, optimize=True, progressive=True)
    return len(stale)


def image_record(kind, key, rel):
    """kind: 'episodes' | 'people'; rel: path relative to <data>/data. Returns dict with url/medium/thumb/small/og/w/h or None."""
    if not rel:
        return None
    src = os.path.join(DATA, "data", rel)
    if not os.path.isfile(src):
        print(f"  ! missing image, skipped: {src}")
        return None
    name = f"{key}-{hashlib.sha1(rel.encode()).hexdigest()[:6]}"
    folder = os.path.join(IMG, kind)
    files = {k: os.path.join(folder, f"{name}{SUFFIX[k]}.webp") for k in SIZES}
    og = os.path.join(folder, f"{name}-og.jpg")
    targets = {files[k]: SIZES[k] for k in SIZES}
    targets[og] = OG_SIZE
    made = 0 if NO_IMAGES else derive_all(src, targets)
    if not os.path.exists(files["url"]):
        return None
    with Image.open(files["url"]) as probe:
        w, h = probe.size
    rec = {k: f"/img/{kind}/{name}{SUFFIX[k]}.webp" for k in SIZES}
    rec.update(og=f"/img/{kind}/{name}-og.jpg", w=w, h=h, files=set(targets), made=made)
    return rec


def img(im, sizes, alt="", eager=False, cls="", full=False):
    """<img> with srcset: 480 / 900 / 1200 px, plus the full-size file only when full=True."""
    if not im:
        return ""
    cands = f'{im["small"]} 480w, {im["thumb"]} 900w, {im["medium"]} 1200w' + (f', {im["url"]} {im["w"]}w' if full else "")
    return Markup(
        f'<img{" class=" + chr(34) + cls + chr(34) if cls else ""} src="{im["thumb"]}" srcset="{cands}" sizes="{sizes}" '
        f'width="{im["w"]}" height="{im["h"]}" alt="{html.escape(str(alt))}" '
        f'loading="{"eager" if eager else "lazy"}"{" fetchpriority=" + chr(34) + "high" + chr(34) if eager else ""} decoding="async">')


# ---------------------------------------------------------------- text helpers
def slugify(s):
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


URL_RX = re.compile(r"https?://[^\s<>\"]+")


def paragraphs(text):
    """Plain text -> <p> per blank-line block, <br> for single newlines, bare URLs linked."""
    out = []
    text = (text or "").strip()
    blocks = re.split(r"\n\s*\n", text)
    if len(blocks) == 1 and text.count("\n") >= 3:     # no blank lines at all: every line is its own paragraph
        blocks = text.split("\n")
    for block in blocks:
        lines = [l.strip() for l in block.split("\n") if l.strip()]
        if not lines:
            continue
        esc = [URL_RX.sub(lambda m: f'<a href="{m.group()}" rel="noopener">{m.group()}</a>', html.escape(l)) for l in lines]
        out.append("<p>" + "<br>".join(esc) + "</p>")
    return Markup("\n".join(out))


JUNK_RX = re.compile(r"^(YouTube video|Spotify podcast|Torino e Cultura|\d+ (minuti|ore|giorni) fa)\b")


def clean_info(text, title):
    """Drop a first line that repeats the title and the YouTube-description header lines sometimes pasted in."""
    lines = (text or "").split("\n")
    if lines and lines[0].strip() == (title or "").strip():
        lines = lines[1:]
    return "\n".join(l for l in lines if not JUNK_RX.match(l.strip()))


def excerpt(text, n=160):
    t = re.sub(r"\s+", " ", (text or "")).strip()
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


MESI = ["", "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def it_date(iso):
    try:
        y, m, d = (iso or "")[:10].split("-")
        return f"{int(d)} {MESI[int(m)]} {y}"
    except (ValueError, IndexError):
        return ""


class BodyCleaner(HTMLParser):
    """Substack body_html -> plain editorial HTML: keeps text tags and images, drops widgets (buttons, forms,
    svg icons, iframes: the episode page has its own player), unwraps the layout divs."""
    KEEP = {"p", "strong", "em", "b", "i", "br", "h1", "h2", "h3", "h4", "h5", "hr", "a", "ul", "ol", "li",
            "blockquote", "figure", "figcaption", "img", "pre", "code", "span"}
    DROP = {"button", "svg", "form", "iframe", "input", "label", "script", "style", "select", "textarea"}
    ATTRS = {"a": ("href",), "img": ("src", "alt", "width", "height")}
    VOID = {"br", "hr", "img", "source", "input", "meta", "link", "wbr"}

    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out, self.skip = [], 0          # skip = depth inside a dropped element

    def handle_starttag(self, tag, attrs):
        if self.skip or tag in self.DROP:
            if tag not in self.VOID:
                self.skip += 1
            return
        if tag not in self.KEEP:
            return                                    # div / picture / section: unwrap
        attrs = dict(attrs)
        keep = {k: attrs[k] for k in self.ATTRS.get(tag, ()) if attrs.get(k)}
        if tag == "a" and "image-link" in (attrs.get("class") or ""):
            keep["data-lightbox"] = "article"
        if tag == "a" and keep.get("href", "").startswith("http"):
            keep["rel"] = "noopener"
        self.out.append("<" + tag + "".join(f' {k}="{html.escape(v, quote=True)}"' for k, v in keep.items()) + ">")

    def handle_startendtag(self, tag, attrs):        # <path/> and friends: no end tag, so no depth change
        if not (self.skip or tag in self.DROP):
            self.handle_starttag(tag, attrs)

    def handle_endtag(self, tag):
        if self.skip:
            if tag not in self.VOID:
                self.skip -= 1
            return
        if tag in self.KEEP and tag not in self.VOID:
            self.out.append(f"</{tag}>")

    def handle_data(self, d):
        if not self.skip:
            self.out.append(d)

    def handle_entityref(self, name):
        if not self.skip:
            self.out.append(f"&{name};")

    def handle_charref(self, name):
        if not self.skip:
            self.out.append(f"&#{name};")


IMG_NAME = re.compile(r"images(?:/|%2F)([^/%\s\"?]+)")


def clean_body(body, cover=None):
    c = BodyCleaner()
    c.feed(body or "")
    out = re.sub(r"<p>\s*</p>", "", "".join(c.out)).strip()
    # Substack posts usually open with the cover image itself: the page already shows it above the title
    m = re.match(r"<figure>.*?</figure>", out, re.S)
    if m and cover:
        first = IMG_NAME.search(m.group())
        mine = IMG_NAME.search(cover)
        if first and mine and first.group(1) == mine.group(1):
            out = out[m.end():].strip()
    return Markup(out)


YT_RX = re.compile(r"(?:youtu\.be/|youtube\.com/(?:watch\?v=|embed/|shorts/))([A-Za-z0-9_-]{11})")


def youtube_id(url):
    m = YT_RX.search(url or "")
    return m.group(1) if m else None


def link_label(url):
    h = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url or "")).split("/")[0]
    return {"instagram.com": "Instagram", "facebook.com": "Facebook", "linkedin.com": "LinkedIn", "youtube.com": "YouTube",
            "open.spotify.com": "Spotify", "x.com": "X", "twitter.com": "X", "tiktok.com": "TikTok"}.get(h, "Sito web")


# ---------------------------------------------------------------- build
def main():
    src = os.path.join(DATA, "data", "torino_e_cultura.json")
    print(f"build: reading {src}")
    data = json.load(open(src))
    labels = SITE.get("category_labels", {})
    cat_order = data["reference"]["categories"]

    def cat(name):
        return {"name": name, "label": labels.get(name, name), "slug": slugify(name)} if name else None

    # --- people
    people = []
    for p in data["people"]:
        p = dict(p)
        p["slug"] = slugify(p["name"])
        p["cat"] = cat(p.get("category"))
        p["photo_img"] = image_record("people", p["slug"], p.get("photo_local"))
        p["link_label"] = link_label(p["link"]) if p.get("link") else ""
        p["episodes"] = []
        people.append(p)
    assert len({p["slug"] for p in people}) == len(people), "duplicate person slug"
    by_id = {p["id"]: p for p in people}

    # --- episodes (published only, newest first)
    episodes = []
    unlinked = []
    for e in data["episodes"]:
        if e.get("status") != "Published":
            continue
        e = dict(e)
        e.pop("testo_per_guest", None)
        e.pop("transcript", None)
        e["url"] = f"/episodi/{e['episode']}/"
        e["info"] = clean_info(e.get("info"), e.get("title"))
        e["cat"] = cat(e.get("category"))
        e["tag_cats"] = [cat(t) for t in e.get("tags") or [] if t and t != e.get("category")]
        e["image_img"] = image_record("episodes", f"ep-{e['episode']:03d}", e.get("image_local"))
        e["yt_id"] = youtube_id(e.get("youtube"))
        if e.get("youtube") and not e["yt_id"]:
            print(f"  ! ep {e['episode']}: youtube field is not a YouTube URL: {e['youtube'][:60]}")
        e["reels"] = [e[k] for k in ("reel_1", "reel_2", "reel_3") if e.get(k)]
        e["link_label"] = link_label(e["link"]) if e.get("link") else ""
        e["guest_names"] = ", ".join(g["name"] for g in e["guests"])
        e["excerpt"] = excerpt(e.get("info"))
        gl = []
        for g in e["guests"]:
            person = by_id.get(g.get("person_id"))
            gl.append({"name": g["name"], "person": person})
            if person:
                person["episodes"].append(e)
            else:
                unlinked.append((e["episode"], g["name"]))
        e["guest_list"] = gl
        episodes.append(e)
    episodes.sort(key=lambda e: -e["episode"])
    for p in people:
        p["episodes"].sort(key=lambda e: -e["episode"])
    if unlinked:
        print(f"  note: {len(unlinked)} guests have no person record (no photo/bio in the episode page): "
              + ", ".join(f"ep {n} {g}" for n, g in unlinked[:6]) + (" …" if len(unlinked) > 6 else ""))

    # --- categories (reference order, only those with episodes)
    categories = []
    for c in cat_order:
        eps = [e for e in episodes if e.get("category") == c]
        if eps:
            categories.append({**cat(c), "count": len(eps), "cover": eps[0]})

    # --- articles (Substack cache written by tools/fetch_substack.py)
    articles = []
    sub_path = os.path.join(DATA, "data", "substack.json")
    if os.path.exists(sub_path):
        by_slug, by_num = {}, {}
        for e in episodes:
            m = re.search(r"/p/([^/?#]+)", e.get("substack") or "")
            if m:
                by_slug[m.group(1)] = e
            by_num[e["episode"]] = e
        for a in json.load(open(sub_path))["posts"]:
            a = dict(a)
            a["url"] = f"/articoli/{a['slug']}/"
            a["date"] = it_date(a.get("post_date"))
            a["cover_img"] = image_record("articoli", a["slug"], a.get("cover_local"))
            a["body"] = clean_body(a.get("body_html"), a.get("cover_image"))
            a["excerpt"] = excerpt(a.get("subtitle") or a.get("description") or "")
            m = re.match(r"\s*Ep\.?\s*(\d+)\s*:", a.get("title") or "")
            ep = by_slug.get(a["slug"]) or (by_num.get(int(m.group(1))) if m else None)
            a["episode"] = ep
            if ep and not ep.get("article"):
                ep["article"] = a
            articles.append(a)
        articles.sort(key=lambda a: a.get("post_date") or "", reverse=True)
        print(f"  articles: {len(articles)}, {sum(1 for a in articles if a['episode'])} linked to an episode")

    # prune image derivatives no longer referenced
    keep, made = set(), 0
    for rec in [e["image_img"] for e in episodes] + [p["photo_img"] for p in people if p["episodes"]] + [a["cover_img"] for a in articles]:
        if rec:
            keep |= rec["files"]
            made += rec["made"]
    if not NO_IMAGES and os.path.isdir(IMG):
        for dp, _, fn in os.walk(IMG):
            for f in fn:
                full = os.path.join(dp, f)
                if full not in keep:
                    os.remove(full)
    print(f"  images: {len(keep)} files in use, {made} written")

    presentation = next((e for e in episodes if e["episode"] == 0), None)
    env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")),
                      autoescape=select_autoescape(["html"]), trim_blocks=True, lstrip_blocks=True)
    env.filters.update(paragraphs=paragraphs, excerpt=excerpt)
    env.globals.update(img=img, link_label=link_label)
    base = SITE.get("base_url", "").rstrip("/")
    ctx = dict(site=SITE, base=base, episodes=episodes, categories=categories, articles=articles,
               project=data["project"], presentation=presentation, year=date.today().year,
               latest=[e for e in episodes if e["episode"] > 0][:6])

    def render(tpl, out, **kw):
        path = os.path.join(DOCS, out)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            f.write(env.get_template(tpl).render(**ctx, **kw))

    render("index.html", "index.html", page="home")
    render("episodes.html", "episodi/index.html", page="episodes")
    for i, e in enumerate(episodes):
        render("episode.html", f"episodi/{e['episode']}/index.html", page="episodes", ep=e,
               newer=episodes[i - 1] if i else None, older=episodes[i + 1] if i + 1 < len(episodes) else None)
    if articles:
        render("articles.html", "articoli/index.html", page="articles")
        for a in articles:
            render("article.html", f"articoli/{a['slug']}/index.html", page="articles", a=a)
    for d in os.listdir(os.path.join(DOCS, "articoli")) if os.path.isdir(os.path.join(DOCS, "articoli")) else []:
        full = os.path.join(DOCS, "articoli", d)
        if os.path.isdir(full) and d not in {a["slug"] for a in articles}:
            shutil.rmtree(full)
    render("about.html", "progetto/index.html", page="about")
    render("404.html", "404.html", page="404")
    for d in os.listdir(os.path.join(DOCS, "episodi")):      # pages of episodes no longer published
        full = os.path.join(DOCS, "episodi", d)
        if os.path.isdir(full) and d not in {str(e["episode"]) for e in episodes}:
            shutil.rmtree(full)

    # static assets, GitHub Pages plumbing
    for f in os.listdir(os.path.join(ROOT, "static")):
        shutil.copy(os.path.join(ROOT, "static", f), DOCS)
    open(os.path.join(DOCS, ".nojekyll"), "w").close()
    cname = os.path.join(DOCS, "CNAME")
    if SITE.get("domain"):
        open(cname, "w").write(SITE["domain"].strip() + "\n")
    elif os.path.exists(cname):
        os.remove(cname)
    urls = ["/", "/episodi/", "/progetto/"] + [e["url"] for e in episodes] + (["/articoli/"] if articles else []) + [a["url"] for a in articles]
    with open(os.path.join(DOCS, "sitemap.xml"), "w") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                + "".join(f"  <url><loc>{base}{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    with open(os.path.join(DOCS, "robots.txt"), "w") as f:
        f.write(f"User-agent: *\nAllow: /\nSitemap: {base}/sitemap.xml\n")
    print(f"build: {len(episodes)} episodes, {len(categories)} categories, {len(articles)} articles -> {DOCS}")


if __name__ == "__main__":
    main()
