#!/usr/bin/env python3
"""Toolkit for hand-built README diagrams: dark gradient canvas, glowing gradient cards, labelled
arrows, pill badges — plus the checks that catch what looks wrong (text overflowing its box,
labels overlapping) and a PNG render to look at.

Copy this file next to a small per-diagram generator script (see example.py), so the project can
rebuild the picture without the plugin:

    import sys; from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from diagram_kit import Diagram, finish
    d = Diagram(960, 462)
    d.background("Title", "Subtitle", glows=[(125, 215, "orange")])
    d.card(45, 150, 160, 130, "orange", "🤖", "Claude Code", mono="MCP client")
    ...
    d.save("docs/diagrams/flow.svg")      # prints layout warnings
    finish()                              # with --strict: exit code 1 if any save() warned

Render to look at it: python3 diagram_kit.py render docs/diagrams/*.svg (PNG to the temp dir).
Stdlib only. Text never wraps in SVG, so every string's width is estimated and checked.
"""
import atexit
import hashlib
import os
import re
import random
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif"
MONO = "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"

# name: (gradient top, gradient bottom, stroke, accent text, glow)
PALETTES = {
    "orange": ("#ea580c", "#9a3412", "#fdba74", "#fed7aa", "#ea580c"),
    "violet": ("#6d28d9", "#3b0764", "#c4b5fd", "#ddd6fe", "#7c3aed"),
    "teal": ("#0d9488", "#134e4a", "#5eead4", "#99f6e4", "#14b8a6"),
    "indigo": ("#4338ca", "#312e81", "#a5b4fc", "#c7d2fe", "#6366f1"),
    "emerald": ("#059669", "#065f46", "#6ee7b7", "#a7f3d0", "#10b981"),
    "amber": ("#d97706", "#92400e", "#fcd34d", "#fde68a", "#f59e0b"),
    "rose": ("#e11d48", "#881337", "#fda4af", "#fecdd3", "#f43f5e"),
    "sky": ("#0284c7", "#0c4a6e", "#7dd3fc", "#bae6fd", "#0ea5e9"),
    "slate": ("#1e293b", "#0f172a", "#64748b", "#cbd5e1", "#475569"),
}
# Arrow / line colours by role.
INK = {"main": "#e2e8f0", "dim": "#94a3b8", "magic": "#fcd34d"}
INK.update({k: v[2] for k, v in PALETTES.items()})


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


CYR_WIDE_CAPS = "МЖШЩЮФЫ"

# Minimum card heights for the fixed text offsets in card(): title only / + mono / + line.
CARD_MIN_H = {"title": 80, "mono": 100, "line": 120}
BOX_MIN_H = {"head": 24, "sub": 40}

# Warnings of every save() in this process, so --strict can check all languages before exiting.
_SAVED_WARNINGS = []
_FINISHED = [False]


def _is_emoji(ch):
    o = ord(ch)
    return o >= 0x1F000 or 0x2600 <= o <= 0x27BF or 0x2B00 <= o <= 0x2BFF


def text_width(s, size, mono=False, bold=False):
    """Rough rendered width in px. Errs a little wide on purpose: a false warning is cheap."""
    w = 0.0
    for ch in str(s):
        if _is_emoji(ch):
            w += 1.15
        elif ch in "\ufe0f\u200d":
            continue
        elif mono:
            w += 0.61
        elif ch == " ":
            w += 0.28
        elif ch in "il.,:;|'!·":
            w += 0.3
        elif ch in "mwMW—Шшщ" or ch in CYR_WIDE_CAPS:
            w += 0.85
        elif "\u0400" <= ch <= "\u042f":  # other Cyrillic capitals: wider than Latin ones
            w += 0.72
        elif "\u0400" <= ch <= "\u04ff":
            w += 0.6
        elif ch.isupper() or ch.isdigit():
            w += 0.64
        else:
            w += 0.54
    return w * size * (1.07 if bold and not mono else 1.0)  # monospace bold keeps the advance width


