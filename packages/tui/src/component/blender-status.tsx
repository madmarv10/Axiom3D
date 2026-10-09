import { createMemo, createSignal, onCleanup, onMount } from "solid-js"
import net from "node:net"
import { readFile } from "node:fs/promises"
import { join } from "node:path"
import { useProject } from "../context/project"
import { useTuiPaths } from "../context/runtime"
import { useTheme } from "../context/theme"

type BlenderState = "connected" | "disconnected" | "poisoned"

const POLL_MS = 3000
const PING_TIMEOUT_MS = 1500

// Ask the persistent Blender worker whether it is alive, the same way the tool
// client does (newline-delimited JSON "ping" over localhost TCP).
function pingWorker(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = net.createConnection({ port, host: "127.0.0.1" })
    let settled = false
    let buffer = ""
    const timer = setTimeout(() => finish(false), PING_TIMEOUT_MS)
    function finish(ok: boolean) {
      if (settled) return
      settled = true
      clearTimeout(timer)
      socket.destroy()
      resolve(ok)
    }
    socket.once("connect", () => socket.write(JSON.stringify({ id: 0, cmd: "ping", params: {} }) + "\n"))
    socket.on("data", (chunk) => {
      buffer += chunk.toString()
      const newline = buffer.indexOf("\n")
      if (newline < 0) return // wait for the rest of the response line
      try {
        finish(JSON.parse(buffer.slice(0, newline)).ok === true)
      } catch {
        finish(false)
      }
    })
    socket.once("error", () => finish(false))
    socket.once("close", () => finish(false))
  })
}

// Top-right badge: reads the worker's port file and pings it on an interval so the
// indicator reflects a live connection (including kill/restart) rather than a stale flag.
export function BlenderStatus() {
  const project = useProject()
  const paths = useTuiPaths()
  const { theme } = useTheme()
  const [state, setState] = createSignal<BlenderState>("disconnected")

  const probe = async () => {
    try {
      const dir = project.instance.path().directory || paths.cwd
      const raw = await readFile(join(dir, ".axiom3d", "blender.port"), "utf8")
      const info = JSON.parse(raw) as { port?: number; poisoned?: boolean }
      if (typeof info.port !== "number") {
        setState("disconnected")
        return
      }
      if (info.poisoned) {
        setState("poisoned")
        return
      }
      setState((await pingWorker(info.port)) ? "connected" : "disconnected")
    } catch {
      // No port file yet (worker never spawned) or unreadable — treat as not connected.
      setState("disconnected")
    }
  }

  onMount(() => {
    void probe()
    const id = setInterval(() => void probe(), POLL_MS)
    onCleanup(() => clearInterval(id))
  })

  const label = createMemo(() =>
    state() === "connected" ? "connected" : state() === "poisoned" ? "poisoned" : "disconnected",
  )
  const color = createMemo(() => {
    const current = state()
    if (current === "connected") return theme.success
    if (current === "poisoned") return theme.warning
    return theme.textMuted
  })
  const dot = createMemo(() => (state() === "disconnected" ? "○" : "●"))

  return (
    <box flexDirection="row" gap={1} alignItems="center">
      <text fg={color()}>{dot()}</text>
      <text fg={theme.text}>Blender</text>
      <text fg={color()}>{label()}</text>
    </box>
  )
}