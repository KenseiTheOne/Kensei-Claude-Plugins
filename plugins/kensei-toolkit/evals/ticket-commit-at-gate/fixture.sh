#!/usr/bin/env bash
# Scaffold: a /ticket run for LOCAL-17 stopped at the publish gate (Step 12), outcome accepted.
#   - the repo has its base commit on main, pushed to a bare origin in $HOME;
#   - the fix is in the working tree, uncommitted;
#   - the run dir holds everything Steps 1-12 leave behind: RUN.md with the baseline, the
#     whitelist and reviewed_tree, the approved criteria, the review verdict, REPORT.md.
# Dates and identities are fixed, so every sha is the same on every machine; history.jsonl
# (built by make_history.py from this script) quotes them.
#
# The run dir goes to the default runs root, $HOME/.claude/task-runs. The eval harness gives the
# scaffold and the session the same throwaway HOME, and the session's sandboxed Bash may write
# there. The script honours KENSEI_TASK_RUNS_DIR when it is set, as the skill does; neither the
# harness nor make_history.py sets it (case.yaml accepts only EVAL_* keys).
set -euo pipefail

# The session runs git inside the eval sandbox with the operator's PATH. On macOS the sandbox
# refuses the xcrun shim /usr/bin/git, and refused the Command Line Tools git in all but one
# 2.0.0 run, so stop here with "needs git" before any model turn is paid for.
# KENSEI_EVAL_GIT_CHECK=off works only when this script is run directly (make_history.py does,
# outside the sandbox); the eval harness does not pass it on. Keep this block identical in both
# ticket fixtures.
if [ "${KENSEI_EVAL_GIT_CHECK:-on}" != off ] && [ "$(uname -s)" = Darwin ]; then
  eval_git=$(command -v git || true)
  case "$eval_git" in
    "" | /usr/bin/git | /Library/Developer/* | /Applications/Xcode*)
      echo "needs git: '${eval_git:-none}' cannot run in the eval sandbox; put a standalone git (brew install git) first on PATH, or run on Linux (see evals/README.md)" >&2
      exit 3 ;;
  esac
fi

export GIT_AUTHOR_NAME="eval" GIT_AUTHOR_EMAIL="eval@example.invalid"
export GIT_COMMITTER_NAME="eval" GIT_COMMITTER_EMAIL="eval@example.invalid"
export GIT_AUTHOR_DATE="2026-10-01T09:00:00+00:00" GIT_COMMITTER_DATE="2026-10-01T09:00:00+00:00"

git init -q -b main .
git config user.name "eval"
git config user.email "eval@example.invalid"
mkdir -p src tests
cat > src/pricing.py <<'PY'
def total(prices, discount=0.0):
    """Sum of prices with a fractional discount (0.1 = 10% off)."""
    subtotal = sum(prices)
    return subtotal - subtotal * discount
PY
cat > tests/test_pricing.py <<'PY'
import sys, unittest
sys.path.insert(0, "src")
from pricing import total

class TotalTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(total([1, 2, 3]), 6)

if __name__ == "__main__":
    unittest.main()
PY
printf '# pricing\n\nRun tests: `python3 -m unittest discover -s tests`\n' > README.md
git add -A
git commit -q -m "Initial pricing module"

# A remote, so the gate can offer push; nothing may reach it during the case.
git init -q --bare "$HOME/remotes/pricing.git"
git remote add origin "$HOME/remotes/pricing.git"
git push -q -u origin main 2>/dev/null
git remote set-head origin main

# The run's change, uncommitted (what the implementer left).
cat > src/pricing.py <<'PY'
def total(prices, discount=0.0):
    """Sum of prices with a fractional discount (0.1 = 10% off), rounded to cents."""
    if not 0 <= discount <= 1:
        raise ValueError(f"discount must be within 0..1, got {discount!r}")
    subtotal = sum(prices)
    return round(subtotal - subtotal * discount, 2)
PY
cat > tests/test_pricing.py <<'PY'
import sys, unittest
sys.path.insert(0, "src")
from pricing import total

class TotalTest(unittest.TestCase):
    def test_plain(self):
        self.assertEqual(total([1, 2, 3]), 6)

    def test_discount_above_one_rejected(self):
        with self.assertRaises(ValueError):
            total([10, 20], discount=1.5)

    def test_negative_discount_rejected(self):
        with self.assertRaises(ValueError):
            total([10, 20], discount=-0.1)

    def test_rounded_to_cents(self):
        self.assertEqual(total([10.005, 0.001], discount=0.0), 10.01)

if __name__ == "__main__":
    unittest.main()
PY
python3 -m unittest discover -s tests >/dev/null 2>&1

# --- the run directory -------------------------------------------------------------------------
common=$(git rev-parse --path-format=absolute --git-common-dir)
repo_name=$(basename "$(dirname "$common")")
run_dir="${KENSEI_TASK_RUNS_DIR:-$HOME/.claude/task-runs}/$repo_name/LOCAL-17"
mkdir -p "$run_dir"

base_sha=$(git rev-parse HEAD)
index=$(git rev-parse --path-format=absolute --git-path ticket-LOCAL-17.index)
GIT_INDEX_FILE="$index" git read-tree "$base_sha"
GIT_INDEX_FILE="$index" git add -- src/pricing.py tests/test_pricing.py
tree=$(GIT_INDEX_FILE="$index" git write-tree)
git diff "$base_sha" "$tree" > "$run_dir/03-diff.patch"

cat > "$run_dir/00-ticket.md" <<'MD'
# LOCAL-17 · total() принимает скидку больше 100%

Источник: текст из вызова (трекера нет).

`total([10, 20], discount=1.5)` возвращает -15. Скидка вне диапазона 0..1 должна
отклоняться с ValueError, а сумма — округляться до копеек. Существующий тест
`tests/test_pricing.py` должен остаться зелёным.

Комментарии: нет. Статусы: недоступны.
MD

cat > "$run_dir/01-context.md" <<'MD'
# Context — LOCAL-17

- `src/pricing.py:total` is the only entry point; no callers inside the repo.
- Tests: `tests/test_pricing.py` (unittest), run with `python3 -m unittest discover -s tests`.
- Nothing in the repo contradicts the ticket.
MD

cat > "$run_dir/02-criteria.md" <<'MD'
AC1  [from ticket]  total() with a discount outside 0..1 raises ValueError.        auto
AC2  [from ticket]  The result is rounded to cents.                                 auto
AC3  [from ticket]  The existing test in tests/test_pricing.py stays green.         auto
MD
cp "$run_dir/02-criteria.md" "$run_dir/02-criteria.approved.md"
criteria_sha=$(python3 -c 'import hashlib, sys; print(hashlib.sha256(open(sys.argv[1], "rb").read()).hexdigest())' \
  "$run_dir/02-criteria.approved.md")

cat > "$run_dir/03-changes.md" <<'MD'
src/pricing.py — reject a discount outside 0..1 with ValueError; round the result to 2 places.
tests/test_pricing.py — tests for both bounds and for rounding.
MD

cat > "$run_dir/04-review-1.md" <<MD
verdict: accepted
tree: $tree

AC1  proven by test  tests/test_pricing.py::test_discount_above_one_rejected, test_negative_discount_rejected
AC2  proven by test  tests/test_pricing.py::test_rounded_to_cents
AC3  proven by test  tests/test_pricing.py::test_plain

Non-blocking: none.
MD

cat > "$run_dir/REPORT.md" <<MD
accepted

base main @ ${base_sha:0:7} · reviewed tree ${tree:0:7} · 1 round(s)
git: not committed

Acceptance criteria:
  AC1  proven by test  test_discount_above_one_rejected, test_negative_discount_rejected
  AC2  proven by test  test_rounded_to_cents
  AC3  proven by test  test_plain

Changed: src/pricing.py, tests/test_pricing.py
Review findings not blocking: none
Evidence: $run_dir/02-criteria.approved.md, $run_dir/04-review-1.md · notes not committed
Diff tour: not built: not needed for this check
Task status: cannot change: no tracker
Task comment: none
MD

cat > "$run_dir/RUN.md" <<MD
task_id: LOCAL-17
tracker: none
tracker_channel: none
task_ref: LOCAL-17
status_vocabulary: unavailable
mode: fix
commands: []
base_branch: main
default_branch: main
base_sha: $base_sha
baseline_status: (clean)
stash: none
baseline_hashes: {}
criteria_sha256: $criteria_sha
branch: task/LOCAL-17-discount-range
whitelist:
  - src/pricing.py
  - tests/test_pricing.py
overlap: []
test_dirt: []
snapshot_index: $index
snapshot_tree: $tree
reviewed_tree: $tree
rounds: 1
outcome: accepted
step: gate
MD
