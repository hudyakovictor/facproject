/* V9: unit-тесты контракта на node:test (zero-dep). Запуск: node --test tests/ */
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { classifyPair, zoneLabel, dominantZone, validatePairs, validateZones, validateFrames } from '../src/timeline-data-contract.ts'

const basePair = {
  pairId: 'p1', pairIndex: 0, pairType: 'adjacent', poseBin: 'frontal',
  photoA: 'a', photoB: 'b', dateA: '2000-01-01', dateB: '2000-02-01',
  status: 'residual_pose_mismatch', qcSkipReason: '', analysisSpace: '',
  meshRmse: null, meshMedian: null, meshP95: null, meshPtPlaneRmse: null,
  meshPtPlaneMedian: null, meshPtPlaneP95: null, meshVisibleFraction: null,
  meshCommonVertexCount: null, meshFitVertexCount: null, meshAnchorFraction: null,
  meshEvidenceLevel: '', meshAnatomicalZoneCount: null, meshAlignmentTrimmedCount: null,
  meshAlignResidualBeforeMedian: null, meshAlignResidualAfterMedian: null,
  meshCalibratedStatus: '', meshCalibratedMetricCount: null, meshCalibratedElevatedCount: null,
  meshMaxRobustZ: null, meshRmseRobustZ: null, meshMedianRobustZ: null, meshP95RobustZ: null,
  meshPtPlaneRmseRobustZ: null, meshPtPlaneMedianRobustZ: null,
  meshRmseStatus: '', meshMedianStatus: '', meshP95Status: '', meshPtPlaneRmseStatus: '', meshPtPlaneMedianStatus: '',
  meshRmseCalMedian: null, meshRmseCalP95: null, meshMedianCalMedian: null, meshMedianCalP95: null,
  meshP95CalMedian: null, meshP95CalP95: null,
  mtPApprox: null, mtQValue: null, mtSignificantFdr10: false, mtFdr10DiagnosticFlag: '', mtRole: '', mtRoleDetail: '', mtPointSupport: null,
  smileDetectedA: false, smileDetectedB: false, jawOpenDetectedA: false, jawOpenDetectedB: false,
  jawOpenRatioA: null, jawOpenRatioB: null, expressionSource: '', cornerLiftIocA: null, cornerLiftIocB: null,
  alignmentQualityA: null, alignmentQualityB: null, nearDuplicatePair: false, dateProvenanceLimited: false,
}

test('classifyPair: limited статусы не candidate', () => {
  assert.equal(classifyPair({ ...basePair, status: 'residual_pose_mismatch' }).kind, 'limited')
  assert.equal(classifyPair({ ...basePair, status: 'insufficient_calibration' }).kind, 'limited')
})

test('classifyPair: persistent и candidate', () => {
  assert.equal(classifyPair({ ...basePair, status: 'persistent_geometric_change' }).kind, 'persistent')
  assert.equal(classifyPair({ ...basePair, status: 'coherent_jump_candidate' }).kind, 'candidate')
})

test('classifyPair: unknown → diagnostic; reportable всегда false', () => {
  const c = classifyPair({ ...basePair, status: 'something_new_2030' })
  assert.equal(c.kind, 'diagnostic')
  assert.equal(c.reportable, false)
})

test('zoneLabel: атлас и fallback без выдумывания', () => {
  assert.equal(zoneLabel('x_low_low'), 'низ·лево')
  assert.equal(zoneLabel('x_high_center'), 'верх·центр')
  assert.equal(zoneLabel('x_unknown'), 'x_unknown')
})

test('dominantZone: только measured с rmse; null-безопасно', () => {
  assert.equal(dominantZone(undefined), null)
  assert.equal(dominantZone([{ status: 'insufficient_visibility', rmse: null }]), null)
  const d = dominantZone([
    { status: 'measured', rmse: 0.01, zone: 'x_low_low' },
    { status: 'measured', rmse: 0.05, zone: 'x_high_high' },
  ])
  assert.equal(d?.zone, 'x_high_high')
})

test('validatePairs/validateZones отбрасывают битые записи', () => {
  assert.equal(validatePairs([basePair, { nope: true }, null]).length, 1)
  assert.equal(validateZones([{ pairId: 'p1', zone: 'x_low_low' }, { zone: 'x' }, 42]).length, 1)
  assert.equal(validateZones('not-array').length, 0)
})

const validFrame = {
  id: 'f1', date: '2000-01-01', sameDateSequence: 1, timestamp: 0, year: 2000,
  poseBin: 'frontal', pitch: 0, yaw: 0, roll: 0,
  sourceFilename: '', sourceRelativePath: '',
  dateProvenanceStatus: 'filename_only', exifDate: '', dateDeltaDays: null,
  sourceClaimedDate: '', sourceClaimedDeltaDays: null, dateConflictSources: '[]',
  sourceProvenanceStatus: 'not_provided',
  perceptualDhash: '', nearDuplicateOf: '',
  geometryStatus: 'valid', segmentationStatus: 'valid', uvStatus: 'valid',
  combinedVisibleFraction: 0.6, skinMaskCoverage: 0.3, uvObservedCoverage: 0.8,
  chronologyGlobal: 1, chronologyInPose: 1,
}

test('validateFrames: пропускает корректные кадры, отбрасывает битые', () => {
  assert.equal(validateFrames([validFrame]).length, 1)
  assert.equal(validateFrames([validFrame, { id: 'f2' }, null, 42]).length, 1)
  assert.equal(validateFrames('not-array').length, 0)
  // Неизвестный статус не выбрасывает кадр и не подменяется молча (логируется).
  const warn = console.warn
  const calls: string[] = []
  console.warn = (...a: unknown[]) => calls.push(String(a[0]))
  const out = validateFrames([{ ...validFrame, geometryStatus: 'future_status_x' }])
  console.warn = warn
  assert.equal(out.length, 1)
  assert.equal(out[0].geometryStatus, 'future_status_x')
  assert.ok(calls.some(s => s.includes('future_status_x')))
})
