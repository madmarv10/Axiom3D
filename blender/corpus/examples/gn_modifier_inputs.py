# id: gn-modifier-inputs
# title: Set Geometry Nodes modifier inputs (Blender 5.2)
# tags: geometry, nodes, modifier, inputs, gn
# description: Assign a GN node group and drive its inputs via mod.properties.inputs.

import bpy


def run():
    group = bpy.data.node_groups.new("snippet_gn", "GeometryNodeTree")
    group.interface.new_socket("Size", in_out="INPUT", socket_type="NodeSocketFloat")
    group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    cube = group.nodes.new("GeometryNodeMeshCube")
    comb = group.nodes.new("ShaderNodeCombineXYZ")
    gin = group.nodes.new("NodeGroupInput")
    gout = group.nodes.new("NodeGroupOutput")
    group.links.new(gin.outputs["Size"], comb.inputs["X"])
    group.links.new(comb.outputs[0], cube.inputs["Size"])
    group.links.new(cube.outputs["Mesh"], gout.inputs[0])

    obj = bpy.data.objects.new("snippet_gn_obj", bpy.data.meshes.new("m"))
    bpy.context.scene.collection.objects.link(obj)
    modifier = obj.modifiers.new("GN", "NODES")
    modifier.node_group = group
    ident = next(
        item.identifier
        for item in group.interface.items_tree
        if getattr(item, "item_type", "") == "SOCKET" and item.in_out == "INPUT"
    )
    modifier.properties.inputs[ident]["value"] = 1.5  # 5.2: not mod[ident]
    return {"identifier": ident, "value": modifier.properties.inputs[ident]["value"]}
