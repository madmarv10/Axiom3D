"""Docs command: live API introspection + pattern cookbook + breaking changes.

Thin wrapper over the corpus package. Answers "Principled BSDF sockets in 5.2"
from the installed Blender (version-true), plus matching tested snippets and the
5.0-5.2 renames this harness hit — so the agent retrieves before it plans.
"""

from rpc.base import WorkerError


def cmd_docs(params):
    from corpus import query

    text = params.get("query")
    if not text or not isinstance(text, str):
        raise WorkerError("BadRequest", "docs requires params.query (string)")
    return query(text, limit=int(params.get("limit", 3)))
