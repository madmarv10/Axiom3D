"""Gate command: runs the staged verification pipeline (gate/pipeline.py).

The pipeline import is deferred to call time — it pulls in the full check stack
(api index, geometry, trimesh) and only gate commands need it.
"""

from rpc.base import WorkerError


def cmd_gate(params):
    from gate.pipeline import run_gate

    code = params.get("code")
    if not isinstance(code, str) or not code.strip():
        raise WorkerError("BadRequest", "gate requires params.code (non-empty string)")
    return run_gate(code, params)