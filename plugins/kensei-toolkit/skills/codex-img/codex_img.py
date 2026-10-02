#!/usr/bin/env python3
"""codex-img — generate and edit images through the Codex CLI's built-in image tool.

  codex_img.py gen --prompt TEXT --out PATH [--ref IMG ...] [--transparent] [--overwrite]
                   [--timeout SECS]
      Generate one image and save it at PATH (or PATH.vN when PATH exists and --overwrite is
      not given). --ref attaches up to 5 images: a style reference for a series, or the image
      to edit (the prompt then says what to change). Prints one JSON object.
  codex_img.py batch MANIFEST [--resume] [--timeout SECS]
      Generate every item of a JSON manifest, one after another:
        {"defaults": {"ref": [...], "transparent": true},
         "items": [{"out": "fire.png", "prompt": "...", "ref": [...]}]}
      Relative paths are resolved against the manifest's folder. A failed item does not stop
      the batch; a rate limit, a Codex that will not start, or two turns in a row that end
      with a Codex error (codex_failing) do. Which file each item was
      written to is kept in MANIFEST's sibling <name>.codex-img-state.json; --resume skips an
      item whose recorded file passes the checks (a transparent item needs real alpha) and
      redoes it in place otherwise. Files the batch did not write are never replaced, unless
      the item sets "overwrite": true.
      Prints {"results": [...], "stopped_reason"?, "hint"?}.

The image comes from the user's ChatGPT subscription via `codex exec` — no API key. The model,
quality and size are chosen by Codex (gpt-image-2 per its source, ~1254x1254); masks are not
supported. Codex writes the image to $CODEX_HOME/generated_images/<thread_id>/; this script
reads thread_id from the first `--json` event and copies that file itself, so the Codex agent
gets a read-only sandbox and never has to touch the disk.

Exit codes: 0 — every image ok; 1 — some image failed (bad input such as a missing reference
included) or the batch stopped; 2 — bad command line, setup or manifest error.
"""

import argparse
import json
import locale
import os
import pathlib
import re
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import threading
import time
import zlib

MIN_CODEX = (0, 158, 0)  # transparent_background arrived in 0.158.0 (openai/codex PR #47484)
MAX_REFS = 5             # the image tool accepts at most 5 input images
# One image takes ~50-90 s. 540 s keeps a `gen` under the Bash tool's 600 s ceiling with room
# for the version check and Python start-up.
DEFAULT_TIMEOUT = 540
REF_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
# The prompt goes in on stdin, not as an argument: `-i <FILE>...` would swallow a positional
# prompt that follows it, and on Windows `codex.cmd` routes arguments through cmd.exe, which
# mangles quotes, % and & inside a prompt.
# Checked live on 0.159.3: with --ephemeral the image still lands in generated_images/<tid>/,
# and a read-only sandbox does not block the image tool.
EPHEMERAL = True
SANDBOX = "read-only"
# A hidden image_gen limit fails the tool call inside the turn: Codex exits 0 and the limit
# shows up only in the agent's reply. The prompt asks for this sentinel; the regex is the
# fallback. Both are consulted only when no image was produced.
RATE_SENTINEL = "CODEX_IMG_RATE_LIMITED"
RATE_LIMIT_RE = re.compile(
    r"\b429\b|rate[ _-]?limit|usage[ _-]?limit|too many requests|quota|"
    r"limit (?:reached|exceeded)|image[ _-]?gen\w*.{0,40}(?:limit|429)", re.I)
# In the agent's reply only the bare keywords count (no "image_gen ... limit" span that would
# swallow the agent's own words); see limit_hit.
REPLY_LIMIT_RE = re.compile(
    r"\b429\b|\brate limit|\busage limit|\btoo many requests\b|\bquota\b|"
    r"\blimit (?:reached|exceeded)\b")
CMD_UNSAFE = set('&|<>^%!"()')  # characters cmd.exe interprets inside a batch-file call
STOP_ERRORS = ("rate_limited", "codex_failed")
# Codex exiting non-zero after the turn started (auth expired mid-run, backend down) gives
# no_image + exit_code; a refusal exits 0. This many in a row stop a batch: the next ones would
# fail the same way, a minute and a half each.
MAX_FAILED_TURNS = 2


