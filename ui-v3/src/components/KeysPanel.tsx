import { useEffect, useMemo, useState } from "react";
import { fetchPhotoInfoKeys } from "../lib/api";
import type { PhotoInfoKeys } from "../lib/types";
import { fmt, NO_DATA } from "../lib/format";
import { Banner, Button, Chip } from "./ui";
function flatten(node: unknown, prefix = ""): Array<[string, unknown]> {
  if (node == null) return [[prefix || "(root)", null]];
  if (typeof node !== "object") return [[prefix, node]];
  if (Array.isArray(node)) return [[prefix, JSON.stringify(node)]];
  const out: Array<[string, unknown]> = [];
  for (const [k, v] of Object.entries(node as Record<string, unknown>)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (v && typeof v === "object" && !Array.isArray(v)) out.push(...flatten(v, path));
    else out.push([path, v]);
  }
  return out;
}
function show(v: unknown): string {
  if (v == null) return NO_DATA;
  if (typeof v === "number") return Number.isFinite(v) ? fmt(v, Math.abs(v) >= 10 ? 2 : 4) : NO_DATA;
  if (typeof v === "boolean") return v ? "true" : "false";
  return String(v);
}
export default function KeysPanel({ photoId, defaultOpen = true }: { photoId: string; defaultOpen?: boolean }) {
  const [data, setData] = useState<PhotoInfoKeys | null>(null);
  const [state, setState] = useState<"loading" | "idle" | "error" | "unavailable">("loading");
  const [message, setMessage] = useState("");
  const [openCats, setOpenCats] = useState<Record<string, boolean>>({});
  useEffect(() => {
    let dead = false; setState("loading"); setData(null); setMessage("");
    fetchPhotoInfoKeys(photoId).then(d => {
      if (dead) return; setData(d); setState("idle");
      const init: Record<string, boolean> = {};
      Object.keys(d.categories || {}).forEach((c, i) => { init[c] = defaultOpen || i < 2; });
      setOpenCats(init);
    }).catch((e: unknown) => {
      if (dead) return;
      const text = e instanceof Error ? e.message : String(e);
      setMessage(text); setState(/404|409/.test(text) ? "unavailable" : "error");
    });
    return () => { dead = true; };
  }, [photoId, defaultOpen]);
  const cats = useMemo(() => Object.entries(data?.categories || {}), [data]);
  const incomplete = !!data && data.leaf_count > 0 && data.leaf_count < 120;
  if (state === "loading") return <div className="muted mono">загрузка Stage 1 keys…</div>;
  if (state === "unavailable") return <Banner kind="warn" title="Ключи Stage 1 недоступны">{message}</Banner>;
  if (state === "error") return <Banner kind="bad" title="Ошибка загрузки ключей">{message}</Banner>;
  if (!data || !cats.length) return <Banner kind="warn" title="Нет извлечённых ключей">info_keys пуст.</Banner>;
  return (
    <div className="stack">
      <div className="row-wrap">
        <Chip kind="info">leaf: {data.leaf_count}</Chip>
        {incomplete && <Chip kind="warn">возможно неполный набор</Chip>}
        <Chip>категорий: {cats.length}</Chip>
        <div className="spacer" />
        <Button size="sm" onClick={() => void navigator.clipboard?.writeText(JSON.stringify(data, null, 2))}>копировать JSON</Button>
      </div>
      {cats.map(([cat, groups]) => {
        const title = data.category_titles?.[cat]?.ru || cat;
        const flat = Object.entries(groups || {}).flatMap(([g, values]) => flatten(values, g));
        const filled = flat.filter(([, v]) => v != null && !(typeof v === "number" && !Number.isFinite(v))).length;
        const open = openCats[cat] ?? false;
        return (
          <div key={cat} className="panel">
            <button type="button" className="panel-hd" style={{ width: "100%", cursor: "pointer" }} onClick={() => setOpenCats(s => ({ ...s, [cat]: !open }))}>
              <h3>{title}</h3><span className="mono faint">{filled}/{flat.length} · {open ? "▾" : "▸"}</span>
            </button>
            {open && (
              <div className="panel-bd" style={{ paddingTop: 0 }}>
                <div className="table-wrap"><table className="data"><thead><tr><th>ключ</th><th>значение</th></tr></thead><tbody>
                  {flat.map(([k, v]) => (
                    <tr key={k}><td className="mono muted">{k}</td><td className="mono">
                      <button type="button" className="btn ghost sm" style={{ padding: 0, minHeight: 0, border: "none" }}
                        onClick={() => void navigator.clipboard?.writeText(`${k}: ${show(v)}`)}>{show(v)}</button>
                    </td></tr>
                  ))}
                </tbody></table></div>
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
