"""Axiom3D persistent Blender worker.

Runs inside headless Blender:  blender --background --factory-startup --python worker.py

Starts a localhost TCP server speaking newline-delimited JSON:
  request  {"id": 1, "cmd": "exec", "params": {...}}
  response {"id": 1, "ok": true, "result": {...}} | {"id": 1, "ok": false, "error": {...}}

Commands: ping, exec, snapshot, restore, reset, query, render, export, validate.

Safety model:
  - every exec auto-snapshots the scene first (snapshot id in port file)
  - exec runs with a soft timeout; on timeout the worker marks itself poisoned and
    refuses scene-mutating commands until restart (the client kills and restarts it,
    then restores the pre-exec snapshot)
  - operator calls are filtered through their RNA signatures so argument drift in a
    newer Blender degrades to "argument ignored" instead of a crash

State files live under $AXIOM3D_ROOT/.axiom3d/ (port file, snapshots, log).
"""

import io
import json
import os
import queue
import re
import socketserver
import sys
import threading
import time
import traceback

import bmesh
import bpy
from mathutils import Vector

ROOT = os.environ.get("AXIOM3D_ROOT") or os.getcwd()
AXIOM_DIR = os.path.join(ROOT, ".axiom3d")
PORT_FILE = os.path.join(AXIOM_DIR, "blender.port")
SNAP_DIR = os.path.join(AXIOM_DIR, "snapshots")
LOG_FILE = os.path.join(AXIOM_DIR, "worker.log")
SNAP_KEEP = 10
DEFAULT_POLY_BUDGET = 100_000

# bpy is main-thread-only: handler threads enqueue jobs, the main thread pumps them.
JOBS: queue.Queue = queue.Queue()
PORT_LOCK = threading.Lock()
STATE = {"started": time.monotonic(), "poisoned": False, "last_snapshot": None, "seq": 0, "version": ""}


class WorkerError(Exception):
    def __init__(self, type_, message):
        super().__init__(message)
        self.type = type_
        self.message = message


def log_error():
    with open(LOG_FILE, "a", encoding="utf-8") as handle:
        handle.write(f"--- {time.strftime('%Y-%m-%d %H:%M:%S')} ---\n")
        handle.write(traceback.format_exc())
        handle.write("\n")


def write_port_file():
    payload = {
        "port": write_port_file.port,
        "pid": os.getpid(),
        "version": STATE["version"],
        "last_snapshot": STATE["last_snapshot"],
        "poisoned": STATE["poisoned"],
    }
    tmp = PORT_FILE + ".tmp"
    with PORT_LOCK:
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        os.replace(tmp, PORT_FILE)


def call_op(op, **kwargs):
    """Call a bpy operator, dropping kwargs its RNA signature does not know."""
    known = {p.identifier for p in op.get_rna_type().properties if p.identifier != "rna_type"}
    filtered = {k: v for k, v in kwargs.items() if k in known}
    return op(**filtered)


def scene_summary():
    summary = {}
    for obj in bpy.data.objects:
        if obj.type == "MESH":
            summary[obj.name] = (obj.type, len(obj.data.vertices), len(obj.data.materials))
        else:
            summary[obj.name] = (obj.type, -1, 0)
    return summary


def scene_diff(before, after):
    added = [name for name in after if name not in before]
    removed = [name for name in before if name not in after]
    modified = [name for name in after if name in before and after[name] != before[name]]
    return {"added": added, "removed": removed, "modified": modified}


def require_live(operation):
    if STATE["poisoned"] and operation != "ping":
        raise WorkerError("WorkerPoisoned", "worker poisoned by timed-out exec; client must restart it")


# ---------------------------------------------------------------- snapshots


