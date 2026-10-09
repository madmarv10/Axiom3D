"""Attribute-chain extraction and symbol checking against the live bpy index
(gate stage 2). Pure Python — the index arrives as a dict so the checker stays
testable outside Blender.

Only statically-known ``bpy``/``bmesh`` attribute paths are verified. Chains that
resolve through runtime values (``bpy.context.scene...``, local variables, dict
lookups, getattr calls) are skipped: flagging what cannot be known statically
would drown real hallucinations in noise. Depth limits follow the same rule —
``bpy.ops.module.op`` is fully checkable, ``bpy.ops.module.op.poll`` is not.
"""

import ast
import difflib


def check_tree(tree, index):
    issues = []
    seen = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Attribute):
            continue
        chain = _chain(node)
        if not chain or chain[0] not in ("bpy", "bmesh") or len(chain) < 2:
            continue
        key = (node.lineno, ".".join(chain))
        if key in seen:
            continue
        seen.add(key)
        issue = _check_chain(node.lineno, chain, index)
        if issue:
            issues.append(issue)
    issues.sort(key=lambda item: (item["line"], item["chain"]))
    return issues


def _chain(node):
    if isinstance(node, ast.Name):
        return [node.id]
    if isinstance(node, ast.Attribute):
        base = _chain(node.value)
        return base + [node.attr] if base else None
    return None


def _check_chain(line, chain, index):
    if chain[0] == "bmesh":
        if chain[1] == "ops" and len(chain) >= 3:
            if chain[2] not in index["bmesh_ops"]:
                return _issue(line, chain, "bmesh.ops." + chain[2], index["bmesh_ops"])
        return None
    return _check_bpy(line, chain, index)


def _check_bpy(line, chain, index):
    topic = chain[1]
    if topic == "ops":
        if len(chain) < 3:
            return None
        module = chain[2]
        candidates = index["ops"].get(module)
        if candidates is None:
            return _issue(line, chain, f"bpy.ops.{module}", sorted(index["ops"]))
        if len(chain) >= 4 and chain[3] not in candidates:
            return _issue(line, chain, f"bpy.ops.{module}.{chain[3]}", candidates)
        return None
    if topic == "types":
        if len(chain) >= 3 and chain[2] not in index["types"]:
            return _issue(line, chain, f"bpy.types.{chain[2]}", index["types"])
        return None
    if topic == "data":
        if len(chain) < 3:
            return None
        if chain[2] not in index["data"]:
            return _issue(line, chain, f"bpy.data.{chain[2]}", index["data"])
        if len(chain) >= 4:
            methods = index["collections"].get(chain[2])
            if methods is not None and chain[3] not in methods:
                return _issue(line, chain, f"bpy.data.{chain[2]}.{chain[3]}", methods)
        return None
    if topic == "props":
        if len(chain) >= 3 and chain[2] not in index["props"]:
            return _issue(line, chain, f"bpy.props.{chain[2]}", index["props"])
        return None
    if topic == "app":
        if len(chain) >= 3 and chain[2] not in index["app"]:
            return _issue(line, chain, f"bpy.app.{chain[2]}", index["app"])
        return None
    if topic == "context":
        return None  # resolves per call site; nothing static to verify past here
    if topic not in index["bpy"]:
        return _issue(line, chain, f"bpy.{topic}", index["bpy"])
    return None


def _issue(line, chain, missing, candidates):
    suggestions = difflib.get_close_matches(missing.rsplit(".", 1)[-1], candidates, n=3, cutoff=0.6)
    message = f"unknown symbol {missing}"
    if suggestions:
        message += f" — did you mean {', '.join(suggestions)}?"
    return {"line": line, "chain": ".".join(chain), "message": message, "suggestions": suggestions}