"""Geometry Nodes template builders for the Axiom3D asset library.

Each builder returns a fully-wired GeometryNodeTree with exposed float inputs.
Every template is cube-based: the Cube node emits a UV Map, so baked instances
carry UVs and pass the gate's missing_uv check without a post-hoc unwrap. The
sleeper/fence/column/truss templates instance cubes along a self-generated
CurveLine (Resample by Length), so agents set parameters and never build node
trees — locked decision #6.

Blender 5.2 API notes (probed 2026-10-09, these drift across versions):
  - GN modifier inputs are NOT idproperties. They live under
    mod.properties.inputs[<identifier>]["value"] (an IDPropertyGroup per socket).
  - Curve Line mode "DIRECTION" exposes Direction + Length; mode "POINTS" exposes
    Start + End. We use DIRECTION so a Length input drives the line.
  - ShaderNodeCombineXYZ / ShaderNodeMath are usable inside a GeometryNodeTree.
  - Instances are realized so the baked mesh is real geometry for gate/export.
"""

import bpy

PREFIX = "Axiom3D_"


def _new_group(label, params):
    """Create a node tree with float input sockets + one Geometry output.

    params: list of (name, default, min, max). Returns (group, gin, gout).
    """
    group = bpy.data.node_groups.new(PREFIX + label, "GeometryNodeTree")
    for name, default, lo, hi in params:
        sock = group.interface.new_socket(name, in_out="INPUT", socket_type="NodeSocketFloat")
        sock.default_value = default
        if lo is not None:
            sock.min_value = lo
        if hi is not None:
            sock.max_value = hi
    group.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    gin = group.nodes.new("NodeGroupInput")
    gout = group.nodes.new("NodeGroupOutput")
    return group, gin, gout


def _combine(group, gin, axes):
    """CombineXYZ whose X/Y/Z come from group-input sockets or float literals."""
    node = group.nodes.new("ShaderNodeCombineXYZ")
    for axis, source in axes.items():
        if isinstance(source, str):
            group.links.new(gin.outputs[source], node.inputs[axis])
        else:
            node.inputs[axis].default_value = source
    return node


def _cube_from(group, gin, axes):
    """Cube node whose Size vector is driven by group inputs / literals."""
    cube = group.nodes.new("GeometryNodeMeshCube")
    comb = _combine(group, gin, axes)
    group.links.new(comb.outputs[0], cube.inputs["Size"])
    return cube


def _curve_line(group, gin, length_name):
    """Straight CurveLine along +X, centered on the origin (Start = -Length/2).

    Centering keeps the run aligned with the Cube-based instances (which are
    centered at the origin), so chords/posts/sleepers and their rails line up.
    """
    line = group.nodes.new("GeometryNodeCurvePrimitiveLine")
    line.mode = "DIRECTION"
    half = group.nodes.new("ShaderNodeMath")
    half.operation = "MULTIPLY"
    group.links.new(gin.outputs[length_name], half.inputs[0])
    half.inputs[1].default_value = -0.5
    comb = group.nodes.new("ShaderNodeCombineXYZ")
    group.links.new(half.outputs[0], comb.inputs["X"])
    group.links.new(comb.outputs[0], line.inputs["Start"])
    line.inputs["Direction"].default_value = (1.0, 0.0, 0.0)
    group.links.new(gin.outputs[length_name], line.inputs["Length"])
    return line


def _resample(group, gin, line, spacing_name):
    """Evenly space points along the line at the given spacing (Length mode)."""
    resample = group.nodes.new("GeometryNodeResampleCurve")
    group.links.new(line.outputs["Curve"], resample.inputs["Curve"])
    resample.inputs["Mode"].default_value = "Length"
    group.links.new(gin.outputs[spacing_name], resample.inputs["Length"])
    return resample


