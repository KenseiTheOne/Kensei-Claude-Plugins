#!/usr/bin/env python3
"""Tests for diagram_kit: width estimate, layout checks, valid SVG, and the reference example."""
import os
import re
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import diagram_kit  # noqa: E402
from diagram_kit import Diagram, esc, label_position, render_png, text_width  # noqa: E402


class TextWidthTest(unittest.TestCase):
    def test_grows_with_length_and_size(self):
        self.assertLess(text_width("abc", 12), text_width("abcdef", 12))
        self.assertAlmostEqual(text_width("abc", 24), 2 * text_width("abc", 12))

    def test_bold_is_wider_but_not_for_monospace(self):
        self.assertGreater(text_width("Bridge", 18, bold=True), text_width("Bridge", 18))
        self.assertEqual(text_width("token", 12, mono=True, bold=True), text_width("token", 12, mono=True))

    def test_cyrillic_and_emoji_counted(self):
        self.assertGreater(text_width("Мост", 12), 0)
        self.assertGreater(text_width("🔁", 12), text_width("a", 12))

    def test_cyrillic_capitals_are_wider_than_lowercase_and_latin(self):
        self.assertGreater(text_width("О", 12), text_width("о", 12))
        self.assertGreater(text_width("О", 12), text_width("O", 12))
        self.assertGreater(text_width("М", 12), text_width("О", 12))  # М Ж Ш Щ Ю Ф Ы are the widest
        self.assertEqual(text_width("Ж", 12), text_width("Ы", 12))

    def test_all_caps_russian_title_overflowing_its_card_is_reported(self):
        # Chrome draws this bold 18 px title about 164 px wide; the card's inner span is 160 px.
        d = Diagram(400, 200)
        d.card(20, 20, 180, 130, "violet", "🌉", "МОДУЛЬ ОПЛАТЫ")
        self.assertTrue(any("overflows its box" in w for w in d.check()))


class LayoutCheckTest(unittest.TestCase):
    def test_overflowing_card_text_is_reported(self):
        d = Diagram(400, 200)
        d.card(10, 10, 100, 100, "teal", "🎮", "A title far too long for this card")
        self.assertTrue(any("overflows its box" in w for w in d.check()))

    def test_fitting_card_has_no_warnings(self):
        d = Diagram(400, 200)
        d.card(10, 10, 160, 120, "teal", "🎮", "Unity", mono="plugin", line="main thread")
        self.assertEqual(d.check(), [])

    def test_overlapping_texts_are_reported(self):
        d = Diagram(400, 200)
        d.text(100, 50, "first label", 12, "#fff")
        d.text(105, 52, "second label", 12, "#fff")
        self.assertTrue(any("overlap" in w for w in d.check()))

    def test_text_off_canvas_is_reported(self):
        d = Diagram(200, 100)
        d.text(195, 50, "runs past the right edge", 12, "#fff", anchor="start")
        self.assertTrue(any("off canvas" in w for w in d.check()))

    def test_badges_check_their_pills(self):
        d = Diagram(960, 100)
        d.badges(20, [("🔁", "Head", "a subtitle that is much much much much much much much longer than a pill")])
        self.assertTrue(any("overflows" in w for w in d.check()))

    def test_text_below_a_short_card_is_reported(self):
        # Lines sit at fixed offsets (y+93, y+112): a 90 px card cannot hold mono and line.
        d = Diagram(400, 200)
        d.card(10, 10, 160, 90, "teal", "🎮", "Unity", mono="plugin", line="main thread")
        warns = d.check()
        self.assertTrue(any("card too short" in w and "120" in w for w in warns), warns)
        self.assertTrue(any("make the box taller" in w and "'main thread'" in w for w in warns), warns)

    def test_card_minimum_heights(self):
        for kw, h in (({}, 80), ({"mono": "pkg"}, 100), ({"mono": "pkg", "line": "does it"}, 120)):
            ok, short = Diagram(400, 300), Diagram(400, 300)
            ok.card(10, 10, 160, h, "teal", "🎮", "Unity", **kw)
            short.card(10, 10, 160, h - 1, "teal", "🎮", "Unity", **kw)
            self.assertEqual(ok.check(), [], kw)
            self.assertTrue(any("card too short" in w for w in short.check()), kw)

    def test_text_below_the_canvas_is_reported(self):
        d = Diagram(400, 200)
        d.text(200, 210, "under the bottom edge", 12, "#fff")
        self.assertTrue(any("off canvas" in w and "y " in w for w in d.check()))

    def test_card_off_the_canvas_bottom_is_reported(self):
        d = Diagram(400, 200)
        d.card(10, 150, 160, 130, "teal", "🎮", "Unity")
        self.assertTrue(any("off canvas: card 'Unity'" in w for w in d.check()))

    def test_box_too_short_for_its_sub_line_is_reported(self):
        d = Diagram(400, 200)
        d.box(10, 10, 300, 30, "📄", "file.json", "what it holds")
        self.assertTrue(any("make the box taller" in w for w in d.check()))
        d = Diagram(400, 200)
        d.box(10, 10, 300, 40, "📄", "file.json", "what it holds")
        self.assertEqual(d.check(), [])

    def test_badges_default_width_fits_four_pills_on_the_canvas(self):
        d = Diagram(960, 100)
        d.badges(20, [("🔁", "A", "b"), ("🎯", "C", "d"), ("🛠", "E", "f"), ("✨", "G", "h")])
        self.assertEqual(d.check(), [])
        pills = [s for s in d.shapes if s[4].startswith("pill")]
        self.assertEqual(len(pills), 4)
        self.assertGreaterEqual(min(p[0] for p in pills), 20 - 0.01)
        self.assertLessEqual(max(p[2] for p in pills), 940 + 0.01)

    def test_badges_default_width_is_capped_at_300(self):
        d = Diagram(960, 100)
        d.badges(20, [("🔁", "A", "b"), ("🎯", "C", "d")])
        self.assertTrue(all(p[2] - p[0] == 300 for p in d.shapes))

    def test_pills_off_the_canvas_are_reported_as_pills(self):
        d = Diagram(960, 100)
        d.badges(20, [("🔁", "A", "b"), ("🎯", "C", "d"), ("🛠", "E", "f"), ("✨", "G", "h")], width=300)
        self.assertTrue(any("off canvas: pill 'A'" in w for w in d.check()))


