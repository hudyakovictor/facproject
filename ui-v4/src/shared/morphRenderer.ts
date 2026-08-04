/**
 * Minimal WebGL textured-mesh renderer for the Morphing workspace (Iteration 09).
 *
 * Renders a triangle mesh with a UV texture; two textures (photo A and photo B)
 * are blended in the fragment shader by a uniform mix factor, and vertex
 * positions are interpolated on the CPU between the two meshes — both meshes
 * share the same topology (BFM), so interpolation is well defined.
 *
 * Landmarks (106/134) are drawn as projected GL points on top of the mesh.
 * The camera is an orbit camera (yaw/elevation/distance around the origin).
 *
 * Visualization-only: interpolated frames are never sent back to the backend.
 */
export interface MorphMeshData {
  vertices: number[] | Float32Array; // flat xyz
  triangles: number[] | Uint32Array; // flat indices
  uv: number[] | Float32Array;       // flat uv (2 per vertex), may be empty
  vertexCount: number;
}

const VERT_SRC = `
attribute vec3 aPos;
attribute vec2 aUv;
attribute vec3 aColor;
uniform mat4 uProjView;
varying vec2 vUv;
varying vec3 vColor;
void main() {
  vUv = aUv;
  vColor = aColor;
  gl_Position = uProjView * vec4(aPos, 1.0);
}`;

const FRAG_SRC = `
precision mediump float;
varying vec2 vUv;
varying vec3 vColor;
uniform sampler2D uTexA;
uniform sampler2D uTexB;
uniform float uBlend;
uniform float uHasTextures;
uniform float uHasColors;
void main() {
  if (uHasColors > 0.5) {
    gl_FragColor = vec4(vColor, 1.0);
  } else if (uHasTextures > 0.5) {
    vec4 a = texture2D(uTexA, vUv);
    vec4 b = texture2D(uTexB, vUv);
    gl_FragColor = mix(a, b, uBlend);
  } else {
    gl_FragColor = vec4(0.62, 0.55, 0.5, 1.0);
  }
}`;

const LDM_VERT_SRC = `
attribute vec3 aPos;
uniform mat4 uProjView;
uniform float uPointSize;
void main() {
  gl_Position = uProjView * vec4(aPos, 1.0);
  gl_PointSize = uPointSize;
}`;

const LDM_FRAG_SRC = `
precision mediump float;
uniform vec4 uColor;
void main() {
  vec2 c = gl_PointCoord - vec2(0.5);
  if (dot(c, c) > 0.25) discard;
  gl_FragColor = uColor;
}`;

function compile(gl: WebGLRenderingContext, type: number, source: string): WebGLShader {
  const shader = gl.createShader(type);
  if (!shader) throw new Error("createShader failed");
  gl.shaderSource(shader, source);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    throw new Error(`shader compile error: ${gl.getShaderInfoLog(shader)}`);
  }
  return shader;
}

function buildProgram(gl: WebGLRenderingContext, vs: string, fs: string): WebGLProgram {
  const program = gl.createProgram();
  if (!program) throw new Error("createProgram failed");
  gl.attachShader(program, compile(gl, gl.VERTEX_SHADER, vs));
  gl.attachShader(program, compile(gl, gl.FRAGMENT_SHADER, fs));
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    throw new Error(`program link error: ${gl.getProgramInfoLog(program)}`);
  }
  return program;
}

export class MorphRenderer {
  private gl: WebGLRenderingContext;
  private meshProgram: WebGLProgram;
  private ldmProgram: WebGLProgram;
  private meshVerts: WebGLBuffer | null = null;
  private meshUv: WebGLBuffer | null = null;
  private meshTris: WebGLBuffer | null = null;
  private colorBuffer: WebGLBuffer | null = null;
  private vertexColors: Float32Array | null = null;
  private meshTriCount = 0;
  private ldmBuffer: WebGLBuffer | null = null;
  private ldmCount = 0;
  private texA: WebGLTexture | null = null;
  private texB: WebGLTexture | null = null;
  private mesh: { va: Float32Array; vb: Float32Array; uv: Float32Array | null } | null = null;
  private landmarkPoints: Float32Array | null = null;
  private landmarkColor: [number, number, number, number] = [1, 0.3, 0.25, 0.95];
  yaw = 0;        // degrees
  elevation = -4; // degrees
  distance = 3.2;
  blend = 0;      // 0 = A, 1 = B
  wireframe = false;
  showLandmarks = false;
  private ready = false;

