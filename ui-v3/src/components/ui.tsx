import type { ReactNode, ButtonHTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";
export function cx(...parts: Array<string | false | null | undefined>) { return parts.filter(Boolean).join(" "); }
export function Chip({ kind = "", children }: { kind?: "ok" | "warn" | "bad" | "info" | ""; children: ReactNode }) {
  return <span className={cx("chip", kind)}>{children}</span>;
}
export function Button({ variant = "default", size = "md", className, type, ...rest }: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "default" | "primary" | "danger" | "ghost"; size?: "sm" | "md" | "lg" }) {
  return <button type={type || "button"} className={cx("btn", variant !== "default" && variant, size !== "md" && size, className)} {...rest} />;
}
export function Input(props: InputHTMLAttributes<HTMLInputElement>) { return <input className={cx("input", props.className)} {...props} />; }
export function Select(props: SelectHTMLAttributes<HTMLSelectElement>) { return <select className={cx("select", props.className)} {...props} />; }
export function Textarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) { return <textarea className={cx("textarea", props.className)} {...props} />; }
export function Panel({ title, right, children }: { title?: ReactNode; right?: ReactNode; children: ReactNode }) {
  return (<section className="panel">{(title || right) && (<div className="panel-hd"><h3>{title}</h3><div className="row">{right}</div></div>)}<div className="panel-bd">{children}</div></section>);
}
export function Stat({ k, v, h }: { k: string; v: ReactNode; h?: ReactNode }) {
  return (<div className="stat"><div className="k">{k}</div><div className="v">{v}</div>{h != null && <div className="h">{h}</div>}</div>);
}
export function Banner({ kind = "info", title, children }: { kind?: "info" | "warn" | "bad" | "ok"; title?: string; children?: ReactNode }) {
  return (<div className={cx("banner", kind)} role={kind === "bad" ? "alert" : "status"}><div className="stack" style={{ gap: 4 }}>{title && <strong>{title}</strong>}{children && <div className="muted">{children}</div>}</div></div>);
}
export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (<div className="empty"><div><h3>{title}</h3>{children && <p>{children}</p>}{action && <div style={{ marginTop: 14 }}>{action}</div>}</div></div>);
}
export function Modal({ title, children, onClose, footer }: { title: string; children: ReactNode; onClose: () => void; footer?: ReactNode }) {
  return (<div className="modal-backdrop" onMouseDown={e => { if (e.target === e.currentTarget) onClose(); }}><div className="modal" role="dialog" aria-modal="true" aria-label={title}><div className="modal-hd"><strong>{title}</strong><Button variant="ghost" size="sm" onClick={onClose} aria-label="Закрыть">✕</Button></div><div className="modal-bd">{children}</div>{footer && <div className="modal-ft">{footer}</div>}</div></div>);
}
export function Progress({ value }: { value: number }) {
  return <div className="progress" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}><i style={{ width: `${Math.max(0, Math.min(100, value))}%` }} /></div>;
}
export function Kv({ rows }: { rows: Array<[string, ReactNode]> }) {
  return (<dl className="kv">{rows.map(([k, v]) => (<div key={k} style={{ display: "contents" }}><dt>{k}</dt><dd>{v}</dd></div>))}</dl>);
}
