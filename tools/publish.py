#!/usr/bin/env python3
"""Publish the site: refresh the Substack cache, build docs/, commit and push.

  python3 tools/publish.py              everything
  python3 tools/publish.py --no-fetch   skip the Substack refresh (offline, or in a hurry)

Prints a plain-text log; exit code 0 = published (or nothing to publish), 1 = a step failed.
Called by the "Publish site" button of torinoecultura-data/tec_ui.py, works from the shell too.
"""
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIT_ID = ["-c", "user.name=Carlo De Marchis", "-c", "user.email=carlodemarchis@gmail.com"]   # used only if the repo has no identity


def run(label, cmd, fatal=True, timeout=900):
    print(f"▶ {label}", flush=True)
    t = time.time()
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    out = (r.stdout + r.stderr).strip()
    if out:
        print("  " + out.replace("\n", "\n  "), flush=True)
    print(f"  ({time.time() - t:.0f}s, exit {r.returncode})", flush=True)
    if r.returncode and fatal:
        print(f"✗ {label} failed", flush=True)
        sys.exit(1)
    return r.returncode


def main():
    os.chdir(ROOT)
    if "--no-fetch" not in sys.argv:
        run("Substack: nuovi articoli", [sys.executable, "tools/fetch_substack.py"], fatal=False)
    run("Build del sito", [sys.executable, "build.py"])
    run("git add", ["git", "add", "-A"])
    if subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=ROOT).returncode == 0:
        print("✓ Niente da pubblicare: il sito online è già aggiornato.", flush=True)
        return
    stat = subprocess.run(["git", "diff", "--cached", "--shortstat"], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    print(f"  {stat}", flush=True)
    ident = GIT_ID if not subprocess.run(["git", "config", "user.email"], cwd=ROOT, capture_output=True, text=True).stdout.strip() else []
    run("git commit", ["git", *ident, "commit", "-q", "-m", f"content: aggiornamento {time.strftime('%Y-%m-%d %H:%M')}"])
    if run("git push", ["git", "push", "-q", "origin", "main"], fatal=False):
        print("  push rifiutato: provo a riallineare con origin/main", flush=True)
        run("git pull --rebase", ["git", *ident, "pull", "--rebase", "-X", "theirs", "-q", "origin", "main"])
        run("git push (2)", ["git", "push", "-q", "origin", "main"])
    print("✓ Pubblicato. GitHub Pages aggiorna il sito in 1-2 minuti (cache CDN fino a 10).", flush=True)


if __name__ == "__main__":
    main()
