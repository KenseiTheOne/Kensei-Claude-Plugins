#!/usr/bin/env bash
# Scaffold: a tiny Python project in a git repo with one commit; clean tree.
set -euo pipefail
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
