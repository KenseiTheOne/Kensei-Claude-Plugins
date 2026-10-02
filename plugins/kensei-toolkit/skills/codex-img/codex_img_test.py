#!/usr/bin/env python3
"""Tests for codex_img.py — run: python3 codex_img_test.py

No network and no real Codex: a fake `codex` (a small Python script, wrapped in a .cmd on
Windows) prints canned `--json` events and drops a PNG into a temporary CODEX_HOME.
"""

import json
import os
import pathlib
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import unittest
import unittest.mock
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "codex_img.py")
sys.path.insert(0, HERE)
import codex_img  # noqa: E402


# --- builders ----------------------------------------------------------------------------

def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    return a if pa <= pb and pa <= pc else (b if pb <= pc else c)


def make_png(path, width=4, height=3, color=6, alpha=255, transparent_at=None, filt=0,
             depth=8, idat_size=None):
    """A tiny PNG, written independently of the decoder under test.

    color 0 = grey, 2 = RGB, 4 = grey+alpha, 6 = RGBA; depth 8 or 16; transparent_at=(x, y)
    makes one pixel alpha 0. filt is a filter type (0-4) or a list cycled over the rows, the
    way real encoders pick one per row; idat_size splits the data over several IDAT chunks.
    """
    channels = {0: 1, 2: 3, 4: 2, 6: 4}[color]
    width_b = depth // 8
    bpp = channels * width_b
    full = 0xFF if depth == 8 else 0xFFFF
    filters = filt if isinstance(filt, list) else [filt]
    raw, prev = bytearray(), bytearray(width * bpp)
    for y in range(height):
        row = bytearray()
        for x in range(width):
            # varied colour values, so a wrong unfilter shows up as a wrong alpha
            px = [(37 * x + 91 * y + 50 * c) * (full // 255) % (full + 1) for c in range(channels)]
            if color in (4, 6):
                px[-1] = 0 if transparent_at == (x, y) else (alpha if depth == 8 else alpha * 257)
            for v in px:
                row += v.to_bytes(width_b, "big")
        f = filters[y % len(filters)]
        enc = bytearray(row)
        for i in range(len(row)):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            pred = (0, a, b, (a + b) >> 1, _paeth(a, b, c))[f]
            enc[i] = (row[i] - pred) & 0xFF
        raw += bytes([f]) + enc
        prev = row

    def chunk(kind, body):
        return (struct.pack(">I", len(body)) + kind + body
                + struct.pack(">I", zlib.crc32(kind + body) & 0xFFFFFFFF))

    packed = zlib.compress(bytes(raw))
    step = idat_size or len(packed)
    data = (b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, depth, color, 0, 0, 0))
            + b"".join(chunk(b"IDAT", packed[i:i + step]) for i in range(0, len(packed), step))
            + chunk(b"IEND", b""))
    pathlib.Path(path).parent.mkdir(parents=True, exist_ok=True)
    pathlib.Path(path).write_bytes(data)
    return pathlib.Path(path)


FAKE = r'''
import json, os, pathlib, sys, uuid
args = sys.argv[1:]
if args == ["--version"]:
    print(os.environ.get("FAKE_VERSION", "codex-cli 0.159.3")); sys.exit(0)
mode = os.environ.get("FAKE_MODE", "ok")
if mode == "fail_start":  # a rejected flag: clap exits before any thread starts
    sys.stderr.write("error: unexpected argument '--ephemeral' found\n"); sys.exit(2)
log = os.environ.get("FAKE_LOG")
prompt = sys.stdin.read()
if log:
    with open(log, "a", encoding="utf-8") as fh:
        fh.write(json.dumps({"args": args, "prompt": prompt}) + "\n")
    if mode in ("ok_then_rate", "fail_then_ok"):  # the first call differs from the rest
        with open(log, encoding="utf-8") as fh:
            first = len(fh.readlines()) == 1
        mode = {"ok_then_rate": ("ok", "rate"), "fail_then_ok": ("thread_then_fail", "ok")}[mode][
            0 if first else 1]
tid = str(uuid.uuid4())
print(json.dumps({"type": "thread.started", "thread_id": tid}))
print("not json")
print(json.dumps({"type": "item.completed", "item": "a string, not an object"}))
if mode == "thread_then_fail":  # a turn started, then failed for a reason that is not a limit
    print(json.dumps({"type": "turn.failed", "error": {"message": "stream disconnected"}}))
    sys.exit(1)
if mode == "echo_refuse":  # the agent quotes the description back while refusing
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message",
          "text": "I cannot draw this: " + prompt.strip().splitlines()[-1]}}))
if mode in ("notpng", "partial_then_hang"):
    folder = pathlib.Path(os.environ["CODEX_HOME"]) / "generated_images" / tid
    folder.mkdir(parents=True)
    (folder / "exec-1.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00\x00" if mode == "partial_then_hang"
                                        else b"GIF89a not a png")
if mode == "rate":
    print(json.dumps({"type": "turn.failed", "error": {"message": "429 Too Many Requests: image_gen limit"}}))
    sys.exit(1)
if mode in ("hang", "image_then_hang", "partial_then_hang"):
    import subprocess, time
    if mode == "image_then_hang":
        sys.path.insert(0, os.environ["FAKE_HERE"])
        from codex_img_test import make_png
        make_png(pathlib.Path(os.environ["CODEX_HOME"]) / "generated_images" / tid / "exec-1.png",
                 transparent_at=(0, 0))
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    pathlib.Path(os.environ["FAKE_PIDFILE"]).write_text(str(child.pid))
    sys.stdout.flush()
    time.sleep(60)
if mode == "limit_reply":
    print(json.dumps({"type": "item.completed", "item": {"type": "error", "message": "image generation failed"}}))
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "Image generation failed: usage limit reached for image_gen."}}))
if mode == "sentinel":
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "CODEX_IMG_RATE_LIMITED"}}))
if mode == "refuse":
    print(json.dumps({"type": "item.completed", "item": {"type": "agent_message", "text": "I cannot do that."}}))
elif mode in ("ok", "rgb", "two"):
    sys.path.insert(0, os.environ["FAKE_HERE"])
    from codex_img_test import make_png
    folder = pathlib.Path(os.environ["CODEX_HOME"]) / "generated_images" / tid
    make_png(folder / "exec-1.png", color=2 if mode == "rgb" else 6, transparent_at=(0, 0))
    if mode == "two":
        make_png(folder / "exec-2.png")
print(json.dumps({"type": "turn.completed", "usage": {"input_tokens": 100, "output_tokens": 5}}))
'''


