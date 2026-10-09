import { tool } from "@opencode-ai/plugin"
import { request } from "../lib/blender-client"

export default tool({
  description:
    "Look up Blender 5.2 API facts before planning: node/type sockets and methods (read live from the install), tested pattern snippets, and 5.0-5.2 breaking changes. Query by name, e.g. 'Principled BSDF sockets', 'Curve to Mesh', 'bmesh edit'. Retrieve before you plan — never guess API details.",
  args: {
    query: tool.schema.string().describe("What to look up, e.g. 'Principled BSDF sockets in 5.2' or 'bmesh edit loop'"),
    limit: tool.schema.number().default(3).describe("Max pattern snippets to return"),
  },
  async execute(args) {
    try {
      const result = await request<Record<string, unknown>>(
        "docs",
        { query: args.query, limit: args.limit },
        60_000,
      )
      return JSON.stringify(result, null, 2)
    } catch (error) {
      return `ERROR: ${error instanceof Error ? error.message : String(error)}`
    }
  },
})
