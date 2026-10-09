"""Procedural PBR material builders for the Axiom3D asset library.

Each returns a bpy.data.material with a Principled BSDF driven by a Noise->
ColorRamp for subtle surface variation. Materials are assigned to instances by
name via the instantiate command; agents pick from a known list rather than
authoring shader graphs.
"""

import bpy

MATERIAL_PREFIX = "axiom3d_"


def build_concrete():
    mat = bpy.data.materials.new(MATERIAL_PREFIX + "concrete")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 12.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.52, 0.52, 0.52, 1.0)
    ramp.color_ramp.elements[1].color = (0.68, 0.68, 0.68, 1.0)
    nt.links.new(noise.outputs["Factor"], ramp.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    bsdf.inputs["Metallic"].default_value = 0.0
    return mat


def build_steel():
    mat = bpy.data.materials.new(MATERIAL_PREFIX + "steel")
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    noise = nt.nodes.new("ShaderNodeTexNoise")
    noise.inputs["Scale"].default_value = 30.0
    ramp = nt.nodes.new("ShaderNodeValToRGB")
    ramp.color_ramp.elements[0].color = (0.35, 0.36, 0.38, 1.0)
    ramp.color_ramp.elements[1].color = (0.55, 0.56, 0.58, 1.0)
    nt.links.new(noise.outputs["Factor"], ramp.inputs["Factor"])
    nt.links.new(ramp.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.45
    bsdf.inputs["Metallic"].default_value = 1.0
    return mat


MATERIALS = {
    "concrete": ("Poured concrete: matte gray with noise-driven tone variation.", build_concrete),
    "steel": ("Structural steel: metallic, mid roughness, subtle grain.", build_steel),
}


def build_all():
    return {name: builder() for name, (_, builder) in MATERIALS.items()}


def get_material(key):
    mat = bpy.data.materials.get(MATERIAL_PREFIX + key)
    if mat is None and key in MATERIALS:
        mat = MATERIALS[key][1]()
    return mat
