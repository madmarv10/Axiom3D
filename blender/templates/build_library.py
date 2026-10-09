"""Build and validate the Axiom3D template library.

Run headless:
    blender --background --factory-startup --python blender/templates/build_library.py

Builds every Geometry Nodes template group + material, then instantiates each
template with default parameters and runs the evaluated-mesh geometry and
trimesh-quality checks (gate stages 4-5) against it. A template that produces
any error-severity issue fails the build. Pass ``-- --save out.blend`` after the
``--`` separator to also write an axiom3d_library.blend for GUI editing (the
worker builds groups in-process and does not need the file).
"""

import os
import sys

_here = os.path.dirname(os.path.abspath(__file__))
_root = os.path.dirname(_here)  # blender/
for _path in (os.path.join(_root, "vendor"), _root):
    if _path not in sys.path:
        sys.path.insert(0, _path)
os.environ.setdefault("AXIOM3D_ROOT", os.path.dirname(_root))

import bpy  # noqa: E402

from templates import build_library, instantiate, list_templates  # noqa: E402
from geom.checks import mesh_quality_report, scene_geometry_report  # noqa: E402


def validate():
    """Instantiate each template with defaults and run stage 4+5 checks."""
    results = []
    for entry in list_templates():
        name = entry["name"]
        obj = instantiate(name, {}, name=name)
        try:
            geometry = scene_geometry_report()
            quality = mesh_quality_report()
            geo_issues = [i for i in geometry["issues"] if i["object"] == name]
            qual_issues = [
                i for i in quality["issues"] if i.get("object") == name and i.get("severity") != "warning"
            ]
            passed = not geo_issues and not qual_issues
            results.append(
                {
                    "template": name,
                    "passed": passed,
                    "verts": len(obj.data.vertices),
                    "uv_layers": len(obj.data.uv_layers),
                    "issues": [i["issue"] for i in geo_issues + qual_issues],
                }
            )
        finally:
            bpy.data.objects.remove(obj, do_unlink=True)
    return results


def main():
    info = build_library()
    print(f"built {len(info['groups'])} groups, {len(info['materials'])} materials")

    results = validate()
    failed = [r for r in results if not r["passed"]]
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        detail = f" issues={r['issues']}" if r["issues"] else ""
        print(f"  [{status}] {r['template']}: verts={r['verts']} uv={r['uv_layers']}{detail}")

    if "--save" in sys.argv:
        idx = sys.argv.index("--save")
        if idx + 1 < len(sys.argv):
            path = os.path.abspath(sys.argv[idx + 1])
            os.makedirs(os.path.dirname(path), exist_ok=True)
            bpy.ops.wm.save_as_mainfile(filepath=path)
            print(f"saved library to {path}")

    if failed:
        print(f"BUILD FAILED: {len(failed)} template(s) invalid: {[r['template'] for r in failed]}")
        sys.exit(1)
    print("BUILD OK: all templates pass gate stages 4-5")


if __name__ == "__main__":
    main()
