// ─── Расширенная система типов данных DEEPUTIN ───

export type PoseBin =
  | 'frontal'
  | 'left_light' | 'right_light'
  | 'left_mid' | 'right_mid'
  | 'left_deep' | 'right_deep'
  | 'left_profile' | 'right_profile'

export type StatusValue = 'valid' | 'invalid' | 'unknown' | 'not_provided'

export interface Frame {
  // ─── Идентификация ───
  id: string
  date: string
  sameDateSequence: number
  timestamp: number
  year: number

  // ─── Поза ───
  poseBin: PoseBin
  pitch: number
  yaw: number
  roll: number

  // ─── Источник ───
  sourceFilename: string
  sourceRelativePath: string

  // ─── Происхождение даты ───
  dateProvenanceStatus: string
  exifDate: string
  dateDeltaDays: number | null
  sourceClaimedDate: string
  sourceClaimedDeltaDays: number | null
  dateConflictSources: string
  sourceProvenanceStatus: string

  // ─── Хеши ───
  perceptualDhash: string
  nearDuplicateOf: string

  // ─── Статусы качества ───
  geometryStatus: StatusValue
  segmentationStatus: StatusValue
  uvStatus: StatusValue

  // ─── Покрытие ───
  combinedVisibleFraction: number
  skinMaskCoverage: number
  uvObservedCoverage: number

  // ─── Хронология ───
  chronologyGlobal: number
  chronologyInPose: number

}

// ─── Вычисляемые тренды и производные метрики ───
export interface TimelineMetric {
  id: string
  label: string
  labelShort: string
  unit: string
  color: string
  getValue: (frame: Frame) => number
  inverse: boolean  // высокое = плохо
}

export type AnomalySeverity = 'critical' | 'high' | 'medium' | 'low'
export type AnomalyType = 'sudden_jump' | 'sudden_return' | 'impossible_interval' | 'duplicate' | 'date_conflict' | 'quality' | 'status'

export interface AnomalyMarker {
  frameId: string
  type: AnomalyType
  severity: AnomalySeverity
  description: string
  value: number
}

export interface PoseColor {
  bin: PoseBin
  label: string
  color: string
  colorBright: string
}

// ─── Агрегированная статистика ───
export interface TimelineStats {
  totalFrames: number
  withAnomalies: number
  withDuplicates: number
  dateConflictCount: number
  geometryIssues: number
  avgVisibility: number
  avgAuthenticity: number
  yearRange: [number, number]
  poseDistribution: Record<string, number>
  statusDistribution: Record<string, number>
}

// ─── Пер-фото метрики из info.json (batch) ───

export interface PhotoMetrics {
  id: string
  pitch?: number
  yaw?: number
  roll?: number
  poseBin?: string
  alignmentQuality?: number
  expressionMagnitude?: number
  poseConfidence?: number
  smileDetected?: boolean
  jawOpenDetected?: boolean
  jawOpenDegree?: number
  faceAreaRatio?: number
  cornerLiftIoc?: number
  laplacianVariance?: number
  tenengradMean?: number
  noiseResidualMean?: number
  gradientAnisotropy?: number
  skinAuthenticityScore?: number
  skinAuthenticityStatus?: string
  skinQualityScore?: number
  maskStatus?: string
  hardAreaFraction?: number
  uvStatus?: string
  uvMeanConfidence?: number
  reprojectionRMSE?: number
}

export function getSkinAuthColor(score: number | undefined): string {
  if (score === undefined || score === null) return '#334155'
  if (score > 1.4) return '#ef4444'    // low_authenticity (above q99)
  if (score > 1.165) return '#f97316'  // borderline (q95-q99)
  if (score > 0.5) return '#eab308'    // elevated
  return '#22c55e'                     // normal
}

export interface PairConnection {
  pairId: string
  pairIndex: number
  pairType: string
  poseBin: string
  photoA: string
  photoB: string
  dateA: string
  dateB: string
  status: string
  qcSkipReason: string
  analysisSpace: string

