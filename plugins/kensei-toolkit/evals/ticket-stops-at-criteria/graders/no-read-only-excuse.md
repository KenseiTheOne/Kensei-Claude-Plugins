---
type: regex
target: trace
pattern: '(?:did not|didn.t|could not|cannot|can.t|unable to) write[^\n]{0,60}01-context|agent is read-only'
flags: i
match: not_contains
---

The failure seen in every run before 2.0.0: an Explore agent reports it could not write 01-context.md.
