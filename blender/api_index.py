"""Live bpy symbol index for hallucination checks (gate stage 2).

Built by walking the *installed* Blender's modules — the only source of truth that
cannot drift from the runtime. Cached to $AXIOM3D_ROOT/.axiom3d/api_index.json
keyed by bpy.app.version_string; a cache from another Blender version is discarded
and rebuilt. Run standalone under Blender's Python to dump the index for corpus
use:  blender --background --factory-startup --python api_index.py
"""

import json
import os
import time

ROOT = os.environ.get("AXIOM3D_ROOT") or os.getcwd()
AXIOM_DIR = os.path.join(ROOT, ".axiom3d")
INDEX_FILE = os.path.join(AXIOM_DIR, "api_index.json")


def build_index():
    """Walk bpy.ops / bpy.types / bpy.data / bpy.props / bpy.app / bmesh.ops.

    bpy.ops is the tricky part: getattr on a missing operator does NOT raise (it
    returns a stub that only fails at call time), so hasattr lies. dir() membership
    is the honest check.
    """
    import bmesh
    import bpy

    ops = {}
    for name in sorted(dir(bpy.ops)):
        if name.startswith("_"):
            continue
        module = getattr(bpy.ops, name, None)
        if module is None:
            continue
        members = [member for member in dir(module) if not member.startswith("_")]
        if members:
            ops[name] = members

    data = []
    collections = {}
    for name in sorted(dir(bpy.data)):
        if name.startswith("_"):
            continue
        data.append(name)
        collection = getattr(bpy.data, name, None)
        if collection is None:
            continue
        try:
            members = [member for member in dir(collection) if not member.startswith("_")]
        except Exception:  # noqa: BLE001 - some bpy proxies refuse dir(); skip them
            continue
        if "new" in members:
            collections[name] = members

    return {
        "version": bpy.app.version_string,
        "built_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "bpy": [name for name in dir(bpy) if not name.startswith("_")],
        "ops": ops,
        "types": [name for name in dir(bpy.types) if not name.startswith("_")],
        "data": data,
        "collections": collections,
        "props": [name for name in dir(bpy.props) if not name.startswith("_")],
        "app": [name for name in dir(bpy.app) if not name.startswith("_")],
        "bmesh_ops": [name for name in dir(bmesh.ops) if not name.startswith("_")],
    }


def load_or_build():
    import bpy

    cached = None
    try:
        with open(INDEX_FILE, "r", encoding="utf-8") as handle:
            cached = json.load(handle)
    except (OSError, ValueError):
        pass
    if cached and cached.get("version") == bpy.app.version_string:
        return cached

    index = build_index()
    os.makedirs(AXIOM_DIR, exist_ok=True)
    tmp = INDEX_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as handle:
        json.dump(index, handle)
    os.replace(tmp, INDEX_FILE)
    return index


if __name__ == "__main__":
    print(json.dumps(build_index(), indent=2))
