---
type: llm
focus: last_message
---

PASS if the reply lists acceptance criteria for LOCAL-17 (discount outside 0..1 raises ValueError, rounding to cents, the existing test stays green, or close equivalents) and asks the user to approve them or choose a mode before any implementation.
FAIL if the reply says the fix was implemented, tests were run on a fix, a commit or push was made, or it ends without presenting criteria for approval. Also FAIL if the run stopped before the criteria step for any other reason (for example git not working in the sandbox), even when the reply mentions the criteria it would draft later.
The language of the reply does not matter.
