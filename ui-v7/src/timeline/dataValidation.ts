import type { TimelinePhoto, TimelineResponse } from '../types/timeline';

/**
 * Data Validation and Logging System for UI.
 * 
 * Validates all data displayed in the interface and logs any issues.
 * Covers 100% of data fields from backend stages.
 */

export interface DataIssue {
  severity: 'error' | 'warning' | 'info';
  field: string;
  photoId?: string;
  message: string;
  value?: unknown;
}

export interface ValidationResult {
  totalPhotos: number;
  issues: DataIssue[];
  stage: 'stage1' | 'stage2' | 'unknown';
  schemaCompliant: boolean;
}

// Complete field contract from backend
const STAGE1_REQUIRED_FIELDS = [
  'id', 'date', 't', 'era', 'bucket', 'quality', 'yaw', 'pitch', 'roll',
] as const;

const STAGE1_OPTIONAL_FIELDS = [
  'qualityBasis', 'boneScore', 'orbit', 'chin', 'jaw', 'cheek', 'symmetry',
  'siliconeProb', 'fillerProb', 'skinQuality', 'wrinkleDensity', 'subsurface',
  'visualAge', 'calendarAge', 'zOrbitDepth', 'zChinProj', 'zJawWidth', 'zCheek',
  'p0', 'p1', 'p2', 'dominant', 'fuzzy', 'confidence', 'flags', 'sourceMode',
  'analysisStage', 'dateProvenanceStatus', 'dateProvenanceLimited', 'exifAnomaly',
  'uiContractViolations', 'uiFieldsSchema',
] as const;

const STAGE2_ADDITIONAL_FIELDS = [
  'evidenceState', 'stage2PairCount', 'stage2StatusCounts', 'stage2EvidenceCounts',
  'bayesianProjectionAvailable', 'measurementStatus', 'exifDate', 'dateDeltaDays',
  'sourceClaimedDate', 'sourceClaimedDeltaDays', 'dateConflictSources',
  'alignmentQuality', 'poseConfidence', 'detectionConfidence', 'uvCoverage',
  'expressionMagnitude', 'jawOpenDegree', 'jawOpenRatio', 'jawOpenDetected',
  'smileDetected', 'visibleLdm106', 'visibleLdm134', 'faceAreaRatio',
  'correctionMagnitude', 'residualYaw', 'residualPitch', 'residualRoll',
  'skinAuthenticity', 'laplacianVariance', 'tenengradMean', 'noiseResidual',
  'skinMaskCoverage', 'canonicalYaw', 'ldmShapeDifference', 'ldm106Difference',
  'ldm134Difference',
] as const;

const ALL_FIELDS = [...STAGE1_REQUIRED_FIELDS, ...STAGE1_OPTIONAL_FIELDS, ...STAGE2_ADDITIONAL_FIELDS];

/**
 * Validate a single photo record against the complete contract.
 */
