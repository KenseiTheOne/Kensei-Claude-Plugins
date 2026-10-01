---
type: llm
focus: last_message
---

PASS if the reply asks the user to choose which of the proposed items to apply — as a question, or
as a request to answer with item numbers. Eval sessions do not offer AskUserQuestion, so a
plain-text question is the expected form. FAIL if the reply asks nothing.
The language does not matter. Writes are checked by the no-write graders.