class ArrowLabelTest(unittest.TestCase):
    @staticmethod
    def _side(px, py, x1, y1, x2, y2):
        """Signed distance of (px, py) from the line through the two points."""
        dx, dy = x2 - x1, y2 - y1
        return ((px - x1) * dy - (py - y1) * dx) / (dx * dx + dy * dy) ** 0.5

    def _label_box(self, *line, **kw):
        d = Diagram(600, 600)
        d.arrow(*line, label="TCP 127.0.0.1", **kw)
        x0, y0, x1, y1 = d.texts[-1][:4]
        return [(x0, y0), (x1, y0), (x0, y1), (x1, y1)]

    def test_horizontal_label_sits_above_the_line_as_before(self):
        d = Diagram(600, 200)
        d.arrow(100, 100, 300, 100, label="stdio")
        x, y = d.texts[-1][0] + d.texts[-1][2], d.texts[-1][3] - 12.5 * 0.25  # 2*centre x, baseline
        self.assertAlmostEqual(x / 2, 200)
        self.assertAlmostEqual(y, 100 - 11, delta=0.2)  # baseline about 11 px above the line

    def test_diagonal_label_box_is_clear_of_its_line(self):
        for line in ((100, 100, 400, 400), (400, 100, 100, 400), (100, 400, 400, 100), (300, 100, 300, 500)):
            corners = self._label_box(*line)
            sides = [self._side(x, y, *line) for x, y in corners]
            self.assertTrue(all(s > 7 for s in sides) or all(s < -7 for s in sides), (line, sides))

    def test_label_side_flips_the_label(self):
        line = (100, 100, 400, 400)
        a = self._side(*self._label_box(*line)[0], *line)
        b = self._side(*self._label_box(*line, label_side=-1)[0], *line)
        self.assertLess(a * b, 0)

    def test_label_position_vertical_line_goes_right(self):
        x, _ = label_position(300, 100, 300, 500, 40, 12.5)
        self.assertGreater(x, 300 + 20)


