# id: bmesh-edit-loop
# title: Edit a mesh with bmesh (remove a face)
# tags: bmesh, mesh, edit, topology
# description: Open a mesh in bmesh, edit topology, and write it back.

import bmesh
import bpy


def run():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    obj = bpy.context.active_object
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.faces.ensure_lookup_table()
    removed = len(bm.faces)
    bm.faces.remove(bm.faces[0])
    bm.to_mesh(obj.data)
    bm.free()
    obj.data.update()
    return {"faces_before": removed, "faces_after": len(obj.data.polygons)}
