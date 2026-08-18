import { useEffect, useRef, useState } from 'react'
import type { PairConnection } from './types'

const STORAGE_KEY = 'deeputin_journal_v2'

export function SessionJournal({ pairs: _pairs, selectedPairId: sp, activeSection }: {
  pairs: PairConnection[]; selectedPairId: string | null; activeSection: string | null
}) {
  const [open, setOpen] = useState(false)
  const [journal, setJournal] = useState<{ ts: string; action: string; detail?: string }[]>([])
  const last = useRef({ pairId: null as string | null, section: null as string | null })

  useEffect(() => {
    if (sp && sp !== last.current.pairId) {
      addEntry({ action: 'view_pair', detail: sp })
      last.current.pairId = sp
    }
  }, [sp])

  useEffect(() => {
    if (activeSection !== last.current.section) {
      addEntry({ action: activeSection ? 'open_section' : 'close_section', detail: activeSection ?? '' })
      last.current.section = activeSection
    }
  }, [activeSection])

  const addEntry = (e: { action: string; detail?: string }) => {
    setJournal(j => {
      const next = [...j, { ...e, ts: new Date().toISOString() }].slice(-500)
      try { localStorage.setItem(STORAGE_KEY, JSON.stringify(next)) } catch {}
      return next
    })
  }

  useEffect(() => {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) setJournal(JSON.parse(saved))
    } catch {}
  }, [])

  const exportJournal = () => {
    const blob = new Blob([JSON.stringify(journal, null, 2)], { type: 'application/json' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'deeputin_session.json'; a.click()
  }

  const clear = () => { setJournal([]); localStorage.removeItem(STORAGE_KEY) }

  return (
    <div className={`sj ${open ? 'open' : ''}`}>
      <button className="sj-toggle" onClick={() => setOpen(v => !v)} title="Журнал сессии">
        📋<span className="sj-badge">{journal.length}</span>
      </button>
      {open && <div className="sj-panel">
        <div className="sj-header">
          <strong>Журнал сессии</strong>
          <div className="sj-hdr-actions">
            <button onClick={exportJournal}>Экспорт</button>
            <button onClick={clear}>Очистить</button>
            <button onClick={() => setOpen(false)}>×</button>
          </div>
        </div>
        <div className="sj-list">
          {journal.length === 0 && <div className="sj-empty">Нет записей</div>}
          {journal.slice().reverse().slice(0, 100).map((e, i) => (
            <div key={i} className="sj-entry">
              <span className="sj-time">{e.ts.slice(11, 19)}</span>
              <span className="sj-act">{e.action}</span>
              {e.detail && <span className="sj-det">{e.detail.length > 40 ? e.detail.slice(0, 40) + '…' : e.detail}</span>}
            </div>
          ))}
        </div>
      </div>}
    </div>
  )
}