"""Axiom3D persistent Blender worker.

Runs inside headless Blender:  blender --background --factory-startup --python worker.py

Starts a localhost TCP server speaking newline-delimited JSON:
  request  {"id": 1, "cmd": "exec", "params": {...}}
  response {"id": 1, "ok": true, "result": {...}} | {"id": 1, "ok": false, "error": {...}}

Commands: ping, exec, snapshot, restore, reset, query, render, export, validate,
gate. Handlers live in rpc/ (transport stays here); the gate pipeline lives in
gate/.

Safety model:
  - every exec auto-snapshots the scene first (snapshot id in port file)
  - exec runs with a soft timeout; on timeout the worker marks itself poisoned and
    refuses scene-mutating commands until restart (the client kills and restarts it,
    then restores the pre-exec snapshot)
  - operator calls are filtered through their RNA signatures so argument drift in a
    newer Blender degrades to "argument ignored" instead of a crash

State files live under $AXIOM3D_ROOT/.axiom3d/ (port file, snapshots, log).
"""

import json
import os
import queue
import socketserver
import sys
import threading
import time
import traceback

# Bootstrap: make blender/ (handler packages) and vendor/ (pip --target deps like
# trimesh) importable no matter what cwd Blender was launched with.
HERE = os.path.dirname(os.path.abspath(__file__))
for _path in (os.path.join(HERE, "vendor"), HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import bpy  # noqa: E402 - isort: skip (bpy is builtin; path bootstrap above must precede rpc imports)

from rpc import dispatch  # noqa: E402
from rpc.base import AXIOM_DIR, STATE, log_error, ping_result, write_port_file  # noqa: E402

# bpy is main-thread-only: handler threads enqueue jobs, the main thread pumps them.
JOBS: queue.Queue = queue.Queue()


def handler_wait(cmd, params):
    """How long a handler thread waits for the main-thread pump before answering with a
    timeout error. Must stay under the client's rpc timeout so the answer wins the race."""
    if cmd == "exec":
        return min(max(float(params.get("timeout", 30)), 1), 600) + 2
    if cmd == "gate":
        return min(max(float(params.get("timeout", 300)), 30), 1200) + 60
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
        wait = handler_wait(cmd, params)
        if done.wait(wait):
            return box["response"]
        if cmd in ("exec", "gate"):
            # The pump is stuck inside this job (gate embeds an exec); nothing else
            # can run until it dies, so report poisoned exactly like a plain exec timeout.
            STATE["poisoned"] = True
            write_port_file()
            return {
                "id": request.get("id"),
                "ok": False,
                "error": {
                    "type": "ExecTimeout",
                    "message": f"{cmd} exceeded {wait:.0f}s and is still running on "
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