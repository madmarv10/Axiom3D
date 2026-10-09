# Axiom3D Scene Conventions

Enforced by `blender_validate` (gate stage 4). Agent prompt carries the summary; this file
is the full spec, loaded on demand via `references` config in `.opencode/opencode.jsonc`.

## Status

Finalized in Phase 3 alongside the gate implementation. Enforced by `blender_validate`
(scene lint) and gate stages 4 (geometry) + 5 (mesh quality); the gate report carries
the issue vocabulary below as structured evidence.

## Scale

- 1 unit = 1 meter, always. Scene unit scale = 1.0.
- No applying scale to hit a number: author geometry at final size.
- Asset bounds check: declared dimensions vs measured bounds within 1% tolerance.

## Origin

- Origin at asset logical base: ground-plane contact point for props, center of footprint
  for buildings/platforms.
- Ground plane = Z 0. No floating assets, no sunk geometry.
- Applied transforms: location at creation point, rotation/scale zeroed after apply.

## Naming

- Pattern: `<type>_<domain>_<detail>` in snake_case, e.g. `platform_west_surface`,
  `rail_north_main`, `truss_canopy_01`.
- Types: `rail`, `sleeper`, `platform`, `truss`, `column`, `fence`, `canopy`, `building`,
  `prop`, `camera`, `light`, `material`.
- No default names survive (`Cube.001`, `Material.007`) — validator fails them.

## Mesh health

- Manifold: no non-manifold edges (except intentional open surfaces: declared via
  `["open_surface"]` custom property).
- No self-intersection: separate shells must not overlap (except intentional
  multi-part assemblies — truss chords + web posts, fence posts + rail — declared
  via the `["assembly"]` custom property; `blender-template` sets this on
  canopy_truss and fence_run).
- No zero-area faces, no flipped normals, triangulated consistently.
- UV layer present on every renderable mesh.
- Poly budget per asset class: default cap is 100,000 evaluated verts per mesh
  (gate param `poly_budget` overrides); per-asset-class budgets land with the
  template library in Phase 4.

## Materials

- Template materials from `axiom3d_library.blend` first; procedural ad-hoc material only
  when no template fits, and must expose base color/roughness/metallic as node group
  inputs.

## Export

- glTF default, 1 unit = 1 m, Y-up handled by exporter, apply modifiers before export
  (`export_apply` on Blender 5.2's glTF exporter).
- Roundtrip check (gate stage 6) must pass: mesh object count exact, world bounds
  within 1%, triangle count within 1%. Vertex counts are reported but not compared —
  the glTF exporter splits vertices per unique normal/UV, so they change legitimately
  across a roundtrip.