class Fake:
    """Install the fake codex and a temporary CODEX_HOME for the duration of a test."""

    def __init__(self, mode="ok", version=None):
        self.dir = pathlib.Path(tempfile.mkdtemp())
        self.home = self.dir / "codex-home"
        self.log = self.dir / "calls.jsonl"
        script = self.dir / "fake_codex.py"
        script.write_text(FAKE, encoding="utf-8")
        if os.name == "nt":
            self.bin = self.dir / "codex.cmd"
            # cmd.exe reads batch files in the OEM code page: keep the file ASCII, paths in env
            self.bin.write_text('@"%FAKE_PY%" "%FAKE_SCRIPT%" %*\r\n', encoding="ascii")
        else:
            self.bin = self.dir / "codex"
            self.bin.write_text(f"#!/bin/sh\nexec '{sys.executable}' '{script}' \"$@\"\n")
            self.bin.chmod(0o755)
        self.env = {"CODEX_IMG_CODEX_BIN": str(self.bin), "CODEX_HOME": str(self.home),
                    "FAKE_MODE": mode, "FAKE_LOG": str(self.log), "FAKE_HERE": HERE,
                    "FAKE_PY": sys.executable, "FAKE_SCRIPT": str(script),
                    "FAKE_PIDFILE": str(self.dir / "grandchild.pid")}
        if version:
            self.env["FAKE_VERSION"] = version
        self.saved = {}

    def __enter__(self):
        for k, v in self.env.items():
            self.saved[k] = os.environ.get(k)
            os.environ[k] = v
        return self

    def __exit__(self, *exc):
        for k, v in self.saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        shutil.rmtree(self.dir, ignore_errors=True)

    def set_mode(self, mode):
        os.environ["FAKE_MODE"] = mode

    def calls(self):
        if not self.log.exists():
            return []
        return [json.loads(l) for l in self.log.read_text(encoding="utf-8").splitlines()]


def tmpdir(test):
    path = pathlib.Path(tempfile.mkdtemp())
    test.addCleanup(shutil.rmtree, path, True)
    return path


def cli(*args, env=None):
    proc = subprocess.run([sys.executable, SCRIPT, *args], capture_output=True,
                          env={**os.environ, **(env or {})})
    out = proc.stdout.decode("utf-8")
    return proc.returncode, json.loads(out) if out.strip() else None, proc.stderr.decode("utf-8")


# --- pure functions ----------------------------------------------------------------------

class CommandTest(unittest.TestCase):
    def test_refs_follow_options_and_no_positional_prompt(self):
        cmd = codex_img.build_command(["codex"], [pathlib.Path("a.png"), pathlib.Path("b.png")])
        self.assertEqual(cmd[:2], ["codex", "exec"])
        self.assertEqual(cmd[-4:], ["-i", "a.png", "-i", "b.png"])
        for flag in ("--json", "--skip-git-repo-check", "--ephemeral"):
            self.assertIn(flag, cmd)  # without --skip-git-repo-check codex refuses outside git
        self.assertEqual(cmd[cmd.index("-c") + 1], "approval_policy=never")
        self.assertEqual(cmd[cmd.index("-s") + 1], "read-only")
        self.assertNotIn("-", cmd)  # prompt goes via stdin, no "-" placeholder either

    def test_no_quotes_in_arguments(self):
        # arguments to codex.cmd pass through cmd.exe on Windows
        for arg in codex_img.build_command(["codex"], [pathlib.Path("x.png")]):
            self.assertNotIn('"', arg)

    def test_wrap_prompt(self):
        plain = codex_img.wrap_prompt("  a red gem  ", False, [])
        self.assertTrue(plain.endswith("a red gem"))
        self.assertNotIn("transparent_background", plain)
        self.assertNotIn("reference", plain)
        both = codex_img.wrap_prompt("a red gem", True, ["r1", "r2"])
        self.assertIn("transparent_background=true", both)
        self.assertIn("all 2 attached image(s)", both)
        self.assertIn("exactly once", both)
        self.assertIn(codex_img.RATE_SENTINEL, both)

    def test_parse_version(self):
        self.assertEqual(codex_img.parse_version("codex-cli 0.159.3\n"), (0, 159, 3))
        self.assertIsNone(codex_img.parse_version("garbage"))


