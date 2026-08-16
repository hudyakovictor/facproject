/**
 * DEEPUTIN UI-v7 · Timeline Types
 * 
 * Core data types for the forensic timeline interface.
 */

// ========================================
// Photo & Timeline Data
// ========================================

export interface TimelinePhoto {
  id: string;
  date: string | null;
  t: number | null;
  bucket: string;
  era: string;
  quality: number | null;
  yaw: number | null;
  pitch: number | null;
  roll: number | null;
  fuzzy: string;
  measurementStatus: string;
  flags: string[];
  sourceMode: string;
  analysisStage: string;
  dateProvenanceStatus?: string | null;

  // Quality fields
  alignmentQuality?: number | null;
  poseConfidence?: number | null;
  detectionConfidence?: number | null;
  confidence?: number | null;

  // Texture fields
  skinQuality?: number | null;
  skinAuthenticity?: number | null;
  siliconeProb?: number | null;
  fillerProb?: number | null;
  wrinkleDensity?: number | null;
  subsurface?: number | null;
  uvCoverage?: number | null;

  // Geometry fields
  boneScore?: number | null;
  orbit?: number | null;
  chin?: number | null;
  jaw?: number | null;
  cheek?: number | null;
  symmetry?: number | null;

  // PCA fields
  p0?: number | null;
  p1?: number | null;
  p2?: number | null;

  // Calibration z-scores
  zOrbitDepth?: number | null;
  zChinProj?: number | null;
  zJawWidth?: number | null;
  zCheek?: number | null;

  // Chronology fields
  expressionMagnitude?: number | null;
  jawOpenDegree?: number | null;
  jawOpenRatio?: number | null;
  jawOpenDetected?: boolean;
  smileDetected?: boolean;
  visualAge?: number | null;
  calendarAge?: number | null;
  faceAreaRatio?: number | null;
  correctionMagnitude?: number | null;
  residualYaw?: number | null;
  residualPitch?: number | null;
  residualRoll?: number | null;

  // LDM fields (NEW for v7)
  ldmShapeDifference?: number | null;
  ldm106Difference?: number | null;
  ldm134Difference?: number | null;
  visibleLdm106?: number | null;
  visibleLdm134?: number | null;

  // Stage 2 fields
  evidenceState?: string;
  stage2PairCount?: number;
  stage2StatusCounts?: Record<string, number>;
  stage2EvidenceCounts?: Record<string, number>;

  // Other
  canonicalYaw?: number | null;
  exifAnomaly?: boolean;
  dateProvenanceLimited?: boolean;
  bayesianProjectionAvailable?: boolean;
  laplacianVariance?: number | null;
  tenengradMean?: number | null;
  noiseResidual?: number | null;
  skinMaskCoverage?: number | null;
}

export interface TimelineResponse {
  schema?: string;
  source_mode: string;
  not_a_verdict: boolean;
  note?: string;
  photos: TimelinePhoto[];
  era_meta: Record<string, { label: string; start: string; end: string }>;
  chronology_anomalies?: Record<string, unknown>;
  analysis_manifest?: Record<string, unknown>;
  analysis_stage?: string;
  stage1_manifest?: Record<string, unknown> | null;
  ui_fields_schema?: string;
  ui_fields_complete_photo_count?: number;
  ui_fields_violations_by_field?: Record<string, number>;
}

// ========================================
// Anomaly Types
// ========================================

export type AnomalyKind =
  | 'change_point'
  | 'persistent_change'
  | 'return'
  | 'rapid_rate'
  | 'same_day'
  | 'provenance'
  | 'review';

export interface AnomalyEvent {
  id: string;
  kind: AnomalyKind;
  label: string;
  time: number | null;
  year?: number;
  photoId?: string;
}

// ========================================
// Viewport & Navigation
// ========================================

export interface Viewport {
  start: number;
  end: number;
}

export interface TimeBounds {
  min: number;
  max: number;
}

// ========================================
// Track Types
// ========================================

export type TrackKind =
  | 'photo'
  | 'quality'
  | 'texture'
  | 'geometry'
  | 'pca'
  | 'calibration'
  | 'pose'
  | 'chronology'
  | 'ldm_difference'
  | 'anomaly';

export interface TrackDescriptor {
  id: string;
  kind: TrackKind;
  label: string;
  color: string;
  visible: boolean;
  height: number;
  dataKey: string;
  domain?: [number, number] | null;
  unit?: string | null;
}

// ========================================
// Filter Types
// ========================================

export interface FilterState {
  qualityRange: [number, number];
  alignmentQualityRange: [number, number];
  poseConfidenceRange: [number, number];
  skinQualityRange: [number, number];
  skinAuthenticityRange: [number, number];
  siliconeProbRange: [number, number];
  boneScoreRange: [number, number];
  symmetryRange: [number, number];
  yawRange: [number, number];
  pitchRange: [number, number];
  rollRange: [number, number];
  dateRange: [number, number] | null;
  visualAgeRange: [number, number];
  shapeDifferenceRange: [number, number];
  activeAnomalyKinds: Set<AnomalyKind>;
  searchQuery: string;
  activePoseBin: string | null;
  showFindingsOnly: boolean;
}

// ========================================
// Metric Types
// ========================================

export interface MetricPoint {
  time: number;
  value: number | null;
  photoId: string;
}

export interface TrackData {
  descriptor: TrackDescriptor;
  points: MetricPoint[];
  domain: [number, number];
}