  // Mesh metrics
  meshRmse: number | null
  meshMedian: number | null
  meshP95: number | null
  meshPtPlaneRmse: number | null
  meshPtPlaneMedian: number | null
  meshPtPlaneP95: number | null
  meshVisibleFraction: number | null
  meshCommonVertexCount: number | null
  meshFitVertexCount: number | null
  meshAnchorFraction: number | null
  meshEvidenceLevel: string
  meshAnatomicalZoneCount: number | null
  meshAlignmentTrimmedCount: number | null
  meshAlignResidualBeforeMedian: number | null
  meshAlignResidualAfterMedian: number | null

  // Calibration
  meshCalibratedStatus: string
  meshCalibratedMetricCount: number | null
  meshCalibratedElevatedCount: number | null
  meshMaxRobustZ: number | null

  // Per-metric robust z and status
  meshRmseRobustZ: number | null
  meshMedianRobustZ: number | null
  meshP95RobustZ: number | null
  meshPtPlaneRmseRobustZ: number | null
  meshPtPlaneMedianRobustZ: number | null

  meshRmseStatus: string
  meshMedianStatus: string
  meshP95Status: string
  meshPtPlaneRmseStatus: string
  meshPtPlaneMedianStatus: string

  // Calibration medians
  meshRmseCalMedian: number | null
  meshRmseCalP95: number | null
  meshMedianCalMedian: number | null
  meshMedianCalP95: number | null
  meshP95CalMedian: number | null
  meshP95CalP95: number | null

  // FDR (P0)
  mtPApprox: number | null
  mtQValue: number | null
  mtSignificantFdr10: boolean
  mtFdr10DiagnosticFlag: string
  mtRole: string
  mtRoleDetail: string
  mtPointSupport: number | null

  // Expression
  smileDetectedA: boolean
  smileDetectedB: boolean
  jawOpenDetectedA: boolean
  jawOpenDetectedB: boolean
  jawOpenRatioA: number | null
  jawOpenRatioB: number | null
  expressionSource: string
  cornerLiftIocA: number | null
  cornerLiftIocB: number | null

  // Quality
  alignmentQualityA: number | null
  alignmentQualityB: number | null

  // Provenance
  nearDuplicatePair: boolean
  dateProvenanceLimited: boolean
}

export function getPairSeverity(p: PairConnection): AnomalySeverity {
  const z = p.meshMaxRobustZ ?? 0
  if (z > 20) return 'critical'
  if (z > 10) return 'high'
  if (z > 5) return 'medium'
  return 'low'
}

export function getPairColor(p: PairConnection): string {
  const z = p.meshMaxRobustZ ?? 0
  if (z > 20) return '#ef4444'
  if (z > 10) return '#f97316'
  if (z > 5) return '#eab308'
  if (z > 3) return '#38bdf8'
  return '#22c55e'
}

export function getPairColorRGBA(p: PairConnection, alpha: number = 0.6): string {
  const z = p.meshMaxRobustZ ?? 0
  if (z > 20) return `rgba(239,68,68,${alpha})`
  if (z > 10) return `rgba(249,115,22,${alpha})`
  if (z > 5) return `rgba(234,179,8,${alpha})`
  if (z > 3) return `rgba(56,189,248,${alpha})`
  return `rgba(34,197,94,${alpha})`
}
export const POSE_CONFIGS: PoseColor[] = [
  { bin: 'frontal',      label: 'Анфас',        color: '#38bdf8', colorBright: '#7dd3fc' },
  { bin: 'left_light',   label: 'Левый 3/4 light', color: '#4ade80', colorBright: '#86efac' },
  { bin: 'right_light',  label: 'Правый 3/4 light', color: '#fbbf24', colorBright: '#fde68a' },
  { bin: 'left_mid',     label: 'Левый 3/4 mid',   color: '#f472b6', colorBright: '#f9a8d4' },
  { bin: 'right_mid',    label: 'Правый 3/4 mid',  color: '#fb923c', colorBright: '#fdba74' },
  { bin: 'left_deep',    label: 'Левый 3/4 deep',  color: '#818cf8', colorBright: '#a5b4fc' },
  { bin: 'right_deep',   label: 'Правый 3/4 deep', color: '#c084fc', colorBright: '#d8b4fe' },
  { bin: 'left_profile',  label: 'Левый профиль',   color: '#94a3b8', colorBright: '#cbd5e1' },
  { bin: 'right_profile', label: 'Правый профиль',  color: '#f87171', colorBright: '#fca5a5' },
]