class Diagram:
    def __init__(self, width=960, height=460, seed=7):
        self.w, self.h = width, height
        self.rnd = random.Random(seed)
        self.defs = []
        self.body = []
        self.texts = []  # (x0, y0, x1, y1, label, container or None)
        self.shapes = []  # (x0, y0, x1, y1, label): cards, boxes, pills — must stay on the canvas
        self.notes = []  # warnings found while building (a card too short for its lines)
        self.warnings = []
        self._markers = set()
        self._grads = set()

    # ---- primitives -------------------------------------------------------------------------
    def text(self, x, y, s, size, fill, weight=None, anchor="middle", mono=False, opacity=None,
             container=None, check=True):
        """Adds a text; container=(x0, x1) or (x0, x1, y0, y1) checks it stays inside that span."""
        attrs = f'x="{x:.1f}" y="{y:.1f}" text-anchor="{anchor}" font-size="{size}" fill="{fill}"'
        if weight:
            attrs += f' font-weight="{weight}"'
        if mono:
            attrs += f' font-family="{MONO}"'
        if opacity is not None:
            attrs += f' opacity="{opacity}"'
        self.body.append(f"<text {attrs}>{esc(s)}</text>")
        if check:
            tw = text_width(s, size, mono, bool(weight) and str(weight) >= "600")
            x0 = {"start": x, "middle": x - tw / 2, "end": x - tw}[anchor]
            self.texts.append((x0, y - size * 0.8, x0 + tw, y + size * 0.25, s, container))

    def _gradient(self, name):
        gid = f"g-{name}"
        if gid not in self._grads:
            top, bottom = PALETTES[name][:2]
            self.defs.append(f'<linearGradient id="{gid}" x1="0" y1="0" x2="0" y2="1">'
                             f'<stop offset="0" stop-color="{top}"/><stop offset="1" stop-color="{bottom}"/>'
                             "</linearGradient>")
            self._grads.add(gid)
        return gid

    def _marker(self, color):
        hexa = color.lstrip("#")
        if re.fullmatch(r"[0-9a-fA-F]{3,8}", hexa):
            mid = "m" + hexa
        else:  # rgb(...), a CSS name: anything else would make an invalid id and lose the arrowhead
            mid = "m-" + hashlib.sha1(color.encode("utf-8")).hexdigest()[:10]
        if mid not in self._markers:
            self.defs.append(f'<marker id="{mid}" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" '
                             f'markerHeight="7" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>')
            self._markers.add(mid)
        return mid

    # ---- building blocks ------------------------------------------------------------------
    def background(self, title, subtitle=None, glows=(), sparks=26, colors=("#0b1020", "#111a33", "#0f2a2e")):
        """Dark diagonal gradient, faint grid, colour glows (x, y, palette[, r]), sparks kept off the title."""
        self.defs.append('<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">'
                         f'<stop offset="0" stop-color="{colors[0]}"/><stop offset="0.5" stop-color="{colors[1]}"/>'
                         f'<stop offset="1" stop-color="{colors[2]}"/></linearGradient>')
        self.defs.append('<filter id="glow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="18"/></filter>')
        self.defs.append('<pattern id="grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0 L0 0 0 24" '
                         'fill="none" stroke="#ffffff" stroke-opacity="0.035" stroke-width="1"/></pattern>')
        self.body.append(f'<rect width="{self.w}" height="{self.h}" rx="18" fill="url(#bg)"/>')
        self.body.append(f'<rect width="{self.w}" height="{self.h}" rx="18" fill="url(#grid)"/>')
        for g in glows:
            x, y, pal = g[:3]
            r = g[3] if len(g) > 3 else 80
            self.body.append(f'<circle cx="{x}" cy="{y}" r="{r}" fill="{PALETTES[pal][4]}" opacity="0.2" filter="url(#glow)"/>')
        tw = max(text_width(title, 23, bold=True), text_width(subtitle or "", 13.5))
        clear = (self.w / 2 - tw / 2 - 30, self.w / 2 + tw / 2 + 30)
        for _ in range(sparks):
            x = self.rnd.uniform(20, self.w - 20)
            if clear[0] < x < clear[1]:
                continue
            y = self.rnd.uniform(18, 110)
            self.body.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{self.rnd.choice([0.8, 1.0, 1.3])}" '
                             f'fill="#ffffff" opacity="{self.rnd.uniform(0.2, 0.6):.2f}"/>')
        self.text(self.w / 2, 44, title, 23, "#f8fafc", 700, container=(16, self.w - 16))
        if subtitle:
            self.text(self.w / 2, 69, subtitle, 13.5, "#cbd5e1", container=(16, self.w - 16))

    def card(self, x, y, w, h, palette, icon, title, mono=None, line=None):
        """Gradient card with drop shadow: emoji, bold title, optional mono line and plain line.
        The lines sit at fixed offsets; minimum h is CARD_MIN_H (80, 100 with mono, 120 with line)."""
        pal = PALETTES[palette]
        need = CARD_MIN_H["line" if line else "mono" if mono else "title"]
        if h < need:
            self.notes.append(f"card too short: {title!r} is {h:g} px tall, needs at least {need} for its lines")
        self.shapes.append((x, y, x + w, y + h, f"card {title!r}"))
        gid = self._gradient(palette)
        self.body.append(f'<rect x="{x + 3}" y="{y + 5}" width="{w}" height="{h}" rx="16" fill="#000" opacity="0.4"/>')
        self.body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="16" fill="url(#{gid})" '
                         f'stroke="{pal[2]}" stroke-width="1.6"/>')
        cx, inner = x + w / 2, (x + 10, x + w - 10, y + 2, y + h - 2)
        self.text(cx, y + 40, icon, 28, "#fff", check=False)
        self.text(cx, y + 72, title, 18, "#ffffff", 700, container=inner)
        if mono:
            self.text(cx, y + 93, mono, 12.5, pal[3], mono=True, container=inner)
        if line:
            self.text(cx, y + 112, line, 12, "#e2e8f0", opacity=0.85, container=inner)
        return (x, y, w, h)

    def box(self, x, y, w, h, icon, head, sub=None):
        """Low-key slate box for a file, a store, a config: emoji + mono heading + small line.
        Minimum h: 24, or 40 with sub."""
        self.shapes.append((x, y, x + w, y + h, f"box {head!r}"))
        self.body.append(f'<rect x="{x + 3}" y="{y + 4}" width="{w}" height="{h}" rx="12" fill="#000" opacity="0.4"/>')
        self.body.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="12" fill="#111827" stroke="#64748b" stroke-width="1.3"/>')
        self.text(x + 22, y + h / 2 + 6, icon, 18, "#fff", anchor="start", check=False)
        inner = (x + 10, x + w - 10, y + 1, y + h - 1)
        self.text(x + 50, y + h / 2 - 4 if sub else y + h / 2 + 5, head, 12.5, "#e2e8f0", 600, anchor="start",
                  mono=True, container=inner)
        if sub:
            self.text(x + 50, y + h / 2 + 15, sub, 11.5, "#94a3b8", anchor="start", container=inner)

    def arrow(self, x1, y1, x2, y2, ink="main", label=None, label_side=1, label_dx=0, label_dy=0, mono=True,
              width=2.2, dashed=False, gap=8):
        """Straight arrow. The label sits beside the middle of the line, `gap` px off it along the
        line's normal, so a diagonal edge does not cross its own label: above a horizontal line,
        right of a vertical one; label_side=-1 puts it on the other side, label_dx/dy nudge it."""
        color = INK.get(ink, ink)
        dash = ' stroke-dasharray="5 5"' if dashed else ""
        self.body.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"{dash} '
                         f'marker-end="url(#{self._marker(color)})"/>')
        if label:
            size = 12.5
            x, y = label_position(x1, y1, x2, y2, text_width(label, size, mono, True), size, label_side, gap)
            self.text(x + label_dx, y + label_dy, label, size, "#f8fafc", 600, mono=mono)

    def duplex(self, x1, x2, y, top=None, bottom=None):
        """Two parallel arrows (request →, response ←) with labels above and below — a protocol edge."""
        self.arrow(x1, y - 7, x2, y - 7, "main")
        self.arrow(x2, y + 7, x1, y + 7, "dim")
        mid = (x1 + x2) / 2
        if top:
            self.text(mid, y - 18, top, 12.5, "#f8fafc", 600, mono=True, container=(x1, x2))
        if bottom:
            self.text(mid, y + 30, bottom, 11.5, "#94a3b8", mono=True, container=(x1, x2))

    def curve(self, d, ink="magic", label=None, at=None, dashed=True, label_color=None, anchor="middle"):
        """Free path (SVG 'd'); the dashed amber default marks the special, 'magic' path of the story."""
        color = INK.get(ink, ink)
        dash = ' stroke-dasharray="5 5"' if dashed else ""
        self.body.append(f'<path d="{d}" fill="none" stroke="{color}" stroke-width="1.8"{dash} '
                         f'marker-end="url(#{self._marker(color)})"/>')
        if label and at:
            self.text(at[0], at[1], label, 11.5, label_color or color, 600, anchor=anchor)

    def badges(self, y, items, width=None, gap=12):
        """Row of 44 px pill badges [(emoji, head, sub)] centred horizontally — the takeaways of the
        picture. width (per pill) defaults to min(300, what fits the canvas with 20 px margins)."""
        n = len(items)
        if width is None:
            width = min(300, (self.w - 40 - gap * (n - 1)) / n)
        x0 = (self.w - (n * width + (n - 1) * gap)) / 2
        for i, (icon, head, sub) in enumerate(items):
            bx = x0 + i * (width + gap)
            inner = (bx + 10, bx + width - 14, y, y + 44)
            self.shapes.append((bx, y, bx + width, y + 44, f"pill {head!r}"))
            self.body.append(f'<rect x="{bx:.1f}" y="{y}" width="{width:g}" height="44" rx="22" fill="#ffffff" '
                             'fill-opacity="0.06" stroke="#ffffff" stroke-opacity="0.14"/>')
            self.text(bx + 24, y + 29, icon, 17, "#fff", check=False)
            self.text(bx + 44, y + 19, head, 13, "#f8fafc", 700, anchor="start", container=inner)
            self.text(bx + 44, y + 35, sub, 11, "#94a3b8", anchor="start", container=inner)

    # ---- output and checks ------------------------------------------------------------------
    def check(self):
        """Layout warnings: text off the canvas or out of its container (both axes), a card too short
        for its lines, a card/box/pill off the canvas, and texts overlapping each other. Lines and
        curves are not obstacles: a label crossed by a line is caught only by looking at the PNG."""
        warns = list(self.notes)
        for x0, y0, x1, y1, s in self.shapes:
            if x0 < 0 or y0 < 0 or x1 > self.w or y1 > self.h:
                warns.append(f"off canvas: {s} spans x {x0:.0f}..{x1:.0f}, y {y0:.0f}..{y1:.0f} "
                             f"of {self.w}x{self.h}")
        for x0, y0, x1, y1, s, cont in self.texts:
            if x0 < 4 or x1 > self.w - 4:
                warns.append(f"off canvas: {s!r} spans {x0:.0f}..{x1:.0f} of 0..{self.w}")
            if y0 < 4 or y1 > self.h - 4:
                warns.append(f"off canvas: {s!r} spans y {y0:.0f}..{y1:.0f} of 0..{self.h}")
            if cont and (x0 < cont[0] - 1 or x1 > cont[1] + 1):
                warns.append(f"overflows its box: {s!r} spans {x0:.0f}..{x1:.0f}, box {cont[0]:.0f}..{cont[1]:.0f}"
                             f" — shorten it or widen the box")
            if cont and len(cont) == 4 and (y0 < cont[2] - 1 or y1 > cont[3] + 1):
                warns.append(f"overflows its box: {s!r} spans y {y0:.0f}..{y1:.0f}, box y {cont[2]:.0f}..{cont[3]:.0f}"
                             f" — make the box taller")
        boxes = self.texts
        for i in range(len(boxes)):
            for j in range(i + 1, len(boxes)):
                a, b = boxes[i], boxes[j]
                if a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]:
                    warns.append(f"texts overlap: {a[4]!r} and {b[4]!r} — move one")
        self.warnings = warns
        return warns

    def svg(self):
        return "\n".join([f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.w}" height="{self.h}" '
                          f'viewBox="0 0 {self.w} {self.h}" font-family="{SANS}">',
                          "<defs>", *self.defs, "</defs>", *self.body, "</svg>"]) + "\n"

    def save(self, path, strict=None):
        """Writes the SVG, prints layout warnings. strict=True exits 1 on warnings at once; with
        --strict on argv the warnings are collected and finish() (or the end of the script) exits 1,
        so every language is built and checked first."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = self.svg()
        ET.fromstring(data)  # must be well-formed XML: GitHub shows nothing for a broken SVG
        path.write_text(data, encoding="utf-8")
        warns = self.check()
        print(f"wrote {path} ({len(data) // 1024 + 1} KB){'' if warns else ' — layout OK'}")
        for w in warns:
            print("  WARNING", w)
        _SAVED_WARNINGS.extend(f"{path.name}: {w}" for w in warns)
        if warns and strict:
            sys.exit(1)
        return warns


def finish(strict=None):
    """Call once after every save(): with --strict on argv (or strict=True) exits 1 if any save()
    in this run reported warnings."""
    _FINISHED[0] = True
    strict = "--strict" in sys.argv if strict is None else strict
    if _SAVED_WARNINGS and strict:
        print(f"--strict: {len(_SAVED_WARNINGS)} layout warning(s) in total, fix them")
        sys.exit(1)


@atexit.register
def _strict_exit_guard():
    # A generator that forgot finish() must still fail under --strict (sys.exit is ignored here).
    if not _FINISHED[0] and _SAVED_WARNINGS and "--strict" in sys.argv:
        print(f"--strict: {len(_SAVED_WARNINGS)} layout warning(s) in total, fix them", flush=True)
        sys.stderr.flush()
        os._exit(1)


def label_position(x1, y1, x2, y2, tw, size, side=1, gap=8):
    """Baseline centre (x, y) for a label of width tw beside segment (x1, y1)-(x2, y2): the text box
    is `gap` px from the line along its normal (up for a horizontal line, right for a vertical)."""
    dx, dy = x2 - x1, y2 - y1
    length = (dx * dx + dy * dy) ** 0.5 or 1.0
    nx, ny = dy / length, -dx / length
    if ny > 0 or (ny == 0 and nx < 0):
        nx, ny = -nx, -ny
    nx, ny = nx * side, ny * side
    th = size * 1.05  # the text box check() uses: size*0.8 above the baseline, size*0.25 below
    reach = gap + abs(nx) * tw / 2 + abs(ny) * th / 2
    cx, cy = (x1 + x2) / 2 + nx * reach, (y1 + y2) / 2 + ny * reach
    return cx, cy + size * 0.8 - th / 2


def find_chrome():
    for p in (os.environ.get("CHROME"),
              "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
              "/Applications/Chromium.app/Contents/MacOS/Chromium",
              "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
              r"C:\Program Files\Google\Chrome\Application\chrome.exe",
              r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"):
        if p and Path(p).exists():
            return p
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "msedge"):
        if shutil.which(name):
            return shutil.which(name)
    return None


def render_png(svg_path, png_path, scale=2, timeout=60):
    """Renders the SVG to PNG for a visual check (headless Chrome/Edge, CHROME=path overrides the
    search; rsvg-convert as fallback). The old PNG is deleted first, so a failed render raises
    RuntimeError with the renderer's output instead of leaving the previous picture in place."""
    svg_path, png_path = Path(svg_path).resolve(), Path(png_path).resolve()
    root = ET.parse(svg_path).getroot()
    w, h = int(float(root.get("width"))), int(float(root.get("height")))
    png_path.parent.mkdir(parents=True, exist_ok=True)
    if png_path.exists():
        png_path.unlink()
    chrome = find_chrome()
    if chrome:
        cmd = [chrome, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--window-size={w},{h}",
               f"--force-device-scale-factor={scale}", f"--screenshot={png_path}", svg_path.as_uri()]
    elif shutil.which("rsvg-convert"):
        cmd = ["rsvg-convert", "-z", str(scale), "-o", str(png_path), str(svg_path)]
    else:
        raise RuntimeError("no renderer: install Google Chrome or Microsoft Edge (or set CHROME=path to one), "
                           "or librsvg's rsvg-convert")
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"renderer timed out after {timeout} s: {cmd[0]} (no PNG written: {png_path})") from None
    except OSError as e:
        raise RuntimeError(f"renderer failed to start: {cmd[0]}: {e}") from None
    if not png_path.exists() or png_path.stat().st_size == 0:
        out = ((r.stderr or "") + (r.stdout or "")).strip()[-800:]
        raise RuntimeError(f"render produced no PNG ({cmd[0]} exit code {r.returncode}): {png_path}"
                           + (f"\n{out}" if out else ""))
    return png_path


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "render":
        for svg in sys.argv[2:]:
            out = Path(tempfile.gettempdir()) / (Path(svg).stem + ".png")
            print(render_png(svg, out))
    else:
        print("usage: diagram_kit.py render <file.svg>...  (each PNG goes to the temp dir; the path is printed)")