class EventsTest(unittest.TestCase):
    def test_real_shape(self):
        text = "\n".join([
            '{"type":"thread.started","thread_id":"01a0f88c-d2cf"}',
            '{"type":"turn.started"}',
            '{"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"done"}}',
            '{"type":"turn.completed","usage":{"input_tokens":31548,"output_tokens":114}}',
        ])
        info = codex_img.parse_events(text)
        self.assertEqual(info["thread_id"], "01a0f88c-d2cf")
        self.assertEqual(info["usage"]["input_tokens"], 31548)
        self.assertEqual(info["last_message"], "done")
        self.assertEqual(info["errors"], [])

    def test_garbage_and_errors(self):
        text = 'Reading additional input\n{bad json\n[1,2]\n{"type":"error","message":"boom"}\n' \
               '{"type":"turn.failed","error":{"message":"429 limit"}}'
        info = codex_img.parse_events(text)
        self.assertIsNone(info["thread_id"])
        self.assertEqual(info["errors"], ["boom", "429 limit"])

    def test_error_shapes(self):
        text = "\n".join([
            '{"type":"turn.failed","error":"429 Too Many Requests"}',
            '{"type":"item.completed","item":{"type":"error","message":"image_gen failed"}}',
            '{"type":"item.completed","item":"not an object"}',
            '{"type":"item.completed","item":null}',
        ])
        info = codex_img.parse_events(text)
        self.assertEqual(info["errors"], ["429 Too Many Requests", "image_gen failed"])

    def test_limit_hit(self):
        hit = codex_img.limit_hit
        self.assertTrue(hit("", "429 Too Many Requests", "a gem"))
        self.assertTrue(hit("CODEX_IMG_RATE_LIMITED", "", "a gem"))
        self.assertTrue(hit("Failed: usage limit reached for image_gen.", "", "a gem"))
        # quoting the description back is a refusal, not a limit
        self.assertFalse(hit("I cannot draw a speed limit reached sign.", "",
                             "a speed limit reached sign"))
        self.assertTrue(hit("Rate limit hit while drawing the sign.", "",
                            "a speed limit reached sign"))
        # the agent's own words around a quoted phrase are not a limit either
        self.assertFalse(hit("The image generation tool refused to draw the speed limit sign.",
                             "", "a speed limit sign"))
        # a keyword is looked up as a word: "quota" is not inside "quotation"
        self.assertTrue(hit("You've reached your image quota, try later.", "",
                            "speech bubble with quotation marks"))
        self.assertFalse(hit("I won't draw a usage-limit warning.", "", "a usage_limit warning"))


class FilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tmpdir(self)

    def test_find_result(self):
        folder = self.tmp / "generated_images" / "t1"
        self.assertIsNone(codex_img.find_result(self.tmp, "t1")[0])
        folder.mkdir(parents=True)
        path, err = codex_img.find_result(self.tmp, "t1")
        self.assertIsNone(path)
        self.assertIn("no image", err)
        make_png(folder / "a.png")
        self.assertEqual(codex_img.find_result(self.tmp, "t1")[0].name, "a.png")
        make_png(folder / "b.png")
        path, err = codex_img.find_result(self.tmp, "t1")
        self.assertIsNone(path)
        self.assertIn("2 images", err)

    def test_claim_path(self):
        out = self.tmp / "fire.png"
        self.assertEqual(codex_img.claim_path(out), out)
        self.assertTrue(out.exists())  # claimed, so the next caller cannot take it
        self.assertEqual(codex_img.claim_path(out).name, "fire.v2.png")
        self.assertEqual(codex_img.claim_path(out).name, "fire.v3.png")

    def test_png_alpha(self):
        rgb = codex_img.png_info(make_png(self.tmp / "rgb.png", color=2))
        self.assertEqual((rgb["width"], rgb["height"], rgb["has_alpha"]), (4, 3, False))
        opaque = codex_img.png_info(make_png(self.tmp / "o.png", color=6))
        self.assertFalse(opaque["has_alpha"])
        last = codex_img.png_info(make_png(self.tmp / "t.png", transparent_at=(3, 2)))
        self.assertTrue(last["has_alpha"])
        half = codex_img.png_info(make_png(self.tmp / "h.png", alpha=128))
        self.assertTrue(half["has_alpha"])

    def test_png_alpha_with_sub_filter(self):
        # filtered bytes differ from pixel values; only proper unfiltering finds the pixel
        p = make_png(self.tmp / "f.png", width=5, transparent_at=(4, 1), filt=1)
        self.assertTrue(codex_img.png_info(p)["has_alpha"])
        p = make_png(self.tmp / "g.png", width=5, filt=1)
        self.assertFalse(codex_img.png_info(p)["has_alpha"])

    def test_png_alpha_every_filter(self):
        # real encoders pick a filter per row and split IDAT; each must unfilter correctly
        for f in (0, 1, 2, 3, 4):
            for depth in (8, 16):
                for color in (4, 6):
                    case = f"filter {f}, {depth}-bit, colour {color}"
                    p = make_png(self.tmp / "p.png", width=6, height=5, color=color,
                                 depth=depth, filt=[f], transparent_at=(4, 3))
                    self.assertTrue(codex_img.png_info(p)["has_alpha"], case)
                    p = make_png(self.tmp / "q.png", width=6, height=5, color=color,
                                 depth=depth, filt=[f])
                    self.assertFalse(codex_img.png_info(p)["has_alpha"], case)

    def test_png_mixed_filters_and_split_idat(self):
        p = make_png(self.tmp / "m.png", width=40, height=30, filt=[4, 2, 3, 1, 0],
                     idat_size=7, transparent_at=(39, 29))
        self.assertTrue(codex_img.png_info(p)["has_alpha"])
        p = make_png(self.tmp / "n.png", width=40, height=30, filt=[4, 2, 3, 1, 0], idat_size=7)
        self.assertFalse(codex_img.png_info(p)["has_alpha"])

    def test_png_almost_opaque(self):
        self.assertTrue(codex_img.png_info(make_png(self.tmp / "a.png", alpha=254))["has_alpha"])
        p = make_png(self.tmp / "b.png", depth=16, alpha=255)  # 0xFFFF, fully opaque
        self.assertFalse(codex_img.png_info(p)["has_alpha"])

    def test_truncated_png_is_rejected(self):
        # what a codex killed mid-write leaves: the start of the file parses, the end is missing
        for color in (2, 6):
            data = make_png(self.tmp / "w.png", width=64, height=64, color=color,
                            transparent_at=(0, 0)).read_bytes()
            for cut in (40, len(data) // 2, len(data) - 12):
                (self.tmp / "cut.png").write_bytes(data[:cut])
                with self.assertRaises(ValueError, msg=f"colour {color}, cut at {cut}"):
                    codex_img.png_info(self.tmp / "cut.png")

    def test_decode_falls_back_without_raising(self):
        self.assertEqual(codex_img._decode("кот".encode("utf-8")), "кот")
        self.assertIsInstance(codex_img._decode(b"\x8a\xae\xe2 \xff"), str)  # cp866 bytes

    def test_not_png(self):
        (self.tmp / "x.png").write_bytes(b"hello")
        with self.assertRaises(ValueError):
            codex_img.png_info(self.tmp / "x.png")

    def test_check_refs(self):
        ok = make_png(self.tmp / "r.png")
        self.assertIsNone(codex_img.check_refs([ok]))
        self.assertIn("at most 5", codex_img.check_refs([ok] * 6))
        self.assertIn("not found", codex_img.check_refs([self.tmp / "nope.png"]))
        (self.tmp / "r.gif").write_bytes(b"x")
        self.assertIn("png, jpg or webp", codex_img.check_refs([self.tmp / "r.gif"]))


# --- end to end with the fake codex ------------------------------------------------------

class GenTest(unittest.TestCase):
    def setUp(self):
        self.out = tmpdir(self) / "икон ки" / "fire.png"  # spaces, Cyrillic

    def test_ok_transparent(self):
        with Fake() as fake:
            code, res, _ = cli("gen", "--prompt", 'a "red" gem & 100% fire', "--out",
                               str(self.out), "--transparent")
            self.assertEqual(code, 0, res)
            self.assertTrue(res["ok"])
            self.assertTrue(res["has_alpha"])
            self.assertEqual(res["size"], "4x3")
            self.assertEqual(res["tokens"]["input_tokens"], 100)
            self.assertTrue(self.out.exists())
            call = fake.calls()[0]
            self.assertIn('a "red" gem & 100% fire', call["prompt"])  # reached codex intact
            self.assertIn("transparent_background=true", call["prompt"])

    def test_refs_are_passed(self):
        ref = make_png(tmpdir(self) / "style.png")  # a plain path: passed as it is everywhere
        with Fake() as fake:
            code, res, _ = cli("gen", "--prompt", "water gem", "--out", str(self.out),
                               "--ref", str(ref))
            self.assertEqual(code, 0, res)
            args = fake.calls()[0]["args"]
            self.assertEqual(args[-2:], ["-i", str(ref)])

    def test_out_must_be_png(self):
        with Fake() as fake:
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out.with_suffix(".jpg")))
            self.assertEqual(code, 1)
            self.assertIn(".png", res["error"])
            self.assertEqual(fake.calls(), [])  # nothing spent

    def test_no_overwrite_by_default(self):
        with Fake():
            cli("gen", "--prompt", "x", "--out", str(self.out))
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out))
            self.assertEqual(code, 0)
            self.assertTrue(res["out"].endswith("fire.v2.png"))
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out), "--overwrite")
            self.assertTrue(res["out"].endswith("fire.png"))

    def test_no_alpha_keeps_file(self):
        with Fake("rgb"):
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out), "--transparent")
            self.assertEqual(code, 1)
            self.assertEqual(res["error"], "no_alpha")
            self.assertTrue(self.out.exists())

    def test_refused(self):
        with Fake("refuse"):
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out))
            self.assertEqual(code, 1)
            self.assertEqual(res["error"], "no_image")
            self.assertEqual(res["codex_said"], "I cannot do that.")
            self.assertFalse(self.out.exists())

    def test_two_images_is_an_error(self):
        with Fake("two"):
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out))
            self.assertEqual(code, 1)
            self.assertEqual(res["error"], "no_image")
            self.assertIn("2 images", res["detail"])
            self.assertFalse(self.out.exists())

    def test_not_a_png_from_codex(self):
        with Fake("notpng"):
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out))
            self.assertEqual(code, 1)
            self.assertTrue(res["error"].startswith("bad png"), res)

    def test_rate_limited(self):
        with Fake("rate"):
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out))
            self.assertEqual(code, 1)
            self.assertEqual(res["error"], "rate_limited")

    def test_old_codex(self):
        with Fake(version="codex-cli 0.157.9"):
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out))
            self.assertEqual(code, 2)
            self.assertEqual(res["error"], "setup")
            self.assertIn("too old", res["detail"])
        with Fake(version="codex-cli 0.158.0"):
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out))
            self.assertEqual(code, 0, res)

    def test_missing_codex(self):
        code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out),
                           env={"CODEX_IMG_CODEX_BIN": "", "PATH": str(tmpdir(self))})
        self.assertEqual(code, 2)
        self.assertIn("codex not found", res["detail"])


