# id: set-principled-sockets
# title: Set Principled BSDF sockets by name
# tags: shader, material, principled, bsdf
# description: Find the Principled BSDF node and set Base Color / Metallic / Roughness.

import bpy


def run():
    mat = bpy.data.materials.new("snippet_principled")
    mat.use_nodes = True
    node = next(n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED")
    node.inputs["Base Color"].default_value = (0.8, 0.2, 0.2, 1.0)
    node.inputs["Metallic"].default_value = 1.0
    node.inputs["Roughness"].default_value = 0.4
    return {"roughness": node.inputs["Roughness"].default_value}