def cmd_snapshot(params):
    STATE["seq"] += 1
    label = re.sub(r"[^a-z0-9_-]", "_", str(params.get("label", "manual")).lower())[:32]
    snap_id = f"snap{STATE['seq']:04d}_{label}"
    path = os.path.join(SNAP_DIR, snap_id + ".blend")
    os.makedirs(SNAP_DIR, exist_ok=True)
    call_op(bpy.ops.wm.save_as_mainfile, filepath=path, copy=True)
    if not os.path.exists(path):
        raise WorkerError("SnapshotFailed", f"snapshot file not written: {path}")
    STATE["last_snapshot"] = snap_id
    write_port_file()
    prune = sorted(f for f in os.listdir(SNAP_DIR) if f.endswith(".blend"))
    for old in prune[: max(0, len(prune) - SNAP_KEEP)]:
        os.remove(os.path.join(SNAP_DIR, old))
    return {"id": snap_id, "path": path}


def cmd_restore(params):
    snap_id = params.get("id")
    if not snap_id:
        raise WorkerError("BadRequest", "restore requires params.id")
    path = os.path.join(SNAP_DIR, snap_id + ".blend")
    if not os.path.exists(path):
        raise WorkerError("NotFound", f"no snapshot {snap_id}")
    result = call_op(bpy.ops.wm.open_mainfile, filepath=path)
    if "FINISHED" not in result:
        raise WorkerError("RestoreFailed", f"open_mainfile returned {result}")
    STATE["poisoned"] = False
    STATE["last_snapshot"] = snap_id
    write_port_file()
    return {"restored": snap_id}


def cmd_reset(params):
    call_op(bpy.ops.wm.read_factory_settings, use_empty=True)
    STATE["poisoned"] = False
    write_port_file()
    return {"reset": True}


# ---------------------------------------------------------------- exec


def cmd_exec(params):
    require_live("exec")
    code = params.get("code")
    if not isinstance(code, str) or not code.strip():
        raise WorkerError("BadRequest", "exec requires params.code (non-empty string)")

    if params.get("snapshot", True):
        cmd_snapshot({"label": "auto-exec"})

    before = scene_summary()
    out, err = io.StringIO(), io.StringIO()
    error = None
    namespace = {"bpy": bpy, "__builtins__": __builtins__, "__name__": "__axiom3d_exec__"}

    old_out, old_err = sys.stdout, sys.stderr
    sys.stdout, sys.stderr = out, err
    started = time.monotonic()
    try:
        exec(compile(code, "<axiom3d>", "exec"), namespace)
    except SystemExit:
        error = None
    except BaseException as exc:  # noqa: BLE001 - report any script failure verbatim
        error = {
            "type": type(exc).__name__,
            "message": str(exc),
            "traceback": traceback.format_exc(),
        }
    finally:
        sys.stdout, sys.stderr = old_out, old_err
    duration_ms = int((time.monotonic() - started) * 1000)

    after = scene_summary()
    result = {
        "stdout": out.getvalue(),
        "stderr": err.getvalue(),
        "error": error,
        "duration_ms": duration_ms,
        "snapshot": STATE["last_snapshot"],
        "scene_diff": scene_diff(before, after),
    }
    if error:
        raise ExecScriptError(result)
    return result


class ExecScriptError(WorkerError):
    def __init__(self, result):
        super().__init__(result["error"]["type"], result["error"]["message"])
        self.result = result


# ---------------------------------------------------------------- query


