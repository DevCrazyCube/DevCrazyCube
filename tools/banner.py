"""Draws the profile banner twice (light and dark): assets/banner-light.svg and banner-dark.svg.

usage: python3 tools/banner.py [out dir]      (default: assets)

The banner is one of StudySync's moments: one flat colour and the character big on its own flat
shadow. The character is my cell from StudySync, holding a magnifying glass, because checking
what the agents made is the job; the lens catches the light, and the word "check" has its gold. tools/art/cell.svg is that drawing, exported
from StudySync's character code (cellSvg in lib/character/cell.ts, its look in tools/art/cell.json),
turned to face the words. The words are Nunito, set as paths by tools/lettering.py.
Standard library only.
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from lettering import Lettering  # noqa: E402

W, H = 1200, 360

THEMES = {
    # field: the flat colour (StudySync's cobalt); ground: the cell's shadow on it; line: the
    # sentence; key: the word "check", in the lens rim's gold; glint: the light off the lens
    "light": dict(field="#2f55d4", ground="#2443aa", name="#ffffff", line="#d6deff", key="#ffc43d",
                  glint="#ffffff"),
    "dark": dict(field="#2a4cc0", ground="#1f3b98", name="#ffffff", line="#c9d3ff", key="#ffc43d",
                 glint="#ffffff"),
}

NAME = "Joyren Terken"
LINE1 = "I build by directing AI coding agents,"
LINE2 = (("and I ", "line"), ("check", "key"), (" what they make.", "line"))

# The cell's stage (cell units: 160 x 180, ground at y 168), its size and place on the banner.
K = 2.12
STAGE = (-14, 0, 188, 180)
CELL_AT = (818, -34)
HAND = (137, 124)  # where the cell's right hand holds things (HOLD_HAND), before it is turned around
LENS = (6.6, 90.3)  # the lens's centre once the cell faces left (the magnifier is held at x 153.4)


def at(x, y):
    """A point of the cell's stage on the banner."""
    return CELL_AT[0] + (x - STAGE[0]) * K, CELL_AT[1] + (y - STAGE[1]) * K


def glint(cx, cy, colour):
    """The lens catching the light: three short strokes off its upper rim, the cartoon "ting"."""
    d = ""
    for deg, r0, r1 in ((198, 46, 62), (226, 46, 68), (254, 46, 62)):
        a = math.radians(deg)
        d += (f"M{cx + r0 * math.cos(a):.1f},{cy + r0 * math.sin(a):.1f} "
              f"L{cx + r1 * math.cos(a):.1f},{cy + r1 * math.sin(a):.1f} ")
    return (f'<path class="ting" d="{d.strip()}" fill="none" stroke="{colour}" stroke-width="7" '
            f'stroke-linecap="round" style="transform-origin:{cx:.1f}px {cy:.1f}px"/>')


def banner(t, cell):
    L = Lettering("b")
    words = [
        L.text(NAME, 70, 156, 92, 900, t["name"], tracking=-0.012),
        L.text(LINE1, 73, 222, 31, 800, t["line"]),
        L.runs([(s, t[c]) for s, c in LINE2], 73, 264, 31, 800),
    ]
    sx, sy, sw, sh = STAGE
    stage = (f'<svg x="{CELL_AT[0]}" y="{CELL_AT[1]}" width="{sw * K:.1f}" height="{sh * K:.1f}" '
             f'viewBox="{sx} {sy} {sw} {sh}" overflow="visible">'
             f'<g transform="translate(160 0) scale(-1 1)">{cell}</g></svg>')
    gx, gy = at(80, 168)
    ground = f'<ellipse cx="{gx:.1f}" cy="{gy:.1f}" rx="{64 * K:.1f}" ry="{8.5 * K:.1f}" fill="{t["ground"]}"/>'
    lx, ly = at(*LENS)
    hx, hy = at(160 - HAND[0], HAND[1])
    # the glint sways with the lens (about the hand) and gives a small "ting" once a sway
    shine = f'<g class="sw" style="transform-origin:{hx:.1f}px {hy:.1f}px">{glint(lx, ly, t["glint"])}</g>'
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" aria-label="Joyren Terken. I build by directing AI coding agents, and I check what they make.">
<defs>{L.defs()}<clipPath id="field"><rect width="{W}" height="{H}" rx="28"/></clipPath></defs>
<style>
.cell .c-body{{animation:breathe 2.8s ease-in-out infinite}}
.cell .c-eyes{{animation:blink 4.6s infinite}}
.cell .c-held{{animation:sway 4.2s ease-in-out infinite}}
.sw{{animation:sway-mirror 4.2s ease-in-out infinite}}
.ting{{animation:ting 4.2s ease-out infinite}}
@keyframes ting{{0%,62%,100%{{transform:scale(1)}}72%{{transform:scale(1.16)}}}}
@keyframes sway-mirror{{0%,100%{{transform:rotate(0)}}50%{{transform:rotate(6deg)}}}}
@keyframes breathe{{0%,100%{{transform:scale(1,1)}}50%{{transform:scale(1.018,.978)}}}}
@keyframes blink{{0%,90%,100%{{transform:scaleY(1)}}93%,95%{{transform:scaleY(.08)}}}}
@keyframes sway{{0%,100%{{transform:rotate(0)}}50%{{transform:rotate(-6deg)}}}}
@media (prefers-reduced-motion:reduce){{*{{animation:none!important}}}}
</style>
<g clip-path="url(#field)">
<rect width="{W}" height="{H}" fill="{t["field"]}"/>
{ground}
{stage}
{shine}
</g>
{"".join(words)}
</svg>
'''


def main():
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent.parent / "assets"
    cell = (Path(__file__).parent / "art" / "cell.svg").read_text(encoding="utf-8").strip()
    out.mkdir(parents=True, exist_ok=True)
    for name, theme in THEMES.items():
        (out / f"banner-{name}.svg").write_text(banner(theme, cell), encoding="utf-8")
        print("wrote", out / f"banner-{name}.svg")


if __name__ == "__main__":
    main()
