"""Live bpy introspection — the most version-true API source.

Reading socket names, types, defaults, and method lists straight from the
installed Blender beats fetching docs.blender.org, which can silently mismatch a
local build. This backs the ``blender_docs`` command's answer to queries like
"Principled BSDF sockets in 5.2" by resolving the human name to a bpy.types node
class, instantiating it in a throwaway node tree, and listing its real sockets.
"""

import re

import bpy

_NODE_PREFIXES = ("ShaderNode", "GeometryNode", "FunctionNode")


def _normalize(text):
    return re.sub(r"[^a-z0-9]", "", text.lower())


def _camel_tokens(name):
    """Split CamelCase into lowercase words: "BsdfPrincipled" -> {bsdf, principled}."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    return set(re.findall(r"[a-z0-9]+", spaced.lower()))


def resolve_node(text):
    """Resolve a human node name ("Principled BSDF") to a bpy.types class name.

    Returns the best node class, or None. A node is only chosen on a confident
    match: exact/normalized substring (score >= 10) or at least two camelCase
    token overlaps. A lone generic token ("apply") must not resolve a node.
    Ties prefer the shorter core name, so "cube" -> MeshCube not CubeGridTopology.
    """
    query_norm = _normalize(text)
    query_tokens = set(re.findall(r"[a-z0-9]+", text.lower()))
    best, best_key = None, None
    for name in dir(bpy.types):
        if not name.startswith(_NODE_PREFIXES):
            continue
        core = name
        for prefix in _NODE_PREFIXES:
            if core.startswith(prefix):
                core = core[len(prefix) :]
                break
        core_norm = _normalize(core)
        if not core_norm:
            continue  # bare "FunctionNode" etc. — nothing to match
        base = 0
        if query_norm == core_norm:
            base = 100
        elif query_norm in core_norm or core_norm in query_norm:
            base = 10 + min(len(query_norm), len(core_norm))
        token_score = len(query_tokens & _camel_tokens(core))
        if base < 10 and token_score < 2:
            continue  # not a confident match
        key = (base + token_score, -len(core_norm))
        if best_key is None or key > best_key:
            best, best_key = name, key
    return best


def _jsonable(value):
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    try:
        return [round(float(v), 6) for v in value]  # bpy float arrays (Vector/Color)
    except TypeError:
        return str(value)


def node_sockets(class_name):
    """Instantiate a node in a throwaway tree and list its real input/output sockets.

    Returns None when the node type cannot be instantiated standalone (some special
    nodes like simulation-state consumers are undefined outside their context).
    """
    is_shader = class_name.startswith("ShaderNode")
    tree_type = "ShaderNodeTree" if is_shader else "GeometryNodeTree"
    tree = bpy.data.node_groups.new("axiom3d_probe", tree_type)
    try:
        try:
            node = tree.nodes.new(class_name)
        except RuntimeError:
            return None
        inputs = [
            {
                "name": socket.name,
                "type": socket.type,
                "enabled": socket.enabled,
                "default": _jsonable(getattr(socket, "default_value", None)),
            }
            for socket in node.inputs
        ]
        outputs = [{"name": socket.name, "type": socket.type} for socket in node.outputs]
        return {"inputs": inputs, "outputs": outputs}
    finally:
        bpy.data.node_groups.remove(tree)


def type_info(type_name):
    """List an RNA type's methods and properties (names only)."""
    rna = getattr(bpy.types, type_name, None)
    if rna is None:
        return None
    methods, properties = [], []
    for name in dir(rna):
        if name.startswith("_"):
            continue
        attr = getattr(rna, name, None)
        if callable(attr):
            methods.append(name)
        else:
            properties.append(name)
    return {"type": type_name, "methods": methods, "properties": properties}


def query(text):
    """Best-effort live answer: node sockets for a node name, else an RNA type."""
    node_class = resolve_node(text)
    if node_class:
        sockets = node_sockets(node_class)
        if sockets is not None:
            return {
                "kind": "node",
                "class": node_class,
                "inputs": sockets["inputs"],
                "outputs": sockets["outputs"],
            }
    type_name = text if hasattr(bpy.types, text) else None
    if type_name is None:
        # try a normalized match against bpy.types class names
        target = _normalize(text)
        for name in dir(bpy.types):
            if not name.startswith("_") and _normalize(name) == target:
                type_name = name
                break
    if type_name:
        info = type_info(type_name)
        if info:
            return {"kind": "type", **info}
    return {"kind": "unknown", "query": text}
