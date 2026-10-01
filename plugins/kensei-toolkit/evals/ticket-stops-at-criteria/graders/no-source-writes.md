---
type: tool_used
tool: Write
input_match: '"file_path"\s*:\s*"[^"]*src/pricing\.py"'
min: 0
max: 0
arm: both
---

Companion to no-source-edits: overwriting the file with Write counts as an edit too.
The match is on `file_path`: a run-dir note whose text names src/pricing.py is not a source write.
