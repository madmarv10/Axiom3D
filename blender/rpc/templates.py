"""Template commands: list_templates, instantiate.

Thin wrappers over the templates package. instantiate bakes a template into a
real grounded mesh in the scene; the agent never touches node trees (locked
decision #6), only named parameters.
"""

from rpc.base import WorkerError


def cmd_list_templates(params):
    from templates import available_materials, list_templates

    return {"templates": list_templates(), "materials": available_materials()}


def cmd_instantiate(params):
    from templates import instantiate

    template = params.get("template")
    if not template or not isinstance(template, str):
        raise WorkerError("BadRequest", "instantiate requires params.template (string)")
    try:
        obj = instantiate(
            template,
            params.get("params") or {},
            name=params.get("name"),
            material=params.get("material"),
        )
    except KeyError as exc:
        raise WorkerError("NotFound", str(exc)) from exc
    return {
        "name": obj.name,
        "template": template,
        "verts": len(obj.data.vertices),
        "polys": len(obj.data.polygons),
        "uv_layers": len(obj.data.uv_layers),
        "dimensions": [round(v, 6) for v in obj.dimensions],
        "materials": [m.name for m in obj.data.materials if m],
    }
