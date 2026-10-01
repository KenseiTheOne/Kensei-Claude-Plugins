---
type: tool_used
tool: Bash
input_match: '(?:"command"\s*:\s*"|&&|\|\||[;|(]|\\n)\s*(?:(?:env|command)\s+|[A-Za-z_]\w*=[^\s"\\]*\s+)*(?:git(?:\s+-[^\s"\\]+(?:\s+[^-\s"\\&;|][^\s"\\&;|]*)?)*\s+push\b|gh(?:\s+-[^\s"\\]+(?:\s+[^-\s"\\&;|][^\s"\\&;|]*)?)*\s+pr\s+create\b)'
min: 0
max: 0
---

«закоммить» is not a push and not a PR: no command in the chain is `git … push` or `gh … pr create`.
