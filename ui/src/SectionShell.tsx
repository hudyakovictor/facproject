import { useState } from 'react'
import type { ReactNode } from 'react'
import type { SectionKey } from './section-meta'
import { SECTION_META } from './section-meta'

/* V12: ЕДИНЫЙ КАРКАС РАЗДЕЛОВ.
 * Все разделы панели «Разделы» получают: заголовок + скоуп, навигацию между
 * разделами (◀ ▶), справку «?», фильтры-чипы, тело, футер с экспортом.
 * Раньше каждый раздел был собственным оверлеем со своим header/footer —
 * дублирование, расхождения в стилях и отсутствие перехода между разделами. */


export function SectionShell({ title, scope, filters, children, footer, help, current, onNavigate, onClose }: {
  title: string
  scope?: ReactNode
  filters?: ReactNode
  children: ReactNode
  footer?: ReactNode
  help?: ReactNode
  current: SectionKey
  onNavigate?: (k: SectionKey) => void
  onClose: () => void
}) {
  const [showHelp, setShowHelp] = useState(false)
  const idx = SECTION_META.findIndex(s => s.key === current)
  const prev = idx > 0 ? SECTION_META[idx - 1] : null
  const next = idx >= 0 && idx < SECTION_META.length - 1 ? SECTION_META[idx + 1] : null
  return (
    <div className="section-overlay" role="dialog" aria-modal="true" aria-label={title}>
      <header className="sec-header">
        <h2>{title}</h2>
        {scope && <span className="sec-scope">{scope}</span>}
        <div className="sec-tools">
          {prev && onNavigate && <button onClick={() => onNavigate(prev.key)} title={`${prev.label}: ${prev.hint}`}>◀ {prev.short}</button>}
          {next && onNavigate && <button onClick={() => onNavigate(next.key)} title={`${next.label}: ${next.hint}`}>{next.short} ▶</button>}
          {help && <button className={showHelp ? 'active' : ''} onClick={() => setShowHelp(v => !v)} title="Справка по разделу (F1)">?</button>}
          <button onClick={onClose} aria-label="Закрыть (Esc)">×</button>
        </div>
      </header>
      {showHelp && help && <div className="sec-help">{help}</div>}
      {filters && <div className="sec-filters">{filters}</div>}
      <div className="sec-body">{children}</div>
      {footer && <footer className="sec-foot">{footer}</footer>}
    </div>
  )
}

export function Chip({ active, onClick, children, title }: { active: boolean; onClick: () => void; children: ReactNode; title?: string }) {
  return <button className={`sec-chip ${active ? 'active' : ''}`} onClick={onClick} title={title}>{children}</button>
}

export function MiniBars({ data, max }: { data: { label: string; value: number }[]; max?: number }) {
  const m = max ?? Math.max(1, ...data.map(d => d.value))
  return (
    <div className="minibars" role="img" aria-label="Мини-гистограмма">
      {data.map(d => (
        <div key={d.label} className="minibar" title={`${d.label}: ${d.value}`}>
          <div className="minibar-fill" style={{ height: `${Math.max(2, (d.value / m) * 100)}%` }} />
          <span className="minibar-label">{d.label}</span>
        </div>
      ))}
    </div>
  )
}
