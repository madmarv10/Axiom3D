# Axiom3D Scene Conventions

Enforced by `blender_validate` (gate stage 4). Agent prompt carries the summary; this file
is the full spec, loaded on demand via `references` config in `.opencode/opencode.jsonc`.

## Status

Skeleton — values finalized during Phase 2/3 alongside the validator implementation.

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
- No zero-area faces, no flipped normals, triangulated consistently.
- UV layer present on every renderable mesh.
- Poly budget per asset class: TBD Phase 3 (gate stage 4 reads budget from asset
  metadata, default cap applies when absent).

## Materials

- Template materials from `axiom3d_library.blend` first; procedural ad-hoc material only
  when no template fits, and must expose base color/roughness/metallic as node group
  inputs.

## Export

- glTF default, 1 unit = 1 m, Y-up handled by exporter, apply modifiers before export.
- Roundtrip check (gate stage 6) must pass: bounds within 1%, vertex count within 1%.