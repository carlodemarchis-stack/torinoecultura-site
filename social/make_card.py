#!/usr/bin/env python3
"""Instagram card (default 1012x1350, no photos): logo, tagline, URL in evidence, social row.

  python3 social/make_card.py                      -> social/card-1012x1350.png
  python3 social/make_card.py --size 1080x1350     any size
  python3 social/make_card.py --tagline "…"        override the text (default: site tagline)

Renders social/card.html with jinja2 (icons from templates/_icons.html) and shoots it with headless Chrome
(wrapped in a perl alarm: Chrome on this Mac sometimes hangs after writing the file).
"""
import json
import os
import subprocess
import sys

from jinja2 import Environment, FileSystemLoader

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = json.load(open(os.path.join(ROOT, "site.json")))
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
args = sys.argv[1:]
size = args[args.index("--size") + 1] if "--size" in args else "1012x1350"
tagline = args[args.index("--tagline") + 1] if "--tagline" in args else SITE["tagline"]
w, h = (int(x) for x in size.split("x"))

TEMPLATE = """<!doctype html><html lang="it"><head><meta charset="utf-8">
<style>
html,body{margin:0;background:#000;color:#fff;font-family:"Helvetica Neue",Helvetica,Arial,sans-serif;-webkit-font-smoothing:antialiased}
.card{width:{{ w }}px;height:{{ h }}px;display:flex;flex-direction:column;justify-content:space-between;padding:{{ (w*0.085)|int }}px;box-sizing:border-box}
.logo{width:{{ (w*0.72)|int }}px;height:auto;display:block}
.tag{font-weight:700;font-size:{{ (w*0.064)|int }}px;line-height:1.1;letter-spacing:-.03em;margin:0;text-wrap:balance}
.url{display:inline-block;background:#fff;color:#000;font-weight:700;font-size:{{ (w*0.078)|int }}px;letter-spacing:-.035em;line-height:1;padding:{{ (w*0.03)|int }}px {{ (w*0.045)|int }}px;align-self:flex-start}
.url small{display:block;font-size:{{ (w*0.024)|int }}px;letter-spacing:.14em;text-transform:uppercase;font-weight:500;margin-bottom:{{ (w*0.014)|int }}px}
.social{display:flex;gap:{{ (w*0.05)|int }}px;align-items:center}
.social span{display:inline-flex}
.social svg{width:{{ (w*0.07)|int }}px;height:{{ (w*0.07)|int }}px;display:block}
.handle{font-size:{{ (w*0.034)|int }}px;font-weight:600;color:#fff;margin:{{ (w*0.035)|int }}px 0 0;letter-spacing:-.01em}
.handle small{display:block;font-size:{{ (w*0.024)|int }}px;color:#999;font-weight:500;letter-spacing:.12em;text-transform:uppercase;margin-top:{{ (w*0.01)|int }}px}
</style></head><body><div class="card">
<img class="logo" src="file://{{ logo }}" alt="Torino e Cultura">
<p class="tag">{{ tagline }}</p>
<a class="url"><small>Il nuovo sito</small>{{ domain }}</a>
<div>
<div class="social">{% for k, label in socials %}<span title="{{ label }}">{{ ico[k]() }}</span>{% endfor %}</div>
<p class="handle">@torinoecultura<small>Instagram · YouTube · Spotify · Substack · LinkedIn</small></p>
</div>
</div></body></html>"""

env = Environment(loader=FileSystemLoader(os.path.join(ROOT, "templates")))
ico = env.get_template("_icons.html").module
html = env.from_string(TEMPLATE).render(w=w, h=h, logo=os.path.join(ROOT, "static", "logo-wide.webp"), tagline=tagline, domain=SITE["domain"], ico=ico,
                                        socials=[("instagram", "Instagram"), ("youtube", "YouTube"), ("spotify", "Spotify"), ("substack", "Substack"), ("linkedin", "LinkedIn")])
page = os.path.join(ROOT, "social", "card.html")
open(page, "w").write(html)
out = os.path.join(ROOT, "social", f"card-{w}x{h}.png")
subprocess.run(["perl", "-e", "alarm 60; exec @ARGV", CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--no-first-run",
                "--user-data-dir=/tmp/claude-501/chrome-tec-card", "--force-device-scale-factor=1", f"--window-size={w},{h}", f"--screenshot={out}", "file://" + page],
               capture_output=True)
print(out if os.path.exists(out) else "FAILED: no screenshot written")