class SetupError(Exception):
    """Codex is missing, too old or unusable — nothing can be generated."""


class ManifestError(Exception):
    """The batch manifest is malformed."""


# --- codex -------------------------------------------------------------------------------

def _windows_npm_launcher(shim):
    """For an npm `codex.cmd`, the [node, codex.js] it would run — skipping cmd.exe."""
    folder = pathlib.Path(shim).parent
    script = folder / "node_modules" / "@openai" / "codex" / "bin" / "codex.js"
    node = folder / "node.exe"
    node = str(node) if node.is_file() else shutil.which("node")
    return [node, str(script)] if node and script.is_file() else None


def find_codex():
    """argv prefix that starts Codex."""
    found = os.environ.get("CODEX_IMG_CODEX_BIN")
    if not found:
        found = shutil.which("codex")  # on Windows this resolves codex.cmd through PATHEXT
        if found and os.name == "nt":
            exts = [e.upper() for e in
                    (os.environ.get("PATHEXT") or ".EXE;.CMD;.BAT").split(";") if e]
            if pathlib.Path(found).suffix.upper() not in exts:
                # some Python versions return npm's extensionless sh shim, which cannot be run
                found = shutil.which("codex.exe") or shutil.which("codex.cmd") or found
    if not found:
        raise SetupError("codex not found in PATH. Install Codex CLI >= 0.158 "
                         "(brew install --cask codex, or npm i -g @openai/codex) "
                         "and sign in with ChatGPT: codex login")
    if os.name == "nt" and found.lower().endswith((".cmd", ".bat")):
        launcher = _windows_npm_launcher(found)
        if launcher:
            return launcher
    return [found]


def via_cmd(argv):
    return os.name == "nt" and argv[0].lower().endswith((".cmd", ".bat"))


def codex_home():
    return pathlib.Path(os.environ.get("CODEX_HOME") or pathlib.Path.home() / ".codex")


def _kill_tree(proc):
    if os.name == "nt":
        taskkill = os.path.join(os.environ.get("SystemRoot") or r"C:\Windows",
                                "System32", "taskkill.exe")
        try:
            subprocess.run([taskkill, "/T", "/F", "/PID", str(proc.pid)],
                           capture_output=True, timeout=30)
        except (OSError, subprocess.SubprocessError):
            pass
        try:
            proc.kill()  # at least the direct child, if taskkill could not run
        except OSError:
            pass
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass


def _decode(raw):
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        # cmd.exe and Windows itself speak the OEM code page (cp866 on a Russian system)
        try:
            return raw.decode("oem" if os.name == "nt" else locale.getpreferredencoding(False),
                              "replace")
        except LookupError:
            return raw.decode("utf-8", "replace")


def run_process(argv, data, timeout):
    """Run argv, feed data on stdin; on timeout kill the whole process tree.

    Codex gets its own process group so the timeout can kill the tree — which also means a
    Ctrl+C or a kill of this script would not reach it; those are passed on explicitly.
    Output goes to temporary files, not pipes: a grandchild that outlives the kill (node under
    codex.cmd) would otherwise keep the pipes open and block the read forever.
    Returns (returncode, stdout, stderr, timed_out).
    """
    extra = ({"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt"
             else {"start_new_session": True})
    with tempfile.TemporaryFile() as out, tempfile.TemporaryFile() as err:
        proc = subprocess.Popen(argv, stdin=subprocess.PIPE, stdout=out, stderr=err, **extra)

        def feed():  # in a thread: a prompt bigger than the pipe buffer must not dodge the timeout
            try:
                proc.stdin.write(data)
            except OSError:
                pass  # the child exited early; its output says why
            try:
                proc.stdin.close()
            except OSError:
                pass

        timed_out = False
        try:  # opened right after Popen: from here on, any interruption takes codex down
            threading.Thread(target=feed, daemon=True).start()
            deadline = time.monotonic() + timeout
            while True:
                # short slices: on Windows one long wait cannot be interrupted by Ctrl+C
                try:
                    proc.wait(timeout=max(0.0, min(0.5, deadline - time.monotonic())))
                    break
                except subprocess.TimeoutExpired:
                    if time.monotonic() >= deadline:
                        raise
        except subprocess.TimeoutExpired:
            timed_out = True
            _kill_tree(proc)
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
        except BaseException:  # Ctrl+C, SIGTERM: an orphaned codex would keep spending quota
            _kill_tree(proc)
            raise
        out.seek(0)
        err.seek(0)
        # stdout is codex's JSON, always UTF-8; only stderr may come from cmd.exe in OEM
        return (proc.returncode, out.read().decode("utf-8", "replace"), _decode(err.read()),
                timed_out)


def parse_version(text):
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in m.groups()) if m else None