def cmd_query(params):
    kind = params.get("kind", "summary")
    if kind == "summary":
        counts = {}
        for obj in bpy.data.objects:
            counts[obj.type] = counts.get(obj.type, 0) + 1
        return {
            "version": bpy.app.version_string,
            "file": bpy.data.filepath,
            "objects": counts,
            "materials": len(bpy.data.materials),
            "node_groups": len(bpy.data.node_groups),
            "unit": {
                "system": bpy.context.scene.unit_settings.system,
                "scale_length": bpy.context.scene.unit_settings.scale_length,
            },
            "engine": bpy.context.scene.render.engine,
            "poisoned": STATE["poisoned"],
            "last_snapshot": STATE["last_snapshot"],
        }
    if kind == "objects":
        objects = []
        for obj in bpy.data.objects:
            entry = {
                "name": obj.name,
                "type": obj.type,
                "location": [round(v, 6) for v in obj.location],
                "rotation_euler": [round(v, 6) for v in obj.rotation_euler],
                "scale": [round(v, 6) for v in obj.scale],
                "dimensions": [round(v, 6) for v in obj.dimensions],
                "parent": obj.parent.name if obj.parent else None,
                "visible": not obj.hide_render and not obj.hide_viewport,
                "materials": [m.name for m in obj.data.materials] if obj.type == "MESH" else [],
                "modifiers": [{"name": m.name, "type": m.type} for m in obj.modifiers],
            }
            if obj.type == "MESH":
                entry["vertices"] = len(obj.data.vertices)
                entry["polygons"] = len(obj.data.polygons)
                entry["uv_layers"] = [uv.name for uv in obj.data.uv_layers]
            objects.append(entry)
        return {"objects": objects}
    if kind == "materials":
        return {
            "materials": [
                {
                    "name": mat.name,
                    "users": mat.users,
                    "has_nodes": mat.use_nodes,
                    "nodes": len(mat.node_tree.nodes) if mat.use_nodes and mat.node_tree else 0,
                }
                for mat in bpy.data.materials
            ]
        }
    if kind == "node_groups":
        groups = []
        for group in bpy.data.node_groups:
            groups.append(
                {
                    "name": group.name,
                    "type": group.type,
                    "inputs": [
                        {"name": item.name, "type": item.socket_type}
                        for item in group.interface.items_tree
                        if getattr(item, "item_type", "") == "SOCKET" and item.in_out == "INPUT"
                    ],
                }
            )
        return {"node_groups": groups}
    raise WorkerError("BadRequest", f"unknown query kind: {kind}")


# ---------------------------------------------------------------- render

ENGINE_CANDIDATES = {
    "WORKBENCH": ["BLENDER_WORKBENCH"],
    "EEVEE": ["BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"],
    "CYCLES": ["CYCLES"],
}

VIEW_DIRECTIONS = [
    ("front", (1, 0, 0)),
    ("back", (-1, 0, 0)),
    ("left", (0, 1, 0)),
    ("right", (0, -1, 0)),
    ("top", (0, 0, 1)),
    ("iso", (1, 1, 1)),
]


def set_engine(scene, key):
    for ident in ENGINE_CANDIDATES.get(key, []):
        try:
            scene.render.engine = ident
            return ident
        except TypeError:
            continue
    raise WorkerError("RenderEngine", f"engine {key} unavailable, tried {ENGINE_CANDIDATES.get(key)}")


def scene_bounds():
    corners = []
    for obj in bpy.data.objects:
        if obj.type != "MESH" or obj.hide_render:
            continue
        corners.extend(obj.matrix_world @ Vector(corner) for corner in obj.bound_box)
    if not corners:
        raise WorkerError("NothingToRender", "no renderable mesh objects in scene")
    minimum = Vector(tuple(min(c[i] for c in corners) for i in range(3)))
    maximum = Vector(tuple(max(c[i] for c in corners) for i in range(3)))
    center = (minimum + maximum) / 2
    radius = max((corner - center).length for corner in corners) or 1.0
    return center, radius


def cmd_render(params):
    scene = bpy.context.scene
    outdir = params.get("outdir") or os.path.join(AXIOM_DIR, "render", time.strftime("%Y%m%d_%H%M%S"))
    os.makedirs(outdir, exist_ok=True)
    key = str(params.get("engine", "WORKBENCH")).upper()
    width = int(params.get("width", 960))
    height = int(params.get("height", 540))

    saved = {
        "engine": scene.render.engine,
        "camera": scene.camera,
        "resolution": (scene.render.resolution_x, scene.render.resolution_y),
    }
    engine_used = set_engine(scene, key)

    camera_data = bpy.data.cameras.new("axiom3d_render_cam")
    camera = bpy.data.objects.new("axiom3d_render_cam", camera_data)
    scene.collection.objects.link(camera)
    scene.camera = camera

    sun = None
    if engine_used != "BLENDER_WORKBENCH":
        sun_data = bpy.data.lights.new("axiom3d_render_sun", type="SUN")
        sun = bpy.data.objects.new("axiom3d_render_sun", sun_data)
        scene.collection.objects.link(sun)
        sun.location = (5, 5, 10)

    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.image_settings.file_format = "PNG"
    center, radius = scene_bounds()
    wanted = params.get("views")
    views = [v for v in VIEW_DIRECTIONS if not wanted or v[0] in wanted]
    if not views:
        raise WorkerError("BadRequest", f"no matching views for {wanted}")

    files = []
    try:
        for name, direction in views:
            direction_v = Vector(direction).normalized()
            camera.location = center + direction_v * (radius * 2.5)
            camera.rotation_euler = (center - camera.location).to_track_quat("-Z", "Y").to_euler()
            path = os.path.join(outdir, f"{name}.png")
            scene.render.filepath = path
            try:
                bpy.ops.render.render(write_still=True)
            except RuntimeError as exc:
                if key != "WORKBENCH":
                    set_engine(scene, "WORKBENCH")
                    engine_used = "BLENDER_WORKBENCH"
                    bpy.ops.render.render(write_still=True)
                else:
                    raise WorkerError("RenderFailed", str(exc))
            files.append(path)
    finally:
        for temp in (camera, sun):
            if temp:
                bpy.data.objects.remove(temp, do_unlink=True)
        scene.camera = saved["camera"]
        scene.render.engine = saved["engine"]
        scene.render.resolution_x, scene.render.resolution_y = saved["resolution"]
    return {"files": files, "engine_used": engine_used, "outdir": outdir}


