# Axiom3D

An AI harness for generating **3D assets in Blender**, built as a specialized fork of
[opencode](https://opencode.ai). An LLM agent authors `bpy` scripts, and a persistent
headless Blender session verifies every change through a staged gate before it is
trusted — so hallucinated APIs and silently-broken geometry are caught, not shipped.

---

## The problem

Left alone, an LLM writing Blender Python fails in two characteristic ways:

- **Hallucinated APIs** — operators, socket names, or arguments that don't exist in
  the *installed* Blender version (training data lags the runtime).
- **Silent geometry failures** — scripts that run without error but produce
  non-manifold, inside-out, wrong-scale, floating, or self-intersecting meshes.

Both are invisible until someone opens the file. Axiom3D makes them visible: the agent
retrieves the real API, instantiates proven templates, and every scene change is
verified by a gate that fails fast with structured evidence.

## The approach

| Problem | Fix |
| --- | --- |
| API drift vs. training data | Live introspection of the installed Blender + a symbol check that rejects unknown names with a suggestion |
| Scripts that hang or crash Blender | A persistent worker with per-call timeouts, auto-snapshots, and kill/restore recovery |
| Broken geometry | A staged verification gate: syntax → API → execute → evaluated-mesh geometry → trimesh quality/intersections → glTF roundtrip → multi-view render |
| Reinventing every part | A parametric template library (rail, sleepers, columns, fence, platform, canopy truss) agents instantiate by setting parameters |
| Guessing node trees | Agents never build Geometry Nodes — they set exposed inputs on prebuilt groups |

## How it works

- **Persistent worker** — a headless Blender 5.2 process that stays alive and speaks
  newline-delimited JSON over localhost TCP. Every `exec` auto-snapshots first; on a
  timeout the client kills and restarts the worker, then restores the last snapshot, so
  a bad script never leaves the scene wrecked.
- **Staged verification gate** (`blender-gate`) — runs a script through seven stages and
  returns a structured JSON report with evidence. Script stages (syntax, API symbols,
  exec) fail fast; scene stages (geometry, mesh quality, export roundtrip, render) all
  run and accumulate issues so one report carries everything the agent needs to fix.
- **Template library** (`blender-template`) — parametric Geometry Nodes assets with
  exposed float inputs. `instantiate` bakes a template into a real, grounded, UV'd mesh.
  Agents set parameters; they never build node trees.
- **Live API corpus** (`blender-docs`) — resolves a human name ("Principled BSDF") to the
  real node class and lists its actual sockets read from the running Blender, plus a
  cookbook of tested pattern snippets and the 5.0–5.2 breaking changes this harness hit.
- **Agent + tools** — an `axiom3d` agent wired with `blender-{exec, scene, checkpoint,
  validate, render, export, gate, template, docs}`, following a retrieve → template →
  gate → critique → export loop.

## Requirements

- **Blender 5.2** (headless; the harness pins this version exactly)
- **[Bun](https://bun.sh)**

## Getting started

```bash
bun install

# Point the harness at your Blender install (or let it auto-discover on Windows):
export BLENDER_PATH="/path/to/blender"     # e.g. .../Blender 5.2/blender.exe

# Install the one Python dep into Blender's bundled interpreter:
"<blender>/5.2/python/bin/python" -m pip install --no-deps \
  --target blender/vendor -r blender/requirements.txt

# Run the agent (the axiom3d agent is available in the TUI):
bun run dev
```

Ask it to build something — e.g. *“make a 1 m crate”* or *“assemble a small railway
station from templates”*. The agent retrieves the API, instantiates templates, and runs
the gate until the asset passes.

The full design, phase history, and conventions live in [`PLAN.md`](./PLAN.md) and
[`docs/axiom3d/conventions.md`](./docs/axiom3d/conventions.md).

## Development

The harness tests spawn a real headless Blender. They share one worker through a port
file, so they must run single-worker (parallel file workers race the scene and the
snapshot pool):

```bash
cd blender
bun test --parallel=1 --no-isolate
```

Build-time validators (also run in CI):

```bash
blender --background --factory-startup --python blender/templates/build_library.py
blender --background --factory-startup --python blender/corpus/validate_patterns.py
```

CI (`.github/workflows/axiom3d.yml`) runs on every push/PR to `main`: it installs the
pinned Blender 5.2.2 (cached), `bun typecheck`, the build validators, and the full
headless Workbench test suite under Xvfb.

## Layout

```
blender/
├── worker.py        persistent session: JSON-RPC loop, snapshot/restore, watchdog
├── rpc/             command handlers (exec, gate, templates, docs, render, export, ...)
├── gate/            staged verification pipeline + AST API-symbol checker
├── geom/            evaluated-mesh geometry + trimesh quality checks
├── templates/       parametric GN asset library + build/validate script
├── corpus/          live bpy introspection + pattern cookbook + breaking changes
└── tests/           bun test suite (worker, tools, gate, templates, corpus)
.opencode/
├── tools/           blender-* agent tools
├── agent/axiom3d.md the agent's workflow prompt
├── skills/          blender-asset-authoring skill
└── lib/             TypeScript worker client (spawn, RPC, timeout, restart)
```

## Credits

Built on [opencode](https://opencode.ai), the open-source AI coding agent.

---

**Axiom3D** — Blender 5.2 · persistent worker · staged verification gate · template
library · live API corpus