export function getPoseColor(bin: string): string {
  return POSE_CONFIGS.find(p => p.bin === bin)?.color ?? '#38bdf8'
}
export function getPoseColorBright(bin: string): string {
  return POSE_CONFIGS.find(p => p.bin === bin)?.colorBright ?? '#7dd3fc'
}
export function getPoseLabel(bin: string): string {
  return POSE_CONFIGS.find(p => p.bin === bin)?.label ?? bin
}

// ─── Метрики для отображения на графиках ───
export const ALL_METRICS: TimelineMetric[] = [
  {
    id: 'visibility',
    label: 'Видимость лица',
    labelShort: 'Видимость',
    unit: '%',
    color: '#38bdf8',
    getValue: (f) => f.combinedVisibleFraction * 100,
    inverse: false,
  },
  {
    id: 'skin_coverage',
    label: 'Покрытие кожи',
    labelShort: 'Кожа',
    unit: '%',
    color: '#4ade80',
    getValue: (f) => f.skinMaskCoverage * 100,
    inverse: false,
  },
  {
    id: 'uv_coverage',
    label: 'Покрытие UV',
    labelShort: 'UV',
    unit: '%',
    color: '#c084fc',
    getValue: (f) => f.uvObservedCoverage * 100,
    inverse: false,
  },
  {
    id: 'pitch',
    label: 'Наклон (Pitch)',
    labelShort: 'Pitch',
    unit: '°',
    color: '#fbbf24',
    getValue: (f) => f.pitch,
    inverse: true,
  },
  {
    id: 'yaw',
    label: 'Поворот (Yaw)',
    labelShort: 'Yaw',
    unit: '°',
    color: '#f472b6',
    getValue: (f) => Math.abs(f.yaw),
    inverse: true,
  },
]

// PATCH: QC metrics are opt-in. The default timeline is pair evidence + photos + time.
export const DEFAULT_VISIBLE_METRICS: string[] = []

// ─── Timeline Track Registry (Step 2) ───
// Нормативный конфиг дорожек таймлайна. Каждая дорожка — один источник данных.
// Default: только pair evidence. QC tracks — opt-in через кнопку.

export interface TimelineTrackDef {
  id: string
  label: string
  source: 'pair_evidence' | 'photo_metric' | 'qc' | 'diagnostic'
  unit: string
  domain: 'geometry' | 'texture' | 'applicability' | 'provenance'
  applicability: 'always' | 'opt_in'
  scale: 'linear' | 'log' | 'discrete'
  nullPolicy: 'skip' | 'zero' | 'break_line'
  defaultVisible: boolean
  tooltip: string
  legendSymbol: string
  referenceLine?: { label: string; value: number; color: string }
  offScaleMarker?: { threshold: number; symbol: string }
}