# ---------------------------------------------------------------- export

EXPORT_OPS = {
    "glb": lambda path, apply: call_op(
        bpy.ops.export_scene.gltf, filepath=path, export_format="GLB", use_mesh_modifiers=apply
    ),
    "gltf": lambda path, apply: call_op(
        bpy.ops.export_scene.gltf, filepath=path, export_format="GLTF_SEPARATE", use_mesh_modifiers=apply
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


# ---------------------------------------------------------------- validate (basic; gate lands Phase 3)

DEFAULT_NAME = re.compile(r"^(Cube|Sphere|Cylinder|Plane|Circle|Torus|Suzanne|Monkey)(\.\d+)?$")
CLEAN_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def cmd_validate(params):
    issues = []
    unit = bpy.context.scene.unit_settings
    if unit.scale_length != 1.0:
        issues.append({"object": "<scene>", "issue": "unit_scale", "detail": f"scale_length={unit.scale_length}"})
    if unit.system == "NONE":
        issues.append({"object": "<scene>", "issue": "no_unit_system", "detail": "unit system is NONE"})

    for obj in bpy.data.objects:
        if obj.type != "MESH":
            continue
        if DEFAULT_NAME.match(obj.name):
            issues.append({"object": obj.name, "issue": "default_name", "detail": obj.name})
        elif not CLEAN_NAME.match(obj.name):
            issues.append({"object": obj.name, "issue": "bad_naming", "detail": "not snake_case"})
        if tuple(round(v, 6) for v in obj.scale) != (1.0, 1.0, 1.0):
            issues.append({"object": obj.name, "issue": "unapplied_scale", "detail": list(obj.scale)})
        if any(d < 0.001 for d in obj.dimensions):
            issues.append({"object": obj.name, "issue": "degenerate", "detail": list(obj.dimensions)})
        if obj.data.polygons and not obj.data.uv_layers:
            issues.append({"object": obj.name, "issue": "missing_uv", "detail": "no UV layers"})
        if len(obj.data.vertices) > DEFAULT_POLY_BUDGET:
            issues.append(
                {"object": obj.name, "issue": "over_budget", "detail": f"{len(obj.data.vertices)} verts"}
            )
        bm = bmesh.new()
        try:
            bm.from_mesh(obj.data)
            bad = sum(1 for edge in bm.edges if len(edge.link_faces) != 2)
        finally:
            bm.free()
        if bad:
            issues.append({"object": obj.name, "issue": "non_manifold", "detail": f"{bad} edges"})
    return {"phase": "basic", "issues": issues, "passed": not issues}


# ---------------------------------------------------------------- server


COMMANDS = {
    "exec": cmd_exec,
    "snapshot": cmd_snapshot,
    "restore": cmd_restore,
    "reset": cmd_reset,
    "query": cmd_query,
    "render": cmd_render,
    "export": cmd_export,
    "validate": cmd_validate,
}


def dispatch(request):
    cmd = request.get("cmd")
    params = request.get("params") or {}
    handler = COMMANDS.get(cmd)
    if not handler:
        raise WorkerError("UnknownCommand", f"unknown command: {cmd}")
    require_live(cmd)
    try:
        return {"ok": True, "result": handler(params)}
    except ExecScriptError as exc:
        return {"ok": False, "error": {"type": exc.type, "message": exc.message, "result": exc.result}}
    except WorkerError as exc:
        return {"ok": False, "error": {"type": exc.type, "message": str(exc)}}


def ping_result():
    return {
        "version": STATE["version"],
        "pid": os.getpid(),
        "uptime_s": round(time.monotonic() - STATE["started"], 1),
        "poisoned": STATE["poisoned"],
        "last_snapshot": STATE["last_snapshot"],
    }


def handler_wait(cmd, params):
    """How long a handler thread waits for the main-thread pump before answering with a
    timeout error. Must stay under the client's rpc timeout so the answer wins the race."""
    if cmd == "exec":
        return min(max(float(params.get("timeout", 30)), 1), 600) + 2
    if cmd == "render":
        return 300.0
    return 120.0


class Handler(socketserver.StreamRequestHandler):
    """Runs on a server thread. Never touches bpy: ping answers from cached STATE,
    everything else is queued for the main thread and awaited."""

    def handle(self):
        for raw in self.rfile:
            line = raw.decode("utf-8", "replace").strip()
            if not line:
                continue
            request_id = None
            try:
                request = json.loads(line)
                request_id = request.get("id")
                response = self.process(request)
            except Exception as exc:  # noqa: BLE001 - one bad request must not kill the loop
                log_error()
                response = {
                    "id": request_id,
                    "ok": False,
                    "error": {"type": type(exc).__name__, "message": str(exc)},
                }
            self.wfile.write((json.dumps(response) + "\n").encode("utf-8"))
            self.wfile.flush()

    def process(self, request):
        cmd = request.get("cmd")
        params = request.get("params") or {}
        if cmd == "ping":
            return {"id": request.get("id"), "ok": True, "result": ping_result()}
        done = threading.Event()
        box: dict = {}
        JOBS.put({"request": request, "done": done, "box": box})
        if done.wait(handler_wait(cmd, params)):
            return box["response"]
        if cmd == "exec":
            STATE["poisoned"] = True
            write_port_file()
            return {
                "id": request.get("id"),
                "ok": False,
                "error": {
                    "type": "ExecTimeout",
                    "message": f"exec exceeded {params.get('timeout', 30)}s and is still running on "
                    "the main thread. Worker poisoned: client must restart and restore.",
                },
            }
        return {
            "id": request.get("id"),
            "ok": False,
            "error": {"type": "ServerTimeout", "message": f"{cmd} did not finish in time; worker busy?"},
        }


def main():
    os.makedirs(AXIOM_DIR, exist_ok=True)
    os.makedirs(SNAP_DIR, exist_ok=True)
    sys.excepthook = lambda *args: log_error()
    STATE["version"] = bpy.app.version_string
    server = socketserver.ThreadingTCPServer(("127.0.0.1", 0), Handler)
    server.daemon_threads = True
    write_port_file.port = server.server_address[1]
    write_port_file()
    threading.Thread(target=server.serve_forever, name="axiom3d-accept", daemon=True).start()
    print(f"AXIOM3D_WORKER_READY port={write_port_file.port} pid={os.getpid()}", flush=True)
    # Main thread pump: bpy calls only ever happen here. Script never returns,
    # which keeps Blender alive in background mode.
    while True:
        try:
            job = JOBS.get(timeout=0.05)
        except queue.Empty:
            continue
        request = job["request"]
        try:
            job["box"]["response"] = {"id": request.get("id"), **dispatch(request)}
        except Exception:  # noqa: BLE001 - report, never kill the pump
            log_error()
            job["box"]["response"] = {
                "id": request.get("id"),
                "ok": False,
                "error": {"type": "Internal", "message": traceback.format_exc().splitlines()[-1]},
            }
        finally:
            job["done"].set()


main()