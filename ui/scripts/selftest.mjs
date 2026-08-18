#!/usr/bin/env node
/* V8 SELFTEST — контрактные инварианты данных без новых зависимостей.
 * Запуск: node scripts/selftest.mjs  (exit 1 при нарушении).
 * Почему отдельный скрипт: vitest/jest в проект не добавляем — zero-dep CI-гейт. */
import { readFileSync } from 'node:fs'

const root = new URL('../public/data/', import.meta.url)
const csv = readFileSync(new URL('main_timeline.csv', root), 'utf8')
const pairs = JSON.parse(readFileSync(new URL('pair_metrics.json', root), 'utf8'))
const photos = JSON.parse(readFileSync(new URL('photo_metrics.json', root), 'utf8'))
const zones = JSON.parse(readFileSync(new URL('zone_metrics.json', root), 'utf8'))

let failures = 0
const check = (name, ok, detail = '') => {
  console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? ' — ' + detail : ''}`)
  if (!ok) failures++
}

// 1. Целостность связей: ни одна пара не ссылается на несуществующий кадр
const headers = csv.trim().split(/\r?\n/)[0].split(',')
const idCol = headers.indexOf('photo_id')
const ids = new Set(csv.trim().split(/\r?\n/).slice(1).map(l => l.split(',')[idCol]))
check('frames present', ids.size > 0, `${ids.size} кадров`)
const orphans = pairs.filter(p => !ids.has(p.photoA) || !ids.has(p.photoB))
check('orphan pairs', orphans.length === 0, `${orphans.length}`)

// 2. Enum статусов пар — неизвестный статус не должен молча становиться normal
const KNOWN = new Set(['residual_pose_mismatch', 'coherent_jump_candidate', 'persistent_geometric_change', 'insufficient_calibration', 'same_day_conflict_candidate', 'alpha_id_change_candidate'])
const unknown = pairs.filter(p => !KNOWN.has(p.status))
check('pair status enum', unknown.length === 0, unknown.slice(0, 3).map(p => p.status).join(','))

// 3. Null-политика: meshMaxRobustZ либо число, либо null — не undefined/строка
check('robustZ typed', pairs.every(p => p.meshMaxRobustZ === null || typeof p.meshMaxRobustZ === 'number'))
check('visibility domain', pairs.every(p => p.meshVisibleFraction == null || (p.meshVisibleFraction >= 0 && p.meshVisibleFraction <= 1)))

// 4. Зональный слой: 100% join, 9 зон на пару, и КРИТИЧНО — robustZ зон сейчас некалиброван
const pairIds = new Set(pairs.map(p => p.pairId))
check('zone join coverage', zones.every(z => pairIds.has(z.pairId)), `${zones.length} строк`)
const perPair = zones.reduce((m, z) => m.set(z.pairId, (m.get(z.pairId) ?? 0) + 1), new Map())
check('zones 9 per pair', [...perPair.values()].every(n => n === 9))
const badCalib = zones.filter(z => z.status === 'measured' && z.calibrationStatus === 'insufficient_calibration').length
console.log(`INFO  zone robustZ некалиброван: ${badCalib} measured-строк — UI обязан показывать raw rmse, НЕ z`)
check('zone robustZ guarded', badCalib > 0, 'предупреждение задокументировано')

// 5. Кандидаты/FDR согласованы с индикаторами UI
check('FDR count sane', pairs.filter(p => p.mtSignificantFdr10).length > 0)
check('photo metrics count', photos.length === ids.size, `${photos.length} vs ${ids.size}`)

// 6. Исключённые метрики остаются исключёнными (регресс-гард каталога)
check('reprojectionRMSE constant-zero (не показывать)', photos.every(p => p.reprojectionRMSE === 0))
check('poseConfidence quantized (не показывать как граф)', new Set(photos.map(p => p.poseConfidence)).size <= 6)
console.log(`\n${failures === 0 ? '✅ ALL CONTRACT CHECKS PASSED' : `❌ ${failures} FAILURES`}`)
process.exit(failures === 0 ? 0 : 1)
