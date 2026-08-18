import type { Frame, PairConnection } from './types'

export const DATA_CONTRACT_VERSION = 'deeputin-timeline-v2'
export type PairClass = { kind:'persistent'|'candidate'|'limited'|'diagnostic'; label:string; symbol:string; reportable:false }

/* Evidence is NOT computed here. Backend status is rendered conservatively.
   Even FDR-significant candidates remain candidates; the UI never upgrades
   them to a verdict/reportable fact. Unknown status defaults to diagnostic. */
export function classifyPair(p:PairConnection):PairClass{
  const s=p.status||'unknown'
  if(/mismatch|insufficient|limited|excluded|not_measurable/.test(s))return{kind:'limited',label:`Ограничено: ${s}`,symbol:'!',reportable:false}
  if(s==='persistent_geometric_change')return{kind:'persistent',label:`Устойчивое изменение · кандидат${p.mtSignificantFdr10?' · FDR10':''}`,symbol:'◆',reportable:false}
  if(s.includes('candidate'))return{kind:'candidate',label:`Кандидат: ${s}${p.mtSignificantFdr10?' · FDR10':''}`,symbol:'▲',reportable:false}
  return{kind:'diagnostic',label:`Диагностическая пара: ${s}`,symbol:'·',reportable:false}
}

export type FrameEvent={kind:'date'|'duplicate'|'same_day'|'limited';label:string;symbol:string;pairId?:string}
export function getFrameEvents(frame:Frame,pairs:PairConnection[]):FrameEvent[]{
  const out:FrameEvent[]=[]
  if(frame.dateConflictSources&&frame.dateConflictSources!=='[]')out.push({kind:'date',label:'Конфликт датировки',symbol:'D'})
  const limited=pairs.find(p=>classifyPair(p).kind==='limited')
  if(limited)out.push({kind:'limited',label:`Ограниченная пара: ${limited.status}`,symbol:'!',pairId:limited.pairId})
  if(frame.nearDuplicateOf)out.push({kind:'duplicate',label:'Near duplicate',symbol:'≈'})
  if(frame.sameDateSequence>1)out.push({kind:'same_day',label:`Кадр #${frame.sameDateSequence} в эту дату`,symbol:`#${frame.sameDateSequence}`})
  return out
}
export function pickDisplayPair(pairs:PairConnection[],lane:'evidence'|'qc'):PairConnection|undefined{
  const ranked=[...pairs].sort((a,b)=>rank(b)-rank(a));return lane==='evidence'?ranked.find(p=>['persistent','candidate'].includes(classifyPair(p).kind)):ranked.find(p=>classifyPair(p).kind==='limited')
}
function rank(p:PairConnection){const c=classifyPair(p);return(c.kind==='persistent'?400:c.kind==='candidate'?300:c.kind==='limited'?200:100)+(p.mtSignificantFdr10?20:0)+(p.pairType==='adjacent'?3:p.pairType==='baseline'?2:1)}

export function validatePairConnection(p:unknown):p is PairConnection{if(!p||typeof p!=='object')return false;const r=p as Record<string,unknown>;return['pairId','photoA','photoB','dateA','dateB','status','poseBin'].every(k=>typeof r[k]==='string'&&r[k])}
export function validatePairs(v:unknown):PairConnection[]{if(!Array.isArray(v))return[];return v.filter(validatePairConnection)}

// Gate 1/Этап 1: runtime-валидация кадров. Статусы геометрии/сегментации/UV
// приводим к известному набору, неизвестное значение логируем, но НЕ молча
// заменяем на 'unknown' (принцип «не фабриковать»).
const STATUS_SET = new Set(['valid', 'invalid', 'unknown', 'not_provided'])
export function validateFrames(v: unknown): Frame[] {
  if (!Array.isArray(v)) return []
  return v.filter((f): f is Frame => {
    if (!f || typeof f !== 'object') return false
    const r = f as Record<string, unknown>
    const ok = typeof r.id === 'string' && typeof r.date === 'string' && typeof r.poseBin === 'string'
    if (!ok) return false
    for (const k of ['geometryStatus', 'segmentationStatus', 'uvStatus'] as const) {
      const s = r[k]
      if (s != null && typeof s === 'string' && !STATUS_SET.has(s)) {
        console.warn(`[data-contract] кадр ${String(r.id)}: неизвестный статус ${k}=${s}, оставлен как есть`)
      }
    }
    return true
  })
}


// ─── V8: зональные данные и русские подписи 3×3 атласа ───
import type { ZoneMetric } from './types'

// Почему RU-маппинг здесь, а не в компоненте: зона — часть контракта данных;
// неизвестная зона НЕ выдумывается, а показывается как есть (принцип «не фабриковать»).
const V: Record<string, string> = { low: 'низ', center: 'центр', high: 'верх' }
const H: Record<string, string> = { low: 'лево', center: 'центр', high: 'право' }
export function zoneLabel(zone: string): string {
  const m = zone.match(/^x_(low|center|high)_(low|center|high)$/)
  return m ? `${V[m[1]]}·${H[m[2]]}` : zone
}

// Доминантная зона пары выбирается по raw rmse среди measured, потому что
// robustZ в текущем export НЕкалиброван (см. комментарий в types.ts).
export function dominantZone(zones: ZoneMetric[] | undefined): ZoneMetric | null {
  if (!zones?.length) return null
  const measured = zones.filter(z => z.status === 'measured' && z.rmse != null)
  if (!measured.length) return null
  return measured.reduce((a, b) => (b.rmse! > a.rmse! ? b : a))
}

export function validateZones(v: unknown): ZoneMetric[] {
  if (!Array.isArray(v)) return []
  return v.filter(z => z && typeof z === 'object'
    && typeof (z as Record<string, unknown>).pairId === 'string'
    && typeof (z as Record<string, unknown>).zone === 'string') as ZoneMetric[]
}

// V8: сверка версии контракта — payload без версии логируем, не молчим.
export function checkContractVersion(payload: unknown, source: string): void {
  const ver = (payload as Record<string, unknown> | null)?.contractVersion
  if (ver == null) console.info(`[data-contract] ${source}: нет contractVersion, принимаем ${DATA_CONTRACT_VERSION} по умолчанию`)
  else if (ver !== DATA_CONTRACT_VERSION) console.warn(`[data-contract] ${source}: версия ${String(ver)} ≠ ${DATA_CONTRACT_VERSION}`)
}
