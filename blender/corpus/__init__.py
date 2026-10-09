"""Axiom3D API-doc corpus: live introspection + tested pattern cookbook + curated
breaking changes.

The primary API source is live introspection of the installed Blender (version-true
by construction); the cookbook supplies runnable patterns; breaking changes capture
the 5.0-5.2 renames this harness actually hit. ``query`` merges all three into one
answer for the ``blender_docs`` command.
"""

from corpus import breaking_changes, introspect, patterns


def query(text, limit=3):
    """Answer a docs query: introspected API + matching patterns + breaking changes."""
    result = {
        "query": text,
        "introspection": introspect.query(text),
        "patterns": [
            {"id": p["id"], "title": p["title"], "tags": p["tags"], "description": p.get("description", ""), "code": p["code"]}
            for p in patterns.search(text, limit=limit)
        ],
        "breaking_changes": breaking_changes.search(text),
    }
    return result
