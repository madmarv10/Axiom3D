"""Curated Blender 5.0-5.2 breaking changes relevant to the Axiom3D harness.

Hand-curated (not fetched) from the changes this project actually hit, plus the
well-known 5.x renames. Each entry is version-true for the pinned Blender 5.2
install. Search matches on keywords + the version + the affected API surface.
"""

ENTRIES = [
    {
        "id": "gltf-apply-modifiers",
        "versions": ["4.0", "5.0"],
        "surface": "bpy.ops.export_scene.gltf",
        "summary": "use_mesh_modifiers was renamed to export_apply on the glTF exporter.",
        "detail": "Passing use_mesh_modifiers is silently dropped (call_op filters unknown "
        "kwargs). Use export_apply=True to apply modifiers on export.",
        "keywords": ["gltf", "export", "modifiers", "export_apply", "use_mesh_modifiers"],
    },
    {
        "id": "gn-modifier-inputs",
        "versions": ["5.0"],
        "surface": "GeometryNodes modifier",
        "summary": "GN modifier inputs are no longer idproperties (mod[ident]=val fails).",
        "detail": "Read/write them via mod.properties.inputs[<identifier>]['value']. Each "
        "socket is an IDPropertyGroup with keys value/type/attribute_name. Identifier "
        "comes from the node-group interface item (e.g. 'Socket_0').",
        "keywords": ["geometry", "nodes", "modifier", "inputs", "properties", "idprop", "socket"],
    },
    {
        "id": "int-not-float-slot",
        "versions": ["5.0"],
        "surface": "GN modifier inputs",
        "summary": "An int does not stick on a float modifier-input slot.",
        "detail": "Coerce numeric params to float before assigning "
        "mod.properties.inputs[id]['value'] — RPC JSON sends 10 not 10.0 and the int is dropped.",
        "keywords": ["geometry", "nodes", "modifier", "int", "float", "coerce", "socket"],
    },
    {
        "id": "curve-tangent-rename",
        "versions": ["5.0"],
        "surface": "GeometryNodeInputTangent",
        "summary": "The curve Tangent node is GeometryNodeInputTangent (was GeometryNodeCurveTangent).",
        "detail": "Access the tangent via the node's 'Tangent' output. The old "
        "GeometryNodeCurveTangent identifier is undefined in 5.x.",
        "keywords": ["curve", "tangent", "geometry", "nodes", "rename"],
    },
    {
        "id": "manifold-boolean-crash",
        "versions": ["5.2"],
        "surface": "Boolean modifier solver",
        "summary": "The MANIFOLD solver can hard-crash Blender on multi-shell input.",
        "detail": "During verification, MANIFOLD raised an access violation on some "
        "multi-component template geometry. Use the EXACT solver for reliability; MANIFOLD "
        "is faster but not safe on arbitrary/jammed meshes.",
        "keywords": ["boolean", "manifold", "exact", "solver", "crash", "intersection"],
    },
    {
        "id": "use-nodes-deprecated",
        "versions": ["5.2"],
        "surface": "Material.use_nodes",
        "summary": "Material.use_nodes is deprecated (removal planned for 6.0).",
        "detail": "Still functional in 5.2 but emits a DeprecationWarning. Prefer creating "
        "a ShaderNodeTree node group when you only need to introspect/build shader nodes.",
        "keywords": ["material", "shader", "nodes", "use_nodes", "deprecat"],
    },
]


def search(text):
    """Return entries whose keywords/summary/detail match the query tokens."""
    tokens = set(text.lower().split())
    hits = []
    for entry in ENTRIES:
        haystack = " ".join(
            [entry["summary"], entry["detail"], entry["surface"], " ".join(entry["keywords"])]
        ).lower()
        if any(token in haystack for token in tokens if len(token) > 2):
            hits.append(entry)
    return hits
