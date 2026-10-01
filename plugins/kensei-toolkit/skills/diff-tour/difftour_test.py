#!/usr/bin/env python3
"""Tests for difftour.py — run: python3 difftour_test.py"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SCRIPT = os.path.join(HERE, "difftour.py")
sys.path.insert(0, HERE)
import difftour  # noqa: E402

OUT = tempfile.mkdtemp()  # run directories go here, not to ~/.cache


# --- builders ----------------------------------------------------------------------------

def git(repo, *args):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t",
                    "-c", "commit.gpgsign=false", *args], cwd=repo, check=True,
                   capture_output=True)


def write(repo, path, data):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "wb") as fh:
        fh.write(data if isinstance(data, bytes) else data.encode())


def repo(files=None):
    path = tempfile.mkdtemp()
    git(path, "init", "-q", "-b", "main")
    for name, data in (files or {}).items():
        write(path, name, data)
    if files:
        git(path, "add", "-A")
        git(path, "commit", "-qm", "init")
    return path


def run(cwd, *args):
    proc = subprocess.run([sys.executable, SCRIPT, *args], cwd=cwd, capture_output=True,
                          text=True)
    return proc.returncode, proc.stdout, proc.stderr


def collect(cwd, *args):
    code, out, err = run(cwd, "collect", *args, "--out-root", OUT)
    assert code == 0, err
    assert out.startswith("Run directory: "), out
    return out.splitlines()[0].split(": ", 1)[1], out


def index(run_dir):
    with open(os.path.join(run_dir, "hunks.json"), encoding="utf-8") as fh:
        return json.load(fh)["units"]


def by_path(run_dir):
    return {u["path"]: u for u in index(run_dir)}


def build(run_dir, notes):
    with open(os.path.join(run_dir, "notes.json"), "w", encoding="utf-8") as fh:
        json.dump(notes, fh, ensure_ascii=False)
    return run(run_dir, "build", run_dir)


def page(run_dir):
    with open(os.path.join(run_dir, "index.html"), encoding="utf-8") as fh:
        return fh.read()


def every_kind(hostile):
    """A repository whose working tree holds one change of every kind the parser knows."""
    path = repo({
        "mod.txt": "a\nb\nc\n\nd\n", "del.txt": "x\n", "old name.txt": "same\nline2\nline3\n",
        "bin.dat": b"\x00\x01\x02", "s.sh": "#!/bin/sh\necho hi\n", "nonl.txt": "no newline",
        "package-lock.json": "{}\n", ".gitignore": "ignored.log\n", "sub/keep.txt": "k\n",
    })
    write(path, "mod.txt", "a\nB\nc\n\nd\n")
    os.remove(os.path.join(path, "del.txt"))
    git(path, "mv", "old name.txt", "новое имя.txt")
    write(path, "bin.dat", b"\x00\x09\x02")
    os.chmod(os.path.join(path, "s.sh"), 0o755)
    write(path, "nonl.txt", "no newline changed")
    write(path, "package-lock.json", '{"a": 1}\n')
    write(path, "staged.txt", "staged\n")
    git(path, "add", "staged.txt")
    write(path, "untracked dir/u.cs", "class U {}\n")
    write(path, "newbin.bin", b"\x00bin")
    write(path, "ignored.log", "x\n")
    if hostile:
        for key, value in (("diff.noprefix", "true"), ("diff.mnemonicPrefix", "true"),
                           ("color.ui", "always"), ("color.diff", "always"),
                           ("diff.suppressBlankEmpty", "true"), ("diff.external", "false"),
                           ("diff.relative", "true"), ("core.quotepath", "true")):
            git(path, "config", key, value)
    return path


# --- collect -----------------------------------------------------------------------------

class Collect(unittest.TestCase):

    def test_every_kind_of_change(self):
        for hostile in (False, True):
            with self.subTest(hostile=hostile):
                path = every_kind(hostile)
                cwd = os.path.join(path, "sub") if hostile else path  # diff.relative + subdir
                run_dir, out = collect(cwd)
                units = by_path(run_dir)
                self.assertEqual(units["mod.txt"]["status"], "M")
                self.assertEqual((units["mod.txt"]["added"], units["mod.txt"]["removed"]),
                                 (1, 1))
                self.assertEqual(units["del.txt"]["status"], "D")
                self.assertEqual(units["новое имя.txt"]["status"], "R")
                self.assertIn("renamed from old name.txt", units["новое имя.txt"]["facts"])
                self.assertIn("binary", units["bin.dat"]["facts"])
                self.assertIn("mode 100644 -> 100755", units["s.sh"]["facts"])
                self.assertEqual(units["staged.txt"]["status"], "A")
                self.assertEqual(units["untracked dir/u.cs"]["status"], "A")
                self.assertIn("binary", units["newbin.bin"]["facts"])
                self.assertTrue(units["package-lock.json"]["id"].startswith("n"))
                self.assertIn("noise", units["package-lock.json"]["facts"])
                self.assertNotIn("ignored.log", units)
                self.assertEqual(len(units), 10)
                meta, files, _ = difftour.load_snapshot(run_dir)
                nonl = next(f for f in files if f["new"] == "nonl.txt")
                self.assertIn(["\\", "No newline at end of file"], nonl["hunks"][0]["lines"])
                self.assertEqual(meta["root"], os.path.realpath(path))

    def test_index_does_not_change(self):
        path = every_kind(False)
        before = subprocess.run(["git", "diff", "--cached", "--name-status"], cwd=path,
                                capture_output=True, text=True).stdout
        collect(path)
        after = subprocess.run(["git", "diff", "--cached", "--name-status"], cwd=path,
                               capture_output=True, text=True).stdout
        self.assertEqual(before, after)

    def test_quoted_paths(self):
        path = repo({'q"uote.txt': "1\n"})
        write(path, 'q"uote.txt', "2\n")
        write(path, "tab\tname.txt", "t\n")
        run_dir, _ = collect(path)
        self.assertEqual(set(by_path(run_dir)), {'q"uote.txt', "tab\tname.txt"})

    def test_no_changes(self):
        path = repo({"a.txt": "a\n"})
        code, out, _ = run(path, "collect", "--out-root", OUT)
        self.assertEqual((code, out.strip()), (0, "No changes."))
        self.assertFalse(os.path.exists(os.path.join(OUT, os.path.basename(path))))

    def test_not_a_repository(self):
        code, _, err = run(tempfile.mkdtemp(), "collect", "--out-root", OUT)
        self.assertEqual(code, 2)
        self.assertIn("not inside a git working tree", err)

    def test_unknown_ref(self):
        code, _, err = run(repo({"a.txt": "a\n"}), "collect", "nope", "--out-root", OUT)
        self.assertEqual(code, 2)
        self.assertIn("not a commit: nope", err)

    def test_repository_without_commits(self):
        path = repo()
        write(path, "a.txt", "a\n")
        write(path, "b.txt", "b\n")
        git(path, "add", "b.txt")
        run_dir, out = collect(path)
        self.assertIn("Base: empty tree", out)
        self.assertEqual(set(by_path(run_dir)), {"a.txt", "b.txt"})

    def test_range_leaves_out_the_working_tree(self):
        path = repo({"a.txt": "1\n"})
        write(path, "a.txt", "2\n")
        git(path, "commit", "-qam", "two")
        write(path, "a.txt", "3\n")
        write(path, "u.txt", "u\n")
        run_dir, _ = collect(path, "HEAD~1..HEAD")
        units = index(run_dir)
        self.assertEqual([u["path"] for u in units], ["a.txt"])
        _, files, _ = difftour.load_snapshot(run_dir)
        self.assertIn(["+", "2"], files[0]["hunks"][0]["lines"])

    def test_project_noise_patterns(self):
        path = repo({".claude/diff-tour-noise": "# generated\ngenerated/\n*.g.cs\n"})
        for name in ("generated/x.cs", "src/a.g.cs", "src/c.cs"):
            write(path, name, "x\n")
        run_dir, _ = collect(path)
        units = by_path(run_dir)
        self.assertIn("noise", units["generated/x.cs"]["facts"])
        self.assertIn("noise", units["src/a.g.cs"]["facts"])
        self.assertNotIn("noise", units["src/c.cs"]["facts"])

    def test_nested_repository_is_reported_not_diffed(self):
        path = repo({"a.txt": "a\n"})
        nested = os.path.join(path, "nested")
        os.makedirs(nested)
        git(nested, "init", "-q")
        write(path, "nested/x.txt", "x\n")
        write(path, "a.txt", "b\n")
        run_dir, out = collect(path)
        self.assertIn("Skipped untracked nested repository: nested/", out)
        self.assertEqual(list(by_path(run_dir)), ["a.txt"])


class CollectRegressions(unittest.TestCase):

    def test_index_file_is_not_rewritten(self):
        path = repo({"a.txt": "a\n", "b.txt": "b\n"})
        write(path, "a.txt", "A\n")
        write(path, "new.txt", "n\n")                       # takes the throwaway-index path
        later = os.path.getmtime(os.path.join(path, "b.txt")) + 5
        os.utime(os.path.join(path, "b.txt"), (later, later))  # stat-dirty, same content
        index_file = os.path.join(path, ".git", "index")
        with open(index_file, "rb") as fh:
            before = fh.read()
        run_dir, _ = collect(path)
        code, _, err = build(run_dir, {"title": "t", "lede": "l", "notes": []})
        self.assertEqual(code, 0, err)
        with open(index_file, "rb") as fh:
            self.assertEqual(fh.read(), before)

    def test_same_second_same_size_edit_is_not_lost(self):
        # Racy git: the index and the edited file share one mtime, and the edit keeps the size,
        # so only the index's own mtime tells git to look at the content. A copy of the index
        # with a fresh mtime made git trust the stale stat and drop a.txt from the diff.
        path = repo()
        git(path, "config", "core.trustctime", "false")
        a, then = os.path.join(path, "a.txt"), 1_700_000_000
        write(path, "a.txt", "1\n")
        os.utime(a, (then, then))
        git(path, "add", "a.txt")
        git(path, "commit", "-qm", "init")
        write(path, "a.txt", "2\n")
        os.utime(a, (then, then))
        os.utime(os.path.join(path, ".git", "index"), (then, then))
        write(path, "u.txt", "u\n")                         # takes the throwaway-index path
        run_dir, _ = collect(path)
        self.assertEqual(set(by_path(run_dir)), {"a.txt", "u.txt"})
        code, out, _ = build(run_dir, notes_with())         # check_drift takes the same path
        self.assertEqual(code, 0)
        self.assertNotIn("WARNING", out)

    def test_submodule_change_survives_diff_submodule_log(self):
        src = repo({"a.txt": "a\n"})
        path = repo({"x.txt": "x\n"})
        git(path, "-c", "protocol.file.allow=always", "submodule", "add", "-q", src, "sub")
        git(path, "commit", "-qm", "sub")
        write(os.path.join(path, "sub"), "a.txt", "b\n")
        git(os.path.join(path, "sub"), "commit", "-qam", "bump")
        git(path, "config", "diff.submodule", "log")
        run_dir, _ = collect(path)                            # a submodule-only change
        self.assertEqual(list(by_path(run_dir)), ["sub"])
        git(path, "config", "diff.submodule", "diff")
        write(path, "x.txt", "y\n")
        run_dir, _ = collect(path)
        self.assertEqual(set(by_path(run_dir)), {"sub", "x.txt"})

    def test_untracked_symlink_is_a_link(self):
        outside = tempfile.mkdtemp()
        write(outside, "null", "outside secret\n")
        path = repo({"a.txt": "a\n"})
        os.symlink(outside, os.path.join(path, "linkdir"))
        run_dir, _ = collect(path)
        self.assertEqual(list(by_path(run_dir)), ["linkdir"])
        _, files, _ = difftour.load_snapshot(run_dir)
        self.assertEqual(files[0]["new_mode"], "120000")
        self.assertIn(["+", outside], files[0]["hunks"][0]["lines"])
        with open(os.path.join(run_dir, "patch.diff"), encoding="utf-8") as fh:
            self.assertNotIn("outside secret", fh.read())

    def test_commit_after_collect_is_drift(self):
        path = three_changes()
        run_dir, _ = collect(path)
        git(path, "commit", "-qam", "all of it")
        _, out, _ = build(run_dir, NOTES)
        self.assertIn("WARNING: the working tree or HEAD changed", out)

    def test_sha256_repository_without_commits(self):
        path = tempfile.mkdtemp()
        git(path, "init", "-q", "--object-format=sha256", "-b", "main")
        write(path, "a.txt", "a\n")
        run_dir, out = collect(path)
        self.assertIn("Base: empty tree", out)
        self.assertEqual(list(by_path(run_dir)), ["a.txt"])

    def test_ref_is_compared_from_the_merge_base(self):
        path = repo({"a.txt": "a\n"})
        git(path, "checkout", "-q", "-b", "feature")
        write(path, "f.txt", "f\n")
        git(path, "add", "f.txt")
        git(path, "commit", "-qm", "feature work")
        git(path, "checkout", "-q", "main")
        write(path, "m.txt", "m\n")
        git(path, "add", "m.txt")
        git(path, "commit", "-qm", "main moved on")
        git(path, "checkout", "-q", "feature")
        write(path, "f.txt", "f\nwip\n")
        run_dir, out = collect(path, "main")
        self.assertIn("Base: merge-base of main and HEAD", out)
        self.assertEqual(list(by_path(run_dir)), ["f.txt"])  # not m.txt reversed
        build(run_dir, notes_with())
        self.assertIn("branch since the base + uncommitted", page(run_dir))

    def test_tree_range_for_a_caller(self):
        # What ticket's publish gate passes: the base commit .. the reviewed tree id.
        path = repo({"a.txt": "1\n"})
        base = subprocess.run(["git", "rev-parse", "HEAD"], cwd=path, capture_output=True,
                              text=True).stdout.strip()
        write(path, "a.txt", "2\n")
        write(path, "n.txt", "n\n")
        git(path, "add", "-A")
        tree = subprocess.run(["git", "write-tree"], cwd=path, capture_output=True,
                              text=True).stdout.strip()
        write(path, "a.txt", "3\n")                         # later edits stay out of it
        run_dir, out = collect(path, f"{base}..{tree}")
        self.assertIn(f"Base: {base}..{tree}", out)
        self.assertEqual(set(by_path(run_dir)), {"a.txt", "n.txt"})
        _, files, _ = difftour.load_snapshot(run_dir)
        self.assertIn(["+", "2"], files[0]["hunks"][0]["lines"])
        code, out, err = build(run_dir, notes_with())
        self.assertEqual(code, 0, err)
        self.assertNotIn("WARNING", out)

    def test_head_base_is_uncommitted(self):
        run_dir, _ = collect(three_changes())
        build(run_dir, notes_with())
        self.assertIn("· uncommitted</span>", page(run_dir))


def feature_branch():
    """main with one commit, feature with two commits on top of it, nothing uncommitted."""
    path = repo({"a.txt": "a\n"})
    git(path, "checkout", "-q", "-b", "feature")
    for name in ("f1.txt", "f2.txt"):
        write(path, name, name + "\n")
        git(path, "add", name)
        git(path, "commit", "-qm", name)
    return path


class AfterCommit(unittest.TestCase):

    def test_falls_back_to_the_default_branch(self):
        run_dir, out = collect(feature_branch())
        self.assertIn("Base: main (", out)
        self.assertIn("Nothing uncommitted — showing the commits HEAD has beyond main", out)
        self.assertEqual(set(by_path(run_dir)), {"f1.txt", "f2.txt"})
        code, out, err = build(run_dir, notes_with())
        self.assertEqual(code, 0, err)
        self.assertNotIn("WARNING", out)

    def test_upstream_comes_first(self):
        path = feature_branch()
        git(path, "branch", "pushed", "HEAD~1")
        git(path, "branch", "-u", "pushed")
        run_dir, out = collect(path)
        self.assertIn("beyond pushed", out)
        self.assertEqual(list(by_path(run_dir)), ["f2.txt"])

    def test_up_to_date_upstream_falls_through(self):
        path = feature_branch()
        git(path, "branch", "pushed", "HEAD")
        git(path, "branch", "-u", "pushed")
        run_dir, out = collect(path)
        self.assertIn("beyond main", out)
        self.assertEqual(set(by_path(run_dir)), {"f1.txt", "f2.txt"})

    def test_uncommitted_work_wins(self):
        path = feature_branch()
        write(path, "a.txt", "b\n")
        run_dir, out = collect(path)
        self.assertNotIn("Nothing uncommitted", out)
        self.assertEqual(list(by_path(run_dir)), ["a.txt"])

    def test_explicit_ref_never_falls_back(self):
        path = feature_branch()
        code, out, _ = run(path, "collect", "HEAD", "--out-root", OUT)
        self.assertEqual((code, out.strip()), (0, "No changes."))


class RunDirectories(unittest.TestCase):

    def test_private_and_rotated(self):
        root = os.path.join(tempfile.mkdtemp(), "cache")
        path = repo({"a.txt": "a\n"})
        write(path, "a.txt", "b\n")
        repo_dir = os.path.join(root, os.path.basename(path))
        os.makedirs(repo_dir)
        for k in range(difftour.KEEP_RUNS + 3):              # older runs, oldest first
            old = os.path.join(repo_dir, f"20200101-0000{k:02d}")
            os.makedirs(old)
            with open(os.path.join(old, "hunks.json"), "w") as fh:
                fh.write("{}")
        os.makedirs(os.path.join(repo_dir, "keep-me"))       # not a run directory
        code, out, err = run(path, "collect", "--out-root", root)
        self.assertEqual(code, 0, err)
        run_dir = out.splitlines()[0].split(": ", 1)[1]
        self.assertEqual(os.stat(run_dir).st_mode & 0o777, 0o700)
        left = sorted(os.listdir(repo_dir))
        self.assertIn("keep-me", left)
        self.assertIn(os.path.basename(run_dir), left)
        runs = [d for d in left if d != "keep-me"]
        self.assertEqual(len(runs), difftour.KEEP_RUNS)
        self.assertNotIn("20200101-000000", runs)            # the oldest went first
        self.assertIn(f"20200101-0000{difftour.KEEP_RUNS + 2:02d}", runs)

    def test_new_directories_are_private(self):
        root = os.path.join(tempfile.mkdtemp(), "a", "cache")
        run_dir = difftour.new_run_dir(root, "repo")
        for d in (root, os.path.dirname(run_dir), run_dir):
            self.assertEqual(os.stat(d).st_mode & 0o777, 0o700, d)


class Noise(unittest.TestCase):

    def test_patterns(self):
        cases = [
            ("a/package-lock.json", ["package-lock.json"], True),
            ("gen_out/a.cs", ["gen*/"], True), ("x/gen_out/a.cs", ["gen*/"], True),
            ("gen_out.cs", ["gen*/"], False),
            ("Assets/Generated/a.cs", ["Assets/Gen*/"], True),
            ("Other/Assets/Generated/a.cs", ["Assets/Gen*/"], False),
            ("src/obj/a.cs", ["**/obj/"], True), ("src/obj/a.cs", ["/obj/"], False),
            ("obj/a.cs", ["/obj/"], True), ("a.g.cs", ["**/*.g.cs"], True),
            ("src/a.g.cs", ["src/*.g.cs"], True), ("lib/src/a.g.cs", ["src/*.g.cs"], False),
            ("x/gen/a.cs", ["**/gen/*.cs"], True), ("src/c.cs", ["generated/", "*.g.cs"], False),
        ]
        for path, patterns, expected in cases:
            with self.subTest(path=path, patterns=patterns):
                self.assertEqual(difftour.is_noise(path, patterns), expected)


# --- parser ------------------------------------------------------------------------------

class Parse(unittest.TestCase):

    def test_read_quoted(self):
        self.assertEqual(difftour.read_quoted('"a/\\321\\217 \\"x\\"\\t.txt" rest'),
                         ('a/я "x"\t.txt', " rest"))

    def test_git_line_with_b_slash_in_the_name(self):
        self.assertEqual(difftour.split_git_line("a/x b/y b/x b/y"), ("x b/y", "x b/y"))

    def test_removed_line_that_looks_like_a_header(self):
        text = ("diff --git a/f b/f\nindex 1..2 100644\n--- a/f\n+++ b/f\n"
                "@@ -1,2 +1 @@\n--- a/x\n keep\n")
        files = difftour.parse(text)
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["hunks"][0]["lines"], [["-", "-- a/x"], [" ", "keep"]])


# --- notes.json --------------------------------------------------------------------------

SAMPLE = (
    "diff --git a/a.cs b/a.cs\nindex 1..2 100644\n--- a/a.cs\n+++ b/a.cs\n"
    "@@ -1,3 +1,3 @@\n keep\n-return old;\n+return fresh;\n tail\n"
    "@@ -10,2 +10,3 @@\n x = 1;\n-y = 2;\n+y = 3;\n+y = 4;\n"
    "diff --git a/b.bin b/b.bin\nindex 1..2 100644\nBinary files a/b.bin and b/b.bin differ\n"
    "diff --git a/package-lock.json b/package-lock.json\nindex 1..2 100644\n"
    "--- a/package-lock.json\n+++ b/package-lock.json\n@@ -1 +1 @@\n-{}\n+{\"a\": 1}\n"
)
FILES = difftour.parse(SAMPLE)
UNITS = difftour.make_units(FILES, difftour.DEFAULT_NOISE)  # h1 h2 (a.cs), h3 (b.bin), n1


def note(**over):
    n = {"unit": "h1", "text": "why", "source": "session"}
    n.update(over)
    return n


def notes_with(**over):
    n = {"title": "t", "lede": "l", "notes": []}
    n.update(over)
    return n


class Validate(unittest.TestCase):

    def problems(self, notes):
        return difftour.validate(notes, FILES, UNITS)

    def test_units(self):
        self.assertEqual([u["id"] for u in UNITS], ["h1", "h2", "h3", "n1"])

    def test_valid(self):
        self.assertEqual(self.problems(notes_with()), [])
        self.assertEqual(self.problems({
            "lang": "ru", "title": "t", "lede": "l",
            "link": {"url": "https://example.com/t/1", "label": "Task 1"},
            "panels": [{"title": "What", "text": "x"},
                       {"title": "Checks", "checks": [{"pill": "3/3", "text": "tests"},
                                                      {"pill": "no", "text": "c", "warn": True}]}],
            "files": [{"path": "a.cs", "role": "game code", "kind": "prod"},
                      {"path": "b.bin"}],
            "notes": [note(after="return fresh;"), note(unit="h2", after="y =", side="old"),
                      note(unit="n1", kind="stray", source="inferred")],
            "unexplained": {"h3": "что"}}), [])

    def test_uncovered_units_are_not_a_problem(self):
        self.assertEqual(self.problems(notes_with(notes=[note()])), [])

    def assertProblem(self, notes, fragment):
        found = self.problems(notes)
        self.assertTrue(any(fragment in p for p in found), f"{fragment!r} not in {found}")

    def test_each_problem(self):
        cases = [
            ({"lede": "l", "notes": []}, "title: required"),
            ({"title": "t", "notes": []}, "lede: required"),
            ({"title": "t", "lede": "l"}, "notes: required"),
            (notes_with(extra=1), "unknown top-level keys: extra"),
            (notes_with(link={"url": "javascript:alert(1)", "label": "x"}), "http(s) only"),
            (notes_with(link={"url": "https://x.y"}), "http(s) only"),
            (notes_with(panels=[{"title": "p", "text": "a", "checks": []}]),
             "exactly one of text, checks"),
            (notes_with(panels=[{"title": "p", "checks": [{"pill": "1", "text": "a",
                                                           "warn": "yes"}]}]),
             "checks[1]"),
            (notes_with(panels=[{"title": "p", "checks": []}]), "checks: a non-empty list"),
            (notes_with(files=[{"path": "nope.cs"}]), "'nope.cs' is not in the diff"),
            (notes_with(files=[{"path": "a.cs"}, {"path": "a.cs"}]), "listed twice"),
            (notes_with(files=[{"path": "a.cs", "kind": "core"}]), "kind: one of"),
            (notes_with(notes=[note(unit="h9")]), "unknown unit id 'h9'"),
            (notes_with(notes=[note(text="")]), "text: required"),
            (notes_with(notes=[note(source="guess")]), "source: one of"),
            (notes_with(notes=[note(kind="maybe")]), "kind: one of"),
            (notes_with(notes=[note(line=3)]), "unknown keys: line"),
            (notes_with(notes=[note(side="new")]), "only together with after"),
            (notes_with(notes=[note(after="absent")]), "no line of h1 contains 'absent'"),
            (notes_with(notes=[note(after="return")]), "2 lines of h1 contain 'return'"),
            (notes_with(notes=[note(unit="h2", after="y =")]), "3 lines of h2 contain"),
            (notes_with(notes=[note(unit="h3", after="x")]), "no line of h3 contains"),
            (notes_with(notes=[note(after="a\nb")]), "piece of one line"),
            (notes_with(notes=[note()], unexplained={"h1": "x"}), "h1 has notes"),
            (notes_with(unexplained={"h9": "x"}), "unexplained: unknown unit id 'h9'"),
            (notes_with(unexplained={"h1": 5}), "a string"),
            (notes_with(files=[{"path": ["a.cs"]}]), "files[1].path: a string"),
        ]
        for notes, fragment in cases:
            with self.subTest(fragment=fragment):
                self.assertProblem(notes, fragment)

    def test_side_hint_only_without_side(self):
        found = self.problems(notes_with(notes=[note(unit="h2", after="y =", side="new")]))
        self.assertEqual(len(found), 1)
        self.assertNotIn("add side", found[0])

    def test_side_disambiguates(self):
        self.assertEqual(self.problems(notes_with(notes=[note(after="return", side="new")])), [])
        self.assertEqual(difftour.anchor_matches(FILES, UNITS[0], "return", "old"), [(0, 1)])


# --- moved blocks ------------------------------------------------------------------------

def one_file(*hunks):
    text = "diff --git a/m.cs b/m.cs\nindex 1..2 100644\n--- a/m.cs\n+++ b/m.cs\n"
    for old_start, lines in hunks:
        olds = sum(1 for ln in lines if ln[0] in " -")
        news = sum(1 for ln in lines if ln[0] in " +")
        text += f"@@ -{old_start},{olds} +{old_start},{news} @@\n" + "".join(ln + "\n" for ln in lines)
    return difftour.parse(text)[0]


class Moved(unittest.TestCase):

    def test_block_moved_between_hunks(self):
        f = one_file((1, [" a", "-first();", "-second();", "-{", "-third();", " b"]),
                     (50, [" c", "+first();", "+second();", "+{", "+third();", " d"]))
        moved = difftour.moved_lines(0, f)
        self.assertEqual(moved, {(0, 0, i) for i in range(1, 5)} | {(0, 1, i) for i in range(1, 5)})

    def test_two_lines_are_a_coincidence(self):
        f = one_file((1, [" a", "-first();", "-second();", " b"]),
                     (50, [" c", "+first();", "+second();", " d"]))
        self.assertEqual(difftour.moved_lines(0, f), set())

    def test_reindented_block_is_not_moved(self):
        f = one_file((1, [" a", "-first();", "-second();", "-third();",
                          "+    first();", "+    second();", "+    third();", " b"]))
        self.assertEqual(difftour.moved_lines(0, f), set())

    def test_brace_style_method_moves_with_its_braces(self):
        body = ["void Fire()", "{", "    Shoot(target);", "    Recoil();", "}"]
        f = one_file((1, [" a"] + ["-" + x for x in body] + [" b"]),
                     (50, [" c"] + ["+" + x for x in body] + [" d"]))
        moved = difftour.moved_lines(0, f)
        self.assertEqual(moved, {(0, h, i) for h in (0, 1) for i in range(1, 6)})

    def test_braces_alone_are_chance(self):
        f = one_file((1, [" a", "-}", "-", "-return x;", " b"]),
                     (50, [" c", "+}", "+", "+return x;", " d"]))
        self.assertEqual(difftour.moved_lines(0, f), set())

    def test_changed_line_breaks_the_block(self):
        f = one_file((1, [" a", "-one();", "-two();", "-three();", " b"]),
                     (50, [" c", "+one();", "+two(changed);", "+three();", " d"]))
        moved = difftour.moved_lines(0, f)
        self.assertNotIn((0, 1, 2), moved)          # the edited line stays an addition
        self.assertEqual({k for k in moved if k[1] == 1}, set())  # 1 + 1 matched: no block


# --- build -------------------------------------------------------------------------------

def three_changes():
    path = repo({"a.cs": "one\n", "b.cs": "two\n", "c.cs": "three\n"})
    write(path, "a.cs", "ONE\n")
    write(path, "b.cs", "TWO\n")
    write(path, "c.cs", "THREE\n")
    return path


NOTES = {"lang": "ru", "title": "Правки", "lede": "Абзац",
         "notes": [{"unit": "h1", "after": "ONE", "text": "**Фикс.** верхний регистр",
                    "source": "session", "kind": "untested"}],
         "unexplained": {"h2": "поменял b"}}


class Build(unittest.TestCase):

    def test_page_and_report(self):
        run_dir, _ = collect(three_changes())
        code, out, err = build(run_dir, NOTES)
        self.assertEqual(code, 0, err)
        self.assertIn("notes: 1 · flags: 1 · inferred: 0 · unexplained: 2 (of 3 units)", out)
        self.assertIn("h2    b.cs  поменял b", out)
        self.assertIn("h3    c.cs  (no description)", out)
        html = page(run_dir)
        self.assertEqual(html.count('<details class="file loose"'), 2)
        self.assertEqual(html.count('<details class="file"'), 1)
        self.assertIn("Самопроверка", html)
        self.assertIn('<table class="diff unified"', html)
        self.assertIn('<table class="diff split"', html)
        self.assertIn("<b>Фикс.</b>", html)
        self.assertNotIn('<div class="banner">', html)
        self.assertIn(f'src="{difftour.HLJS}" integrity="{difftour.HLJS_SRI}" '
                      f'crossorigin="anonymous"', html)

    def test_anchored_note_follows_its_line(self):
        run_dir, _ = collect(three_changes())
        build(run_dir, NOTES)
        unified = page(run_dir).split('<table class="diff unified"')[1].split("</table>")[0]
        self.assertRegex(unified, r'>ONE</span></td></tr><tr class="note-row">.*Фикс')

    def test_files_order_and_roles(self):
        run_dir, _ = collect(three_changes())
        notes = dict(NOTES, files=[{"path": "c.cs", "role": "игровой код", "kind": "prod"}])
        build(run_dir, notes)
        html = page(run_dir)
        cards = html.split("<main>")[1]
        self.assertLess(cards.index("c.cs"), cards.index("a.cs"))
        self.assertIn('<span class="role prod">игровой код</span>', html)

    def test_english_labels_by_default(self):
        run_dir, _ = collect(three_changes())
        notes = dict(NOTES)
        del notes["lang"]
        build(run_dir, notes)
        self.assertIn("Self-check", page(run_dir))

    def test_invalid_notes(self):
        run_dir, _ = collect(three_changes())
        code, out, _ = build(run_dir, dict(NOTES, notes=[{"unit": "h1", "text": "x",
                                                          "source": "maybe"}]))
        self.assertEqual(code, 1)
        self.assertIn("1 problem(s)", out)
        self.assertFalse(os.path.exists(os.path.join(run_dir, "index.html")))

    def test_not_json(self):
        run_dir, _ = collect(three_changes())
        with open(os.path.join(run_dir, "notes.json"), "w") as fh:
            fh.write("{oops")
        code, out, _ = run(run_dir, "build", run_dir)
        self.assertEqual(code, 1)
        self.assertIn("not valid JSON", out)

    def test_missing_notes(self):
        run_dir, _ = collect(three_changes())
        code, _, err = run(run_dir, "build", run_dir)
        self.assertEqual(code, 2)
        self.assertIn("no notes.json", err)

    def test_everything_is_escaped(self):
        path = repo({"x.html": "a\n"})
        write(path, "x.html", "<script>alert(1)</script>\n")
        run_dir, _ = collect(path)
        code, _, err = build(run_dir, {
            "title": "<b>t</b>", "lede": "<i>l</i>",
            "link": {"url": "https://x.y/?a=\"><b>", "label": "<u>x</u>"},
            "panels": [{"title": "<em>p</em>", "checks": [{"pill": "<s>1</s>",
                                                          "text": "<img src=y>"}]}],
            "notes": [note(after="alert", text="<img src=x onerror=alert(2)> `<br>`")]})
        self.assertEqual(code, 0, err)
        html = page(run_dir)
        for raw in ("<script>alert(1)", "<img src=x", "<img src=y", "<b>t</b>", "<i>l</i>",
                    "<u>x</u>", "<em>p</em>", "<s>1</s>", '"><b>'):
            self.assertNotIn(raw, html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertIn("<code>&lt;br&gt;</code>", html)

    def test_drift_is_reported(self):
        path = three_changes()
        run_dir, _ = collect(path)
        write(path, "a.cs", "changed again\n")
        code, out, _ = build(run_dir, NOTES)
        self.assertEqual(code, 0)
        self.assertIn("WARNING: the working tree or HEAD changed after collect", out)
        self.assertIn('<div class="banner">', page(run_dir))

    def test_tampered_snapshot(self):
        run_dir, _ = collect(three_changes())
        with open(os.path.join(run_dir, "patch.diff"), "ab") as fh:
            fh.write(b"+sneaky\n")
        code, _, err = build(run_dir, NOTES)
        self.assertEqual(code, 2)
        self.assertIn("modified after collect", err)

    def test_folding(self):
        path = repo({"small.txt": "s\n", "package-lock.json": "{}\n"})
        big = "".join(f"line {i}\n" for i in range(1600))
        write(path, "big.txt", big)
        write(path, "noted.txt", big)
        write(path, "small.txt", "S\n")
        write(path, "package-lock.json", '{"a": 1}\n')
        run_dir, _ = collect(path)
        ids = {p: u["id"] for p, u in by_path(run_dir).items()}
        build(run_dir, notes_with(notes=[note(unit=ids["noted.txt"], after="line 1500")]))
        html = page(run_dir)
        heads = {p: html.split(f">{p}</span>")[0].rsplit("<details", 1)[1]
                 for p in ("big.txt", "noted.txt", "small.txt", "package-lock.json")}
        self.assertNotIn(" open>", heads["big.txt"])            # big, nothing to read in it
        self.assertIn(" open>", heads["noted.txt"])             # big, but it carries a note
        self.assertNotIn(" open>", heads["package-lock.json"])  # noise
        self.assertIn(" open>", heads["small.txt"])

    def test_new_file_has_one_side(self):
        path = repo({"old.cs": "a\n"})
        write(path, "old.cs", "b\n")
        write(path, "new.cs", "c\n")
        run_dir, _ = collect(path)
        build(run_dir, notes_with())
        html = page(run_dir)
        card = html.split(">new.cs</span>")[1].split("</details>")[0]
        self.assertIn('<table class="diff unified solo"', card)
        self.assertNotIn('<table class="diff split"', card)
        self.assertIn('class="seg"', html)

    def test_no_view_switch_without_two_sided_files(self):
        path = repo({"keep.txt": "k\n"})
        write(path, "new.cs", "c\n")
        run_dir, _ = collect(path)
        build(run_dir, notes_with())
        html = page(run_dir)
        self.assertNotIn('class="seg"', html)
        self.assertNotIn('<table class="diff split"', html)

    def test_moved_block_is_marked(self):
        body = [f"line number {i}\n" for i in range(12)]
        path = repo({"m.cs": "".join(body)})
        write(path, "m.cs", "".join(body[:2] + body[6:] + body[2:6]))
        run_dir, _ = collect(path)
        build(run_dir, notes_with())
        html = page(run_dir)
        self.assertIn('<tr class="moved">', html)
        self.assertIn("c-moved", html)

    def test_huge_diff_renders_unified_only(self):
        run_dir, _ = collect(three_changes())
        meta, files, units = difftour.load_snapshot(run_dir)
        saved = difftour.SPLIT_MAX
        difftour.SPLIT_MAX = 0
        try:
            html, _ = difftour.render(meta, files, units, NOTES, None, run_dir)
        finally:
            difftour.SPLIT_MAX = saved
        self.assertNotIn('<table class="diff split"', html)
        self.assertNotIn('class="seg"', html)

    def test_side_new_anchors_the_duplicate_not_the_original(self):
        path = repo({"d.c": "a();\nfoo();\nb();\n"})
        write(path, "d.c", "a();\nfoo();\nfoo();\nb();\n")
        run_dir, _ = collect(path)
        code, out, err = build(run_dir, notes_with(notes=[
            note(after="foo();", side="new", kind="stray", text="STRAY")]))
        self.assertEqual(code, 0, out + err)
        unified = page(run_dir).split('<table class="diff unified"')[1].split("</table>")[0]
        self.assertRegex(unified, r'<tr class="add">(?:(?!</tr>).)*foo\(\);</span></td></tr>'
                                  r'<tr class="note-row">(?:(?!</tr>).)*STRAY')

    def test_mid_line_cr_is_visible(self):
        path = repo({"keep.txt": "k\n"})
        write(path, "cr.cs", b"alpha\rbeta\n")
        run_dir, _ = collect(path)
        build(run_dir, notes_with())
        self.assertIn("alpha␍beta", page(run_dir))

    def test_markup_and_labels(self):
        run_dir, _ = collect(three_changes())
        build(run_dir, dict(NOTES, title="Тур **по** `диффу`",
                            files=[{"path": "a.cs", "kind": "prod"}],
                            notes=[note(text="**`build` не доверяет.** дальше")]))
        html = page(run_dir)
        self.assertIn("<title>Тур по диффу</title>", html)
        self.assertIn("<b><code>build</code> не доверяет.</b>", html)
        self.assertIn('<span class="role prod">код</span>', html)   # kind alone gives a badge
        self.assertIn("table.solo ", difftour.PAGE_JS)                # links reach one-sided files

    def test_lone_surrogate_does_not_break_the_page(self):
        run_dir, _ = collect(three_changes())
        with open(os.path.join(run_dir, "notes.json"), "w", encoding="utf-8") as fh:
            fh.write('{"title": "cut \\ud83d", "lede": "l", "notes": []}')
        code, _, err = run(run_dir, "build", run_dir)
        self.assertEqual(code, 0, err)
        self.assertGreater(os.path.getsize(os.path.join(run_dir, "index.html")), 1000)

    @unittest.skipUnless(shutil.which("node"), "node is not installed")
    def test_highlight_split_keeps_spans_per_line(self):
        js = difftour.PAGE_JS
        start = js.index("function lines(")
        end = js.index("function paint(")
        probe = (js[start:end] + "\nconsole.log(JSON.stringify(lines("
                 "'<span class=\"c\">/* a\\nb */</span>\\nx/y <span class=\"k\">if</span>')));")
        out = subprocess.run(["node", "-e", probe], capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(out.stdout), ['<span class="c">/* a</span>',
                                                  '<span class="c">b */</span>',
                                                  'x/y <span class="k">if</span>'])

    def test_open_bypasses_the_open_on_path(self):
        calls = []
        real_run, real_platform = difftour.subprocess.run, difftour.sys.platform
        difftour.subprocess.run = lambda argv, **kw: calls.append(argv)
        difftour.sys.platform = "darwin"
        try:
            difftour.open_in_browser("/tmp/x/index.html")
        finally:
            difftour.subprocess.run, difftour.sys.platform = real_run, real_platform
        if os.path.exists("/usr/bin/open"):
            self.assertEqual(calls, [["/usr/bin/open", "/tmp/x/index.html"]])


if __name__ == "__main__":
    unittest.main()