class SvgTest(unittest.TestCase):
    def test_svg_is_well_formed_and_escaped(self):
        d = Diagram(400, 200)
        d.background("A <b> & \"c\"", "sub")
        d.box(10, 100, 300, 50, "📄", "~/.x/<id>.json", "a & b")
        d.duplex(10, 200, 80, "stdio", "MCP")
        root = ET.fromstring(d.svg())
        self.assertTrue(root.tag.endswith("svg"))
        self.assertIn("&lt;id&gt;", d.svg())
        self.assertEqual(esc('<"&>'), "&lt;&quot;&amp;&gt;")

    def test_markers_and_gradients_are_defined_once(self):
        d = Diagram(400, 200)
        for _ in range(3):
            d.card(10, 10, 160, 120, "violet", "🌉", "X")
            d.arrow(0, 0, 10, 10, "main")
        svg = d.svg()
        self.assertEqual(svg.count('id="g-violet"'), 1)
        self.assertEqual(svg.count("<marker"), 1)

    def test_marker_ids_are_valid_for_any_colour(self):
        d = Diagram(400, 200)
        d.arrow(0, 0, 10, 10, "rgb(255, 0, 0)")
        d.curve("M 0 0 L 10 10", "tomato")
        d.arrow(0, 0, 10, 10, "#fcd34d")
        ids = re.findall(r'<marker id="([^"]+)"', d.svg())
        self.assertEqual(len(ids), 3)
        for mid in ids:
            self.assertRegex(mid, r"^[A-Za-z][\w-]*$")
            self.assertIn(f"url(#{mid})", d.svg())
        self.assertIn("mfcd34d", ids)  # hex inks keep their readable id

    def test_save_strict_fails_on_warnings(self):
        d = Diagram(200, 100)
        d.text(195, 50, "off the edge", 12, "#fff", anchor="start")
        with tempfile.TemporaryDirectory() as tmp, self.assertRaises(SystemExit):
            d.save(Path(tmp) / "x.svg", strict=True)

    def test_strict_from_argv_checks_every_build_before_exiting(self):
        script = (
            "import sys; sys.path.insert(0, %r)\n"
            "from diagram_kit import Diagram, finish\n"
            "for name in ('a.svg', 'b.svg'):\n"
            "    d = Diagram(200, 100); d.text(195, 50, 'off ' + name, 12, '#fff', anchor='start')\n"
            "    d.save(sys.argv[1] + '/' + name)\n"
            "    print('built', name)\n"
            "%s"
        )
        for tail in ("finish()\n", ""):  # finish() and, as a fallback, the exit guard
            with tempfile.TemporaryDirectory() as tmp:
                r = subprocess.run([sys.executable, "-c", script % (str(HERE), tail), tmp, "--strict"],
                                   capture_output=True, text=True)
                self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
                self.assertIn("built b.svg", r.stdout)
                self.assertIn("2 layout warning(s)", r.stdout)


class RenderTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.svg = self.dir / "x.svg"
        Diagram(200, 100).save(self.svg, strict=False)
        self.png = self.dir / "x.png"

    def tearDown(self):
        self.tmp.cleanup()

    def _fake(self, body):
        exe = self.dir / "fake-chrome"
        exe.write_text("#!/bin/sh\n" + body + "\n")
        exe.chmod(0o755)
        return str(exe)

    @unittest.skipIf(os.name == "nt", "shell-script renderer")
    def test_failed_render_raises_and_leaves_no_stale_png(self):
        self.png.write_bytes(b"old picture")
        exe = self._fake('echo "GPU process crashed" >&2; exit 3')
        with mock.patch.dict(os.environ, {"CHROME": exe}), self.assertRaises(RuntimeError) as cm:
            render_png(self.svg, self.png)
        self.assertIn("exit code 3", str(cm.exception))
        self.assertIn("GPU process crashed", str(cm.exception))
        self.assertFalse(self.png.exists())

    @unittest.skipIf(os.name == "nt", "shell-script renderer")
    def test_successful_render_returns_a_fresh_png(self):
        self.png.write_bytes(b"old picture")
        old = time.time() - 100
        os.utime(self.png, (old, old))
        exe = self._fake('for a in "$@"; do case "$a" in --screenshot=*) printf new > "${a#--screenshot=}";; esac; done')
        with mock.patch.dict(os.environ, {"CHROME": exe}):
            out = render_png(self.svg, self.png)
        self.assertEqual(out.read_bytes(), b"new")

    def test_timeout_is_a_clear_error(self):
        with mock.patch.object(diagram_kit, "find_chrome", return_value="/x/chrome"), \
                mock.patch.object(diagram_kit.subprocess, "run",
                                  side_effect=subprocess.TimeoutExpired("/x/chrome", 60)), \
                self.assertRaises(RuntimeError) as cm:
            render_png(self.svg, self.png)
        self.assertIn("timed out after 60 s", str(cm.exception))

    def test_no_renderer_names_the_ways_out(self):
        with mock.patch.object(diagram_kit, "find_chrome", return_value=None), \
                mock.patch.object(diagram_kit.shutil, "which", return_value=None), \
                self.assertRaises(RuntimeError) as cm:
            render_png(self.svg, self.png)
        self.assertIn("CHROME=", str(cm.exception))
        self.assertIn("rsvg-convert", str(cm.exception))


class ExampleTest(unittest.TestCase):
    def test_reference_example_builds_clean_in_both_languages(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run([sys.executable, str(HERE / "example.py"), tmp, "--strict"],
                               capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            for name in ("how-it-works.svg", "how-it-works.ru.svg"):
                ET.parse(Path(tmp) / name)


if __name__ == "__main__":
    unittest.main(verbosity=1)
