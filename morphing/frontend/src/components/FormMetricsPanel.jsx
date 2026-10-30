import React, { useEffect, useMemo, useRef, useState } from 'react';
import { IDENTITY_COLORS, IDENTITY_LABELS, IDENTITY_LETTERS, UNKNOWN_COLOR, identityColor } from '../constants/identities';

// ── ФОРМА-МЕТРИКИ: 30 утверждённых метрик по двум фото ───────────────────────
// Цвет ячейки — цвет того человека, на которого смотрит значение метрики. Эталон —
// медиана метрики по спокойным кадрам каждой из трёх личностей (put / vas / udmurt).
// Значение делит ячейку между ДВУМЯ ближайшими эталонами пропорционально близости:
// ровно посередине между двумя лицами — 50/50 двумя цветами, у самой медианы — один
// цвет. Так сразу виден общий тренд: кто преобладает по всему набору метрик.
// Все 30 ячеек залиты одинаково насыщенно (бледный вариант на тёмном фоне не читался);
// 9 устойчивых к подфронтальному повороту метрик обведены БЕЛОЙ РАМКОЙ — им можно верить
// при угле головы 10–25°.
// Серая ячейка — метрика не посчиталась; пунктир под числом — ни на одно из трёх лиц это
// значение не похоже (дальше откалиброванной гулянки одного лица).

const GROUP_TITLES = {
  ldm_hypotheses: 'Профиль и средняя зона (3D-гипотезы)',
  ldm_top3d: 'Базовые 3D-отношения (106 точек)',
  ldm134_eyes: 'Глаза (134 точки)',
  ldm134_brows: 'Брови (134 точки)',
  ldm134_lips: 'Губы (134 точки)',
  mp_top30: 'MediaPipe: каркас лица',
  mp_hypotheses: 'MediaPipe: гипотезы',
  mp_probe: 'MediaPipe: probe-признаки',
  cross_iris_fissure: 'Кросс: радужка (MP) × щель (134)',
};
const GROUP_ORDER = Object.keys(GROUP_TITLES);
const MARK = { same: '✓', border: '~', differ: '✗', unknown: '·' };
const RU_VERDICT = { same: 'совпадает', border: 'на границе', differ: 'расходится', unknown: 'нет данных' };
// Насыщенность заливки общая для всех 30 ячеек: различать метрики надо цветом, а не
// бледностью — полупрозрачный вариант на тёмном фоне не читался.
const FILL_ALPHA = 0.92;

function numberFormat(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
  const abs = Math.abs(value);
  const digits = abs >= 100 ? 1 : abs >= 1 ? 3 : 4;
  return Number(value).toFixed(digits);
}

