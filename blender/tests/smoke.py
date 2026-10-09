"""Headless Blender smoke test.

Run: blender --background --factory-startup --python blender/tests/smoke.py

Prints version, creates a cube, verifies it exists. Exits 0 on success, 1 on failure.
Blender often exits 0 even when a script raises, so failure is signaled explicitly.
"""

import sys
import traceback

try:
    import bpy

    print(f"BLENDER_VERSION={bpy.app.version_string}")

    # Clean factory scene is guaranteed by --factory-startup, but be explicit.
    bpy.ops.wm.read_factory_settings(use_empty=True)

    bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0.0, 0.0, 1.0))
    cube = bpy.context.active_object
    assert cube is not None, "no active object after primitive_cube_add"
    assert cube.type == "MESH", f"expected MESH, got {cube.type}"
    assert len(cube.data.vertices) == 8, f"expected 8 verts, got {len(cube.data.vertices)}"

    depsgraph = bpy.context.evaluated_depsgraph_get()
    evaluated = cube.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    assert len(mesh.vertices) == 8, f"evaluated mesh has {len(mesh.vertices)} verts"
    evaluated.to_mesh_clear()

    print(f"BLENDER_SMOKE_OK object={cube.name}")
    sys.exit(0)
except Exception:
    traceback.print_exc()
    print("BLENDER_SMOKE_FAIL")
    sys.exit(1)