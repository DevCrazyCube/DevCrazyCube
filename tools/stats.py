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
The card's words are Nunito glyphs read from tools/fonts/nunito.json (see tools/lettering.py).
"""
import datetime
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lettering import Lettering  # noqa: E402  (tools/lettering.py: words as Nunito paths)

CODE = {
    ".py": "Python", ".ts": "TypeScript", ".tsx": "TypeScript", ".js": "JavaScript",
    ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript", ".java": "Java",
    ".cs": "C#", ".sql": "SQL", ".sh": "Shell", ".css": "CSS", ".html": "HTML",
    ".rs": "Rust", ".go": "Go", ".c": "C", ".h": "C", ".cpp": "C++", ".kt": "Kotlin",
}
SKIP_DIRS = {"node_modules", "dist", "build", "vendor", ".venv", "venv", "__pycache__",
             ".idea", "models", "logs", "lib", "third_party"}
MAX_BYTES = 1_000_000

# The card is drawn in StudySync's own material: keys with a solid darker bottom edge (no blurred
# shadows), one cobalt key for the number that leads, and a chunky bar for the languages. The
# words are Nunito, set as paths by tools/lettering.py (GitHub's <img> loads no outside fonts).
THEMES = {
    "light": dict(face="#ffffff", frame="#d3dae3", edge="#c3ccd8", num="#15202e", label="#5a6473",
                  hero="#2f55d4", hero_edge="#1f3b98", hero_num="#ffffff", hero_label="#d6deff",
                  track="#e4e8ee", track_edge="#d3dae3", note="#5a6473", other="#8794ad",
                  # checked with a colour-vision validator against white, in this order
                  langs=["#2f55d4", "#d99a0b", "#0d8f84", "#e0521c", "#9a62f2"]),
    "dark": dict(face="#161d27", frame="#2a3340", edge="#333d4b", num="#e8edf3", label="#93a0b0",
                 hero="#2f55d4", hero_edge="#1a3080", hero_num="#ffffff", hero_label="#d6deff",
                 track="#161d27", track_edge="#2a3340", note="#93a0b0", other="#6b7686",
                 # the same check against GitHub's dark page (#0d1117)
                 langs=["#3f62e3", "#b8820a", "#17a99d", "#e8601f", "#9a64f5"]),
}
# A colour follows its language, not its rank: these keep their slot in `langs` whenever they are
# shown; another language that makes the top five takes a slot none of the shown ones holds.
LANG_SLOT = {"Python": 0, "JavaScript": 1, "TypeScript": 2, "Rust": 3, "HTML": 4}
SHOWN = 5  # languages named on the bar; the rest are added up as "Other"
W = 1200


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


def plural(n, one, many):
    return one if n == 1 else many


def key(x, y, w, h, face, frame, edge, depth=8, r=18, line=2.5):
    """A key: its face in a frame, standing on a solid darker edge (no blur)."""
    return (f'<rect x="{x:.1f}" y="{y + depth}" width="{w:.1f}" height="{h}" rx="{r}" fill="{edge}"/>'
            f'<rect x="{x:.1f}" y="{y}" width="{w:.1f}" height="{h}" rx="{r}" fill="{frame}"/>'
            f'<rect x="{x + line:.1f}" y="{y + line}" width="{w - 2 * line:.1f}" height="{h - 2 * line}" '
            f'rx="{r - line}" fill="{face}"/>')


def fit(L, s, size, weight, room):
    """`size`, or smaller until `s` fits in `room` px."""
    w = L.width(s, size, weight)
    return size if w <= room else size * room / w


def ink_on(colour):
    """White words on `colour` when they reach 4.5:1, else whichever of white and ink reads better."""
    def ch(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (int(colour[i:i + 2], 16) for i in (1, 3, 5))
    lum = 0.2126 * ch(r) + 0.7152 * ch(g) + 0.0722 * ch(b)
    white, ink = 1.05 / (lum + 0.05), (lum + 0.05) / 0.0638  # 0.0638: the ink #15202e, plus 0.05
    return "#ffffff" if white >= 4.5 or white >= ink else "#15202e"


def lang_parts(langs, palette, other):
    """[(name, lines, colour)]: the top languages, then the rest as Other."""
    ranked = sorted(langs.items(), key=lambda kv: (-kv[1], kv[0]))
    top, rest = ranked[:SHOWN], sum(n for _, n in ranked[SHOWN:])
    taken = {LANG_SLOT[name] for name, _ in top if name in LANG_SLOT}
    free = [i for i in range(len(palette)) if i not in taken]
    parts = [(name, n, palette[LANG_SLOT[name] if name in LANG_SLOT else free.pop(0)]) for name, n in top]
    if rest:
        parts.append(("Other", rest, other))
    return parts


def draw(data, theme, today):
    t = THEMES[theme]
    L = Lettering("s")
    out = []

    # The keys: lines of code leads, on the cobalt key; the other four on white ones.
    y, h, gap = 2, 136, 16
    lead = f'{data["lines"]:,}'
    lead_w = max(372, L.width(lead, 68, 900) + 72)
    out.append(key(0, y, lead_w, h, t["hero"], t["hero"], t["hero_edge"]))
    out.append(L.text(lead, 34, y + 80, 68, 900, t["hero_num"], tracking=-0.01))
    out.append(L.text(plural(data["lines"], "line of code", "lines of code"), 36, y + 113, 24, 800, t["hero_label"]))
    small = [(data["commits"], "commit", "commits"), (data["repos"], "public repo", "public repos"),
             (data["followers"], "follower", "followers"), (data["stars"], "star", "stars")]
    w = (W - lead_w - gap * len(small)) / len(small)
    size = min(fit(L, f"{n:,}", 56, 900, w - 56) for n, _, _ in small)  # one size for all four
    x = lead_w + gap
    for n, one, many in small:
        out.append(key(x, y, w, h, t["face"], t["frame"], t["edge"]))
        out.append(L.text(f"{n:,}", x + 28, y + 78, size, 900, t["num"], tracking=-0.01))
        out.append(L.text(plural(n, one, many), x + 30, y + 113, 24, 800, t["label"]))
        x += w + gap

    # The languages: a chunky bar like a StudySync session's, each part as wide as its share of
    # the lines. A part wide enough carries its own name; the others are named in the line below.
    by, bh = 184, 30
    total = sum(data["langs"].values()) or 1
    parts = lang_parts(data["langs"], t["langs"], t["other"])
    segs, labels, legend = [], [], []
    x = 0.0
    for i, (name, n, colour) in enumerate(parts):
        sw = W * n / total
        share = n / total * 100
        text = f"{name} {share:.0f}%" if share >= 0.5 else f"{name} <1%"
        width = sw if i == len(parts) - 1 else max(sw - 3, 1)  # a 3 px gap of track between parts
        segs.append(f'<rect x="{x:.1f}" y="{by}" width="{width:.1f}" height="{bh}" fill="{colour}"/>')
        if sw >= L.width(text, 18, 800) + 36:
            labels.append(L.text(text, x + 16, by + 23, 18, 800, ink_on(colour)))
        else:
            legend.append((text, colour))
        x += sw
    out.append(f'<rect x="0" y="{by + 5}" width="{W}" height="{bh}" rx="{bh / 2}" fill="{t["track_edge"]}"/>')
    out.append(f'<rect x="0" y="{by}" width="{W}" height="{bh}" rx="{bh / 2}" fill="{t["track"]}"/>')
    out.append(f'<clipPath id="bar"><rect x="0" y="{by}" width="{W}" height="{bh}" rx="{bh / 2}"/></clipPath>')
    out.append(f'<g clip-path="url(#bar)"><g class="fill">{"".join(segs)}'
               f'<rect x="12" y="{by + 5}" width="{W - 24}" height="4" rx="2" fill="#ffffff" opacity=".24"/></g></g>')
    out.extend(labels)

    ly, lx = by + bh + 40, 0.0
    for text, colour in legend:
        out.append(f'<rect x="{lx:.1f}" y="{ly - 15}" width="16" height="16" rx="4" fill="{colour}"/>')
        out.append(L.text(text, lx + 24, ly, 20, 800, t["label"]))
        lx += 24 + L.width(text, 20, 800) + 26
    note = f"public repos only · counted {today}"
    if lx + L.width(note, 18, 700) + 24 > W:
        ly += 34  # no room beside the legend: the note gets its own line
    out.append(L.text(note, W, ly, 18, 700, t["note"], anchor="end"))
    height = ly + 10

    top = max(data["langs"], key=data["langs"].get) if data["langs"] else None
    label = (f'{data["lines"]:,} lines of code, {data["commits"]:,} commits, {data["repos"]} public repos, '
             f'{data["followers"]} followers, {data["stars"]} stars'
             + (f'; {data["langs"][top] / total * 100:.0f}% of the lines are {top}' if top else "")
             + f'. Public repos only, counted {today}.')
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {height}" width="{W}" height="{height}" role="img" aria-label="{label}">
<defs>{L.defs()}</defs>
<style>
.fill{{transform-box:fill-box;transform-origin:left center;animation:fill 1.1s cubic-bezier(.2,.8,.2,1)}}
@keyframes fill{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
@media (prefers-reduced-motion:reduce){{.fill{{animation:none}}}}
</style>
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