def check_version(argv):
    try:
        _, text, _, _ = run_process(argv + ["--version"], b"", 30)
    except OSError as exc:
        raise SetupError(f"cannot run {argv[0]} --version: {exc}")
    version = parse_version(text)
    if version is None:
        raise SetupError(f"cannot read the Codex version from: {text.strip()!r}")
    if version < MIN_CODEX:
        need = ".".join(map(str, MIN_CODEX))
        raise SetupError(f"Codex {'.'.join(map(str, version))} is too old, need >= {need} "
                         "(brew upgrade --cask codex, or npm i -g @openai/codex@latest)")
    return version


def wrap_prompt(prompt, transparent, refs):
    """Narrow the Codex agent to one image-tool call; everything else is done by this script."""
    lines = ["Use your built-in image generation tool exactly once, with the description below."]
    if refs:
        lines.append(f"Pass all {len(refs)} attached image(s) to the tool as reference images.")
    if transparent:
        lines.append("Set transparent_background=true.")
    lines += ["Do not rewrite or extend the description, do not generate variations, "
              "do not run shell commands and do not edit any files. "
              "After the tool returns, reply with one short line.",
              f"If the image tool fails because of a usage or rate limit, reply exactly: "
              f"{RATE_SENTINEL}",
              "",
              "Description:",
              prompt.strip()]
    return "\n".join(lines)


def build_command(codex, refs):
    cmd = list(codex) + ["exec", "--skip-git-repo-check", "--json", "-s", SANDBOX,
                         "-c", "approval_policy=never"]  # unquoted: no quotes through cmd.exe
    if EPHEMERAL:
        cmd.append("--ephemeral")
    for ref in refs:
        cmd += ["-i", str(ref)]
    return cmd  # no positional prompt: codex exec reads it from stdin


def parse_events(text):
    """Pull what we need out of `codex exec --json` output; bad lines are skipped."""
    info = {"thread_id": None, "usage": None, "errors": [], "last_message": None}
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if not isinstance(event, dict):
            continue
        kind = event.get("type")
        if kind == "thread.started" and not info["thread_id"]:
            info["thread_id"] = event.get("thread_id")
        elif kind == "turn.completed":
            info["usage"] = event.get("usage")
        elif kind in ("error", "turn.failed"):
            err = event.get("error")
            msg = event.get("message") or (err.get("message") if isinstance(err, dict) else err)
            info["errors"].append(str(msg or event))
        elif kind == "item.completed":
            item = event.get("item")
            if not isinstance(item, dict):
                continue
            if item.get("type") == "agent_message" and item.get("text"):
                info["last_message"] = item["text"]
            elif item.get("type") == "error":
                info["errors"].append(str(item.get("message") or item))
    return info


def find_result(home, thread_id):
    folder = pathlib.Path(home) / "generated_images" / thread_id
    pngs = sorted(folder.glob("*.png")) if folder.is_dir() else []
    if len(pngs) == 1:
        return pngs[0], None
    if not pngs:
        return None, f"no image in {folder}"
    return None, f"{len(pngs)} images in {folder}, expected one: " + ", ".join(p.name for p in pngs)


# --- files -------------------------------------------------------------------------------

