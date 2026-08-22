#!/usr/bin/env python3
"""Render an Android adaptive launcher icon (vector drawable foreground + solid
background colour) to a square PNG, for fastlane images/icon.png.

usage: vd2png.py <foreground.xml> <background_hex> <out.png> [size=512]

Handles <path> (pathData, fillColor, strokeColor, strokeWidth, strokeLineCap,
strokeLineJoin, fillAlpha, strokeAlpha) and <group> (rotation/pivotX/pivotY,
scaleX/scaleY, translateX/translateY). Gradients/clip-paths are NOT supported —
it fails loudly if it meets an element it doesn't know.
"""
import subprocess, sys, xml.etree.ElementTree as ET

A = "{http://schemas.android.com/apk/res/android}"

def color(c, alpha_attr=None):
    """#AARRGGBB / #RRGGBB -> (svg colour, opacity)"""
    if c is None: return None, 1.0
    c = c.strip()
    if len(c) == 9:  # #AARRGGBB
        a = int(c[1:3], 16) / 255.0
        return "#" + c[3:], a
    return c, 1.0

def path_el(e):
    attrs = []
    fc, fa = color(e.get(A + "fillColor"))
    sc, sa = color(e.get(A + "strokeColor"))
    attrs.append(f'd="{e.get(A + "pathData")}"')
    attrs.append(f'fill="{fc}"' if fc and fa > 0 else 'fill="none"')
    if fc and fa < 1 and fa > 0: attrs.append(f'fill-opacity="{fa}"')
    fa2 = e.get(A + "fillAlpha")
    if fa2: attrs.append(f'fill-opacity="{fa2}"')
    if sc and sa > 0:
        attrs.append(f'stroke="{sc}"')
        attrs.append(f'stroke-width="{e.get(A + "strokeWidth", "1")}"')
        if sa < 1: attrs.append(f'stroke-opacity="{sa}"')
        sa2 = e.get(A + "strokeAlpha")
        if sa2: attrs.append(f'stroke-opacity="{sa2}"')
        cap = e.get(A + "strokeLineCap"); join = e.get(A + "strokeLineJoin")
        if cap: attrs.append(f'stroke-linecap="{cap}"')
        if join: attrs.append(f'stroke-linejoin="{join}"')
    return f"<path {' '.join(attrs)}/>"

def walk(e):
    tag = e.tag.split("}")[-1]
    if tag == "path": return path_el(e)
    if tag == "group":
        px, py = e.get(A + "pivotX", "0"), e.get(A + "pivotY", "0")
        t = []
        tx, ty = e.get(A + "translateX"), e.get(A + "translateY")
        if tx or ty: t.append(f"translate({tx or 0} {ty or 0})")
        r = e.get(A + "rotation")
        if r: t.append(f"rotate({r} {px} {py})")
        sx, sy = e.get(A + "scaleX"), e.get(A + "scaleY")
        if sx or sy: t.append(f"translate({px} {py}) scale({sx or 1} {sy or 1}) translate(-{px} -{py})")
        inner = "".join(walk(c) for c in e)
        return f'<g transform="{" ".join(t)}">{inner}</g>' if t else f"<g>{inner}</g>"
    raise SystemExit(f"vd2png: unsupported element <{tag}> — extend the converter")

def main():
    if len(sys.argv) < 4: raise SystemExit(__doc__)
    src, bg, out = sys.argv[1:4]
    size = int(sys.argv[4]) if len(sys.argv) > 4 else 512
    root = ET.parse(src).getroot()
    vw, vh = root.get(A + "viewportWidth"), root.get(A + "viewportHeight")
    body = "".join(walk(c) for c in root)
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {vw} {vh}" width="{size}" height="{size}">'
           f'<rect width="{vw}" height="{vh}" fill="{bg}"/>{body}</svg>')
    subprocess.run(["rsvg-convert", "-w", str(size), "-h", str(size), "-o", out], input=svg.encode(), check=True)
    print(f"wrote {out} ({size}x{size})")

if __name__ == "__main__":
    main()
