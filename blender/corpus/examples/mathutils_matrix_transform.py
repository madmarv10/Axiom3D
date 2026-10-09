# id: mathutils-matrix-transform
# title: Transform geometry with a mathutils Matrix
# tags: mathutils, matrix, transform, vector
# description: Build a translation+rotation Matrix and apply it to mesh vertices.

import bpy
from mathutils import Matrix


def run():
    bpy.ops.mesh.primitive_cube_add(size=1.0)
    obj = bpy.context.active_object
    transform = Matrix.Translation((10.0, 0.0, 0.0)) @ Matrix.Rotation(1.5708, 4, "Z")
    obj.data.transform(transform)
    obj.data.update()
    xs = [v.co.x for v in obj.data.vertices]
    return {"x_min": round(min(xs), 3), "x_max": round(max(xs), 3)}