def _instance_on_points(group, points_socket, instance_socket):
    node = group.nodes.new("GeometryNodeInstanceOnPoints")
    group.links.new(points_socket, node.inputs["Points"])
    group.links.new(instance_socket, node.inputs["Instance"])
    return node


def _realize(group, geometry_socket):
    node = group.nodes.new("GeometryNodeRealizeInstances")
    group.links.new(geometry_socket, node.inputs["Geometry"])
    return node


def _transform_up(group, gin, geometry_socket, z_source):
    """Translate geometry up along Z by a group input (str) or literal (float)."""
    node = group.nodes.new("GeometryNodeTransform")
    group.links.new(geometry_socket, node.inputs["Geometry"])
    comb = _combine(group, gin, {"Z": z_source})
    group.links.new(comb.outputs[0], node.inputs["Translation"])
    return node


def build_rail_segment():
    group, gin, gout = _new_group(
        "RailSegment",
        [("Length", 6.0, 0.1, 1000.0), ("Width", 0.07, 0.01, 1.0), ("Height", 0.05, 0.01, 1.0)],
    )
    cube = _cube_from(group, gin, {"X": "Length", "Y": "Width", "Z": "Height"})
    group.links.new(cube.outputs["Mesh"], gout.inputs[0])
    return group


def build_sleeper_array():
    group, gin, gout = _new_group(
        "SleeperArray",
        [
            ("Length", 12.0, 0.5, 1000.0),
            ("Spacing", 0.6, 0.1, 10.0),
            ("Width", 2.6, 0.1, 10.0),
            ("Depth", 0.25, 0.02, 2.0),
            ("Height", 0.18, 0.02, 2.0),
        ],
    )
    line = _curve_line(group, gin, "Length")
    resample = _resample(group, gin, line, "Spacing")
    # sleepers run across the track (Y = Width) and are thin along it (X = Depth),
    # so adjacent sleepers at Spacing never overlap
    sleeper = _cube_from(group, gin, {"X": "Depth", "Y": "Width", "Z": "Height"})
    inst = _instance_on_points(group, resample.outputs["Curve"], sleeper.outputs["Mesh"])
    real = _realize(group, inst.outputs["Instances"])
    group.links.new(real.outputs["Geometry"], gout.inputs[0])
    return group


def build_column_grid():
    group, gin, gout = _new_group(
        "ColumnGrid",
        [
            ("Width", 8.0, 0.5, 1000.0),
            ("Depth", 6.0, 0.5, 1000.0),
            ("Count X", 3, 2, 100),
            ("Count Y", 3, 2, 100),
            ("Height", 4.0, 0.1, 100.0),
            ("Size", 0.3, 0.02, 5.0),
        ],
    )
    grid = group.nodes.new("GeometryNodeMeshGrid")
    group.links.new(gin.outputs["Width"], grid.inputs["Size X"])
    group.links.new(gin.outputs["Depth"], grid.inputs["Size Y"])
    group.links.new(gin.outputs["Count X"], grid.inputs["Vertices X"])
    group.links.new(gin.outputs["Count Y"], grid.inputs["Vertices Y"])
    column = _cube_from(group, gin, {"X": "Size", "Y": "Size", "Z": "Height"})
    inst = _instance_on_points(group, grid.outputs["Mesh"], column.outputs["Mesh"])
    real = _realize(group, inst.outputs["Instances"])
    group.links.new(real.outputs["Geometry"], gout.inputs[0])
    return group