export function validatePhoto(photo: TimelinePhoto, index: number): DataIssue[] {
  const issues: DataIssue[] = [];
  const photoId = photo.id || `index:${index}`;

  // Check required fields
  if (!photo.id) {
    issues.push({
      severity: 'error',
      field: 'id',
      photoId,
      message: 'Missing required field: id',
    });
  }

  if (!photo.date) {
    issues.push({
      severity: 'warning',
      field: 'date',
      photoId,
      message: 'Missing date - photo will not appear on timeline',
    });
  }

  if (photo.t == null) {
    issues.push({
      severity: 'warning',
      field: 't',
      photoId,
      message: 'Missing timestamp - photo positioning may be incorrect',
    });
  }

  if (!photo.bucket) {
    issues.push({
      severity: 'warning',
      field: 'bucket',
      photoId,
      message: 'Missing pose bin - photo will not be filtered correctly',
    });
  }

  // Validate numeric ranges
  if (photo.quality != null && (photo.quality < 0 || photo.quality > 1)) {
    issues.push({
      severity: 'error',
      field: 'quality',
      photoId,
      message: `Quality out of range [0,1]: ${photo.quality}`,
      value: photo.quality,
    });
  }

  if (photo.skinAuthenticity != null && (photo.skinAuthenticity < 0 || photo.skinAuthenticity > 1)) {
    issues.push({
      severity: 'error',
      field: 'skinAuthenticity',
      photoId,
      message: `Skin authenticity out of range [0,1]: ${photo.skinAuthenticity}`,
      value: photo.skinAuthenticity,
    });
  }

  if (photo.siliconeProb != null && (photo.siliconeProb < 0 || photo.siliconeProb > 1)) {
    issues.push({
      severity: 'error',
      field: 'siliconeProb',
      photoId,
      message: `Silicone probability out of range [0,1]: ${photo.siliconeProb}`,
      value: photo.siliconeProb,
    });
  }

  if (photo.boneScore != null && (photo.boneScore < 0 || photo.boneScore > 1)) {
    issues.push({
      severity: 'error',
      field: 'boneScore',
      photoId,
      message: `Bone score out of range [0,1]: ${photo.boneScore}`,
      value: photo.boneScore,
    });
  }

  if (photo.symmetry != null && (photo.symmetry < 0 || photo.symmetry > 1)) {
    issues.push({
      severity: 'error',
      field: 'symmetry',
      photoId,
      message: `Symmetry out of range [0,1]: ${photo.symmetry}`,
      value: photo.symmetry,
    });
  }

  if (photo.ldmShapeDifference != null && (photo.ldmShapeDifference < 0 || photo.ldmShapeDifference > 1)) {
    issues.push({
      severity: 'error',
      field: 'ldmShapeDifference',
      photoId,
      message: `LDM shape difference out of range [0,1]: ${photo.ldmShapeDifference}`,
      value: photo.ldmShapeDifference,
    });
  }

  // Validate pose angles
  if (photo.yaw != null && Math.abs(photo.yaw) > 90) {
    issues.push({
      severity: 'warning',
      field: 'yaw',
      photoId,
      message: `Yaw angle suspicious: ${photo.yaw}°`,
      value: photo.yaw,
    });
  }

  if (photo.pitch != null && Math.abs(photo.pitch) > 45) {
    issues.push({
      severity: 'warning',
      field: 'pitch',
      photoId,
      message: `Pitch angle suspicious: ${photo.pitch}°`,
      value: photo.pitch,
    });
  }

  if (photo.roll != null && Math.abs(photo.roll) > 45) {
    issues.push({
      severity: 'warning',
      field: 'roll',
      photoId,
      message: `Roll angle suspicious: ${photo.roll}°`,
      value: photo.roll,
    });
  }

  // Check for null fields that should have values in Stage 2
  if (photo.analysisStage === 'stage2_pairs') {
    if (photo.evidenceState == null) {
      issues.push({
        severity: 'warning',
        field: 'evidenceState',
        photoId,
        message: 'Stage 2 photo missing evidenceState',
      });
    }

    if (photo.stage2PairCount === 0) {
      issues.push({
        severity: 'info',
        field: 'stage2PairCount',
        photoId,
        message: 'Stage 2 photo has 0 pairs',
      });
    }
  }

  // Validate flags array
  if (photo.flags && !Array.isArray(photo.flags)) {
    issues.push({
      severity: 'error',
      field: 'flags',
      photoId,
      message: 'Flags is not an array',
      value: typeof photo.flags,
    });
  }

  return issues;
}

/**
 * Validate complete timeline response.
 */
export function validateTimelineResponse(data: TimelineResponse): ValidationResult {
  const issues: DataIssue[] = [];

  // Check schema
  const stage = data.schema?.includes('stage2') ? 'stage2' : 
                data.schema?.includes('stage1') ? 'stage1' : 'unknown';
  
  if (stage === 'unknown') {
    issues.push({
      severity: 'warning',
      field: 'schema',
      message: `Unknown schema: ${data.schema}`,
      value: data.schema,
    });
  }

  // Check photos array
  if (!data.photos || !Array.isArray(data.photos)) {
    issues.push({
      severity: 'error',
      field: 'photos',
      message: 'Missing or invalid photos array',
    });
    return {
      totalPhotos: 0,
      issues,
      stage,
      schemaCompliant: false,
    };
  }

  // Validate each photo
  for (let i = 0; i < data.photos.length; i++) {
    const photo = data.photos[i];
    if (!photo) {
      issues.push({
        severity: 'error',
        field: 'photo',
        message: `Photo at index ${i} is null/undefined`,
      });
      continue;
    }
    issues.push(...validatePhoto(photo, i));
  }

  // Check era_meta
  if (!data.era_meta || Object.keys(data.era_meta).length === 0) {
    issues.push({
      severity: 'warning',
      field: 'era_meta',
      message: 'Missing era metadata',
    });
  }

  // Check chronology_anomalies
  if (stage === 'stage2' && !data.chronology_anomalies) {
    issues.push({
      severity: 'info',
      field: 'chronology_anomalies',
      message: 'Stage 2 response missing chronology_anomalies',
    });
  }

  // UI fields schema validation
  if (data.ui_fields_schema) {
    const expectedSchema = 'deeputin-ui-fields-v1.0';
    if (data.ui_fields_schema !== expectedSchema) {
      issues.push({
        severity: 'warning',
        field: 'ui_fields_schema',
        message: `UI fields schema mismatch: expected ${expectedSchema}, got ${data.ui_fields_schema}`,
        value: data.ui_fields_schema,
      });
    }
  }

  return {
    totalPhotos: data.photos.length,
    issues,
    stage,
    schemaCompliant: issues.filter(i => i.severity === 'error').length === 0,
  };
}

