"""Counts this account's public numbers and draws them as two SVG cards (light and dark).

usage: python3 tools/stats.py <login> <out dir> [--have name=path ...]

What it counts, and only this:
  repos      public repositories the account owns that are not forks
  stars      stars on those repositories
  followers  the account's followers
  commits    commits on the default branch of each of those repositories, added up
  lines      lines in the code files of those repositories' default branch (see CODE below);
             vendored folders, files over 1 MB and minified files are left out

It reads GitHub through the `gh` command (which takes its token from the environment in an
Action, or from `gh auth login` on a laptop) and clones each repository at depth 1 into a
temporary folder to count lines. `--have name=path` uses a checkout that is already on disk
for that repository instead of cloning it.

Standard library only. Nothing is written outside <out dir> and the temporary folder.
"""
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CODE = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
    ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".java": "Java",
    ".cs": "C#", ".sql": "SQL", ".sh": "Shell", ".css": "CSS", ".html": "HTML",
    ".rs": "Rust", ".go": "Go", ".c": "C", ".h": "C", ".cpp": "C++", ".kt": "Kotlin",
}
SKIP_DIRS = {"node_modules", "dist", "build", "vendor", ".venv", "venv", "__pycache__",
             ".idea", "models", "logs", "lib", "third_party"}
MAX_BYTES = 1_000_000

LANG_COLOURS = ["#2f55d4", "#f2b632", "#2fa36b", "#d6457a", "#7a4fd6", "#8a93a8"]

THEMES = {
    "light": dict(bg="#ffffff", edge="#d9d2c3", ink="#161a26", ink2="#4b5265", tile="#f5f2eb",
                  tile_edge="#e3ddcf", track="#ece7dc"),
    "dark": dict(bg="#0e1424", edge="#27304a", ink="#f1f3fa", ink2="#a4adc6", tile="#151d35",
                 tile_edge="#27304a", track="#1c2540"),
}
TILE_COLOURS = ["#2f55d4", "#f2b632", "#d6457a", "#2fa36b", "#7a4fd6"]
SANS = "-apple-system, 'Segoe UI', Helvetica, Arial, sans-serif"


def gh(*args):
    done = subprocess.run(["gh", "api", *args], capture_output=True, text=True)
    if done.returncode != 0:
        raise SystemExit(f"gh api {' '.join(args)} failed: {done.stderr.strip()[:300]}")
    return done.stdout


def commit_count(full_name):
    """Commits on the default branch: the number of the last page when asking for one a page."""
    done = subprocess.run(["gh", "api", "-i", f"repos/{full_name}/commits?per_page=1"],
                          capture_output=True, text=True)
    if done.returncode != 0:
        return 0  # an empty repository answers 409
    last = re.search(r'[?&]page=(\d+)>; rel="last"', done.stdout)
    return int(last.group(1)) if last else 1


def count_lines(folder):
    """Lines per language in the tracked code files of the checkout in `folder`."""
    listed = subprocess.run(["git", "-C", str(folder), "ls-files", "-z"], capture_output=True)
    if listed.returncode != 0:
        raise SystemExit(f"git ls-files failed in {folder}")
    per_lang = {}
    for raw in listed.stdout.split(b"\0"):
        if not raw:
            continue
        rel = Path(raw.decode("utf-8", "replace"))
        lang = CODE.get(rel.suffix.lower())
        if not lang or SKIP_DIRS & set(rel.parts[:-1]) or ".min." in rel.name:
            continue
        path = Path(folder) / rel
        try:
            if path.is_symlink() or path.stat().st_size > MAX_BYTES:
                continue
            data = path.read_bytes()
        except OSError:
            continue
        per_lang[lang] = per_lang.get(lang, 0) + data.count(b"\n") + (1 if data and not data.endswith(b"\n") else 0)
    return per_lang


def collect(login, have):
    user = json.loads(gh(f"users/{login}"))
    repos = json.loads(gh("--paginate", "--slurp", f"users/{login}/repos?per_page=100&type=owner"))
    repos = [r for page in repos for r in page if not r["fork"] and not r["private"]]
    stars = sum(r["stargazers_count"] for r in repos)
    commits = 0
    langs = {}
    with tempfile.TemporaryDirectory(prefix="stats-") as tmp:
        for r in repos:
            commits += commit_count(r["full_name"])
            if r["size"] == 0:
                continue
            folder = have.get(r["name"])
            if folder is None:
                folder = Path(tmp) / r["name"]
                cloned = subprocess.run(["git", "clone", "-q", "--depth", "1", r["clone_url"], str(folder)],
                                        capture_output=True, text=True)
                if cloned.returncode != 0:
                    raise SystemExit(f"clone of {r['name']} failed: {cloned.stderr.strip()[:300]}")
            for lang, n in count_lines(folder).items():
                langs[lang] = langs.get(lang, 0) + n
            print(f"counted {r['name']}", file=sys.stderr)
    return dict(repos=len(repos), stars=stars, followers=user["followers"], commits=commits,
                lines=sum(langs.values()), langs=langs)


