import { tool } from "@opencode-ai/plugin"
import { isAbsolute, join } from "node:path"
import { request } from "../lib/blender-client"

export default tool({
  description:
    "Export the scene to a production file (glTF/GLB, FBX, USD) with modifiers applied. Relative paths resolve against the project directory. Returns the written path and byte size.",
  args: {
    path: tool.schema.string().describe("Output file path, e.g. assets/crate.glb"),
    format: tool.schema.string().default("glb").describe("glb | gltf | fbx | usd"),
    apply_modifiers: tool.schema.boolean().default(true),
  },
  async execute(args, context) {
    try {
      const target = isAbsolute(args.path) ? args.path : join(context.directory, args.path)
      const result = await request<{ path: string; bytes: number; format: string }>(
        "export",
        { path: target, format: args.format, apply_modifiers: args.apply_modifiers },
        90_000,
      )
      return `exported ${result.format} ${result.bytes} bytes\n${result.path}`
    } catch (error) {
      return `ERROR: ${error instanceof Error ? error.message : String(error)}`
    }
  },
})