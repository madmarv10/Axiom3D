"""RPC command registry. Handlers never touch sockets; worker.py owns the transport
(TCP, main-thread jobs pump, watchdog). Commands: ping (answered from STATE without
the pump), exec, snapshot, restore, reset, query, render, export, validate, gate."""

from rpc.base import ExecScriptError, WorkerError, require_live
from rpc import export, gate, render, session, validate

COMMANDS = {
    "exec": session.cmd_exec,
    "snapshot": session.cmd_snapshot,
    "restore": session.cmd_restore,
    "reset": session.cmd_reset,
    "query": session.cmd_query,
    "render": render.cmd_render,
    "export": export.cmd_export,
    "validate": validate.cmd_validate,
    "gate": gate.cmd_gate,
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