def draw(data, theme, today):
    t = THEMES[theme]
    tiles = [("Public repos", data["repos"]), ("Stars", data["stars"]), ("Followers", data["followers"]),
             ("Commits", data["commits"]), ("Lines of code", data["lines"])]
    out = []
    w, gap, x0, y0, h = 216, 18, 24, 24, 118
    for i, (label, value) in enumerate(tiles):
        x = x0 + i * (w + gap)
        c = TILE_COLOURS[i]
        out.append(
            f'<g class="up" style="animation-delay:{i * 0.12:.2f}s">'
            f'<rect x="{x}" y="{y0}" width="{w}" height="{h}" rx="16" fill="{t["tile"]}" stroke="{t["tile_edge"]}" stroke-width="1.5"/>'
            f'<rect x="{x + 20}" y="{y0 + 20}" width="28" height="6" rx="3" fill="{c}"/>'
            f'<text x="{x + 20}" y="{y0 + 70}" font-family="{SANS}" font-size="38" font-weight="800" letter-spacing="-1" fill="{t["ink"]}">{value:,}</text>'
            f'<text x="{x + 20}" y="{y0 + 96}" font-family="{SANS}" font-size="15" font-weight="600" fill="{t["ink2"]}">{label}</text>'
            f'</g>')

    total = data["lines"] or 1
    ranked = sorted(data["langs"].items(), key=lambda kv: -kv[1])
    top, rest = ranked[:5], sum(n for _, n in ranked[5:])
    if rest:
        top.append(("Other", rest))
    bx, by, bw, bh = 24, 170, 1152, 16
    segs, legend, x = [], [], float(bx)
    lx = bx
    for i, (lang, n) in enumerate(top):
        share = n / total
        sw = bw * share
        colour = LANG_COLOURS[i % len(LANG_COLOURS)]
        segs.append(f'<rect x="{x:.1f}" y="{by}" width="{sw + 0.5:.1f}" height="{bh}" fill="{colour}"/>')
        x += sw
        text = f"{lang} {share * 100:.0f}%" if share >= 0.005 else f"{lang} &lt;1%"
        legend.append(
            f'<circle cx="{lx + 6}" cy="{by + 46}" r="6" fill="{colour}"/>'
            f'<text x="{lx + 20}" y="{by + 51}" font-family="{SANS}" font-size="15" font-weight="600" fill="{t["ink2"]}">{text}</text>')
        lx += 34 + int(len(lang) * 9.2) + 44
    out.append(
        f'<clipPath id="bar"><rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="8"/></clipPath>'
        f'<rect x="{bx}" y="{by}" width="{bw}" height="{bh}" rx="8" fill="{t["track"]}"/>'
        f'<g clip-path="url(#bar)"><g class="grow">{"".join(segs)}</g></g>'
        # The legend does not animate: a delayed fade left it hidden in some renderers.
        f'<g>{"".join(legend)}</g>')
    out.append(
        f'<text x="1176" y="{by + 51}" text-anchor="end" font-family="{SANS}" font-size="13" fill="{t["ink2"]}">'
        f'public repos only · counted {today}</text>')

    label = (f'{data["repos"]} public repos, {data["stars"]} stars, {data["followers"]} followers, '
             f'{data["commits"]:,} commits, {data["lines"]:,} lines of code. Counted {today}.')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 250" width="1200" height="250" role="img" aria-label="{label}">
<style>
.up{{animation:up .6s ease-out both}}
.grow{{transform-box:fill-box;transform-origin:left center;animation:grow 1.1s cubic-bezier(.2,.8,.2,1) .5s both}}
@keyframes up{{from{{opacity:0;transform:translateY(10px)}}to{{opacity:1;transform:none}}}}
@keyframes grow{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@media (prefers-reduced-motion:reduce){{.up,.grow{{animation:none}}}}
</style>
<rect x="1" y="1" width="1198" height="248" rx="22" fill="{t["bg"]}" stroke="{t["edge"]}" stroke-width="2"/>
{"".join(out)}
</svg>
'''


def main():
    args = sys.argv[1:]
    if len(args) < 2:
        raise SystemExit(__doc__)
    login, out = args[0], Path(args[1])
    have = {}
    rest = args[2:]
    while rest:
        if rest[0] != "--have" or len(rest) < 2 or "=" not in rest[1]:
            raise SystemExit("expected --have name=path")
        name, path = rest[1].split("=", 1)
        have[name] = Path(path)
        rest = rest[2:]
    data = collect(login, have)
    today = datetime.date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)
    for theme in THEMES:
        (out / f"stats-{theme}.svg").write_text(draw(data, theme, today), encoding="utf-8")
    (out / "stats.json").write_text(json.dumps(dict(data, counted=today), indent=2, sort_keys=True) + "\n")
    print(json.dumps(data, sort_keys=True))


if __name__ == "__main__":
    main()
