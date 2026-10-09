"""Asset export: glTF (default), FBX, USD. Blender 5.2 renamed the glTF
apply-modifiers flag to export_apply; FBX still uses use_mesh_modifiers; call_op
drops any kwarg the installed RNA signature does not know."""

import os

import bpy

from rpc.base import WorkerError, call_op

EXPORT_OPS = {
    "glb": lambda path, apply: call_op(
        bpy.ops.export_scene.gltf, filepath=path, export_format="GLB", export_apply=apply
    ),
    "gltf": lambda path, apply: call_op(
        bpy.ops.export_scene.gltf, filepath=path, export_format="GLTF_SEPARATE", export_apply=apply
    ),
    "fbx": lambda path, apply: call_op(
        bpy.ops.export_scene.fbx, filepath=path, use_mesh_modifiers=apply, path_mode="COPY"
    ),
    "usd": lambda path, apply: call_op(bpy.ops.wm.usd_export, filepath=path, export_animation=False),
}


def cmd_export(params):
    path = params.get("path")
    if not path:
        raise WorkerError("BadRequest", "export requires params.path")
    fmt = str(params.get("format", "glb")).lower()
    if fmt not in EXPORT_OPS:
        raise WorkerError("BadRequest", f"unknown format {fmt}; expected one of {sorted(EXPORT_OPS)}")
    apply_modifiers = bool(params.get("apply_modifiers", True))
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    EXPORT_OPS[fmt](path, apply_modifiers)
    if not os.path.exists(path):
        raise WorkerError("ExportFailed", f"exporter did not write {path}")
    return {"path": path, "bytes": os.path.getsize(path), "format": fmt}