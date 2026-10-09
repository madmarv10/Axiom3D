# id: numpy-vectorized-layout
# title: Lay out many objects with numpy
# tags: numpy, layout, transforms, performance
# description: Compute instance positions in a vectorized numpy grid, then place objects.

import bpy
import numpy as np


def run():
    count = 5
    xs = np.arange(count) * 2.0
    positions = np.stack([xs, np.zeros(count), np.zeros(count)], axis=1)
    created = []
    for i, pos in enumerate(positions):
        bpy.ops.mesh.primitive_cube_add(size=0.5, location=tuple(float(v) for v in pos))
        obj = bpy.context.active_object
        obj.name = f"layout_{i}"
        created.append(obj.name)
    return {"created": created, "first_x": float(positions[0][0])}
