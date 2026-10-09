"""Library pattern cookbook — tested Blender 5.2 snippets, retrieved on demand.

Single source of truth in ``examples/``. Each snippet is a .py file with a
metadata header (``# id/title/tags/description``) and a ``run()`` entrypoint.
Snippets are pulled into the agent's context by ``blender_docs`` when relevant —
never pasted into the standing prompt (heavy standing context costs tokens every
turn and weakens rule adherence). Every snippet is executed by ``validate_all``
so there are no dead examples.
"""

import importlib.util
import os
import re

SNIPPET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "examples")

_HEADER_KEYS = ("id", "title", "tags", "description")


def load_snippets():
    """Parse every example's header + source without importing it."""
    snippets = []
    if not os.path.isdir(SNIPPET_DIR):
        return snippets
    for filename in sorted(os.listdir(SNIPPET_DIR)):
        if not filename.endswith(".py"):
            continue
        path = os.path.join(SNIPPET_DIR, filename)
        with open(path, "r", encoding="utf-8") as handle:
            source = handle.read()
        meta = {}
        for line in source.splitlines():
            match = re.match(r"^#\s*(\w+):\s*(.+)$", line.strip())
            if match and match.group(1) in _HEADER_KEYS:
                meta[match.group(1)] = match.group(2).strip()
            elif meta and not line.startswith("#"):
                break  # stop at the first code line
        if "id" not in meta:
            continue
        meta["tags"] = [t.strip() for t in meta.get("tags", "").split(",") if t.strip()]
        meta["path"] = path
        meta["code"] = source
        snippets.append(meta)
    return snippets


def search(text, limit=3):
    """Rank snippets by keyword overlap with the query (tags + title + description)."""
    tokens = [t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2]
    scored = []
    for snippet in load_snippets():
        haystack = " ".join([snippet["title"], snippet.get("description", ""), " ".join(snippet["tags"])])
        haystack = haystack.lower()
        score = sum(1 for token in tokens if token in haystack)
        if score:
            scored.append((score, snippet))
    scored.sort(key=lambda pair: (-pair[0], pair[1]["id"]))
    return [snippet for _, snippet in scored[:limit]]


def _load_module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_all():
    """Execute every snippet's run() and report pass/fail (must run inside Blender)."""
    results = []
    for snippet in load_snippets():
        try:
            module = _load_module(snippet["path"], "axiom3d_snippet_" + snippet["id"])
            module.run()
            results.append({"id": snippet["id"], "passed": True})
        except Exception as exc:  # noqa: BLE001 - report any dead example
            results.append({"id": snippet["id"], "passed": False, "error": f"{type(exc).__name__}: {exc}"})
    return results
