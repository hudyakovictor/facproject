export const NO_DATA = "—";
export function isNum(v: unknown): v is number { return typeof v === "number" && Number.isFinite(v); }
export function fmt(v: unknown, digits = 3): string { return isNum(v) ? v.toFixed(digits) : NO_DATA; }
export function fmtDate(isoOrTs: string | number | null | undefined): string {
  if (isoOrTs == null || isoOrTs === "") return NO_DATA;
  const d = typeof isoOrTs === "number" ? new Date(isoOrTs) : new Date(isoOrTs);
  if (Number.isNaN(d.getTime())) return String(isoOrTs);
  return d.toLocaleDateString("ru-RU");
}
export function shortId(id: string, head = 18): string {
  if (!id) return NO_DATA;
  return id.length <= head + 3 ? id : id.slice(0, head) + "…";
}
export function pct(done: number, total: number): number {
  if (!total) return 0;
  return Math.max(0, Math.min(100, Math.round((done / total) * 100)));
}
