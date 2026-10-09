// Phase 4 template-library tests against a live worker: list_templates shape,
// instantiate validity (grounded, UV'd, param-driven), and the station milestone
// (platform + track + canopy assembled from templates, full gate pass).
// Run from blender/:  bun test --parallel=1 --no-isolate

import { afterAll, beforeAll, beforeEach, describe, expect, test } from "bun:test"
import { exec, request, status, stop } from "../../.opencode/lib/blender-client"

type TemplateInput = {
  identifier: string
  name: string
  socket_type: string
  default: number
  min: number | null
  max: number | null
}
type TemplateInfo = { name: string; description: string; inputs: TemplateInput[] }
type ListTemplates = { templates: TemplateInfo[]; materials: Record<string, string> }
type InstantiateResult = {
  name: string
  template: string
  verts: number
  polys: number
  uv_layers: number
  dimensions: number[]
  materials: string[]
}
type GateReport = {
  passed: boolean
  failed_stage: string | null
  stages: Array<{ name: string; passed: boolean; issues?: Array<Record<string, unknown>> }>
}

function listTemplates() {
  return request<ListTemplates>("list_templates", {}, 60_000)
}

function instantiate(params: Record<string, unknown>) {
  return request<InstantiateResult>("instantiate", params, 60_000)
}

beforeAll(async () => {
  await status()
  await request("reset")
}, 90_000)

beforeEach(async () => {
  await request("reset")
})

afterAll(() => {
  stop()
})

describe("list_templates", () => {
  test("returns six templates with float inputs and two materials", async () => {
    const result = await listTemplates()
    const names = result.templates.map((t) => t.name).sort()
    expect(names).toEqual(["canopy_truss", "column_grid", "fence_run", "platform_outline", "rail_segment", "sleeper_array"])
    for (const t of result.templates) {
      expect(t.description.length).toBeGreaterThan(10)
      expect(t.inputs.length).toBeGreaterThan(0)
      for (const input of t.inputs) {
        expect(input.socket_type).toBe("NodeSocketFloat")
        expect(typeof input.default).toBe("number")
      }
    }
    expect(Object.keys(result.materials).sort()).toEqual(["concrete", "steel"])
  })
})

describe("instantiate", () => {
  test("bakes a grounded, UV'd mesh driven by params", async () => {
    const result = await instantiate({
      template: "rail_segment",
      params: { Length: 10, Width: 0.08, Height: 0.06 },
      name: "rail_long",
    })
    expect(result.name).toBe("rail_long")
    expect(result.verts).toBe(8)
    expect(result.uv_layers).toBe(1)
    expect(result.dimensions[0]).toBeCloseTo(10, 3)
    // grounded: lowest point at Z=0 (checked via a follow-up exec on the real mesh)
    const zmin = await exec(`import bpy
obj = bpy.data.objects["rail_long"]
print("zmin", min(v.co.z for v in obj.data.vertices))`)
    expect(zmin.stdout).toContain("zmin 0")
  })

  test("instances along a run scale with spacing/length", async () => {
    const short = await instantiate({ template: "sleeper_array", params: { Length: 6, Spacing: 0.5 }, name: "sleepers_a" })
    const long = await instantiate({ template: "sleeper_array", params: { Length: 12, Spacing: 0.6 }, name: "sleepers_b" })
    expect(long.verts).toBeGreaterThan(short.verts)
  })

  test("assigns a named material", async () => {
    const result = await instantiate({ template: "platform_outline", name: "plat_mat", material: "concrete" })
    expect(result.materials).toEqual(["axiom3d_concrete"])
  })

  test("unknown template and unknown param fail cleanly", async () => {
    await expect(instantiate({ template: "nope" })).rejects.toThrow(/unknown template/)
    await expect(instantiate({ template: "rail_segment", params: { Bogus: 1 } })).rejects.toThrow(/unknown param/)
  })
})

describe("station milestone", () => {
  test("platform + track + canopy from templates pass the full gate", async () => {
    await instantiate({ template: "platform_outline", params: { Width: 20, Depth: 4, Height: 0.9 }, name: "station_platform" })
    await instantiate({ template: "sleeper_array", params: { Length: 20, Spacing: 0.6 }, name: "station_sleepers" })
    await instantiate({ template: "rail_segment", params: { Length: 20 }, name: "station_rail_west" })
    await instantiate({ template: "rail_segment", params: { Length: 20 }, name: "station_rail_east" })
    await instantiate({
      template: "column_grid",
      params: { Width: 16, Depth: 2.4, "Count X": 2, "Count Y": 2, Height: 4, Size: 0.3 },
      name: "station_columns",
    })
    await instantiate({ template: "canopy_truss", params: { Span: 16 }, name: "station_truss" })

    // Position into a station. Hairline gaps keep every part non-intersecting so
    // the strict object_intersection check passes: rails float just above the
    // sleepers, columns sit on the platform, the truss rests on the columns.
    const report = await request<GateReport>(
      "gate",
      {
        code: `import bpy
bpy.data.objects["station_sleepers"].location = (0, -4, 0)
bpy.data.objects["station_rail_west"].location = (0, -4.7175, 0.182)
bpy.data.objects["station_rail_east"].location = (0, -3.2825, 0.182)
bpy.data.objects["station_columns"].location = (0, 0, 0.901)
bpy.data.objects["station_truss"].location = (0, 0, 4.902)`,
        render: true,
        export_roundtrip: true,
        timeout: 300,
      },
      420_000,
    )
    expect(report.passed, JSON.stringify(report, null, 2)).toBe(true)
    expect(report.failed_stage).toBeNull()
    for (const name of ["geometry", "mesh_quality", "export_roundtrip", "render"]) {
      expect(report.stages.find((s) => s.name === name)?.passed).toBe(true)
    }
  }, 420_000)
})