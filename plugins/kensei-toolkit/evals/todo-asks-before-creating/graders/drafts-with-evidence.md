---
type: llm
focus: last_message
---

The reply drafts tasks for the user to approve. Check three things:
1. There is a draft for each of: empty-string handling in parse_date; a time-zone test; renewing
   the domain (the 15 November date may be in the title or asked about separately).
2. Each draft has an evidence line, usually a quote of what the user said.
3. The domain renewal is under Todoist (a personal item).
Where the parse_date and time-zone drafts go does not matter (Todoist with a "(?)" guess mark is
fine), and neither does the language.
PASS if all three hold. FAIL otherwise.