class BatchTest(unittest.TestCase):
    def setUp(self):
        self.dir = tmpdir(self)

    def manifest(self, items, defaults=None):
        path = self.dir / "manifest.json"
        path.write_text(json.dumps({"defaults": defaults or {}, "items": items}),
                        encoding="utf-8")
        return str(path)

    def test_relative_paths_and_defaults(self):
        make_png(self.dir / "style.png")
        m = self.manifest([{"out": "out/a.png", "prompt": "a"},
                           {"out": "out/b.png", "prompt": "b", "transparent": False}],
                          {"ref": ["style.png"], "transparent": True})
        with Fake() as fake:
            code, res, err = cli("batch", m)
            self.assertEqual(code, 0, res)
            self.assertEqual(len(res["results"]), 2)
            self.assertTrue((self.dir / "out" / "a.png").exists())
            calls = fake.calls()
            self.assertIn(str((self.dir / "style.png").resolve()), calls[0]["args"])
            self.assertIn("transparent_background=true", calls[0]["prompt"])
            self.assertNotIn("transparent_background=true", calls[1]["prompt"])
            self.assertIn("[2/2] ok", err)

    def test_failed_item_does_not_stop(self):
        m = self.manifest([{"out": "a.png", "prompt": "a", "ref": ["missing.png"]},
                           {"out": "b.png", "prompt": "b"}])
        with Fake():
            code, res, _ = cli("batch", m)
            self.assertEqual(code, 1)
            self.assertFalse(res["results"][0]["ok"])
            self.assertTrue(res["results"][1]["ok"])
            self.assertNotIn("stopped_reason", res)

    def test_rate_limit_stops_and_resume_skips(self):
        m = self.manifest([{"out": "a.png", "prompt": "a"}, {"out": "b.png", "prompt": "b"}])
        with Fake("ok_then_rate") as fake:
            code, res, _ = cli("batch", m)
            self.assertEqual(code, 1)
            self.assertTrue(res["results"][0]["ok"])
            self.assertEqual(res["stopped_reason"], "rate_limited")
            self.assertIn("--resume", res["hint"])
            fake.set_mode("ok")
            code, res, _ = cli("batch", m, "--resume")
            self.assertEqual(code, 0, res)
            self.assertEqual(res["results"][0]["skipped"], "done earlier")
            self.assertTrue(res["results"][1]["ok"])
            self.assertEqual(len(fake.calls()), 3)

    def test_resume_reports_the_version_it_wrote(self):
        make_png(self.dir / "a.png")  # the user's own file, there before the batch
        m = self.manifest([{"out": "a.png", "prompt": "a"}, {"out": "b.png", "prompt": "b"}])
        with Fake("ok_then_rate") as fake:
            _, res, _ = cli("batch", m)
            self.assertTrue(res["results"][0]["out"].endswith("a.v2.png"))
            fake.set_mode("ok")
            _, res, _ = cli("batch", m, "--resume")
            self.assertEqual(res["results"][0]["skipped"], "done earlier")
            self.assertTrue(res["results"][0]["out"].endswith("a.v2.png"))

    def test_resume_survives_a_moved_project(self):
        proj = self.dir / "proj"
        proj.mkdir()
        m = proj / "m.json"
        m.write_text(json.dumps({"items": [{"out": "a.png", "prompt": "a"},
                                           {"out": "b.png", "prompt": "b"}]}), encoding="utf-8")
        with Fake("ok_then_rate") as fake:
            cli("batch", str(m))
            moved = self.dir / "renamed"
            proj.rename(moved)
            fake.set_mode("ok")
            _, res, _ = cli("batch", str(moved / "m.json"), "--resume")
            self.assertEqual(res["results"][0]["skipped"], "done earlier")
            self.assertEqual(res["results"][0]["out"], str(moved.resolve() / "a.png"))
            self.assertFalse((moved / "a.v2.png").exists())

    def test_unreadable_state_stops_before_codex(self):
        m = self.manifest([{"out": "a.png", "prompt": "a"}])
        codex_img.state_path(m).write_text("", encoding="utf-8")  # cut off mid-write
        with Fake() as fake:
            code, res, _ = cli("batch", m, "--resume")
            self.assertEqual((code, res["error"]), (2, "bad_manifest"))
            self.assertIn("codex-img-state.json", res["detail"])
            self.assertEqual(fake.calls(), [])

    def test_state_file_name_and_atomic_save(self):
        m = self.manifest([{"out": "a.png", "prompt": "a"}])
        state = codex_img.state_path(m)
        self.assertEqual(state.name, "manifest.codex-img-state.json")
        with Fake():
            cli("batch", m)
        self.assertEqual(json.loads(state.read_text(encoding="utf-8")),
                         {"files": {"a.png": "a.png"}})
        self.assertFalse(state.with_name(state.name + ".tmp").exists())

    def test_crash_in_one_item_keeps_the_batch(self):
        jobs = [{"out": self.dir / f"{n}.png", "prompt": n, "refs": [], "transparent": False,
                 "overwrite": False} for n in "ab"]
        calls = []

        def flaky(codex, prompt, out, *rest):
            calls.append(prompt)
            if prompt == "a":
                raise RuntimeError("boom")
            return {"ok": True, "out": str(out)}

        with unittest.mock.patch.object(codex_img, "generate", flaky):
            res = codex_img.run_batch(["codex"], jobs)
        self.assertEqual(calls, ["a", "b"])
        self.assertTrue(res["results"][0]["error"].startswith("internal:"))
        self.assertTrue(res["results"][1]["ok"])

    def test_per_item_overwrite(self):
        make_png(self.dir / "a.png", color=2)
        m = self.manifest([{"out": "a.png", "prompt": "a", "overwrite": True}])
        with Fake():
            code, res, _ = cli("batch", m)
            self.assertEqual(code, 0, res)
            self.assertEqual(res["results"][0]["out"], str(self.dir.resolve() / "a.png"))

    @unittest.skipUnless(sys.platform in ("darwin", "win32"), "case-insensitive file systems")
    def test_duplicate_out_differing_in_case(self):
        with Fake():
            code, res, _ = cli("batch", self.manifest(
                [{"out": "Fire.png", "prompt": "a"}, {"out": "fire.png", "prompt": "b"}]))
            self.assertIn('same "out"', res["detail"])

    def test_bad_manifest(self):
        with Fake() as fake:
            code, res, _ = cli("batch", self.manifest([{"out": "a.png"}]))
            self.assertEqual(code, 2)
            self.assertEqual(res["error"], "bad_manifest")
            self.assertIn("needs \"out\" and \"prompt\"", res["detail"])
            code, res, _ = cli("batch", self.manifest([{"out": "a", "prompt": "a"}], ["x"]))
            self.assertIn('"defaults" must be an object', res["detail"])
            code, res, _ = cli("batch", self.manifest([{"out": "a", "prompt": "a", "ref": 5}]))
            self.assertIn('"ref" must be a path', res["detail"])
            code, res, _ = cli("batch", self.manifest([{"out": 5, "prompt": "a"}]))
            self.assertEqual((code, res["error"]), (2, "bad_manifest"))
            code, res, _ = cli("batch", self.manifest(
                [{"out": "a.png", "prompt": "a", "transparent": "false"}]))
            self.assertIn('"transparent" must be true or false', res["detail"])
            code, res, _ = cli("batch", self.manifest(
                [{"out": "a.png", "prompt": "a"}, {"out": "./a.png", "prompt": "b"}]))
            self.assertIn('same "out"', res["detail"])
            code, res, _ = cli("batch", self.manifest(
                [{"out": "a.png", "prompt": "a"}, {"out": "b.webp", "prompt": "b"}]))
            self.assertIn('must be a .png', res["detail"])
            self.assertEqual(fake.calls(), [])  # nothing spent on any of these


