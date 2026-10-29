#!/usr/bin/env python3
"""Refresh the local cache of the Torino e Cultura Substack (all posts, full text, cover images).

  python3 tools/fetch_substack.py          new posts + posts whose date changed; bodies already cached are kept
  python3 tools/fetch_substack.py --all    refetch every body

Writes <data_dir>/data/substack.json and <data_dir>/data/photos/substack/<slug>.<ext>  (data_dir from site.json).
The public RSS feed only carries the latest ~20 posts; the archive API is paged by offset and each post's
body_html comes from /api/v1/posts/<slug>. Only free ("everyone") posts are kept.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = json.load(open(os.path.join(ROOT, "site.json")))
DATA = os.path.abspath(os.path.join(ROOT, os.path.expanduser(SITE["data_dir"])))
PUB = SITE.get("substack", "https://torinoecultura.substack.com").rstrip("/")
OUT = os.path.join(DATA, "data", "substack.json")
PHOTOS = os.path.join(DATA, "data", "photos", "substack")
KEEP = ("id", "slug", "title", "subtitle", "description", "post_date", "canonical_url", "cover_image", "wordcount", "audience", "type")
UA = {"User-Agent": "Mozilla/5.0 (torinoecultura.it site build)"}


def get(url, binary=False):
    for wait in (0, 15, 45, 120):
        if wait:
            print(f"  429, waiting {wait}s"); time.sleep(wait)
        req = urllib.request.Request(url, headers=UA)
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return r.read() if binary else json.load(r)
        except urllib.error.HTTPError as e:
            if e.code != 429:
                raise
    raise RuntimeError(f"still rate-limited: {url}")


def save(out):
    out = sorted(out, key=lambda r: r["post_date"] or "", reverse=True)
    json.dump({"fetched": time.strftime("%Y-%m-%d"), "publication": PUB, "posts": out}, open(OUT, "w"), ensure_ascii=False, indent=1)


def main():
    refetch_all = "--all" in sys.argv
    old = {}
    if os.path.exists(OUT):
        old = {p["slug"]: p for p in json.load(open(OUT))["posts"]}
    posts, offset = [], 0
    while True:
        page = get(f"{PUB}/api/v1/archive?sort=new&search=&offset={offset}&limit=12")
        if not page:
            break
        posts.extend(page)
        offset += len(page)
        time.sleep(0.3)
    print(f"archive: {len(posts)} posts")
    os.makedirs(PHOTOS, exist_ok=True)
    out, fetched = [], 0
    for p in posts:
        if p.get("type") not in ("newsletter", "podcast", None) or p.get("audience") not in ("everyone", None):
            print(f"  skip {p['slug']} ({p.get('type')}, {p.get('audience')})")
            continue
        rec = {k: p.get(k) for k in KEEP}
        prev = old.get(p["slug"])
        if prev and prev.get("body_html") and not refetch_all and prev.get("post_date") == p.get("post_date"):
            rec["body_html"] = prev["body_html"]
            rec["cover_local"] = prev.get("cover_local")
        else:
            full = get(f"{PUB}/api/v1/posts/{p['slug']}")
            rec["body_html"] = full.get("body_html") or ""
            fetched += 1
            time.sleep(1)
        if rec.get("cover_image") and not (rec.get("cover_local") and os.path.exists(os.path.join(DATA, "data", rec["cover_local"]))):
            try:
                blob = get(rec["cover_image"], binary=True)
                ext = "png" if blob[:4] == b"\x89PNG" else ("webp" if blob[8:12] == b"WEBP" else "jpg")
                name = f"{p['slug']}.{ext}"
                open(os.path.join(PHOTOS, name), "wb").write(blob)
                rec["cover_local"] = f"photos/substack/{name}"
            except Exception as e:
                print(f"  ! cover of {p['slug']}: {e}")
                rec["cover_local"] = None
        out.append(rec)
        if fetched and fetched % 10 == 0:
            save(out + [o for s_, o in old.items() if s_ not in {r["slug"] for r in out}])   # partial progress survives a crash
    save(out)
    print(f"wrote {OUT}: {len(out)} posts, {fetched} bodies fetched")


if __name__ == "__main__":
    main()