  constructor(private canvas: HTMLCanvasElement) {
    const gl = canvas.getContext("webgl", { antialias: true, alpha: true, premultipliedAlpha: false });
    if (!gl) throw new Error("WebGL недоступен в этом браузере");
    this.gl = gl;
    this.meshProgram = buildProgram(gl, VERT_SRC, FRAG_SRC);
    this.ldmProgram = buildProgram(gl, LDM_VERT_SRC, LDM_FRAG_SRC);
    gl.enable(gl.BLEND);
    gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);
  }

  /** Set both meshes (shared topology) and upload topology once. */
  setMeshes(a: MorphMeshData, b: MorphMeshData): void {
    const gl = this.gl;
    const va = new Float32Array(a.vertices);
    const vb = new Float32Array(b.vertices);
    const uv = a.uv.length ? new Float32Array(a.uv) : null;
    const tris = new Uint32Array(a.triangles);
    this.mesh = { va, vb, uv };
    this.meshTriCount = tris.length / 3;

    if (!this.meshVerts) this.meshVerts = gl.createBuffer();
    if (!this.meshUv) this.meshUv = gl.createBuffer();
    if (!this.meshTris) this.meshTris = gl.createBuffer();
    if (!this.colorBuffer) this.colorBuffer = gl.createBuffer();
    this.vertexColors = null;

    gl.bindBuffer(gl.ARRAY_BUFFER, this.meshVerts);
    gl.bufferData(gl.ARRAY_BUFFER, va, gl.DYNAMIC_DRAW);
    gl.bindBuffer(gl.ARRAY_BUFFER, this.meshUv);
    gl.bufferData(gl.ARRAY_BUFFER, uv ?? new Float32Array(0), gl.STATIC_DRAW);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.meshTris);
    gl.bufferData(gl.ELEMENT_ARRAY_BUFFER, tris, gl.STATIC_DRAW);

    if (!this.ldmBuffer) this.ldmBuffer = gl.createBuffer();
    this.ready = true;
  }

  /** Set interpolated landmark overlay points (flat xyz). */
  setLandmarks(points: Float32Array | null, color?: [number, number, number, number]): void {
    this.landmarkPoints = points;
    if (color) this.landmarkColor = color;
    if (points && this.ldmBuffer) {
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, this.ldmBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, points, gl.DYNAMIC_DRAW);
      this.ldmCount = points.length / 3;
    } else {
      this.ldmCount = 0;
    }
  }

  /**
   * Per-vertex colors (flat RGB 0..1, one triple per vertex). When set, the
   * mesh is drawn with these colors instead of the UV textures — used for the
   * 3D displacement heatmap. Pass null to switch back to textures.
   */
  setVertexColors(colors: Float32Array | null): void {
    this.vertexColors = colors;
    if (colors && this.colorBuffer) {
      const gl = this.gl;
      gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuffer);
      gl.bufferData(gl.ARRAY_BUFFER, colors, gl.STATIC_DRAW);
    }
  }

  /** Replace the B mesh vertices (e.g. with the Kabsch-aligned set). */
  setMeshB(vertices: Float32Array): void {
    if (this.mesh && this.mesh.vb.length === vertices.length) {
      this.mesh.vb = vertices;
    }
  }

  /** Load texture from a URL (relative same-origin). */
  loadTexture(slot: "a" | "b", url: string): Promise<void> {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => {
        const gl = this.gl;
        const texture = gl.createTexture();
        if (!texture) { reject(new Error("createTexture failed")); return; }
        gl.bindTexture(gl.TEXTURE_2D, texture);
        gl.texImage2D(gl.TEXTURE_2D, 0, gl.RGB, gl.RGB, gl.UNSIGNED_BYTE, image);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
        gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
        if (slot === "a") this.texA = texture; else this.texB = texture;
        resolve();
      };
      image.onerror = () => { if (slot === "a") this.texA = null; else this.texB = null; reject(new Error(`texture load failed: ${url}`)); };
      image.src = url;
    });
  }

  clearTextures(): void {
    this.texA = null;
    this.texB = null;
  }

  resize(): void {
    const canvas = this.canvas;
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    const width = Math.max(1, Math.floor(canvas.clientWidth * dpr));
    const height = Math.max(1, Math.floor(canvas.clientHeight * dpr));
    if (canvas.width !== width || canvas.height !== height) {
      canvas.width = width;
      canvas.height = height;
    }
    this.gl.viewport(0, 0, canvas.width, canvas.height);
  }

  /** Interpolate geometry by blend factor and render. */
  render(): void {
    if (!this.ready || !this.mesh) return;
    const gl = this.gl;
    this.resize();
    gl.clearColor(0.035, 0.05, 0.07, 1);
    gl.clear(gl.COLOR_BUFFER_BIT | gl.DEPTH_BUFFER_BIT);
    gl.enable(gl.DEPTH_TEST);

    const t = Math.min(1, Math.max(0, this.blend));
    const { va, vb, uv } = this.mesh;
    if (va.length === vb.length) {
      const interpolated = new Float32Array(va.length);
      for (let i = 0; i < va.length; i++) interpolated[i] = va[i] + (vb[i] - va[i]) * t;
      gl.bindBuffer(gl.ARRAY_BUFFER, this.meshVerts);
      gl.bufferSubData(gl.ARRAY_BUFFER, 0, interpolated);
    }

    const projView = this.projViewMatrix();

    // --- textured triangles ---
    gl.useProgram(this.meshProgram);
    const posLoc = gl.getAttribLocation(this.meshProgram, "aPos");
    const uvLoc = gl.getAttribLocation(this.meshProgram, "aUv");
    const colorLoc = gl.getAttribLocation(this.meshProgram, "aColor");
    gl.bindBuffer(gl.ARRAY_BUFFER, this.meshVerts);
    gl.enableVertexAttribArray(posLoc);
    gl.vertexAttribPointer(posLoc, 3, gl.FLOAT, false, 0, 0);
    if (this.vertexColors && this.colorBuffer) {
      gl.bindBuffer(gl.ARRAY_BUFFER, this.colorBuffer);
      gl.enableVertexAttribArray(colorLoc);
      gl.vertexAttribPointer(colorLoc, 3, gl.FLOAT, false, 0, 0);
      gl.uniform1f(gl.getUniformLocation(this.meshProgram, "uHasColors"), 1);
    } else {
      gl.disableVertexAttribArray(colorLoc);
      gl.uniform1f(gl.getUniformLocation(this.meshProgram, "uHasColors"), 0);
    }
    if (uv && uv.length && this.texA && this.texB) {
      gl.bindBuffer(gl.ARRAY_BUFFER, this.meshUv);
      gl.enableVertexAttribArray(uvLoc);
      gl.vertexAttribPointer(uvLoc, 2, gl.FLOAT, false, 0, 0);
      gl.uniform1f(gl.getUniformLocation(this.meshProgram, "uHasTextures"), 1);
      gl.activeTexture(gl.TEXTURE0);
      gl.bindTexture(gl.TEXTURE_2D, this.texA);
      gl.activeTexture(gl.TEXTURE1);
      gl.bindTexture(gl.TEXTURE_2D, this.texB);
      gl.uniform1i(gl.getUniformLocation(this.meshProgram, "uTexA"), 0);
      gl.uniform1i(gl.getUniformLocation(this.meshProgram, "uTexB"), 1);
    } else {
      gl.disableVertexAttribArray(uvLoc);
      gl.uniform1f(gl.getUniformLocation(this.meshProgram, "uHasTextures"), 0);
    }
    gl.uniform1f(gl.getUniformLocation(this.meshProgram, "uBlend"), t);
    gl.uniformMatrix4fv(gl.getUniformLocation(this.meshProgram, "uProjView"), false, projView);
    gl.disable(gl.CULL_FACE);
    gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER, this.meshTris);
    gl.drawElements(gl.TRIANGLES, this.meshTriCount * 3, gl.UNSIGNED_INT, 0);

    // --- wireframe overlay ---
    if (this.wireframe) {
      gl.useProgram(this.meshProgram);
      gl.uniform1f(gl.getUniformLocation(this.meshProgram, "uHasTextures"), 0);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.meshProgram, "uProjView"), false, projView);
      gl.bindBuffer(gl.ARRAY_BUFFER, this.meshVerts);
      gl.enableVertexAttribArray(posLoc);
      gl.vertexAttribPointer(posLoc, 3, gl.FLOAT, false, 0, 0);
      gl.drawElements(gl.LINES, Math.min(this.meshTriCount * 3, 60_000), gl.UNSIGNED_INT, 0);
    }

    // --- landmarks ---
    if (this.showLandmarks && this.landmarkPoints && this.ldmCount > 0) {
      gl.useProgram(this.ldmProgram);
      const ldmPos = gl.getAttribLocation(this.ldmProgram, "aPos");
      gl.bindBuffer(gl.ARRAY_BUFFER, this.ldmBuffer);
      gl.enableVertexAttribArray(ldmPos);
      gl.vertexAttribPointer(ldmPos, 3, gl.FLOAT, false, 0, 0);
      gl.uniformMatrix4fv(gl.getUniformLocation(this.ldmProgram, "uProjView"), false, projView);
      gl.uniform1f(gl.getUniformLocation(this.ldmProgram, "uPointSize"), 7);
      gl.uniform4fv(gl.getUniformLocation(this.ldmProgram, "uColor"), this.landmarkColor);
      gl.drawArrays(gl.POINTS, 0, this.ldmCount);
    }
    gl.disable(gl.DEPTH_TEST);
  }

  private projViewMatrix(): Float32Array {
    const yawRad = (this.yaw * Math.PI) / 180;
    const elevRad = (this.elevation * Math.PI) / 180;
    const cy = Math.cos(yawRad), sy = Math.sin(yawRad);
    const ce = Math.cos(elevRad), se = Math.sin(elevRad);
    const eye: [number, number, number] = [
      this.distance * cy * ce,
      this.distance * se,
      this.distance * sy * ce,
    ];
    const up: [number, number, number] = [0, 1, 0];
    // lookAt(eye, origin, up)
    const zAxis = norm(sub([0, 0, 0], eye));
    const xAxis = norm(cross(up, zAxis));
    const yAxis = cross(zAxis, xAxis);
    const view = new Float32Array([
      xAxis[0], yAxis[0], zAxis[0], 0,
      xAxis[1], yAxis[1], zAxis[1], 0,
      xAxis[2], yAxis[2], zAxis[2], 0,
      -(dot(xAxis, eye)), -(dot(yAxis, eye)), -(dot(zAxis, eye)), 1,
    ]);
    const aspect = Math.max(0.1, this.canvas.clientWidth / Math.max(1, this.canvas.clientHeight));
    const fovy = (42 * Math.PI) / 180;
    const near = 0.01, far = 100;
    const f = 1 / Math.tan(fovy / 2);
    const proj = new Float32Array([
      f / aspect, 0, 0, 0,
      0, f, 0, 0,
      0, 0, (far + near) / (near - far), -1,
      0, 0, (2 * far * near) / (near - far), 0,
    ]);
    const out = new Float32Array(16);
    for (let col = 0; col < 4; col++) {
      for (let row = 0; row < 4; row++) {
        out[col * 4 + row] = proj[0 * 4 + row] * view[col * 4 + 0]
          + proj[1 * 4 + row] * view[col * 4 + 1]
          + proj[2 * 4 + row] * view[col * 4 + 2]
          + proj[3 * 4 + row] * view[col * 4 + 3];
      }
    }
    return out;
  }
}

function sub(a: number[], b: number[]): number[] { return [a[0] - b[0], a[1] - b[1], a[2] - b[2]]; }
function cross(a: number[], b: number[]): number[] {
  return [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
}
function dot(a: number[], b: number[]): number { return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]; }
function norm(v: number[]): number[] {
  const len = Math.hypot(v[0], v[1], v[2]) || 1;
  return [v[0] / len, v[1] / len, v[2] / len];
}
