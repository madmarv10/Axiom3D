"""Validate every cookbook snippet by executing it (must run inside Blender).

Run headless:
    blender --background --factory-startup --python blender/corpus/validate_patterns.py

Exits non-zero if any snippet's run() raises, so a dead example fails the build.
"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)  # blender/
for _path in (os.path.join(_root, "vendor"), _root):
    if _path not in sys.path:
        sys.path.insert(0, _path)
os.environ.setdefault("AXIOM3D_ROOT", os.path.dirname(_root))

from corpus import patterns  # noqa: E402


def main():
    results = patterns.validate_all()
    failed = [r for r in results if not r["passed"]]
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        detail = f"  {r['error']}" if r.get("error") else ""
        print(f"  [{status}] {r['id']}{detail}")
    if failed:
        print(f"PATTERNS FAILED: {len(failed)} dead example(s): {[r['id'] for r in failed]}")
        sys.exit(1)
    print(f"PATTERNS OK: {len(results)} snippets validated")


if __name__ == "__main__":
    main()
