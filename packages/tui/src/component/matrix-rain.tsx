import { FrameBufferRenderable, type OptimizedBuffer, type RenderContext, type RenderableOptions } from "@opentui/core"
import { extend } from "@opentui/solid"
import { MatrixRainPainter } from "./matrix-rain-render"

// Frame-buffer renderable that drives the matrix-rain painter at the render fps, so it
// animates behind transparent content. Mount with position="absolute" + zIndex={0} and
// put content at zIndex={1} to layer it as a background.

type MatrixRainOptions = RenderableOptions<FrameBufferRenderable>

class MatrixRainRenderable extends FrameBufferRenderable {
  private painter = new MatrixRainPainter()

  constructor(ctx: RenderContext, options: MatrixRainOptions = {}) {
    const width = typeof options.width === "number" ? options.width : 1
    const height = typeof options.height === "number" ? options.height : 1
    super(ctx, { ...options, width, height, live: options.live ?? true, respectAlpha: false })
    if (options.width !== undefined && typeof options.width !== "number") this.width = options.width
    if (options.height !== undefined && typeof options.height !== "number") this.height = options.height
  }

  protected override renderSelf(buffer: OptimizedBuffer, deltaTime = 0): void {
    if (!this.visible || this.isDestroyed) return
    this.painter.render(this.frameBuffer, deltaTime)
    super.renderSelf(buffer)
  }
}

declare module "@opentui/solid" {
  interface OpenTUIComponents {
    matrix_rain: typeof MatrixRainRenderable
  }
}

extend({ matrix_rain: MatrixRainRenderable })

// Full-screen, live background layer.
export function MatrixRain() {
  return <matrix_rain width="100%" height="100%" live />
}