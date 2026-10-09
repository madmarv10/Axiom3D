import { tool } from "@opencode-ai/plugin"
import { request } from "../lib/blender-client"

export default tool({
  description:
    "Render multi-view PNGs of the scene (auto-framed cameras) and attach them as images for visual critique. Workbench is fastest and needs no GPU; use EEVEE for final looks.",
  args: {
    engine: tool.schema.string().default("workbench").describe("workbench | eevee | cycles"),
    width: tool.schema.number().default(640),
    height: tool.schema.number().default(360),
    views: tool.schema
      .array(tool.schema.string())
      .optional()
      .describe("Subset of front, back, left, right, top, iso — default all six"),
  },
  async execute(args) {
    try {
      const result = await request<{ files: string[]; engine_used: string }>(
        "render",
        { engine: args.engine, width: args.width, height: args.height, views: args.views },
        310_000,
      )
      const attachments = await Promise.all(
        result.files.map(async (file) => ({
          type: "file" as const,
          mime: "image/png",
          url: `data:image/png;base64,${Buffer.from(await Bun.file(file).arrayBuffer()).toString("base64")}`,
        })),
      )
      return {
        title: `Rendered ${result.files.length} views (${result.engine_used})`,
        output: [
          `engine: ${result.engine_used}`,
          `files:\n${result.files.join("\n")}`,
          "Attached images are auto-framed views. Critique them: does the geometry match the brief, are proportions right, is anything missing or intersecting? If not, fix with blender-exec and re-render.",
        ].join("\n"),
        attachments,
      }
    } catch (error) {
      return `ERROR: ${error instanceof Error ? error.message : String(error)}`
    }
  },
})