def build_fence_run():
    group, gin, gout = _new_group(
        "FenceRun",
        [
            ("Length", 10.0, 0.5, 1000.0),
            ("Post Spacing", 2.0, 0.3, 50.0),
            ("Post Height", 1.2, 0.2, 10.0),
            ("Post Size", 0.08, 0.02, 1.0),
            ("Rail Height", 0.9, 0.1, 9.0),
            ("Rail Size", 0.05, 0.01, 1.0),
        ],
    )
    line = _curve_line(group, gin, "Length")
    resample = _resample(group, gin, line, "Post Spacing")
    post = _cube_from(group, gin, {"X": "Post Size", "Y": "Post Size", "Z": "Post Height"})
    inst = _instance_on_points(group, resample.outputs["Curve"], post.outputs["Mesh"])
    posts = _realize(group, inst.outputs["Instances"])
    rail = _cube_from(group, gin, {"X": "Length", "Y": "Rail Size", "Z": "Rail Size"})
    rail_up = _transform_up(group, gin, rail.outputs["Mesh"], "Rail Height")
    join = group.nodes.new("GeometryNodeJoinGeometry")
    group.links.new(posts.outputs["Geometry"], join.inputs[0])
    group.links.new(rail_up.outputs["Geometry"], join.inputs[0])
    group.links.new(join.outputs[0], gout.inputs[0])
    return group


def build_platform_outline():
    group, gin, gout = _new_group(
        "PlatformOutline",
        [("Width", 20.0, 0.5, 1000.0), ("Depth", 4.0, 0.5, 500.0), ("Height", 0.9, 0.1, 10.0)],
    )
    cube = _cube_from(group, gin, {"X": "Width", "Y": "Depth", "Z": "Height"})
    group.links.new(cube.outputs["Mesh"], gout.inputs[0])
    return group


def build_canopy_truss():
    group, gin, gout = _new_group(
        "CanopyTruss",
        [("Span", 8.0, 0.5, 200.0), ("Depth", 1.2, 0.1, 20.0), ("Bay", 2.0, 0.3, 50.0), ("Member", 0.15, 0.02, 2.0)],
    )
    bottom = _cube_from(group, gin, {"X": "Span", "Y": "Member", "Z": "Member"})
    top = _cube_from(group, gin, {"X": "Span", "Y": "Member", "Z": "Member"})
    top_up = _transform_up(group, gin, top.outputs["Mesh"], "Depth")
    line = _curve_line(group, gin, "Span")
    resample = _resample(group, gin, line, "Bay")
    vert = _cube_from(group, gin, {"X": "Member", "Y": "Member", "Z": "Depth"})
    # verticals span the truss Depth, centered on Depth/2 so they bridge the chords
    half = group.nodes.new("ShaderNodeMath")
    half.operation = "MULTIPLY"
    group.links.new(gin.outputs["Depth"], half.inputs[0])
    half.inputs[1].default_value = 0.5
    vert_up = group.nodes.new("GeometryNodeTransform")
    group.links.new(vert.outputs["Mesh"], vert_up.inputs["Geometry"])
    comb = group.nodes.new("ShaderNodeCombineXYZ")
    group.links.new(half.outputs[0], comb.inputs["Z"])
    group.links.new(comb.outputs[0], vert_up.inputs["Translation"])
    inst = _instance_on_points(group, resample.outputs["Curve"], vert_up.outputs["Geometry"])
    verts = _realize(group, inst.outputs["Instances"])
    join = group.nodes.new("GeometryNodeJoinGeometry")
    group.links.new(bottom.outputs["Mesh"], join.inputs[0])
    group.links.new(top_up.outputs["Geometry"], join.inputs[0])
    group.links.new(verts.outputs["Geometry"], join.inputs[0])
    group.links.new(join.outputs[0], gout.inputs[0])
    return group


BUILDERS = {
    "rail_segment": ("Extruded rail profile (box) of a given length along X.", build_rail_segment),
    "sleeper_array": ("Railway sleepers evenly spaced along a straight track run.", build_sleeper_array),
    "column_grid": ("Grid of vertical columns (buildings, platforms, canopies).", build_column_grid),
    "fence_run": ("Post-and-rail fence along a straight run.", build_fence_run),
    "platform_outline": ("Station platform slab (width x depth x height).", build_platform_outline),
    "canopy_truss": ("Simplified through-truss: two chords + vertical webs over a span.", build_canopy_truss),
}
