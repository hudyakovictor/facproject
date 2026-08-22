// ─── Timeline V7 Track Registry — полный каталог ценных данных ───
// Каждое поле из main_timeline.csv / photo_metrics.json / pair_metrics.json
// имеет назначение: DEFAULT (виден всегда), OPT-IN (dropdown «Данные»),
// POPUP (детали пары/кадра), EXCLUDED (с обоснованием).
// Обоснования по распределениям — см. VALUABLE_DATA_CATALOG_RU.md.

import type { Frame, PhotoMetrics, PairConnection } from './types'

export type TrackDomain = 'pair_evidence' | 'pair_raw' | 'pair_support' | 'applicability' | 'expression' | 'quality' | 'quality_ext'
export type Availability = 'default' | 'opt_in' | 'popup' | 'excluded'

export interface TrackDef {
  id: string
  label: string
  unit: string
  domain: TrackDomain
  availability: Availability
  displayMin: number
  displayMax: number
  color: string
  transform: 'none' | 'log1p'
  getPhoto?: (f: Frame, m?: PhotoMetrics) => number | null
  getPair?: (p: PairConnection) => number | null
}

const log = Math.log1p
export const TRACKS: TrackDef[] = [
  // ── P0 · геометрия пар (разреженные точки, все семейства) ──
  { id: 'pair_max_z', label: 'Max robust z', unit: 'z', domain: 'pair_evidence', availability: 'default', displayMin: 0, displayMax: 36, color: '#de9255', transform: 'log1p', getPair: p => p.meshMaxRobustZ },
  { id: 'pair_fdr', label: 'FDR10 (кольцо)', unit: '', domain: 'pair_evidence', availability: 'default', displayMin: 0, displayMax: 1, color: '#f4f6f8', transform: 'none', getPair: p => p.mtSignificantFdr10 ? 1 : 0 },
  // ── V14: RAW-геометрия (сырые значения, не z) — 6 метрик + калибровочный коридор ──
  { id: 'raw_rmse', label: 'RMSE raw', unit: '', domain: 'pair_raw', availability: 'opt_in', displayMin: 0.0015, displayMax: 0.08, color: '#5e9fe8', transform: 'log1p', getPair: p => p.meshRmse },
  { id: 'raw_median', label: 'Median raw', unit: '', domain: 'pair_raw', availability: 'opt_in', displayMin: 0.0015, displayMax: 0.08, color: '#4fb9c9', transform: 'log1p', getPair: p => p.meshMedian },
  { id: 'raw_p95', label: 'P95 raw', unit: '', domain: 'pair_raw', availability: 'opt_in', displayMin: 0.0015, displayMax: 0.08, color: '#de9255', transform: 'log1p', getPair: p => p.meshP95 },
  { id: 'raw_pt_rmse', label: 'PtPlane RMSE raw', unit: '', domain: 'pair_raw', availability: 'opt_in', displayMin: 0.0015, displayMax: 0.08, color: '#72bc8f', transform: 'log1p', getPair: p => p.meshPtPlaneRmse },
  { id: 'raw_pt_median', label: 'PtPlane Median raw', unit: '', domain: 'pair_raw', availability: 'opt_in', displayMin: 0.0015, displayMax: 0.08, color: '#bf8eda', transform: 'log1p', getPair: p => p.meshPtPlaneMedian },
  { id: 'raw_pt_p95', label: 'PtPlane P95 raw', unit: '', domain: 'pair_raw', availability: 'opt_in', displayMin: 0.0015, displayMax: 0.08, color: '#eac26b', transform: 'log1p', getPair: p => p.meshPtPlaneP95 },
  // ── V14: статусы пер-метричных z (семантика: шум/повышен/неуверенно) ──
  { id: 'metric_statuses', label: 'Статусы 6 метрик', unit: '', domain: 'pair_raw', availability: 'opt_in', displayMin: 0, displayMax: 1, color: '#e97366', transform: 'none', getPair: p => p.meshRmseStatus === 'mesh_elevated_but_uncertain' ? 1 : 0 },
  // ── P1 · opt-in: пять per-metric robust-z ──
  { id: 'z_rmse', label: 'RMSE z', unit: 'z', domain: 'pair_evidence', availability: 'opt_in', displayMin: 0, displayMax: 36, color: '#5e9fe8', transform: 'log1p', getPair: p => p.meshRmseRobustZ },
  { id: 'z_median', label: 'Median z', unit: 'z', domain: 'pair_evidence', availability: 'opt_in', displayMin: 0, displayMax: 36, color: '#4fb9c9', transform: 'log1p', getPair: p => p.meshMedianRobustZ },
  { id: 'z_p95', label: 'P95 z', unit: 'z', domain: 'pair_evidence', availability: 'opt_in', displayMin: 0, displayMax: 36, color: '#de9255', transform: 'log1p', getPair: p => p.meshP95RobustZ },
  { id: 'z_pt_rmse', label: 'PtPlane RMSE z', unit: 'z', domain: 'pair_evidence', availability: 'opt_in', displayMin: 0, displayMax: 36, color: '#72bc8f', transform: 'log1p', getPair: p => p.meshPtPlaneRmseRobustZ },
  { id: 'z_pt_median', label: 'PtPlane Median z', unit: 'z', domain: 'pair_evidence', availability: 'opt_in', displayMin: 0, displayMax: 36, color: '#bf8eda', transform: 'log1p', getPair: p => p.meshPtPlaneMedianRobustZ },
  // ── P0 · поддержка пар ──
  { id: 'pair_visibility', label: 'Mesh visible fraction', unit: '%', domain: 'pair_support', availability: 'default', displayMin: 0, displayMax: 1, color: '#5e9fe8', transform: 'none', getPair: p => p.meshVisibleFraction },
  { id: 'pair_vertices', label: 'Common vertices', unit: 'n', domain: 'pair_support', availability: 'opt_in', displayMin: log(14000), displayMax: log(23000), color: '#72bc8f', transform: 'log1p', getPair: p => p.meshCommonVertexCount },
  { id: 'pair_anchor', label: 'Anchor fraction', unit: '', domain: 'pair_support', availability: 'opt_in', displayMin: 0.25, displayMax: 0.38, color: '#bf8eda', transform: 'none', getPair: p => p.meshAnchorFraction },
  // ── P0 · применимость ──
  { id: 'alignment_quality', label: 'Alignment quality', unit: '', domain: 'applicability', availability: 'default', displayMin: 0, displayMax: 1, color: '#5e9fe8', transform: 'none', getPhoto: (_, m) => m?.alignmentQuality ?? null },
  { id: 'pair_align_residual', label: 'Pair align residual', unit: '', domain: 'applicability', availability: 'default', displayMin: 0, displayMax: 0.045, color: '#de9255', transform: 'none', getPair: p => p.meshAlignResidualAfterMedian },
  // ── P1 · экспрессия (confounder мягких тканей) — opt-in ──
  { id: 'expression', label: 'Общий индекс мимики (служебный)', unit: '', domain: 'expression', availability: 'opt_in', displayMin: 2.8, displayMax: 10.2, color: '#df84a8', transform: 'none', getPhoto: (_, m) => m?.expressionMagnitude ?? null },
  { id: 'jaw_open', label: 'Открытие рта', unit: '°', domain: 'expression', availability: 'default', displayMin: 0, displayMax: 142, color: '#bf8eda', transform: 'none', getPhoto: (_, m) => m?.jawOpenDegree ?? null },
  { id: 'corner_lift', label: 'Подъём уголков губ (служебный)', unit: '', domain: 'expression', availability: 'opt_in', displayMin: -0.07, displayMax: 0.11, color: '#eac26b', transform: 'none', getPhoto: (_, m) => m?.cornerLiftIoc ?? null },
  // ── P0 · качество (группа: резкость/шум/кожа/аутентичность) ──
  { id: 'sharpness', label: 'Резкость (служебная)', unit: 'log', domain: 'quality', availability: 'opt_in', displayMin: log(20), displayMax: log(2000), color: '#4fb9c9', transform: 'log1p', getPhoto: (_, m) => m?.laplacianVariance ?? null },
  { id: 'noise', label: 'Шум (служебный)', unit: '', domain: 'quality', availability: 'opt_in', displayMin: 0.2, displayMax: 3, color: '#eac26b', transform: 'none', getPhoto: (_, m) => m?.noiseResidualMean ?? null },
  { id: 'skin_quality', label: 'Качество кожи', unit: '', domain: 'quality', availability: 'default', displayMin: 0.3, displayMax: 1, color: '#72bc8f', transform: 'none', getPhoto: (_, m) => m?.skinQualityScore ?? null },
  { id: 'skin_auth', label: 'Аутентичность кожи', unit: '', domain: 'quality', availability: 'default', displayMin: -1.5, displayMax: 3.5, color: '#e97366', transform: 'none', getPhoto: (_, m) => m?.skinAuthenticityScore ?? null },
  // ── P2 · текстурная диагностика — opt-in ──
  { id: 'anisotropy', label: 'Анизотропия градиента (служебная)', unit: '', domain: 'quality_ext', availability: 'opt_in', displayMin: 1, displayMax: 3.7, color: '#9aa4b2', transform: 'none', getPhoto: (_, m) => m?.gradientAnisotropy ?? null },
  { id: 'hard_area', label: 'Доля сложной области (служебная)', unit: '', domain: 'quality_ext', availability: 'opt_in', displayMin: 0.2, displayMax: 0.6, color: '#d8b4fe', transform: 'none', getPhoto: (_, m) => m?.hardAreaFraction ?? null },
]

