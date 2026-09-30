import React from 'react';

const colorFor = (status) => status === 'pass' ? '#3fb950' : status === 'warn' ? '#d29922' : status === 'fail' ? '#f85149' : '#8b949e';

export default function TimelineQualityPanel({ keyframes = [], onDownload, loading = false }) {
  if (!keyframes.length) return null;
  const findingsCount = keyframes.reduce((total, frame) => total + (frame.photo?.findings?.length || 0) + (frame.mesh?.findings?.length || 0), 0);
  return (
    <details style={{ background: '#161b22', border: '1px solid #30363d', borderRadius: 8, padding: 11 }}>
      <summary style={{ cursor: 'pointer', color: '#79c0ff', fontSize: 11, fontWeight: 700, textTransform: 'uppercase' }}>
        🧪 Timeline input quality · {findingsCount} findings
      </summary>
      <div style={{ color: '#8b949e', fontSize: 10, lineHeight: 1.45, margin: '8px 0' }}>
        Эвристические проверки качества снимка и реконструированного mesh для каждого keyframe. Это не оценка ground-truth точности реконструкции.
      </div>
      <div style={{ display: 'grid', gap: 6 }}>
        {keyframes.map((frame, index) => (
          <div key={`${frame.index ?? index}-${frame.label}`} style={{ background: '#0d1117', border: '1px solid #30363d', borderRadius: 6, padding: 8 }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 6, marginBottom: 6 }}>
              <b style={{ color: '#e6edf3', fontSize: 10 }}>{frame.label || `Face ${index + 1}`}</b>
              <span style={{ color: '#8b949e', fontSize: 9 }}>{frame.year ?? 'undated'}</span>
            </div>
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 5 }}>
              {[['Photo', frame.photo], ['Mesh', frame.mesh]].map(([title, report]) => (
                <div key={title} style={{ borderLeft: `2px solid ${colorFor(report?.status)}`, paddingLeft: 6 }}>
                  <div style={{ color: '#8b949e', fontSize: 9 }}>{title}</div>
                  <div style={{ color: colorFor(report?.status), fontSize: 10, fontWeight: 700 }}>{report?.status || 'not run'} · {report?.score ?? '—'}/100</div>
                  {(report?.findings || []).slice(0, 2).map((finding, findingIndex) => <div key={`${finding.code}-${findingIndex}`} title={finding.message} style={{ color: '#8b949e', fontSize: 9, marginTop: 2 }}>{finding.code}</div>)}
                  {(report?.findings || []).length > 2 && <div style={{ color: '#6e7681', fontSize: 8 }}>+{report.findings.length - 2} more</div>}
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
      {onDownload && <div style={{ display: 'flex', gap: 6, marginTop: 8 }}>
        {['html', 'json'].map((format) => <button key={format} type="button" disabled={loading} onClick={() => onDownload(format)} style={{ flex: 1, padding: 6, border: '1px solid #30363d', borderRadius: 5, background: '#21262d', color: '#c9d1d9', cursor: loading ? 'wait' : 'pointer', fontSize: 9 }}>{loading ? '⏳' : `⬇ ${format.toUpperCase()} timeline report`}</button>)}
      </div>}
    </details>
  );
}
