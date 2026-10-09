"""Axiom3D template asset library.

Templates are prebuilt Geometry Nodes groups with exposed float inputs (locked
decision #6: agents set parameters, never build node trees). This package builds
the groups into the live Blender session on demand, introspects their interfaces
for list_templates, and instantiates them as baked, grounded meshes via
instantiate — so the agent-facing surface is just two worker commands.

Baking: instantiate creates an empty mesh object, attaches the group as a
GeometryNodes modifier, writes each param into
mod.properties.inputs[<identifier>]["value"], evaluates through the depsgraph,
and replaces the base mesh with the baked result (real geometry, correct
bound_box/dimensions for the gate and exporters). The mesh is then grounded by
translating its lowest vertex to Z=0 so every asset satisfies the
ground-contact convention with its origin at the base plane.
"""

import bpy

from templates.groups import BUILDERS
from templates.materials import MATERIALS, build_all as build_materials, get_material

TEMPLATE_PREFIX = "Axiom3D_"

# Multi-part templates whose members overlap at joints by design (truss chords +
# web posts, fence posts + rail). Exempt from the gate's self-intersection check
# via the "assembly" custom property — same opt-out pattern as "open_surface".
ASSEMBLIES = {"canopy_truss", "fence_run"}


def _existing(name):
    return bpy.data.node_groups.get(TEMPLATE_PREFIX + name)


def build_group(name):
    _, builder = BUILDERS[name]
    old = _existing(name)
    if old is not None:
        bpy.data.node_groups.remove(old)
    return builder()


def build_library():
    """(Re)build every template group and material. Returns built names."""
    groups = [build_group(name) for name in BUILDERS]
    build_materials()
    return {"groups": [g.name for g in groups], "materials": list(MATERIALS)}


def get_group(name):
    if name not in BUILDERS:
        raise KeyError(f"unknown template {name!r}; available: {sorted(BUILDERS)}")
    return _existing(name) or build_group(name)


def list_templates():
    out = []
    for name, (description, _) in BUILDERS.items():
        group = get_group(name)
        inputs = []
        for item in group.interface.items_tree:
            if getattr(item, "item_type", "") == "SOCKET" and item.in_out == "INPUT":
                inputs.append(
                    {
                        "identifier": item.identifier,
                        "name": item.name,
                        "socket_type": item.socket_type,
                        "default": getattr(item, "default_value", None),
                        "min": getattr(item, "min_value", None),
                        "max": getattr(item, "max_value", None),
                    }
                )
        out.append({"name": name, "description": description, "inputs": inputs})
    return out


def _input_identifiers(group):
    return {
        item.name: item.identifier
        for item in group.interface.items_tree
        if getattr(item, "item_type", "") == "SOCKET" and item.in_out == "INPUT"
    }


def _ground(mesh):
    """Translate the mesh so its lowest vertex sits at Z=0 (origin at base)."""
    if not mesh.vertices:
        return
    zmin = min(v.co.z for v in mesh.vertices)
    if abs(zmin) < 1e-9:
        return
    for v in mesh.vertices:
        v.co.z -= zmin
    mesh.update()


def _ensure_uvs(mesh):
    """Add a box-projection UV layer when the bake produced none.

    The Cube node emits UVs, but they do not survive new_from_object as a UV
    layer. All templates are axis-aligned boxes, so a per-face dominant-axis
    projection is correct and satisfies the gate's missing_uv check headlessly.
    """
    if mesh.uv_layers or not mesh.polygons:
        return
    uv_layer = mesh.uv_layers.new(name="UVMap")
    for poly in mesh.polygons:
        normal = poly.normal
        axis = max(range(3), key=lambda i: abs(normal[i]))
        for loop_index in poly.loop_indices:
            co = mesh.vertices[mesh.loops[loop_index].vertex_index].co
            uv_layer.data[loop_index].uv = (co[(axis + 1) % 3], co[(axis + 2) % 3])
    mesh.update()


def instantiate(template, params=None, name=None, material=None):
    """Bake a template into a real, grounded mesh object in the scene."""
    group = get_group(template)
    params = params or {}

    ident = _input_identifiers(group)
    unknown = [key for key in params if key not in ident]
    if unknown:
        raise KeyError(f"unknown param(s) {unknown} for template {template!r}; inputs: {sorted(ident)}")

    mesh = bpy.data.meshes.new(f"{TEMPLATE_PREFIX}{template}")
    obj = bpy.data.objects.new(name or f"{template}_inst", mesh)
    bpy.context.scene.collection.objects.link(obj)

    modifier = obj.modifiers.new("GeometryNodes", "NODES")
    modifier.node_group = group
    for key, value in params.items():
        # All template inputs are floats; an int does not stick on the float
        # idproperty slot, so coerce numeric params (RPC JSON sends 10 not 10.0).
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            value = float(value)
        modifier.properties.inputs[ident[key]]["value"] = value

    deps = bpy.context.evaluated_depsgraph_get()
    deps.update()
    ev = obj.evaluated_get(deps)
    baked = bpy.data.meshes.new_from_object(ev)
    obj.modifiers.clear()
    old = obj.data
    obj.data = baked
    if old.users == 0:
        bpy.data.meshes.remove(old)
    _ground(obj.data)
    _ensure_uvs(obj.data)

    if template in ASSEMBLIES:
        obj["assembly"] = True

    if material:
        mat = get_material(material)
        if mat is None:
            raise KeyError(f"unknown material {material!r}; available: {sorted(MATERIALS)}")
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    return obj


def available_materials():
    return {name: description for name, (description, _) in MATERIALS.items()}
