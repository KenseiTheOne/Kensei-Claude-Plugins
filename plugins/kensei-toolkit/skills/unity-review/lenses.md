# unity-review — lenses

Read by reviewer agents (SKILL.md Step 5). Read the severity section and your own lens
section(s). Each list names what to look for; a finding still needs a location in the change and
a concrete failure scenario. Items marked "when used" apply only when the project context line,
an `.asmdef` or the code's usings show the technology is in use.

## Severity

- **Critical** — a player-visible failure or data loss in a reachable situation: crash, hang,
  leak that grows over a session, broken save, a feature that does not work on a target platform,
  a serialized reference that silently goes missing.
- **Warning** — a real cost or risk that does not break immediately: per-frame GC allocation on a
  hot path, a lifecycle bug that bites on scene reload or domain reload, cost that scales badly
  with content.
- **Suggestion** — a clear, cheap improvement with a stated benefit. Skip anything that is taste.

Calibrate to the target platforms: mobile is strict on GC, memory and thermals; WebGL has no
threads; IL2CPP strips code and has no JIT.

## Performance

A hot path is code that runs every frame or per entity/item: `Update`/`LateUpdate`/`FixedUpdate`,
`OnGUI`, ECS `OnUpdate`, job `Execute`, per-frame UI callbacks, and anything they call. Trace the
callers before calling a path hot.

- Allocations on hot paths: `new` of reference types, closures and lambdas capturing locals,
  string concatenation and formatting, `params` arrays, boxing (value types as `object` or
  interface, enum keys in `Dictionary` without a comparer on old runtimes), `foreach` over
  interfaces.
- LINQ in hot paths or per-item loops.
- Unity API cost: `GetComponent`/`Find*`/`FindObjectsByType` per frame, `Camera.main` in old
  versions, `.material` (instantiates) versus `.sharedMaterial`, `transform` chains, `SendMessage`,
  physics queries allocating (`RaycastAll` versus `RaycastNonAlloc`), `WaitForSeconds` created
  each iteration.
- Physics and timing: work in `FixedUpdate` that belongs in `Update` or the reverse; layer masks
  missing.
- UI: uGUI canvas rebuilds from per-frame text or layout changes, raycast targets on decoration;
  UI Toolkit style or hierarchy changes every frame, `Q<>()` queries per frame.
- Rendering when shaders are in scope: variant explosion from `multi_compile` where
  `shader_feature` fits, per-pixel work that could be per-vertex, SRP Batcher compatibility of
  `CBUFFER` layout (URP/HDRP).
- Burst and Jobs, when used: managed types or exceptions inside `[BurstCompile]` code,
  `Complete()` right after `Schedule()` on the main thread, missing `[ReadOnly]` causing false
  dependencies, scheduling cost exceeding the work. Do not propose Jobs or Burst for a project
  that does not use them.

## Memory & lifecycle

- Events and callbacks: `+=` without a matching `-=` in `OnDisable`/`OnDestroy`/`Dispose`; static
  events holding destroyed objects; lambdas subscribed so they cannot be removed.
- Async and coroutines: `async` methods or UniTask continuing after the object is destroyed
  (missing cancellation token tied to the object's lifetime); coroutines on disabled objects.
- Assets: Addressables handles never released or released twice, `Resources.Load` without
  unload where it matters, runtime-created textures, meshes, materials and RenderTextures never
  destroyed.
- Native memory: `NativeArray`/`NativeList` and other native containers without `Dispose` or with
  the wrong `Allocator` (Temp kept past the frame, Persistent never freed), `GraphicsBuffer`/
  `ComputeBuffer` not released.
- ScriptableObject state: runtime writes to an asset that persist in the Editor and leak between
  play sessions, or shared state assumed per-instance.
- Domain reload, when it is off: static fields and singletons not reset — they need a
  `[RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.SubsystemRegistration)]` reset.
- `DontDestroyOnLoad` objects accumulating across scene loads; pooled objects keeping state.

## Unity architecture

- Serialization: renamed or removed serialized fields without `[FormerlySerializedAs]`;
  `[SerializeField]` on types Unity cannot serialize (dictionaries, interfaces without
  `[SerializeReference]`, properties); `[SerializeReference]` types renamed or moved without
  `[MovedFrom]`. For a changed or deleted `.cs` or `.meta`, take the script GUID from its
  `.meta` (from the diff for a deleted one) and grep every `.prefab`/`.unity`/`.asset` under
  `Assets/` (and embedded packages under `Packages/`) for that GUID and for the old field names —
  the broken assets are usually not in the change. Grep, do not read them whole. Flag references
  the change breaks: a changed GUID, a deleted script still referenced, a renamed field whose
  saved values are lost.
- Execution order: `Awake`/`OnEnable`/`Start` dependencies between objects that are not
  guaranteed; reliance on `[DefaultExecutionOrder]` that is missing; work in `OnValidate` or
  constructors of `MonoBehaviour`/`ScriptableObject`.
- Editor/runtime boundary: `UnityEditor` usage outside an Editor-only assembly or `#if
  UNITY_EDITOR`; `.asmdef` references and platform include lists that break a player build.
- Entities (ECS/DOTS), when used: structural changes inside iteration without an
  `EntityCommandBuffer`; `ComponentLookup`/`BufferLookup` not updated before use; missing
  dependency handling between systems; system ordering (`UpdateInGroup`/`UpdateBefore`) that the
  logic relies on but does not declare; managed components in Burst code; baking logic that
  runs at runtime or the reverse. With Netcode for Entities: prediction logic outside the
  predicted simulation group, ghost fields not marked for replication.
- UI Toolkit, when `.uxml`/`.uss` are in scope or C# queries UI: `Q<>("name")` and class
  lookups matching names that exist in the UXML; binding paths matching the data source;
  template and style sheet references; callbacks registered without unregistering when the
  element outlives its owner.
- Input System, when used: actions enabled without disabling, callbacks not unsubscribed.

## Platform

Use the target platforms from the context line; skip platforms that are not targets.

- IL2CPP: reflection or `Type.GetType` on types that stripping removes (needs `link.xml` or
  `[Preserve]`), generic virtual methods and `MakeGenericType` without AOT hints, serializers
  that rely on runtime code generation.
- Mobile (Android, iOS): main-thread file or network I/O, `Application.persistentDataPath` usage
  and file size, permissions requested in code, background/pause handling (`OnApplicationPause`
  saving state), texture and memory budgets, frame-rate and thermal cost.
- WebGL: threads, `System.Threading`, synchronous I/O, native plugins.
- Platform defines: code paths under `#if UNITY_ANDROID`/`UNITY_IOS`/`UNITY_WEBGL` that do not
  compile or behave differently from the Editor; Editor-only behaviour assumed in builds.
- Dedicated server, when a server target exists: rendering, audio or UI work running in the
  server build.