def claim_path(out):
    """Reserve PATH, or PATH.vN when taken, by creating it empty — atomically, so two runs
    saving to the same name never pick the same file."""
    out = pathlib.Path(out)
    n = 1
    while True:
        candidate = out if n == 1 else out.with_name(f"{out.stem}.v{n}{out.suffix}")
        try:
            os.close(os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
            return candidate
        except FileExistsError:
            n += 1


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def png_info(path):
    """Size, colour type and whether any pixel is actually see-through. Stdlib only.

    For colour types 4/6 the image data is unfiltered row by row until the first pixel with
    alpha below the maximum — on a transparent icon that is the first row, so it is fast.
    Raises ValueError for anything that is not a readable PNG.
    """
    try:
        return _png_info(pathlib.Path(path).read_bytes())
    except (struct.error, zlib.error, IndexError) as exc:
        raise ValueError(f"corrupt PNG: {exc}")


def _png_info(data):
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG file")
    pos, ihdr, trns, idat, ended = 8, None, None, [], False
    while pos + 8 <= len(data):
        length, ctype = struct.unpack(">I4s", data[pos:pos + 8])
        if pos + 12 + length > len(data):
            raise ValueError("truncated PNG: a chunk is cut off")
        body = data[pos + 8:pos + 8 + length]
        if ctype == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif ctype == b"tRNS":
            trns = body
        elif ctype == b"IDAT":
            idat.append(body)
        elif ctype == b"IEND":
            ended = True
            break
        pos += 12 + length
    if ihdr is None:
        raise ValueError("PNG has no IHDR")
    if not ended:  # e.g. codex killed while writing: the start of a file parses fine
        raise ValueError("truncated PNG: no IEND")
    width, height, depth, color, _, _, interlace = ihdr
    info = {"width": width, "height": height, "color_type": color, "has_alpha": False}
    if color in (0, 2, 3):
        # palette or colour-key transparency; good enough as a signal
        info["has_alpha"] = trns is not None and (color != 3 or any(b < 255 for b in trns))
        return info
    if color not in (4, 6) or depth not in (8, 16):
        return info
    if interlace:
        info["has_alpha"] = True  # Adam7 not decoded; Codex output is never interlaced
        return info
    channels = 2 if color == 4 else 4
    bpp = channels * depth // 8           # bytes per pixel
    stride = width * bpp
    alpha_off = bpp - depth // 8          # alpha is the last channel
    opaque = 0xFF if depth == 8 else 0xFFFF
    stream = zlib.decompressobj()
    buf = bytearray()
    prev = bytearray(stride)
    chunks = iter(idat)
    for _ in range(height):
        while len(buf) < stride + 1:
            nxt = next(chunks, None)
            if nxt is None:
                buf += stream.flush()
                break
            buf += stream.decompress(nxt)
        if len(buf) < stride + 1:
            raise ValueError("truncated PNG data")
        ftype, row = buf[0], bytearray(buf[1:stride + 1])
        del buf[:stride + 1]
        for i in range(stride):
            a = row[i - bpp] if i >= bpp else 0
            b = prev[i]
            if ftype == 1:
                row[i] = (row[i] + a) & 0xFF
            elif ftype == 2:
                row[i] = (row[i] + b) & 0xFF
            elif ftype == 3:
                row[i] = (row[i] + ((a + b) >> 1)) & 0xFF
            elif ftype == 4:
                c = prev[i - bpp] if i >= bpp else 0
                row[i] = (row[i] + _paeth(a, b, c)) & 0xFF
        for px in range(alpha_off, stride, bpp):
            value = row[px] if depth == 8 else (row[px] << 8) | row[px + 1]
            if value < opaque:
                info["has_alpha"] = True
                return info
        prev = row
    return info


def is_done(out, transparent):
    """A file this batch wrote earlier counts as done only if it would pass today's checks."""
    if not out.exists():
        return False
    try:
        info = png_info(out)
    except (ValueError, OSError):
        return False
    return info["has_alpha"] or not transparent


# --- one image ---------------------------------------------------------------------------

def check_refs(refs):
    if len(refs) > MAX_REFS:
        return f"at most {MAX_REFS} reference images, got {len(refs)}"
    for ref in refs:
        if not ref.is_file():
            return f"reference image not found: {ref}"
        if ref.suffix.lower() not in REF_SUFFIXES:
            return f"reference must be png, jpg or webp: {ref}"
    return None


def _cmd_safe(path, allow_unicode=False):
    s = str(path)
    return (allow_unicode or s.isascii()) and not (CMD_UNSAFE & set(s))


def limit_hit(reply, detail, prompt):
    """Did the turn fail on a usage or rate limit? Errors and stderr are trusted as they are;
    the agent's reply only through the sentinel or a match it did not just quote from the
    description ("I can't draw a speed limit sign" is a refusal, not a limit)."""
    if RATE_SENTINEL in reply or RATE_LIMIT_RE.search(detail):
        return True

    def norm(text):
        return " ".join(re.sub(r"[_\-]+", " ", text.lower()).split())

    reply, prompt = norm(reply), norm(prompt)
    return any(not re.search(r"(?<!\w)" + re.escape(m.group(0)) + r"(?!\w)", prompt)
               for m in REPLY_LIMIT_RE.finditer(reply))


def generate(codex, prompt, out, refs=(), transparent=False, overwrite=False,
             timeout=DEFAULT_TIMEOUT):
    out = pathlib.Path(out)
    refs = [pathlib.Path(r) for r in refs]
    result = {"ok": False, "out": str(out)}
    problem = (check_refs(refs) or (None if prompt and prompt.strip() else "empty prompt")
               or (None if out.suffix.lower() == ".png" else
                   f"out must be a .png file — Codex always makes PNG: {out}"))
    if problem:
        result["error"] = problem
        return result
    # mkdtemp + ignore_errors rather than TemporaryDirectory: on Windows a reference copy can
    # stay locked (a surviving child, an antivirus scan) and the cleanup must not crash the run
    scratch = tempfile.mkdtemp(prefix="codex-img-")
    try:
        if via_cmd(codex) and not all(_cmd_safe(r) for r in refs):
            # cmd.exe would interpret & % ^ … in a reference path; pass safe copies instead
            if not _cmd_safe(scratch, allow_unicode=True):
                result["error"] = (f"reference paths contain characters cmd.exe cannot pass "
                                   f"and the temp folder {scratch} does too; move the "
                                   f"references to a plain ASCII path")
                return result
            refs_arg = []
            for n, ref in enumerate(refs):
                copy = pathlib.Path(scratch) / f"ref{n}{ref.suffix.lower()}"
                shutil.copy2(ref, copy)
                refs_arg.append(copy)
        else:
            refs_arg = refs
        started = time.monotonic()
        try:
            code, stdout, stderr, timed_out = run_process(
                build_command(codex, refs_arg),
                wrap_prompt(prompt, transparent, refs).encode("utf-8"), timeout)
        except OSError as exc:
            result["error"] = "codex_failed"
            result["detail"] = f"cannot run codex: {exc}"
            return result
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    result["secs"] = round(time.monotonic() - started, 1)
    events = parse_events(stdout)
    result["thread_id"] = events["thread_id"]
    if events["usage"]:
        result["tokens"] = events["usage"]
    source, missing = (find_result(codex_home(), events["thread_id"])
                       if events["thread_id"] else (None, "no thread.started event"))
    if source is not None and timed_out:
        try:
            png_info(source)
        except (ValueError, OSError):  # killed while the image was still being written
            source, missing = None, f"unfinished image {source.name}"
    if source is None:
        reply = events["last_message"] or ""
        detail = " | ".join(events["errors"] + [stderr.strip()[-500:]]).strip(" |")
        if timed_out:
            result["error"] = f"timeout after {timeout} s"
        elif limit_hit(reply, detail, prompt):
            result["error"] = "rate_limited"
        elif not events["thread_id"] and code:
            result["error"] = "codex_failed"  # did not even start a turn: flags, auth, crash
        else:
            result["error"] = "no_image"
        result["detail"] = missing + (f"; codex: {detail}" if detail else "")
        if reply:
            result["codex_said"] = reply[:500]
        if code:
            result["exit_code"] = code
        return result
    if timed_out:
        result["note"] = f"codex was stopped after {timeout} s, but the image had been saved"
    target = None
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        target = out if overwrite else claim_path(out)
        shutil.copy2(source, target)
    except BaseException as exc:  # incl. Ctrl+C/SIGTERM: no empty or half-copied file left
        if target is not None and not overwrite:
            try:
                target.unlink()  # the placeholder claim_path made
            except OSError:
                pass
        if not isinstance(exc, OSError):
            raise
        result.update(error=f"cannot save: {exc}", source=str(source))
        return result
    result.update(out=str(target), source=str(source))
    try:
        info = png_info(target)
    except (ValueError, OSError) as exc:
        result["error"] = f"bad png: {exc}"
        return result
    result["size"] = f"{info['width']}x{info['height']}"
    result["has_alpha"] = info["has_alpha"]
    if transparent and not info["has_alpha"]:
        result["error"] = "no_alpha"  # the file is kept so it can be looked at
        return result
    result["ok"] = True
    return result


# --- batch -------------------------------------------------------------------------------

def _as_list(value, where):
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise ManifestError(f'{where}: "ref" must be a path or a list of paths')


def load_manifest(path):
    path = pathlib.Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ManifestError(f"cannot read manifest {path}: {exc}")
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list) or not items:
        raise ManifestError('manifest needs a non-empty "items" list')
    defaults = data.get("defaults") or {}
    if not isinstance(defaults, dict):
        raise ManifestError('"defaults" must be an object')
    base = path.resolve().parent

    def resolve(p):
        p = pathlib.Path(p)
        return p if p.is_absolute() else base / p

    def text(value):
        return isinstance(value, str) and bool(value.strip())

    jobs, seen = [], {}
    for n, item in enumerate(items):
        if not isinstance(item, dict) or not text(item.get("out")) or not text(item.get("prompt")):
            raise ManifestError(f'item {n} needs "out" and "prompt" as non-empty strings')
        refs = _as_list(defaults.get("ref"), "defaults") + _as_list(item.get("ref"), f"item {n}")
        flags = {}
        for key in ("transparent", "overwrite"):
            value = item.get(key, defaults.get(key, False))
            if not isinstance(value, bool):  # "false" as a string would mean true
                raise ManifestError(f'item {n}: "{key}" must be true or false, got {value!r}')
            flags[key] = value
        out = resolve(item["out"])
        if out.suffix.lower() != ".png":  # caught here, before any image is spent
            raise ManifestError(f'item {n}: "out" must be a .png file, got {item["out"]}')
        key = _path_key(out)
        if key in seen:
            raise ManifestError(f'items {seen[key]} and {n} have the same "out": {item["out"]}')
        seen[key] = n
        jobs.append({"out": out, "prompt": item["prompt"],
                     "refs": [resolve(r) for r in refs], **flags})
    return jobs


