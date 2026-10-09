import { tool } from "@opencode-ai/plugin"
import { request } from "../lib/blender-client"

type ListResult = { templates: Array<Record<string, unknown>>; materials: Record<string, string> }
type InstantiateResult = { name: string; template: string; verts: number; polys: number; dimensions: number[] }

export default tool({
  description:
    "Browse the Axiom3D template library (parametric assets: rail, sleepers, columns, fence, platform, canopy truss) or instantiate one as a baked, grounded mesh. Call with no template to list names, inputs, and defaults; call with a template + params to build it.",
  args: {
    template: tool.schema.string().optional().describe("Template name to instantiate; omit to list the library"),
    params: tool.schema
      .record(tool.schema.string(), tool.schema.number())
      .optional()
      .describe("Template input values; names/defaults come from the list output"),
    name: tool.schema.string().optional().describe("Object name for the instance (snake_case)"),
    material: tool.schema.string().optional().describe("Material to assign: concrete | steel"),
  },
  async execute(args) {
    if (!args.template) {
      const result = await request<ListResult>("list_templates", {}, 60_000)
      return JSON.stringify(result, null, 2)
    }
    try {
      const result = await request<InstantiateResult>(
        "instantiate",
        { template: args.template, params: args.params, name: args.name, material: args.material },
        60_000,
      )
      return [
        `status: ok`,
        `instantiated ${result.template} as "${result.name}"`,
        `verts: ${result.verts}  polys: ${result.polys}`,
        `dimensions: ${JSON.stringify(result.dimensions)}`,
        "The mesh is grounded (lowest point at Z=0) with box-projected UVs. Run blender-validate or blender-gate to confirm it is clean before composing a larger asset.",
      ].join("\n")
    } catch (error) {
      return `ERROR: ${error instanceof Error ? error.message : String(error)}`
    }
  },
})