function hexToRgba(hex, alpha) {
  const digits = hex.replace('#', '');
  const full = digits.length === 3 ? digits.split('').map((c) => c + c).join('') : digits;
  const n = parseInt(full, 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

// Настоящий WCAG-контраст: заливка ложится на фон панели, поэтому считаем составной цвет
// и берём тот текст (белый или тёмный), который на нём читается лучше.
const PANEL_BG = [22, 27, 34];
const TEXT_LIGHT = [255, 255, 255];
const TEXT_DARK = [13, 17, 23];

function rgbOf(hex) {
  const digits = hex.replace('#', '');
  const n = parseInt(digits.length === 3 ? digits.split('').map((c) => c + c).join('') : digits, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

function relLum(rgb) {
  const [r, g, b] = rgb.map((c) => {
    const v = c / 255;
    return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrastRatio(a, b) {
  const [hi, lo] = [relLum(a), relLum(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

function composedOf(hex, alpha = FILL_ALPHA) {
  return rgbOf(hex).map((c, i) => c * alpha + PANEL_BG[i] * (1 - alpha));
}

function textOn(hex, alpha = FILL_ALPHA) {
  const composed = composedOf(hex, alpha);
  return contrastRatio(composed, TEXT_LIGHT) >= contrastRatio(composed, TEXT_DARK) ? '#ffffff' : '#0d1117';
}

// Ячейка залита двумя цветами: выбираем текст, который читается на ХУДШЕЙ из половин,
// иначе число «тонет» там, где градиент переходит в тёмно-синий.
function textOnSplit(split) {
  const parts = (split || []).filter((p) => p && p.w > 0.05);
  if (!parts.length) return '#e6edf3';
  const worst = (text) => Math.min(...parts.map((p) => contrastRatio(composedOf(identityColor(p.ident)), rgbOf(text))));
  return worst(TEXT_LIGHT) >= worst(TEXT_DARK) ? '#ffffff' : '#0d1117';
}

// Жёсткие границы полос: 50/50 видно как две равные половины, а не как размытое смешение.
// Насыщенность одна и та же что для 30, что для 9: бледный вариант не читался.
function splitGradient(split) {
  const parts = (split || []).filter((p) => p && p.w > 0.001);
  if (!parts.length) return hexToRgba(UNKNOWN_COLOR, 0.5);
  if (parts.length === 1) return hexToRgba(identityColor(parts[0].ident), FILL_ALPHA);
  let acc = 0;
  const stops = parts.map((p, i) => {
    const from = Math.round(acc * 100);
    acc += p.w;
    const to = i === parts.length - 1 ? 100 : Math.round(acc * 100);
    return `${hexToRgba(identityColor(p.ident), FILL_ALPHA)} ${from}%, ${hexToRgba(identityColor(p.ident), FILL_ALPHA)} ${to}%`;
  });
  // 90deg = строго слева направо: граница halves вертикальная. Под углом (100deg) она
  // уезжала по диагонали и выглядела артефактом.
  return `linear-gradient(90deg, ${stops.join(', ')})`;
}

// Устойчивые к подфронтальному повороту 9 метрик ничем не залиты иначе — они обведены
// белой рамкой: цвет по-прежнему отвечает «за кого», рамка — «кому можно верить на угле».
function cellStyle(att, trusted) {
  const known = Boolean(att && att.who);
  return {
    background: splitGradient(att?.split),
    color: known ? textOnSplit(att.split) : '#e6edf3',
    border: trusted ? '2px solid #ffffff' : `1px solid ${known ? hexToRgba(identityColor(att.who), 0.55) : '#30363d'}`,
    fontWeight: trusted ? 700 : 600,
    borderBottomStyle: !trusted && att?.stray ? 'dashed' : 'solid',
  };
}

// Короткая подпись под числом: буква личности (и доли, если ячейку делят двое).
function attMark(att) {
  const parts = (att?.split || []).filter((p) => p.w > 0.001);
  if (!parts.length) return '—';
  const letters = parts.map((p) => IDENTITY_LETTERS[p.ident] || '?').join('·');
  if (parts.length === 1) return letters;
  return `${letters} ${parts.map((p) => Math.round(p.w * 100)).join('/')}`;
}

function cellTitle(att, value) {
  if (!att?.who) return att?.reason || 'нет значения';
  const medics = Object.entries(att.medians || {})
    .map(([ident, m]) => `${IDENTITY_LABELS[ident] || ident}: ${numberFormat(m)}`)
    .join(' · ');
  const [near, far] = att.split;
  return [
    `эталоны (${att.regime}${att.extrapolated ? ', ракурс вне калибровки' : ''}): ${medics}`,
    `это значение: ${numberFormat(value)}`,
    far ? `ближе к ${IDENTITY_LABELS[near.ident]} — ${(near.w * 100).toFixed(0)}%, у ${IDENTITY_LABELS[far.ident]} ${(far.w * 100).toFixed(0)}%` : '',
    att.distance !== null && att.distance !== undefined ? `до ближайшего эталона ${numberFormat(att.distance)} полосы` : '',
    att.stray ? 'ни на одно из трёх лиц не похоже (дальше обычной гулянки одного лица)' : '',
  ].filter(Boolean).join('\n');
}

const base = { border: '1px solid #30363d', borderRadius: 8, background: '#161b22', padding: 10 };
const muted = { color: '#8b949e', fontSize: 10, lineHeight: 1.5 };
const num = { fontVariantNumeric: 'tabular-nums' };

// Полоса «кто преобладает»: средние доли цвета по набору ячеек одной фотографии.
function DominanceBar({ people, label, title, strong }) {
  const mix = people?.mix || {};
  const entries = Object.entries(mix).filter(([, share]) => share > 0.001);
  if (!entries.length) {
    return <div style={{ ...muted, fontSize: 9 }}>{label}: {people?.no_value ? 'нет посчитанных метрик' : 'нет эталонов'} · 0/{people?.total || 0}</div>;
  }
  const count = people?.count || {};
  return (
    <div title={title} style={{ marginBottom: 4 }}>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 5, fontSize: 9, color: '#8b949e' }}>
        <span style={{ color: strong ? '#e6edf3' : '#8b949e', fontWeight: strong ? 700 : 400 }}>{label}</span>
        <span style={{ color: strong ? identityColor(people.lead) : '#8b949e', fontWeight: strong ? 700 : 400 }}>
          {IDENTITY_LABELS[people.lead]} {Math.round((people.lead_share || 0) * 100)}%
        </span>
        {people.stray ? <span>· мимо всех троих {people.stray}</span> : null}
      </div>
      <div style={{ display: 'flex', height: strong ? 11 : 8, borderRadius: 999, overflow: 'hidden', border: '1px solid #30363d', marginTop: 2 }}>
        {entries.map(([ident, share]) => (
          <div key={ident} style={{ width: `${share * 100}%`, background: IDENTITY_COLORS[ident] || UNKNOWN_COLOR }} title={`${IDENTITY_LABELS[ident] || ident}: ${Math.round(share * 100)}%`} />
        ))}
      </div>
      <div style={{ display: 'flex', gap: 6, fontSize: 8, marginTop: 1 }}>
        {entries.map(([ident, share]) => (
          <span key={ident} style={{ color: IDENTITY_COLORS[ident] || UNKNOWN_COLOR }}>
            {IDENTITY_LETTERS[ident] || '?'} {Math.round(share * 100)}%
            {strong && count[ident] ? <span style={{ color: '#8b949e' }}> ({count[ident]})</span> : null}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function FormMetricsPanel({ photoA, photoB }) {
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [open, setOpen] = useState(false);
  const token = useRef(0);

  const calculate = async () => {
    if (!photoA || !photoB || loading) return;
    const id = token.current + 1;
    token.current = id;
    setLoading(true);
    setError('');
    try {
      const form = new FormData();
      form.append('photo_a', photoA);
      form.append('photo_b', photoB);
      const response = await fetch('/api/form-metrics', { method: 'POST', body: form });
      const payload = await response.json().catch(() => ({}));
      if (token.current !== id) return;
      if (!response.ok) throw new Error(payload.detail || `HTTP ${response.status}`);
      setResult(payload);
    } catch (requestError) {
      if (token.current === id) setError(requestError.message || 'Запрос метрик не прошёл');
    } finally {
      if (token.current === id) setLoading(false);
    }
  };

  useEffect(() => {
    if (photoA && photoB) { calculate(); setOpen(true); }
    else { setResult(null); setError(''); setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [photoA, photoB]);

  const groups = useMemo(() => {
    const byGroup = new Map();
    (result?.rows || []).forEach((row) => {
      if (!byGroup.has(row.group)) byGroup.set(row.group, []);
      byGroup.get(row.group).push(row);
    });
    return GROUP_ORDER.filter((key) => byGroup.has(key)).map((key) => [key, byGroup.get(key)]);
  }, [result]);

  const ready = Boolean(photoA && photoB);
  const summary = result?.summary?.all;
  const people = result?.summary?.people;

  return (
    <details style={base} open={open} onToggle={(event) => setOpen(event.currentTarget.open)}>
      <summary style={{ cursor: 'pointer', color: '#8b949e', fontSize: 11, fontWeight: 700, textTransform: 'uppercase' }}>
        🎨 30 метрик формы по двум фото · {loading ? 'считаем…' : summary ? `${summary.total} строк` : 'нужны оба фото'}
      </summary>
      <div style={{ ...muted, margin: '8px 0' }}>
        Цвет ячейки — <b>цвет того человека</b>, на которого смотрит значение метрики: {Object.keys(IDENTITY_COLORS).map((ident) => IDENTITY_LABELS[ident]).join(', ')}.
        Посередине между двумя лицами ячейка делится <b>50/50</b>, ближе к одному — доля больше у него.
        Все {result?.metric_set?.approved || 30} метрик залиты одинаково насыщенно;{' '}
        <b style={{ border: '2px solid #ffffff', padding: '0 3px', borderRadius: 3 }}>белой рамкой</b> обведены{' '}
        {result?.metric_set?.trusted || 9} устойчивых к подфронтальному повороту (10–25°) — им доверия больше.
      </div>
      <button
        type="button"
        onClick={calculate}
        disabled={!ready || loading}
        style={{ width: '100%', padding: '7px 9px', borderRadius: 6, border: '1px solid #30363d', background: loading ? '#30363d' : '#21262d', color: '#c9d1d9', cursor: ready && !loading ? 'pointer' : 'not-allowed', fontSize: 10 }}
      >
        {loading ? '⏳ Считаем: 3D-реконструкция + MediaPipe (10–20 с)…' : result ? '↻ Пересчитать метрики' : 'Рассчитать 30 метрик'}
      </button>
      {error && <div role="alert" style={{ marginTop: 7, color: '#ff7b72', fontSize: 10 }}>{error}</div>}

      {result && (
        <div style={{ marginTop: 10 }}>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, ...muted }}>
            <span>{result.regime.note}</span>
            {result.photos.map((photo) => (
              <span key={photo.label}>
                {photo.label}: yaw {photo.yaw ?? '—'}°{photo.expression && photo.expression.neutral === false ? ` · мимика (${photo.expression.flags.join(', ')})` : ''}
                {photo.mediapipe?.available ? '' : ' · MediaPipe недоступен'}
              </span>
            ))}
          </div>

          <div style={{ display: 'flex', gap: 10, margin: '10px 0', flexWrap: 'wrap' }}>
            {result.photos.map((photo) => {
              const side = photo.label.toLowerCase();
              return (
                <div key={photo.label} style={{ flex: '1 1 150px', minWidth: 140 }}>
                  <DominanceBar
                    people={people?.trusted?.[side]}
                    label={`★ ${result.metric_set.trusted} устойчивых · фото ${photo.label}`}
                    title="Средний цвет по девяти метрикам, которые держат подфронт 10–25°: им доверия больше"
                    strong
                  />
                  <DominanceBar
                    people={people?.all?.[side]}
                    label={`все ${result.metric_set.approved} метрик · фото ${photo.label}`}
                    title={result.meaning.mix}
                  />
                </div>
              );
            })}
          </div>

          <div style={{ display: 'flex', gap: 6, margin: '8px 0', flexWrap: 'wrap', alignItems: 'center' }}>
            {Object.keys(IDENTITY_COLORS).map((ident) => (
              <span key={ident} style={{ background: hexToRgba(IDENTITY_COLORS[ident], FILL_ALPHA), border: `1px solid ${hexToRgba(IDENTITY_COLORS[ident], 0.55)}`, color: textOn(IDENTITY_COLORS[ident]), borderRadius: 5, padding: '3px 7px', fontSize: 9, fontWeight: 600 }}>
                {IDENTITY_LETTERS[ident]} {IDENTITY_LABELS[ident]}
              </span>
            ))}
            <span style={{ background: `linear-gradient(90deg, ${hexToRgba(IDENTITY_COLORS.put, FILL_ALPHA)} 0%, ${hexToRgba(IDENTITY_COLORS.put, FILL_ALPHA)} 50%, ${hexToRgba(IDENTITY_COLORS.udmurt, FILL_ALPHA)} 50%, ${hexToRgba(IDENTITY_COLORS.udmurt, FILL_ALPHA)} 100%)`, border: '1px solid #30363d', color: textOnSplit([{ ident: 'put', w: 0.5 }, { ident: 'udmurt', w: 0.5 }]), borderRadius: 5, padding: '3px 7px', fontSize: 9, fontWeight: 600 }} title={result.meaning.cell_color}>
              посередине — 50/50
            </span>
            <span style={{ background: hexToRgba(IDENTITY_COLORS.put, FILL_ALPHA), border: '2px solid #ffffff', color: textOn(IDENTITY_COLORS.put), borderRadius: 5, padding: '2px 6px', fontSize: 9, fontWeight: 700 }}>
              ★ белая рамка = {result.metric_set.trusted} устойчивых
            </span>
          </div>
          <div style={{ ...muted, fontSize: 9 }}>
            Под числом — буква личности и доли. {MARK.differ} {RU_VERDICT.differ} в столбце «Пара» — два снимка
            расходятся сильнее, чем два кадра одного лица (границы калиброваны по разностям внутри каждого лица).
            Разные цвета в одной строке = метрика смотрит на разных людей.
          </div>

          {groups.map(([group, rows]) => (
            <div key={group} style={{ marginTop: 12 }}>
              <div style={{ color: '#8b949e', fontSize: 9, fontWeight: 700, marginBottom: 4, textTransform: 'uppercase' }}>
                {GROUP_TITLES[group]} · {rows.length}
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', tableLayout: 'fixed', fontSize: 10 }}>
                <colgroup>
                  <col style={{ width: '40%' }} />
                  <col style={{ width: '18%' }} />
                  <col style={{ width: '18%' }} />
                  <col style={{ width: '24%' }} />
                </colgroup>
                <thead>
                  <tr style={{ color: '#8b949e', fontSize: 9, textAlign: 'left' }}>
                    <th style={{ padding: '2px 4px', fontWeight: 600 }}>Метрика</th>
                    <th style={{ padding: '2px 4px', fontWeight: 600, textAlign: 'right' }}>A</th>
                    <th style={{ padding: '2px 4px', fontWeight: 600, textAlign: 'right' }}>B</th>
                    <th style={{ padding: '2px 4px', fontWeight: 600 }}>Пара</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.name} title={`${row.description}\nполоса ${numberFormat(row.band)} · |A−B| = ${numberFormat(row.diff)} (${numberFormat(row.ratio)} полосы) · границы ${row.k_same}/${row.k_differ}\nэталоны разнесены на ${numberFormat(row.min_gap)} полосы (меньше 1 — метрика этих людей почти не различает)\nрасходится у разных лиц: ${row.signal_cross === null || row.signal_cross === undefined ? '—' : `${Math.round(row.signal_cross * 100)}%`} пар${row.extrapolated ? '\nракурс вне калибровки (>25°) — граница смягчена' : ''}`}>
                      <td style={{ padding: '3px 4px', borderBottom: '1px solid #21262d', overflowWrap: 'anywhere' }}>
                        <span style={{ fontWeight: row.trusted ? 700 : 400, color: row.trusted ? '#e6edf3' : '#8b949e', fontSize: 9 }}>
                          {row.trusted ? '★' : ''}{row.name}
                        </span>
                      </td>
                      {['a', 'b'].map((side) => (
                        <td key={side} title={cellTitle(row[side], row[`value_${side}`])} style={{ ...cellStyle(row[side], row.trusted), padding: '3px 4px', textAlign: 'right', borderRadius: 4, fontSize: 9, ...num }}>
                          <div>{numberFormat(row[`value_${side}`])}</div>
                          {/* Без opacity: 8px на насыщенной заливке с прозрачностью уже не читался. */}
                          <div style={{ fontSize: 8, fontWeight: 400, overflowWrap: 'anywhere' }}>{attMark(row[side])}</div>
                        </td>
                      ))}
                      <td style={{ padding: '3px 4px', borderBottom: '1px solid #21262d', color: row.other_people ? identityColor(row.a.who) : '#8b949e', fontSize: 9 }}>
                        {MARK[row.verdict]} {row.verdict_ru}
                        {row.other_people ? <div style={{ color: '#d29922', fontWeight: 700 }}>разные лица</div> : null}
                        {row.reason ? <div style={{ color: '#8b949e', overflowWrap: 'anywhere' }}>{row.reason}</div> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ))}
          <div style={{ ...muted, marginTop: 10 }}>
            {result.caveats.map((text) => <div key={text}>• {text}</div>)}
          </div>
        </div>
      )}
    </details>
  );
}
