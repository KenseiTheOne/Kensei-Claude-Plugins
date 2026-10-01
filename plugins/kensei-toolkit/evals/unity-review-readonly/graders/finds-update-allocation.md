---
type: llm
focus: last_message
---

PASS if the report flags the per-frame allocation in `EnemySpawner.Update` (the `new List`, the
LINQ `Where`/`ToList` with a capturing lambda, or `FindGameObjectsWithTag` every frame) with a
location in `Client/Game/Assets/Scripts/EnemySpawner.cs` including a line number, and a concrete
failure scenario (GC spikes or frame cost as enemies grow, especially on mobile).
FAIL if it reports no such finding, gives no line number, says it changed the file, or ends by
asking which review mode to run. The language of the report does not matter.
