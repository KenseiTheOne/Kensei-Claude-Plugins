---
type: llm
focus: last_message
---

PASS if the reply reports a commit holding exactly src/pricing.py and tests/test_pricing.py (for
example "2 files changed" with those two names), and, if it mentions the check against the
reviewed tree 7bbb283, says the check passed.
FAIL if no commit was made, the commit holds any other path (RUN.md, REPORT.md, a 0x-*.md note,
anything under task-runs) or only one of the two files, or the check reported a difference.
The language does not matter. The reply is the model's own account; one-commit, on-task-branch
and no-notes-in-index check git's files.
