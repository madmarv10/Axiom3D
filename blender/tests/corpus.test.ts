// Phase 5 API-doc corpus tests: live introspection (milestone query), pattern
// cookbook search + validation, and breaking-changes lookup — all against a live
// worker. Run from blender/:  bun test --parallel=1 --no-isolate

import { afterAll, beforeAll, describe, expect, test } from "bun:test"
import { join } from "node:path"
import { readdir } from "node:fs/promises"
import { request, status, stop } from "../../.opencode/lib/blender-client"

const ROOT = join(import.meta.dir, "..", "..")

type Socket = { name: string; type: string; enabled: boolean }
type DocsResult = {
  query: string
  introspection: {
    kind: string
    class?: string
    type?: string
    inputs?: Socket[]
    outputs?: Array<{ name: string; type: string }>
    methods?: string[]
    properties?: string[]
  }
  patterns: Array<{ id: string; title: string; code: string }>
  breaking_changes: Array<{ id: string; summary: string }>
}

function docs(query: string, limit = 3) {
  return request<DocsResult>("docs", { query, limit }, 60_000)
}

beforeAll(async () => {
  await status()
}, 90_000)

afterAll(() => {
  stop()
})

describe("live introspection", () => {
  test("milestone: Principled BSDF sockets in 5.2 returns the real 5.2 list", async () => {
    const result = await docs("Principled BSDF sockets in 5.2")
    const intro = result.introspection
    expect(intro.kind).toBe("node")
    expect(intro.class).toBe("ShaderNodeBsdfPrincipled")
    const names = (intro.inputs ?? []).map((s) => s.name)
    for (const expected of ["Base Color", "Metallic", "Roughness", "IOR", "Emission Color"]) {
      expect(names).toContain(expected)
    }
    expect(intro.outputs?.[0]?.name).toBe("BSDF")
  })

  test("resolves common node names to their 5.2 classes", async () => {
    expect((await docs("Curve to Mesh")).introspection.class).toBe("GeometryNodeCurveToMesh")
    expect((await docs("Cube")).introspection.class).toBe("GeometryNodeMeshCube")
    expect((await docs("Instance on Points")).introspection.class).toBe("GeometryNodeInstanceOnPoints")
  })
})

describe("pattern cookbook", () => {
  test("query returns matching tested snippets with runnable code", async () => {
    const result = await docs("bmesh edit")
    const ids = result.patterns.map((p) => p.id)
    expect(ids).toContain("bmesh-edit-loop")
    const snippet = result.patterns.find((p) => p.id === "bmesh-edit-loop")
    expect(snippet?.code).toContain("bmesh")
    expect(snippet?.code).toContain("def run()")
  })

  test("every cookbook snippet has an id header and a run() entrypoint", async () => {
    // Runtime execution is validated by the build-time script
    // blender/corpus/validate_patterns.py (Bun.spawn of Blender segfaults Bun 1.4.2
    // on Windows, so the live check lives there, not here).
    const dir = join(ROOT, "blender", "corpus", "examples")
    const files = (await readdir(dir)).filter((f) => f.endsWith(".py"))
    expect(files.length).toBeGreaterThanOrEqual(8)
    for (const file of files) {
      const source = await Bun.file(join(dir, file)).text()
      expect(source).toStartWith("# id:")
      expect(source).toContain("def run()")
    }
  })
})

describe("breaking changes", () => {
  test("surfaces the 5.2 glTF export_apply rename", async () => {
    const result = await docs("glTF export apply modifiers")
    const ids = result.breaking_changes.map((b) => b.id)
    expect(ids).toContain("gltf-apply-modifiers")
  })

  test("surfaces the GN modifier input idproperty change", async () => {
    const result = await docs("geometry nodes modifier inputs")
    const ids = result.breaking_changes.map((b) => b.id)
    expect(ids).toContain("gn-modifier-inputs")
  })
})