// Исключённые поля (availability='excluded' намеренно не в TRACKS):
//   uvMeanConfidence (0.072–0.152, узкая readiness-полоса), faceAreaRatio (кроп),
//   yaw/pitch/roll (ракурс зафиксирован bin'ом; значения — в hover кадра),
//   poseConfidence (5 уникальных значений — квантован), tenengradMean (дублирует
//   Laplacian), reprojectionRMSE (константный 0 на 1909 кадрах).

export const TRACK_GROUPS = [
  { key: 'pair', label: 'Геометрия пар', trackIds: ['pair_max_z', 'pair_fdr'] },
  { key: 'raw_geom', label: 'Техническая геометрия', trackIds: ['raw_rmse', 'raw_median', 'raw_p95', 'raw_pt_rmse', 'raw_pt_median', 'raw_pt_p95', 'metric_statuses'] },
  { key: 'pair_families', label: 'baseline + rolling семейства', trackIds: [] },
  { key: 'z_suite', label: 'пять robust-z на пару', trackIds: ['z_rmse', 'z_median', 'z_p95', 'z_pt_rmse', 'z_pt_median'] },
  { key: 'zones', label: 'зоны эффекта (глиф 3×3)', trackIds: [] },  // V8: zone_metrics.json; robustZ зон некалиброван — показываем raw rmse
  { key: 'support', label: 'Поддержка пар', trackIds: ['pair_visibility'] },
  { key: 'support_ext', label: 'вершины + якоря', trackIds: ['pair_vertices', 'pair_anchor'] },
  { key: 'applicability', label: 'Применимость', trackIds: ['alignment_quality', 'pair_align_residual'] },
  { key: 'expression', label: 'Открытие рта', trackIds: ['expression', 'jaw_open', 'corner_lift'] },
  { key: 'quality', label: 'Кожа: качество + аутентичность', trackIds: ['sharpness', 'noise', 'skin_quality', 'skin_auth'] },
  { key: 'quality_ext', label: 'Техническая диагностика кожи', trackIds: ['anisotropy', 'hard_area'] },
  { key: 'events', label: 'События и QC-иконки', trackIds: [] },
]

// V9: единый реестр исключённых полей — DataIntegrity показывает его,
// selftest может гардить. Причина обязательна: поле может вернуться только
// с новым доказательством информативности.
export const EXCLUDED_FIELDS: { field: string; reason: string }[] = [
  { field: 'uvMeanConfidence', reason: 'диапазон 0.072–0.152, readiness-only, не влияет на вывод' },
  { field: 'faceAreaRatio', reason: 'характеристика кропа Stage 1, не аналитический сигнал' },
  { field: 'yaw/pitch/roll tracks', reason: 'ракурс зафиксирован pose bin; значения — в hover кадра' },
  { field: 'poseConfidence', reason: '5 уникальных значений — квантован, неинформативен как график' },
  { field: 'tenengradMean', reason: 'дублирует Laplacian (оба оценщики резкости), не интерпретируется' },
  { field: 'reprojectionRMSE', reason: 'константный 0 на всех 1909 кадрах' },
]