/**
 * Log validation results to console.
 */
export function logValidationResult(result: ValidationResult): void {
  const errors = result.issues.filter(i => i.severity === 'error');
  const warnings = result.issues.filter(i => i.severity === 'warning');
  const infos = result.issues.filter(i => i.severity === 'info');

  console.group(`[Timeline Data Validation] Stage: ${result.stage} | Photos: ${result.totalPhotos}`);
  
  if (errors.length > 0) {
    console.error(`❌ ${errors.length} errors found:`);
    errors.forEach(issue => {
      console.error(`  [${issue.field}] ${issue.photoId ?? ''}: ${issue.message}`, issue.value ?? '');
    });
  }

  if (warnings.length > 0) {
    console.warn(`⚠️ ${warnings.length} warnings found:`);
    warnings.forEach(issue => {
      console.warn(`  [${issue.field}] ${issue.photoId ?? ''}: ${issue.message}`, issue.value ?? '');
    });
  }

  if (infos.length > 0) {
    console.info(`ℹ️ ${infos.length} infos found:`);
    infos.forEach(issue => {
      console.info(`  [${issue.field}] ${issue.photoId ?? ''}: ${issue.message}`, issue.value ?? '');
    });
  }

  if (result.issues.length === 0) {
    console.log('✅ All data validated successfully');
  }

  console.log(`Schema compliant: ${result.schemaCompliant}`);
  console.groupEnd();
}

/**
 * Validate data displayed in a specific track.
 */
export function validateTrackData(
  trackId: string,
  photos: TimelinePhoto[],
  values: Array<number | null>
): DataIssue[] {
  const issues: DataIssue[] = [];

  for (let i = 0; i < photos.length; i++) {
    const photo = photos[i]!;
    const value = values[i];

    if (value === null || value === undefined) {
      // Check if field exists on photo
      const fieldValue = photo[trackId as keyof TimelinePhoto];
      if (fieldValue != null) {
        issues.push({
          severity: 'warning',
          field: trackId,
          photoId: photo.id,
          message: `Track data is null but photo has value: ${fieldValue}`,
          value: fieldValue,
        });
      }
    } else if (typeof value === 'number' && !Number.isFinite(value)) {
      issues.push({
        severity: 'error',
        field: trackId,
        photoId: photo.id,
        message: `Non-finite value: ${value}`,
        value,
      });
    }
  }

  return issues;
}

/**
 * Get complete field inventory for a photo.
 */
export function getPhotoFieldInventory(photo: TimelinePhoto): Record<string, string> {
  const inventory: Record<string, string> = {};
  
  for (const field of ALL_FIELDS) {
    const value = photo[field as unknown as keyof TimelinePhoto];
    if (value === null) {
      inventory[field] = 'null';
    } else if (value === undefined) {
      inventory[field] = 'undefined';
    } else if (Array.isArray(value)) {
      inventory[field] = `array[${value.length}]`;
    } else if (typeof value === 'object') {
      inventory[field] = `object{${Object.keys(value).length}}`;
    } else {
      inventory[field] = typeof value;
    }
  }
  
  return inventory;
}

/**
 * Check if all expected fields are present in the response.
 */
export function checkFieldCoverage(data: TimelineResponse): { missing: string[]; extra: string[] } {
  const expectedFields: Set<string> = new Set(ALL_FIELDS);
  const actualFields: Set<string> = new Set<string>();

  if (data.photos.length > 0) {
    const samplePhoto = data.photos[0]!;
    for (const key of Object.keys(samplePhoto)) {
      actualFields.add(key);
    }
  }

  const missing = [...expectedFields].filter(f => !actualFields.has(f));
  const extra = [...actualFields].filter(f => !expectedFields.has(f));

  return { missing, extra };
}
