import type { MeshData, Topology } from "./types";
export async function api<T = any>(
  url: string,
  opts?: RequestInit,
): Promise<T> {
  const r = await fetch("/api" + url, {
    ...opts,
    headers:
      opts?.body instanceof FormData
        ? opts.headers
        : { "Content-Type": "application/json", ...opts?.headers },
  });
  if (!r.ok) {
    let m;
    try {
      m = (await r.json()).detail;
    } catch {
      m = r.statusText;
    }
    throw new Error(typeof m === "string" ? m : JSON.stringify(m));
  }
  return r.json();
}
export const post = <T = any>(url: string, data: any = {}) =>
  api<T>(url, { method: "POST", body: JSON.stringify(data) });
const meshes = new Map<string, Promise<MeshData>>();
let top: Promise<Topology> | null = null;
export function getMesh(id: string, version = "") {
  const cacheId = id + ":" + version;
  if (!meshes.has(cacheId)) {
    const task = fetch(
      "/api/photos/" + id + "/mesh?v=" + encodeURIComponent(version),
    )
      .then(async (r) => {
        if (!r.ok) throw new Error("Меш ещё не готов");
        const a = new Float32Array(await r.arrayBuffer()),
          n = a.length / 3;
        return {
          vertices: a.slice(0, n),
          identity: a.slice(n, 2 * n),
          albedo: a.slice(2 * n),
        };
      })
      .catch((e) => {
        meshes.delete(cacheId);
        throw e;
      });
    meshes.set(cacheId, task);
    if (meshes.size > 25) meshes.delete(meshes.keys().next().value!);
  }
  return meshes.get(cacheId)!;
}
export function getTopology() {
  if (!top)
    top = api<Topology>("/topology").catch((e) => {
      top = null;
      throw e;
    });
  return top;
}
export function downloadBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob),
    a = document.createElement("a");
  a.href = url;
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 5000);
}
export async function pngFromSVG(svg: string, name: string) {
  const image = new Image();
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  await new Promise<void>((resolve, reject) => {
    image.onload = () => resolve();
    image.onerror = reject;
    image.src = url;
  });
  const c = document.createElement("canvas");
  c.width = image.width;
  c.height = image.height;
  c.getContext("2d")!.drawImage(image, 0, 0);
  c.toBlob((b) => b && downloadBlob(b, name), "image/png");
  URL.revokeObjectURL(url);
}