export const TIMELINE_TRACK_REGISTRY: TimelineTrackDef[] = [
  // P0 — pair evidence (default visible)
  { id: 'pair_candidate', label: 'Кандидаты', source: 'pair_evidence', unit: '', domain: 'geometry', applicability: 'always', scale: 'discrete', nullPolicy: 'skip', defaultVisible: true, tooltip: 'Пары, прошедшие порог candidate', legendSymbol: '◆' },
  { id: 'pair_effect_stems', label: 'Эффект пар', source: 'pair_evidence', unit: 'z', domain: 'geometry', applicability: 'always', scale: 'linear', nullPolicy: 'skip', defaultVisible: true, tooltip: 'Calibrated robust z — расстояние от калибровочного эталона', legendSymbol: '◠', referenceLine: { label: 'cal median', value: 0, color: '#5e9fe8' } },
  { id: 'pair_fdr', label: 'FDR значимость', source: 'pair_evidence', unit: '', domain: 'geometry', applicability: 'always', scale: 'discrete', nullPolicy: 'skip', defaultVisible: true, tooltip: 'q-value FDR10 — контроль множественного тестирования', legendSymbol: '‼' },

  // P1 — QC (opt-in, кнопка QC)
  { id: 'qc_visibility', label: 'QC: видимость', source: 'qc', unit: '%', domain: 'applicability', applicability: 'opt_in', scale: 'linear', nullPolicy: 'break_line', defaultVisible: false, tooltip: 'Доля видимых вершин лица', legendSymbol: '▂' },
  { id: 'qc_alignment', label: 'QC: alignment', source: 'qc', unit: '', domain: 'applicability', applicability: 'opt_in', scale: 'linear', nullPolicy: 'skip', defaultVisible: false, tooltip: 'Качество выравнивания 3D-модели', legendSymbol: '⊞' },
  { id: 'qc_skin_quality', label: 'QC: качество кожи', source: 'qc', unit: '', domain: 'applicability', applicability: 'opt_in', scale: 'linear', nullPolicy: 'skip', defaultVisible: false, tooltip: 'Качество текстурного анализа', legendSymbol: '◉' },

  // P2 — photo metrics (opt-in)
  { id: 'photo_visibility', label: 'Видимость фото', source: 'photo_metric', unit: '%', domain: 'applicability', applicability: 'opt_in', scale: 'linear', nullPolicy: 'break_line', defaultVisible: false, tooltip: 'Видимость лица на фото', legendSymbol: '▂', referenceLine: { label: '50%', value: 50, color: '#5e9fe860' } },
  { id: 'photo_pose', label: 'Поза', source: 'photo_metric', unit: '°', domain: 'geometry', applicability: 'opt_in', scale: 'linear', nullPolicy: 'break_line', defaultVisible: false, tooltip: 'Угол поворота головы (yaw)', legendSymbol: '↔' },

  // P3 — skin/texture diagnostics (opt-in, diagnostic only)
  { id: 'skin_authenticity', label: 'Аутентичность кожи', source: 'diagnostic', unit: 'z', domain: 'texture', applicability: 'opt_in', scale: 'linear', nullPolicy: 'skip', defaultVisible: false, tooltip: 'Z-score аутентичности кожи — diagnostic, не identity evidence', legendSymbol: '◌', referenceLine: { label: 'q95', value: 1.165, color: '#de9255' } },
]
// ─── Zone metrics (zone_metrics.json) — добавлено в V8 ───
// 3×3 анатомическая сетка: x_{vertical}_{horizontal}, vertical/horizontal ∈ low|center|high.
export interface ZoneMetric {
  pairId: string
  poseBin: string
  photoA: string
  photoB: string
  zone: string
  status: string                 // 'measured' | 'insufficient_visibility' | ...
  pointCount: number | null
  rmse: number | null
  median: number | null
  p95: number | null
  robustZ: number | null         // ВНИМАНИЕ: в текущем export calibrationStatus='insufficient_calibration' и значения недостоверны (медиана ~2.8e6) — НЕ отображать как z!
  signedX: number | null
  signedY: number | null
  signedZ: number | null
  calibrationP95?: number | null
  calibrationStatus?: string
  mtPApprox?: number | null
  mtQValue?: number | null
  mtSignificantFdr10?: boolean
  mtRole?: string
  mtFdr10DiagnosticFlag?: string
}
