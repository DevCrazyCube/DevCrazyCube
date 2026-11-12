"""Turns the Nunito files in this folder into nunito.json: every printable ASCII character (and a
few punctuation marks) as an SVG path, its advance, and the font's kerning between them.

usage: python3 tools/fonts/make_glyphs.py

Run it by hand, only when a font file here changes. It needs fontTools (pip install fonttools);
the card and banner scripts that read nunito.json need only the standard library.

Why paths and not an embedded font: GitHub shows the SVGs through <img>, where a font has to
travel inside the file. Paths need no font loading at all, so every viewer draws the same letters.

Nunito: Copyright 2014 The Nunito Project Authors, SIL Open Font License 1.1 (OFL.txt here).
The .ttf files are static instances of Nunito 3.602, latin subset.
"""
import json
from pathlib import Path

from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.ttLib import TTFont

HERE = Path(__file__).parent
WEIGHTS = (700, 800, 900)
CHARS = [chr(c) for c in range(32, 127)] + list("·–—’…")


def kerning(font, names):
    """Pair kerning (x advance, font units) between the glyphs in `names`, from GPOS 'kern'."""
    gpos = font["GPOS"].table
    lookups = set()
    for rec in gpos.FeatureList.FeatureRecord:
        if rec.FeatureTag == "kern":
            lookups.update(rec.Feature.LookupListIndex)
    wanted = set(names)
    pairs = {}
    for li in sorted(lookups):
        lookup = gpos.LookupList.Lookup[li]
        done = set()  # within one lookup, the first subtable that covers a pair decides it
        for sub in lookup.SubTable:
            if lookup.LookupType == 9:
                sub = sub.ExtSubTable
            if sub.Format == 1:
                for first, pset in zip(sub.Coverage.glyphs, sub.PairSet):
                    if first not in wanted:
                        continue
                    for rec in pset.PairValueRecord:
                        key = (first, rec.SecondGlyph)
                        if rec.SecondGlyph not in wanted or key in done:
                            continue
                        done.add(key)
                        x = getattr(rec.Value1, "XAdvance", 0) or 0
                        if x:
                            pairs[key] = pairs.get(key, 0) + x
            elif sub.Format == 2:
                c1 = sub.ClassDef1.classDefs
                c2 = sub.ClassDef2.classDefs
                for first in sub.Coverage.glyphs:
                    if first not in wanted:
                        continue
                    row = sub.Class1Record[c1.get(first, 0)]
                    for second in wanted:
                        key = (first, second)
                        if key in done:
                            continue
                        done.add(key)
                        x = getattr(row.Class2Record[c2.get(second, 0)].Value1, "XAdvance", 0) or 0
                        if x:
                            pairs[key] = pairs.get(key, 0) + x
    return pairs


def main():
    out = {"source": "Nunito 3.602 (OFL 1.1), static instances", "unitsPerEm": None, "weights": {}}
    for w in WEIGHTS:
        font = TTFont(HERE / f"Nunito-{w}.ttf")
        out["unitsPerEm"] = font["head"].unitsPerEm
        cmap = font.getBestCmap()
        gs = font.getGlyphSet()
        glyphs, name_of = {}, {}
        for ch in CHARS:
            name = cmap.get(ord(ch))
            if name is None:
                continue
            pen = SVGPathPen(gs, ntos=lambda v: str(round(v)))
            gs[name].draw(pen)
            glyphs[ch] = [font["hmtx"][name][0], pen.getCommands()]
            name_of[name] = ch
        kern = {name_of[a] + name_of[b]: v for (a, b), v in sorted(kerning(font, name_of).items())}
        out["weights"][str(w)] = {"glyphs": glyphs, "kern": kern}
        print(f"Nunito {w}: {len(glyphs)} glyphs, {len(kern)} kerning pairs")
    (HERE / "nunito.json").write_text(json.dumps(out, separators=(",", ":"), ensure_ascii=False) + "\n",
                                      encoding="utf-8")


if __name__ == "__main__":
    main()