def _path_key(path, base=None):
    """Comparable form of a path: relative to base when given, case-folded where the file
    system usually ignores case (macOS, Windows)."""
    path = os.path.abspath(path)
    if base is not None:
        try:
            path = os.path.relpath(path, base)
        except ValueError:  # another drive on Windows
            pass
    path = os.path.normcase(os.path.normpath(path))
    return path.lower() if sys.platform in ("darwin", "win32") else path


def state_path(manifest):
    manifest = pathlib.Path(manifest).resolve()
    return manifest.with_name(manifest.stem + ".codex-img-state.json")


def _load_state(path):
    """{item key: written file relative to the state's folder}; ManifestError if unreadable —
    without it every item would be generated again, silently, as name.vN.png."""
    path = pathlib.Path(path)
    if not path.exists():
        return {}
    try:
        files = json.loads(path.read_text(encoding="utf-8")).get("files")
        if not isinstance(files, dict):
            raise ValueError('no "files" object')
    except (OSError, ValueError, AttributeError) as exc:
        raise ManifestError(f"cannot read {path} ({exc}); fix or delete it — without it "
                            f"--resume generates every item again as name.vN.png")
    return files


def _save_state(path, files):
    """Atomic: a crash or a full disk mid-write leaves the previous state, not an empty file."""
    path = pathlib.Path(path)
    tmp = path.with_name(path.name + ".tmp")
    try:
        tmp.write_text(json.dumps({"files": files}, ensure_ascii=False, indent=1),
                       encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def _same_drive(path, base):
    return os.path.splitdrive(os.path.abspath(path))[0].lower() == \
        os.path.splitdrive(os.path.abspath(base))[0].lower()


def run_batch(codex, jobs, resume=False, timeout=DEFAULT_TIMEOUT, report=None, state=None):
    """state: the file recording where each item was written. Resume trusts only that record —
    a file that merely sits at "out" may be the user's own and is never skipped or replaced."""
    results, stopped = [], None
    # keys and files are relative to the manifest's folder, so a moved or renamed project, or
    # the manifest path typed in another case, still finds its records
    base = pathlib.Path(state).parent if state else pathlib.Path.cwd()
    files = _load_state(state) if (state and resume) else {}
    state_ok, failed_turns = True, 0
    for n, job in enumerate(jobs):
        key = _path_key(job["out"], base)
        written = base / files[key] if resume and key in files else None
        if written is not None and not written.exists():
            written = None
        if written is not None and is_done(written, job["transparent"]):
            res = {"ok": True, "out": str(written), "skipped": "done earlier"}
        else:
            # a file this batch wrote that failed its checks is redone in place, not versioned
            target, overwrite = ((written, True) if written is not None
                                 else (job["out"], job["overwrite"]))
            try:
                res = generate(codex, job["prompt"], target, job["refs"],
                               job["transparent"], overwrite, timeout)
            except Exception as exc:  # one broken item must not lose the batch's results
                res = {"ok": False, "out": str(target), "error": f"internal: {exc!r}"}
            if "source" in res and not str(res.get("error", "")).startswith("cannot save"):
                files[key] = os.path.relpath(res["out"], base) if _same_drive(res["out"], base) \
                    else res["out"]
                if state:
                    state_ok = _save_state(state, files) and state_ok
        results.append(res)
        if report:
            report(f"[{n + 1}/{len(jobs)}] {'ok' if res['ok'] else res.get('error')} {res['out']}")
        if res.get("error") in STOP_ERRORS:
            stopped = res["error"]
            break
        failed_turns = failed_turns + 1 if res.get("error") == "no_image" and res.get("exit_code") \
            else 0
        if failed_turns >= MAX_FAILED_TURNS:
            stopped = "codex_failing"
            break
    out = {"results": results}
    if not state_ok:
        out["warning"] = f"could not write {state}; --resume will not know these files"
    if stopped:
        out["stopped_reason"] = stopped
        out["hint"] = {
            "rate_limited": "image limit reached; rerun later with --resume to continue",
            "codex_failed": "codex did not start; see the last result's detail",
            "codex_failing": (f"codex failed {MAX_FAILED_TURNS} turns in a row (exit code set); "
                              "see the details, fix it, then rerun with --resume"),
        }[stopped]
    return out


# --- cli ---------------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="generate one image")
    g.add_argument("--prompt", required=True)
    g.add_argument("--out", required=True)
    g.add_argument("--ref", action="append", default=[], help="reference image (repeatable)")
    g.add_argument("--transparent", action="store_true")
    g.add_argument("--overwrite", action="store_true")
    g.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT)
    b = sub.add_parser("batch", help="generate every item of a JSON manifest")
    b.add_argument("manifest")
    b.add_argument("--resume", action="store_true",
                   help="skip items this manifest already wrote (recorded in "
                        "<manifest>.codex-img-state.json) that still pass the checks")
    b.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="per image")
    args = parser.parse_args(argv)

    def emit(obj):
        sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")

    try:
        jobs = load_manifest(args.manifest) if args.cmd == "batch" else None
        if jobs and args.resume:
            _load_state(state_path(args.manifest))  # an unreadable state stops before codex runs
        codex = find_codex()
        check_version(codex)
        if args.cmd == "gen":
            res = generate(codex, args.prompt, args.out, args.ref, args.transparent,
                           args.overwrite, args.timeout)
            emit(res)
            return 0 if res["ok"] else 1
        res = run_batch(codex, jobs, args.resume, args.timeout,
                        report=lambda line: print(line, file=sys.stderr, flush=True),
                        state=state_path(args.manifest))
        emit(res)
        return 0 if all(r["ok"] for r in res["results"]) and "stopped_reason" not in res else 1
    except ManifestError as exc:
        emit({"ok": False, "error": "bad_manifest", "detail": str(exc)})
        return 2
    except SetupError as exc:
        emit({"ok": False, "error": "setup", "detail": str(exc)})
        return 2
    except Exception as exc:  # the caller reads JSON; a traceback alone would be lost on it
        emit({"ok": False, "error": f"internal: {exc!r}"})
        return 1


def _exit_on_signal(signum, frame):
    raise SystemExit(128 + signum)  # unwinds through run_process, which kills codex


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows consoles default to a code page
        sys.stderr.reconfigure(encoding="utf-8")
    for name in ("SIGTERM", "SIGHUP"):
        if hasattr(signal, name):
            try:
                signal.signal(getattr(signal, name), _exit_on_signal)
            except (OSError, ValueError):
                pass
    sys.exit(main())
