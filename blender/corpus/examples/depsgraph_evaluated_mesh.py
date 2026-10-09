# id: depsgraph-evaluated-mesh
# title: Read evaluated (modifier-aware) mesh geometry
# tags: depsgraph, mesh, geometry, modifiers
# description: Read the evaluated mesh that includes modifiers via the depsgraph, then free it.

import bpy


def run():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    obj = bpy.context.active_object
    deps = bpy.context.evaluated_depsgraph_get()
    ev = obj.evaluated_get(deps)
    mesh = ev.to_mesh()
    stats = {"verts": len(mesh.vertices), "polys": len(mesh.polygons)}
    ev.to_mesh_clear()
    return stats
