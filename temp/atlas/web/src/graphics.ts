let supported: boolean | undefined;
export function supportsWebGL() {
  if (supported !== undefined) return supported;
  try {
    const canvas = document.createElement("canvas"),
      gl = canvas.getContext("webgl2") || canvas.getContext("webgl");
    supported = !!gl;
    if (gl)
      (gl as WebGLRenderingContext)
        .getExtension("WEBGL_lose_context")
        ?.loseContext();
  } catch {
    supported = false;
  }
  return supported;
}
