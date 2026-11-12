"""Sets words as SVG paths in Nunito, from tools/fonts/nunito.json (made by tools/fonts/make_glyphs.py).

GitHub shows these SVGs through <img>, which loads no outside fonts; letters drawn as paths look the
same in every viewer. Each glyph is drawn once in <defs> and placed with <use>, kerned as the font says.
Standard library only.
"""
import json
import sys
from pathlib import Path

_KIT = None


def _kit():
    global _KIT
    if _KIT is None:
        _KIT = json.loads((Path(__file__).parent / "fonts" / "nunito.json").read_text(encoding="utf-8"))
    return _KIT


class Lettering:
    """One drawing's letters. `prefix` keeps its glyph ids apart from any other drawing's."""

    def __init__(self, prefix="n"):
        self.prefix = prefix
        self.ids = {}  # (weight, char) -> id

    def _run(self, s, weight):
        kit = _kit()
        face = kit["weights"][str(weight)]
        glyphs, kern = face["glyphs"], face["kern"]
        out, x, prev = [], 0, None
        for ch in s:
            if ch not in glyphs:
                print(f"lettering: no glyph for {ch!r}, drawn as a space", file=sys.stderr)
                ch = " "
            if prev is not None:
                x += kern.get(prev + ch, 0)
            out.append((ch, x))
            x += glyphs[ch][0]
            prev = ch
        return out, x, kit["unitsPerEm"]

    def width(self, s, size, weight, tracking=0.0):
        """Width in px of `s` at `size` px; `tracking` is extra space per letter, in em."""
        _, adv, upem = self._run(s, weight)
        return adv * size / upem + tracking * size * max(len(s) - 1, 0)

    def text(self, s, x, y, size, weight, fill, anchor="start", tracking=0.0, cls=""):
        """`s` with its baseline at y. anchor: start, middle or end."""
        return self.runs([(s, fill)], x, y, size, weight, anchor, tracking, cls)

    def runs(self, parts, x, y, size, weight, anchor="start", tracking=0.0, cls=""):
        """One line set as a whole (kerned across the joins), each part [(text, fill), ...] in its own colour."""
        s = "".join(p for p, _ in parts)
        run, adv, upem = self._run(s, weight)
        k = size / upem
        w = adv * k + tracking * size * max(len(s) - 1, 0)
        if anchor == "middle":
            x -= w / 2
        elif anchor == "end":
            x -= w
        face = _kit()["weights"][str(weight)]["glyphs"]
        c = f' class="{cls}"' if cls else ""
        out, i = [], 0
        for part, fill in parts:
            uses = []
            for ch, gx in run[i:i + len(part)]:
                if face[ch][1]:  # a space draws nothing
                    key = (weight, ch)
                    if key not in self.ids:
                        self.ids[key] = f"{self.prefix}{weight // 100}{len(self.ids):x}"
                    ux = gx + (tracking * upem * i if tracking else 0)
                    uses.append(f'<use href="#{self.ids[key]}" x="{ux:.0f}"/>')
                i += 1
            if uses:
                out.append(f'<g fill="{fill}">{"".join(uses)}</g>' if len(parts) > 1 else "".join(uses))
        fill = "" if len(parts) > 1 else f' fill="{parts[0][1]}"'
        return (f'<g{c}{fill} transform="matrix({k:.5f} 0 0 {-k:.5f} {x:.1f} {y:.1f})">'
                f'{"".join(out)}</g>')

    def defs(self):
        """The glyphs used so far, once each. Put it in the drawing's <defs>."""
        kit = _kit()["weights"]
        return "".join(f'<path id="{i}" d="{kit[str(w)]["glyphs"][ch][1]}"/>' for (w, ch), i in self.ids.items())
