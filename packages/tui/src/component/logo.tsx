import { RGBA, TextAttributes } from "@opentui/core"
import { For } from "solid-js"
import { logo } from "../logo"

// Teal + bold to match axiom3d.html (#5EEAD4, font-weight 700).
const TEAL = RGBA.fromHex("#5EEAD4")

export function Logo() {
  return (
    <box>
      <For each={logo}>
        {(line) => (
          <box flexDirection="row">
            {Array.from(line).map((char) => (
              <text fg={TEAL} attributes={TextAttributes.BOLD} selectable={false}>
                {char}
              </text>
            ))}
          </box>
        )}
      </For>
    </box>
  )
}