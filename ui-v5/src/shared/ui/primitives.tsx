import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from "react";
import clsx from "clsx";
import styles from "./primitives.module.css";

export type Tone = "neutral" | "info" | "success" | "warning" | "candidate" | "private" | "missing";

export function Button({
  variant = "secondary",
  size = "md",
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}) {
  return (
    <button className={clsx(styles.button, styles[variant], styles[size], className)} {...props}>
      {children}
    </button>
  );
}

export function IconButton({
  label,
  className,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { label: string; children: ReactNode }) {
  return (
    <button aria-label={label} title={label} className={clsx(styles.iconButton, className)} {...props}>
      {children}
    </button>
  );
}

export function Badge({ tone = "neutral", children, className }: { tone?: Tone; children: ReactNode; className?: string }) {
  return <span className={clsx(styles.badge, styles[`tone-${tone}`], className)}>{children}</span>;
}

export function StatusBadge({ tone, icon, children }: { tone: Tone; icon: ReactNode; children: ReactNode }) {
  return (
    <span className={clsx(styles.statusBadge, styles[`status-${tone}`])}>
      <span aria-hidden="true" className={styles.statusIcon}>{icon}</span>
      <span>{children}</span>
    </span>
  );
}

export function Panel({ children, className, raised = false }: { children: ReactNode; className?: string; raised?: boolean }) {
  return <section className={clsx(styles.panel, raised && styles.raised, className)}>{children}</section>;
}

export function SectionHeader({
  eyebrow,
  title,
  description,
  action,
}: {
  eyebrow: string;
  title: string;
  description: string;
  action?: ReactNode;
}) {
  return (
    <header className={styles.sectionHeader}>
      <div>
        <div className={styles.eyebrow}>{eyebrow}</div>
        <h2>{title}</h2>
        <p>{description}</p>
      </div>
      {action && <div className={styles.sectionAction}>{action}</div>}
    </header>
  );
}

export function Field({
  label,
  hint,
  error,
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { label: string; hint?: string; error?: string }) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      <input className={clsx(styles.input, error && styles.inputError, className)} {...props} />
      {(hint || error) && <span className={clsx(styles.fieldHint, error && styles.errorText)}>{error || hint}</span>}
    </label>
  );
}

export function SelectField({
  label,
  children,
  defaultValue,
}: {
  label: string;
  children: ReactNode;
  defaultValue?: string;
}) {
  return (
    <label className={styles.field}>
      <span className={styles.fieldLabel}>{label}</span>
      <select className={styles.select} defaultValue={defaultValue}>{children}</select>
    </label>
  );
}

export function MetricValue({
  label,
  value,
  unit,
  trend,
  tone = "neutral",
}: {
  label: string;
  value: string;
  unit?: string;
  trend?: string;
  tone?: Tone;
}) {
  return (
    <div className={clsx(styles.metricValue, styles[`metric-${tone}`])}>
      <span>{label}</span>
      <strong>{value}<small>{unit}</small></strong>
      {trend && <em>{trend}</em>}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className={styles.kbd}>{children}</kbd>;
}
