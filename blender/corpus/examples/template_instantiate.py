# id: template-instantiate
# title: Instantiate an Axiom3D template
# tags: template, instantiate, library, axiom3d
# description: Build a parametric template into a baked, grounded mesh object.

import bpy  # noqa: F401 - ensure Blender context for the templates import
from templates import instantiate


def run():
    obj = instantiate("rail_segment", {"Length": 4.0}, name="snippet_rail")
    verts = len(obj.data.vertices)
    bpy.data.objects.remove(obj, do_unlink=True)
    return {"verts": verts}
