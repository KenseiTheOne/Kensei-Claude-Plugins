#!/usr/bin/env bash
# Scaffold: a tiny Python project in a git repo with one commit; clean tree.
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