class FailureModesTest(unittest.TestCase):
    """Cases found in review: hidden limits, early crashes, timeouts, stale files."""

    def setUp(self):
        self.dir = tmpdir(self)
        self.out = self.dir / "a.png"

    def manifest(self, items):
        path = self.dir / "m.json"
        path.write_text(json.dumps({"items": items}), encoding="utf-8")
        return str(path)

    def test_limit_in_agent_reply_stops_batch(self):
        # the image_gen limit fails the tool inside the turn: exit 0, no image, only a reply
        m = self.manifest([{"out": "a.png", "prompt": "a"}, {"out": "b.png", "prompt": "b"}])
        with Fake("limit_reply") as fake:
            code, res, _ = cli("batch", m)
            self.assertEqual(code, 1)
            self.assertEqual(res["results"][0]["error"], "rate_limited")
            self.assertEqual(res["stopped_reason"], "rate_limited")
            self.assertEqual(len(fake.calls()), 1)

    def test_sentinel_reply(self):
        with Fake("sentinel"):
            _, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out))
            self.assertEqual(res["error"], "rate_limited")

    def test_prompt_quoted_in_a_refusal_does_not_fake_a_limit(self):
        m = self.manifest([{"out": "a.png", "prompt": "a speed limit reached sign, 429 km/h"},
                           {"out": "b.png", "prompt": "b"}])
        with Fake("echo_refuse") as fake:
            _, res, _ = cli("batch", m)
            self.assertEqual(res["results"][0]["error"], "no_image")
            self.assertIn("speed limit", res["results"][0]["codex_said"])
            self.assertNotIn("stopped_reason", res)
            self.assertEqual(len(fake.calls()), 2)

    def test_one_failed_turn_does_not_stop_batch(self):
        m = self.manifest([{"out": "a.png", "prompt": "a"}, {"out": "b.png", "prompt": "b"}])
        with Fake("fail_then_ok") as fake:
            _, res, _ = cli("batch", m)
            self.assertEqual(res["results"][0]["error"], "no_image")
            self.assertIn("stream disconnected", res["results"][0]["detail"])
            self.assertEqual(res["results"][0]["exit_code"], 1)
            self.assertTrue(res["results"][1]["ok"])
            self.assertNotIn("stopped_reason", res)
            self.assertEqual(len(fake.calls()), 2)

    def test_failed_turns_in_a_row_stop_batch(self):
        m = self.manifest([{"out": f"{c}.png", "prompt": c} for c in "abcd"])
        with Fake("thread_then_fail") as fake:
            code, res, _ = cli("batch", m)
            self.assertEqual(code, 1)
            self.assertEqual(res["stopped_reason"], "codex_failing")
            self.assertIn("--resume", res["hint"])
            self.assertEqual(len(fake.calls()), 2)

    def test_refusals_in_a_row_do_not_stop_batch(self):
        m = self.manifest([{"out": f"{c}.png", "prompt": c} for c in "abc"])
        with Fake("refuse") as fake:
            _, res, _ = cli("batch", m)
            self.assertNotIn("stopped_reason", res)  # exit 0: the agent said no, codex is fine
            self.assertEqual(len(fake.calls()), 3)

    def test_empty_prompt_spends_nothing(self):
        with Fake() as fake:
            code, res, _ = cli("gen", "--prompt", "   ", "--out", str(self.out))
            self.assertEqual((code, res["error"]), (1, "empty prompt"))
            self.assertEqual(fake.calls(), [])

    def test_codex_that_cannot_run_is_a_setup_error(self):
        with self.assertRaises(codex_img.SetupError) as ctx:
            codex_img.check_version([str(self.dir / "no-such-codex")])
        self.assertIn("cannot run", str(ctx.exception))
        with Fake(version="codex-cli (dev build)"):
            code, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out))
            self.assertEqual((code, res["error"]), (2, "setup"))
            self.assertIn("cannot read the Codex version", res["detail"])

    def test_codex_that_cannot_start_stops_batch(self):
        m = self.manifest([{"out": "a.png", "prompt": "a"}, {"out": "b.png", "prompt": "b"}])
        with Fake("fail_start") as fake:
            code, res, _ = cli("batch", m)
            self.assertEqual(res["results"][0]["error"], "codex_failed")
            self.assertIn("unexpected argument", res["results"][0]["detail"])
            self.assertEqual(res["stopped_reason"], "codex_failed")
            self.assertEqual(len(fake.calls()), 0)  # crashed before reading the prompt

    @unittest.skipIf(os.name == "nt", "POSIX process groups")
    def test_timeout_kills_the_whole_tree(self):
        with Fake("hang") as fake:
            started = time.monotonic()
            _, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out), "--timeout", "2")
            self.assertLess(time.monotonic() - started, 30)
            self.assertEqual(res["error"], "timeout after 2 s")
            self.assertGone(fake)

    def assertGone(self, fake):
        pidfile = fake.dir / "grandchild.pid"
        self.assertTrue(pidfile.exists(), "the fake never started its grandchild")
        pid = int(pidfile.read_text())
        for _ in range(50):  # a zombie still answers kill(0); give init time to reap it
            try:
                os.kill(pid, 0)
            except OSError:
                return
            state = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)],
                                   capture_output=True, text=True).stdout.strip()
            if state.startswith("Z"):
                return
            time.sleep(0.1)
        self.fail(f"grandchild {pid} survived")

    @unittest.skipIf(os.name == "nt", "POSIX signals")
    def test_killing_the_script_kills_codex(self):
        # a background batch stopped by its time limit, or a terminal closed mid-run
        with Fake("hang") as fake:
            proc = subprocess.Popen([sys.executable, SCRIPT, "gen", "--prompt", "x",
                                     "--out", str(self.out)], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE)
            pidfile = fake.dir / "grandchild.pid"
            for _ in range(100):
                if pidfile.exists() and pidfile.read_text():
                    break
                time.sleep(0.1)
            proc.send_signal(signal.SIGTERM)
            proc.communicate(timeout=20)
            self.assertNotEqual(proc.returncode, 0)
            self.assertGone(fake)

    def test_image_saved_before_timeout_is_kept(self):
        with Fake("image_then_hang"):
            _, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out), "--timeout", "3",
                            "--transparent")
            self.assertTrue(res["ok"], res)
            self.assertIn("stopped after 3 s", res["note"])

    def test_unfinished_image_at_timeout_is_not_saved(self):
        with Fake("partial_then_hang"):
            _, res, _ = cli("gen", "--prompt", "x", "--out", str(self.out), "--timeout", "2")
            self.assertEqual(res["error"], "timeout after 2 s")
            self.assertIn("unfinished image", res["detail"])
            self.assertFalse(self.out.exists())

    def test_big_prompt_to_a_codex_that_never_reads_still_times_out(self):
        argv = [sys.executable, "-c", "import time; time.sleep(30)"]
        started = time.monotonic()
        _, _, _, timed_out = codex_img.run_process(argv, b"x" * (4 << 20), 2)
        self.assertTrue(timed_out)
        self.assertLess(time.monotonic() - started, 15)

    def test_failed_copy_leaves_no_placeholder_and_no_state(self):
        m = self.manifest([{"out": "a.png", "prompt": "a"}])
        jobs = codex_img.load_manifest(m)
        state = codex_img.state_path(m)
        with Fake(), unittest.mock.patch.object(codex_img.shutil, "copy2",
                                                side_effect=OSError("disk full")), \
                unittest.mock.patch.object(codex_img, "check_version"):
            res = codex_img.run_batch(codex_img.find_codex(), jobs, state=state)
        self.assertTrue(res["results"][0]["error"].startswith("cannot save"))
        self.assertFalse(self.out.exists())  # the claimed name was given back
        self.assertFalse(state.exists())

    def test_interrupted_copy_leaves_no_placeholder(self):
        with Fake(), unittest.mock.patch.object(codex_img.shutil, "copy2",
                                                side_effect=KeyboardInterrupt):
            with self.assertRaises(KeyboardInterrupt):
                codex_img.generate(codex_img.find_codex(), "x", self.out)
        self.assertFalse(self.out.exists())

    def test_resume_redoes_a_file_that_failed_its_check(self):
        m = self.manifest([{"out": "a.png", "prompt": "a", "transparent": True}])
        with Fake("rgb") as fake:
            _, res, _ = cli("batch", m)
            self.assertEqual(res["results"][0]["error"], "no_alpha")  # the batch wrote a.png
            fake.set_mode("ok")
            code, res, _ = cli("batch", m, "--resume")
            self.assertEqual(code, 0, res)
            self.assertNotIn("skipped", res["results"][0])
            self.assertEqual(res["results"][0]["out"], str(self.out.resolve()))  # in place
            self.assertTrue(codex_img.png_info(self.out)["has_alpha"])
            self.assertFalse((self.dir / "a.v2.png").exists())

    def test_resume_never_touches_a_file_it_did_not_write(self):
        mine = make_png(self.out, color=2).read_bytes()  # the user's own opaque a.png
        m = self.manifest([{"out": "a.png", "prompt": "a", "transparent": True}])
        with Fake():
            code, res, _ = cli("batch", m, "--resume")
            self.assertEqual(code, 0, res)
            self.assertTrue(res["results"][0]["out"].endswith("a.v2.png"))
            self.assertEqual(self.out.read_bytes(), mine)

    def test_resume_redoes_a_corrupt_file(self):
        m = self.manifest([{"out": "a.png", "prompt": "a"}])
        with Fake():
            cli("batch", m)
            self.out.write_bytes(self.out.read_bytes()[:40])  # truncated since
            code, res, _ = cli("batch", m, "--resume")
            self.assertEqual(code, 0, res)
            self.assertNotIn("skipped", res["results"][0])
            codex_img.png_info(self.out)  # whole again

    def test_corrupt_png_is_a_value_error(self):
        good = make_png(self.dir / "g.png").read_bytes()
        (self.dir / "c.png").write_bytes(good[:40])
        with self.assertRaises(ValueError):
            codex_img.png_info(self.dir / "c.png")

    def test_ref_as_string(self):
        make_png(self.dir / "s.png")
        path = self.dir / "m.json"
        path.write_text(json.dumps({"defaults": {"ref": "s.png"},
                                    "items": [{"out": "a.png", "prompt": "a"}]}))
        jobs = codex_img.load_manifest(path)
        self.assertEqual([r.name for r in jobs[0]["refs"]], ["s.png"])

    def test_windows_npm_launcher(self):
        shim = self.dir / "codex.cmd"
        shim.write_text("")
        self.assertIsNone(codex_img._windows_npm_launcher(shim))
        script = self.dir / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
        script.parent.mkdir(parents=True)
        script.write_text("")
        (self.dir / "node.exe").write_text("")
        self.assertEqual(codex_img._windows_npm_launcher(shim),
                         [str(self.dir / "node.exe"), str(script)])

    def test_npm_launcher_for_an_override(self):
        # an override pointing at npm's codex.cmd skips cmd.exe like a PATH lookup does
        # (os.name is faked, so the launcher itself is stubbed: pathlib cannot follow)
        launcher = ["node.exe", "codex.js"]
        with unittest.mock.patch.dict(os.environ, {"CODEX_IMG_CODEX_BIN": r"C:\npm\codex.cmd"}), \
                unittest.mock.patch.object(codex_img.os, "name", "nt"), \
                unittest.mock.patch.object(codex_img, "_windows_npm_launcher",
                                           return_value=launcher) as found:
            self.assertEqual(codex_img.find_codex(), launcher)
        found.assert_called_once_with(r"C:\npm\codex.cmd")

    def test_cmd_safety(self):
        self.assertTrue(codex_img._cmd_safe("C:/icons/fire.png"))
        for bad in ("C:/a&b/x.png", "C:/100%/x.png", "C:/икон/x.png", 'C:/"q"/x.png',
                    "C:/a|b", "C:/a<b", "C:/a>b", "C:/a^b", "C:/a!b", "C:/(x)/y.png"):
            self.assertFalse(codex_img._cmd_safe(bad), bad)
        self.assertTrue(codex_img._cmd_safe("C:/Users/Иван/x.png", allow_unicode=True))
        self.assertFalse(codex_img._cmd_safe("C:/a&b", allow_unicode=True))

    def test_refs_through_cmd_are_passed_as_safe_copies(self):
        # the Windows codex.cmd path, simulated: refs with & or Cyrillic go as plain copies
        ref = make_png(self.dir / "икон & ки" / "style.png")
        seen = {}

        def fake_run(argv, data, timeout):
            seen["refs"] = [pathlib.Path(argv[i + 1]) for i, a in enumerate(argv) if a == "-i"]
            seen["exists"] = all(p.is_file() for p in seen["refs"])
            return 0, "", "", False

        cyrillic_tmp = self.dir / "Иван" / "Temp"  # a Windows user with a Cyrillic name
        cyrillic_tmp.mkdir(parents=True)
        real_mkdtemp = tempfile.mkdtemp
        with unittest.mock.patch.object(codex_img, "via_cmd", return_value=True), \
                unittest.mock.patch.object(codex_img, "run_process", fake_run), \
                unittest.mock.patch.object(codex_img.tempfile, "mkdtemp",
                                           lambda prefix: real_mkdtemp(prefix=prefix,
                                                                       dir=cyrillic_tmp)):
            res = codex_img.generate(["codex.cmd"], "x", self.out, [ref])
        self.assertEqual(res["error"], "no_image")
        self.assertEqual([p.name for p in seen["refs"]], ["ref0.png"])
        self.assertTrue(codex_img._cmd_safe(seen["refs"][0], allow_unicode=True))
        self.assertTrue(seen["exists"])
        self.assertFalse(seen["refs"][0].exists())  # the copies are cleaned up

    def test_gen_crash_still_prints_json(self):
        with Fake(), unittest.mock.patch.object(codex_img, "generate",
                                                side_effect=RuntimeError("boom")):
            out = []
            with unittest.mock.patch.object(codex_img.sys.stdout, "write", out.append):
                code = codex_img.main(["gen", "--prompt", "x", "--out", str(self.out)])
        self.assertEqual(code, 1)
        self.assertIn("internal", json.loads(out[0])["error"])


if __name__ == "__main__":
    unittest.main()
