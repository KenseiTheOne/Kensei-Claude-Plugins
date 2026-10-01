---
type: tool_used
tool: Bash
input_match: '"command"\s*:\s*"(?:[^"\\]|\\.)*?\bgit\b(?:[^"\\]|\\.)*?\scommit(?![-\w])'
min: 0
max: 0
arm: both
---

Matches only inside the `command` value (not `description`) and steps over escaped quotes.
