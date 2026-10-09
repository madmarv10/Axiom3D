# id: kdtree-nearest
# title: Find nearest points with mathutils KDTree
# tags: mathutils, kdtree, nearest, search
# description: Build a KDTree over vertex positions and find the nearest to a query point.

import bpy
from mathutils import kdtree


def run():
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    obj = bpy.context.active_object
    tree = kdtree.KDTree(len(obj.data.vertices))
    for i, v in enumerate(obj.data.vertices):
        tree.insert(v.co, i)
    tree.balance()
    nearest, index, distance = tree.find((0.9, 0.9, 0.9))
    return {"index": index, "distance": round(distance, 4)}
