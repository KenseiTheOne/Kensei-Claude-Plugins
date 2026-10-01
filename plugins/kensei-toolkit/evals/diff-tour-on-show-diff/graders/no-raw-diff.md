---
type: regex
target: last_message
pattern: '^(?:diff --git |@@ -\d|\+\+\+ b/|-{3} a/)'
flags: m
match: not_contains
---

The reply must not paste a unified diff into the terminal; changes are shown on the diff-tour page.
