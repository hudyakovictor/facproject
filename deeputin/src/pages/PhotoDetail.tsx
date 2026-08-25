import { useEffect, useState } from 'react';

import { ApiRequestError, isAbortError, requestJson, unwrapArtifactPayload } from '@/shared/api';
import { PageBlueprint } from '@/shared/PageBlueprint';
import { hashParam, navigateTo } from '@/shared/navigation';
import type { BlockDefinition, PageDefinition } from '@/shared/contracts';

/**
 * PAGE: Photo Detail.
 * Blocks are semantic ownership boundaries. Their internal controls and views stay together;
 * the page owner is free to choose the eventual composition.
 */
export const photoDetailPage = {
  id: 'photo-detail',
  title: 'Photo Detail',
  group: 'analytics',
  purpose:
    'Детальная рабочая область одного кадра: provenance, доступные артефакты, поза, качество, landmarks и texture/UV.',
  primaryQuestion:
    'Что известно об этом кадре, какие артефакты доступны и какие ограничения действуют?',
  blocks: [
    /**
     * BLOCK: Photo overview and artifact viewer.
     * OWNED ELEMENTS: photo identity, date and chronology, original, crop, thumbnail, mask and UV artifact viewer, availability and fallback labels, source provenance and file references, adjacent frames and pair navigation.
     * CONTRACT SURFACE: elements: artifact-specific labels for original/crop/thumbnail/mask/UV, API artifact endpoint context, mesh availability context; actions: open_original, open_thumbnail, open_face_crop, open_face_mask, open_uv_texture, open_artifact_source; states: measured, not_computed, skipped, not_applicable, stale.
     * landmarks_106, landmarks_134, visible_134.
     * DATA KEYS:
     * id, bucket, angles, full_mesh_available, artifact_name, texture_json, mesh_file, mesh_status, stage, relative_path, file_name, created_at.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * photo_id, date, same_date_sequence, chronology_index_global, pose_bin, source_filename, date_provenance_status,
     * source_relative_path, source_url, archive_url, provenance_status, artifact_kind, artifact_path, artifact_type,
     * availability, fallback_reason, mime_type, width, height, alt_text, caption,
     * original_equals_proxy, previous_photo_id, next_photo_id, same_date_photo_ids, pair_ids, current_date, current_pose_bin,
     * route_params, camera, normalization, crop, source_provenance, perceptual_dhash, near_duplicate_of.
     */
    {
      id: 'photo-detail.overview',
      title: 'Photo overview and artifact viewer',
      purpose:
        'Единый блок идентификации кадра, просмотра артефактов, provenance и навигации по соседним кадрам и парам.',
      elements: [
        'artifact-specific labels for original/crop/thumbnail/mask/UV',
        'API artifact endpoint context',
        'mesh availability context',
        'photo identity, date and chronology',
        'original, crop, thumbnail, mask and UV artifact viewer',
        'availability and fallback labels',
        'source provenance and file references',
        'adjacent frames and pair navigation',
      ],
      keys: [
        'landmarks_106',
        'landmarks_134',
        'visible_134',
        'id',
        'bucket',
        'angles',
        'full_mesh_available',
        'artifact_name',
        'texture_json',
        'mesh_file',
        'mesh_status',
        'stage',
        'relative_path',
        'file_name',
        'created_at',
        'source_file',
        'source_key',
        'api_endpoint',
        'limitations',
        'measurement_state',
        'quality_state',
        'visibility_state',
        'calibration_state',
        'schema',
        'source_mode',
        'not_a_verdict',
        'photo_id',
        'date',
        'same_date_sequence',
        'chronology_index_global',
        'pose_bin',
        'source_filename',
        'date_provenance_status',
        'source_relative_path',
        'source_url',
        'archive_url',
        'provenance_status',
        'artifact_kind',
        'artifact_path',
        'artifact_type',
        'availability',
        'fallback_reason',
        'mime_type',
        'width',
        'height',
        'alt_text',
        'caption',
        'original_equals_proxy',
        'previous_photo_id',
        'next_photo_id',
        'same_date_photo_ids',
        'pair_ids',
        'current_date',
        'current_pose_bin',
        'route_params',
        'camera',
        'normalization',
        'crop',
        'source_provenance',
        'perceptual_dhash',
        'near_duplicate_of',
      ],
      sourceRefs: [
        'stage1/<photo_id>/info.json',
        'stage1/main_timeline.csv',
        'stage1/<photo_id>/original.jpg',
        'stage1/<photo_id>/thumb.jpg',
        'stage1/<photo_id>/face_crop.jpg',
        'stage1/<photo_id>/face_mask.png',
        'stage1/<photo_id>/uv_texture.png',
        'stage1/<photo_id>/texture.json',
        'api/v1/photos/{photo_id}',
        'api/v1/photos/{photo_id}/info_keys',
        'api/v1/photos/{photo_id}/artifacts/{name}',
        'api/v1/photos/{photo_id}/image?kind={kind}',
      ],
      actions: [
        'open_original',
        'open_thumbnail',
        'open_face_crop',
        'open_face_mask',
        'open_uv_texture',
        'open_artifact_source',
        'open_source',
        'open_timeline',
        'open_adjacent_photo',
        'open_artifact',
        'switch_artifact_kind',
        'open_previous',
        'open_next',
        'open_pair',
        'return_to_timeline',
      ],
      requiredStates: [
        'measured',
        'not_computed',
        'skipped',
        'not_applicable',
        'stale',
        'loading',
        'empty',
        'unavailable',
        'error',
        'limited',
        'fallback',
      ],
    },
    /**
     * BLOCK: Pose, expression and quality.
     * OWNED ELEMENTS: yaw, pitch, roll and actual pose, expression and smile/jaw state, alignment and reprojection quality, visible landmarks and coverage, quality, authenticity and limitation explanation.
     * CONTRACT SURFACE: elements: measurement-state readout, texture quality context, gate selection context; actions: select_gate, open_texture, open_quality_definition; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * angles, texture_score, quality, visibility, calibration_status, stage, relative_path, file_name.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * yaw, pitch, roll, actual_pose, expression_magnitude, smile_detected, jaw_open_detected,
     * face_area_ratio, alignment_quality, coordinate_space, limitation_refs, visible_landmarks_106, visible_landmarks_134, combined_visible_fraction,
     * skin_mask_coverage, reprojection_rmse, skin_authenticity_score, skin_quality_score, geometry_status, segmentation_status, uv_status,
     * quality_state, visibility_state, corner_lift_ioc.
     */
    {
      id: 'photo-detail.pose-quality',
      title: 'Pose, expression and quality',
      purpose:
        'Совместный контекст позы, мимики, качества реконструкции и видимости, необходимый для чтения кадра.',
      elements: [
        'measurement-state readout',
        'texture quality context',
        'gate selection context',
        'yaw, pitch, roll and actual pose',
        'expression and smile/jaw state',
        'alignment and reprojection quality',
        'visible landmarks and coverage',
        'quality, authenticity and limitation explanation',
      ],
      keys: [
        'angles',
        'texture_score',
        'quality',
        'visibility',
        'calibration_status',
        'stage',
        'relative_path',
        'file_name',
        'source_file',
        'source_key',
        'source_url',
        'api_endpoint',
        'limitations',
        'measurement_state',
        'calibration_state',
        'schema',
        'source_mode',
        'not_a_verdict',
        'yaw',
        'pitch',
        'roll',
        'actual_pose',
        'expression_magnitude',
        'smile_detected',
        'jaw_open_detected',
        'face_area_ratio',
        'alignment_quality',
        'coordinate_space',
        'limitation_refs',
        'visible_landmarks_106',
        'visible_landmarks_134',
        'combined_visible_fraction',
        'skin_mask_coverage',
        'reprojection_rmse',
        'skin_authenticity_score',
        'skin_quality_score',
        'geometry_status',
        'segmentation_status',
        'uv_status',
        'quality_state',
        'visibility_state',
        'corner_lift_ioc',
      ],
      sourceRefs: [
        'stage1/<photo_id>/info.json → api/v1/photos/{photo_id}/info_keys',
        'stage1/main_timeline.csv → api/v1/photos',
        'stage1/<photo_id>/texture.json → api/v1/photos/{photo_id}/artifacts/texture.json',
      ],
      actions: [
        'select_gate',
        'open_texture',
        'open_quality_definition',
        'open_methodology',
        'filter_timeline_by_pose',
        'open_metric_definition',
        'open_limitation',
      ],
      requiredStates: [
        'measured',
        'not_computed',
        'skipped',
        'not_applicable',
        'stale',
        'empty',
        'limited',
        'unavailable',
        'error',
      ],
    },
    /**
     * BLOCK: Landmarks and surface diagnostics.
     * OWNED ELEMENTS: LDM106 and LDM134 views, visible masks and point selection, raw/aligned/original coordinate controls, texture and UV diagnostics, CSV/JSON source inspection and artifact limitations.
     * CONTRACT SURFACE: elements: API point-count and space response, visible and hidden point state, aligned and original source variants; actions: toggle_visibility_filter, open_api_landmarks, set_visibility_filter; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * count, space, points, landmarks_106, landmarks_134, visible_106, visible_134, source_filename, ldm106, ldm134, texture_json, stage, relative_path, file_name, artifact_type, created_at.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * point_set, landmarks, visible_mask, point_index, x, y, z,
     * unit, coordinate_space, csv_row, csv_column, source_ref, overlay_status, texture_score,
     * texture_status, uv_observed_coverage, texture_path, uv_path, availability, fallback_reason, source_key,
     * limitation_refs.
     */
    {
      id: 'photo-detail.landmarks-surface',
      title: 'Landmarks and surface diagnostics',
      purpose:
        'Самостоятельный диагностический блок для landmark-точек, coordinate spaces, texture score и UV-покрытия.',
      elements: [
        'API point-count and space response',
        'visible and hidden point state',
        'aligned and original source variants',
        'LDM106 and LDM134 views',
        'visible masks and point selection',
        'raw/aligned/original coordinate controls',
        'texture and UV diagnostics',
        'CSV/JSON source inspection and artifact limitations',
      ],
      keys: [
        'count',
        'space',
        'points',
        'landmarks_106',
        'landmarks_134',
        'visible_106',
        'visible_134',
        'source_filename',
        'ldm106',
        'ldm134',
        'texture_json',
        'stage',
        'relative_path',
        'file_name',
        'artifact_type',
        'created_at',
        'source_file',
        'source_url',
        'api_endpoint',
        'limitations',
        'measurement_state',
        'quality_state',
        'visibility_state',
        'calibration_state',
        'schema',
        'source_mode',
        'not_a_verdict',
        'point_set',
        'landmarks',
        'visible_mask',
        'point_index',
        'x',
        'y',
        'z',
        'unit',
        'coordinate_space',
        'csv_row',
        'csv_column',
        'source_ref',
        'overlay_status',
        'texture_score',
        'texture_status',
        'uv_observed_coverage',
        'texture_path',
        'uv_path',
        'availability',
        'fallback_reason',
        'source_key',
        'limitation_refs',
      ],
      sourceRefs: [
        'stage1/<photo_id>/ldm106_raw.csv',
        'stage1/<photo_id>/ldm106_aligned.csv',
        'stage1/<photo_id>/ldm106_original.csv',
        'stage1/<photo_id>/ldm106_chronology.csv',
        'stage1/<photo_id>/ldm134_raw.csv',
        'stage1/<photo_id>/ldm134_aligned.csv',
        'stage1/<photo_id>/ldm134_original.csv',
        'stage1/<photo_id>/ldm134_chronology.csv',
        'stage1/<photo_id>/info.json → api/v1/photos/{photo_id}/info_keys',
        'stage1/<photo_id>/texture.json → api/v1/photos/{photo_id}/artifacts/texture.json',
        'stage1/<photo_id>/uv_texture.png → api/v1/photos/{photo_id}/artifacts/uv_texture.png',
        'api/v1/photos/{photo_id}/landmarks/{count}/{space}',
      ],
      actions: [
        'toggle_visibility_filter',
        'open_api_landmarks',
        'set_visibility_filter',
        'select_point',
        'switch_point_set',
        'switch_coordinate_space',
        'open_source',
        'open_texture_artifact',
        'open_methodology',
      ],
      requiredStates: [
        'measured',
        'not_computed',
        'skipped',
        'not_applicable',
        'stale',
        'empty',
        'limited',
        'unavailable',
        'error',
        'long_content',
        'fallback',
      ],
    },
  ],
} satisfies PageDefinition;

type PhotoState = 'idle' | 'loading' | 'ready' | 'empty' | 'error';
type ArtifactKind = 'original' | 'thumbnail' | 'face_crop' | 'face_mask' | 'uv_texture';

type LandmarkSpace = 'raw' | 'aligned' | 'original';
type VisibilityFilter = 'all' | 'visible' | 'hidden';

interface PhotoRecord {
  [key: string]: unknown;
}

interface LandmarkPoint {
  [key: string]: unknown;
}

const ARTIFACTS: readonly { key: ArtifactKind; label: string }[] = [
  { key: 'original', label: 'Original' },
  { key: 'thumbnail', label: 'Thumbnail' },
  { key: 'face_crop', label: 'Face crop' },
  { key: 'face_mask', label: 'Face mask' },
  { key: 'uv_texture', label: 'UV texture' },
];

const POSE_FIELDS: readonly { label: string; key: string; unit?: string }[] = [
  { label: 'Yaw', key: 'yaw', unit: 'deg' },
  { label: 'Pitch', key: 'pitch', unit: 'deg' },
  { label: 'Roll', key: 'roll', unit: 'deg' },
  { label: 'Actual pose', key: 'actual_pose' },
  { label: 'Expression magnitude', key: 'expression_magnitude' },
  { label: 'Face area ratio', key: 'face_area_ratio' },
  { label: 'Alignment quality', key: 'alignment_quality' },
  { label: 'Reprojection RMSE', key: 'reprojection_rmse' },
  { label: 'Visible landmarks 106', key: 'visible_landmarks_106' },
  { label: 'Visible landmarks 134', key: 'visible_landmarks_134' },
  { label: 'Combined visible fraction', key: 'combined_visible_fraction' },
  { label: 'Skin mask coverage', key: 'skin_mask_coverage' },
  { label: 'UV observed coverage', key: 'uv_observed_coverage' },
  { label: 'Skin authenticity', key: 'skin_authenticity_score' },
  { label: 'Skin quality', key: 'skin_quality_score' },
  { label: 'Texture score', key: 'texture_score' },
  { label: 'Texture status', key: 'texture_status' },
  { label: 'Corner lift IOC', key: 'corner_lift_ioc' },
];

const POSE_GATES: readonly { label: string; key: string }[] = [
  { label: 'Quality state', key: 'quality_state' },
  { label: 'Visibility state', key: 'visibility_state' },
  { label: 'Calibration state', key: 'calibration_state' },
  { label: 'Geometry', key: 'geometry_status' },
  { label: 'Segmentation', key: 'segmentation_status' },
  { label: 'UV status', key: 'uv_status' },
  { label: 'Smile detected', key: 'smile_detected' },
  { label: 'Jaw open detected', key: 'jaw_open_detected' },
];

function detailDisplayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Unavailable';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return detailStructuredValue(value);
  return String(value);
}

function detailStructuredValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Unavailable';
  if (typeof value !== 'object') return String(value);
  try {
    const serialized = JSON.stringify(value);
    return serialized && serialized !== '{}' && serialized !== '[]' ? serialized : 'Unavailable';
  } catch {
    return 'Structured value unavailable';
  }
}

function detailStatusTone(value: unknown): 'positive' | 'warning' | 'muted' {
  if (value === true) return 'positive';
  if (value === false) return 'warning';
  if (typeof value !== 'string') return 'muted';
  if (
    ['measured', 'valid', 'pass', 'complete', 'supported', 'accepted', 'available'].includes(value)
  ) {
    return 'positive';
  }
  if (
    [
      'limited',
      'partial',
      'not_computed',
      'skipped',
      'missing',
      'fallback',
      'review',
      'none',
      'unavailable',
      'stale',
      'error',
      'not_applicable',
    ].includes(value)
  ) {
    return 'warning';
  }
  return 'muted';
}

function DetailStatus({ value, label }: { value: unknown; label?: string }) {
  const tone = detailStatusTone(value);
  return (
    <span className={`photo-status photo-status--${tone}`}>
      <span className="photo-status-dot" aria-hidden="true" />
      {label ?? detailDisplayValue(value)}
    </span>
  );
}

function photoErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.detail;
  return 'Источник данных недоступен.';
}

function flattenPhotoInfo(payload: unknown): PhotoRecord {
  const source = unwrapArtifactPayload(payload);
  if (!source || typeof source !== 'object' || Array.isArray(source)) return {};
  const record = source as PhotoRecord;
  const flattened: PhotoRecord = { ...record };
  const categories = record.categories;
  if (categories && typeof categories === 'object' && !Array.isArray(categories)) {
    for (const category of Object.values(categories as PhotoRecord)) {
      if (!category || typeof category !== 'object' || Array.isArray(category)) continue;
      for (const [groupKey, group] of Object.entries(category as PhotoRecord)) {
        if (!group || typeof group !== 'object' || Array.isArray(group)) continue;
        flattened[groupKey] = group;
        Object.assign(flattened, group);
        for (const nested of Object.values(group as PhotoRecord)) {
          if (nested && typeof nested === 'object' && !Array.isArray(nested)) {
            Object.assign(flattened, nested);
          }
        }
      }
    }
  }
  return flattened;
}

function textureArtifactFields(payload: unknown): PhotoRecord {
  const texture = unwrapArtifactPayload(payload);
  if (!texture || typeof texture !== 'object' || Array.isArray(texture)) return {};
  const source = texture as PhotoRecord;
  const quality =
    source.quality && typeof source.quality === 'object' && !Array.isArray(source.quality)
      ? (source.quality as PhotoRecord)
      : undefined;
  const fields: PhotoRecord = { texture_json: source };
  if (quality) {
    if (quality.score !== undefined) fields.texture_score = quality.score;
    if (quality.status !== undefined) fields.texture_status = quality.status;
  }
  for (const key of ['uv_observed_coverage', 'texture_path', 'uv_path', 'fallback_reason']) {
    if (source[key] !== undefined) fields[key] = source[key];
  }
  return fields;
}

interface PhotoSourceResult {
  record: PhotoRecord;
  errors: readonly string[];
}

async function loadPhotoSources(photoId: string): Promise<PhotoSourceResult> {
  const [photoResult, infoResult, textureResult] = await Promise.allSettled([
    requestJson<PhotoRecord>(`/api/v1/photos/${encodeURIComponent(photoId)}`),
    requestJson<unknown>(`/api/v1/photos/${encodeURIComponent(photoId)}/info_keys`),
    requestJson<unknown>(`/api/v1/photos/${encodeURIComponent(photoId)}/artifacts/texture.json`),
  ]);
  const base = photoResult.status === 'fulfilled' ? photoResult.value : {};
  const info = infoResult.status === 'fulfilled' ? flattenPhotoInfo(infoResult.value) : {};
  const texture =
    textureResult.status === 'fulfilled' ? textureArtifactFields(textureResult.value) : {};
  const record = { ...base, ...info, ...texture };
  const errors = [
    photoResult.status === 'rejected'
      ? `photo: ${photoErrorMessage(photoResult.reason)}`
      : undefined,
    infoResult.status === 'rejected'
      ? `info.json: ${photoErrorMessage(infoResult.reason)}`
      : undefined,
    textureResult.status === 'rejected'
      ? `texture.json: ${photoErrorMessage(textureResult.reason)}`
      : undefined,
  ].filter((value): value is string => Boolean(value));
  if (!Object.keys(record).length && errors.length) {
    throw new ApiRequestError({ status: null, detail: errors.join(' · ') });
  }
  return { record, errors };
}

async function loadPhotoInfoArtifacts(photoId: string): Promise<PhotoSourceResult> {
  const [infoResult, textureResult] = await Promise.allSettled([
    requestJson<unknown>(`/api/v1/photos/${encodeURIComponent(photoId)}/info_keys`),
    requestJson<unknown>(`/api/v1/photos/${encodeURIComponent(photoId)}/artifacts/texture.json`),
  ]);
  const record = {
    ...(infoResult.status === 'fulfilled' ? flattenPhotoInfo(infoResult.value) : {}),
    ...(textureResult.status === 'fulfilled' ? textureArtifactFields(textureResult.value) : {}),
  };
  const errors = [
    infoResult.status === 'rejected'
      ? `info.json: ${photoErrorMessage(infoResult.reason)}`
      : undefined,
    textureResult.status === 'rejected'
      ? `texture.json: ${photoErrorMessage(textureResult.reason)}`
      : undefined,
  ].filter((value): value is string => Boolean(value));
  if (!Object.keys(record).length && errors.length) {
    throw new ApiRequestError({ status: null, detail: errors.join(' · ') });
  }
  return { record, errors };
}

function photoPoseValue(record: PhotoRecord, key: string): unknown {
  if (record[key] !== undefined && record[key] !== null) return record[key];
  const chronology = record.chronology;
  if (chronology && typeof chronology === 'object' && !Array.isArray(chronology)) {
    const chronologyRecord = chronology as PhotoRecord;
    if (chronologyRecord[key] !== undefined && chronologyRecord[key] !== null) {
      return chronologyRecord[key];
    }
    const actualPose = chronologyRecord.actual_pose;
    if (Array.isArray(actualPose)) {
      const angleIndex: Record<string, number> = { pitch: 0, yaw: 1, roll: 2 };
      if (key in angleIndex) return actualPose[angleIndex[key]];
    }
    if (actualPose && typeof actualPose === 'object' && !Array.isArray(actualPose)) {
      const poseRecord = actualPose as PhotoRecord;
      if (poseRecord[key] !== undefined && poseRecord[key] !== null) return poseRecord[key];
    }
  }
  const angles = record.angles;
  if (angles && typeof angles === 'object' && !Array.isArray(angles)) {
    return (angles as PhotoRecord)[key];
  }
  const sourceProvenance = record.source_provenance;
  if (
    sourceProvenance &&
    typeof sourceProvenance === 'object' &&
    !Array.isArray(sourceProvenance)
  ) {
    const provenanceRecord = sourceProvenance as PhotoRecord;
    if (provenanceRecord[key] !== undefined && provenanceRecord[key] !== null) {
      return provenanceRecord[key];
    }
  }
  const skin = record.skin;
  if (skin && typeof skin === 'object' && !Array.isArray(skin)) {
    const skinRecord = skin as PhotoRecord;
    const directSkinValue = skinRecord[key];
    if (directSkinValue !== undefined && directSkinValue !== null) return directSkinValue;
    const texture = skinRecord.texture;
    if (texture && typeof texture === 'object' && !Array.isArray(texture)) {
      const textureKey =
        key === 'texture_score' ? 'score' : key === 'texture_status' ? 'status' : key;
      return (texture as PhotoRecord)[textureKey];
    }
  }
  for (const containerKey of ['uv', 'quality_summary', 'reprojection']) {
    const container = record[containerKey];
    if (container && typeof container === 'object' && !Array.isArray(container)) {
      const value = (container as PhotoRecord)[key];
      if (value !== undefined && value !== null) return value;
    }
  }
  return undefined;
}

function PhotoSourceContext({
  state,
  error,
  sourceRefs,
  onRetry,
}: {
  state: PhotoState;
  error?: string;
  sourceRefs: readonly string[];
  onRetry?: () => void;
}) {
  const label = {
    idle: 'Not requested',
    loading: 'Loading source',
    ready: 'Calculated source returned',
    empty: 'No calculated record',
    error: 'Source unavailable',
  }[state];

  return (
    <aside className="photo-source-context" aria-label="Контекст источника Photo Detail">
      <div className="photo-source-heading">
        <div>
          <span className="micro-label">Evidence boundary</span>
          <strong>{label}</strong>
        </div>
        <DetailStatus value={state === 'ready' ? 'measured' : state} />
      </div>
      <div className="photo-source-flags">
        <code>source_mode: research</code>
        <code>not_a_verdict: true</code>
      </div>
      {error ? <p className="photo-error-copy">{error}</p> : null}
      {state === 'error' && onRetry ? (
        <button className="photo-button photo-button--quiet" type="button" onClick={onRetry}>
          Retry source request
        </button>
      ) : null}
      <details className="photo-source-details">
        <summary>Source files and API endpoints</summary>
        <ul>
          {sourceRefs.map((source) => (
            <li key={source}>
              <code>{source}</code>
            </li>
          ))}
        </ul>
      </details>
    </aside>
  );
}

function PhotoIdField({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <label className="photo-field">
      <span>Photo ID</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder="calculated photo_id"
        spellCheck={false}
      />
    </label>
  );
}

function PhotoDataCard({ label, value, unit }: { label: string; value: unknown; unit?: string }) {
  return (
    <div className="photo-data-card">
      <span>{label}</span>
      <strong>{detailDisplayValue(value)}</strong>
      <small>{unit ?? 'source field'}</small>
    </div>
  );
}

function artifactRecord(
  record: PhotoRecord | undefined,
  kind: ArtifactKind,
): PhotoRecord | undefined {
  const artifacts = record?.artifacts;
  if (artifacts && typeof artifacts === 'object' && !Array.isArray(artifacts)) {
    const item = (artifacts as PhotoRecord)[kind];
    if (item && typeof item === 'object' && !Array.isArray(item)) return item as PhotoRecord;
  }
  const direct = record?.[`${kind}_artifact`];
  if (direct && typeof direct === 'object' && !Array.isArray(direct)) return direct as PhotoRecord;
  const files = record?.files;
  if (files && typeof files === 'object' && !Array.isArray(files)) {
    const fileKey: Record<ArtifactKind, string> = {
      original: 'original',
      thumbnail: 'thumb',
      face_crop: 'face_crop',
      face_mask: 'face_mask',
      uv_texture: 'uv_texture',
    };
    const file = (files as PhotoRecord)[fileKey[kind]] ?? (files as PhotoRecord)[kind];
    if (typeof file === 'string' && file) return { file_name: file };
  }
  return undefined;
}

function artifactAvailability(
  record: PhotoRecord | undefined,
  kind: ArtifactKind,
): 'available' | 'unavailable' | 'unknown' {
  const artifact = artifactRecord(record, kind);
  if (!artifact) return 'unknown';
  if (
    artifact.availability === true ||
    artifact.available === true ||
    artifact.status === 'available'
  ) {
    return 'available';
  }
  if (
    artifact.availability === false ||
    artifact.available === false ||
    artifact.status === 'unavailable' ||
    artifact.status === 'missing'
  ) {
    return 'unavailable';
  }
  return 'unknown';
}

function artifactUrl(record: PhotoRecord | undefined, kind: ArtifactKind, photoId: string): string {
  const artifact = artifactRecord(record, kind);
  const candidate = artifact?.url ?? artifact?.artifact_url ?? artifact?.source_url;
  if (
    typeof candidate === 'string' &&
    candidate &&
    (/^https?:\/\//.test(candidate) || candidate.startsWith('/api/'))
  ) {
    return candidate;
  }
  if (kind === 'face_mask') {
    return `/api/v1/photos/${encodeURIComponent(photoId)}/artifacts/face_mask.png`;
  }
  return `/api/v1/photos/${encodeURIComponent(photoId)}/image?kind=${encodeURIComponent(kind)}`;
}

function pairRouteParams(
  pair: unknown,
  activeId: string,
): { photo_a?: string; photo_b?: string } | undefined {
  if (pair && typeof pair === 'object' && !Array.isArray(pair)) {
    const item = pair as PhotoRecord;
    const photoA = item.photo_a ?? item.photoA;
    const photoB = item.photo_b ?? item.photoB;
    if (typeof photoA === 'string' || typeof photoB === 'string') {
      return {
        photo_a: typeof photoA === 'string' ? photoA : undefined,
        photo_b: typeof photoB === 'string' ? photoB : undefined,
      };
    }
  }
  if (typeof pair !== 'string' || !activeId) return undefined;
  const prefix = `${activeId}__`;
  const suffix = `__${activeId}`;
  if (pair.startsWith(prefix)) return { photo_a: activeId, photo_b: pair.slice(prefix.length) };
  if (pair.endsWith(suffix)) return { photo_a: pair.slice(0, -suffix.length), photo_b: activeId };
  return undefined;
}

function PhotoArtifactImage({
  src,
  alt,
  unavailableLabel,
}: {
  src: string;
  alt: string;
  unavailableLabel: string;
}) {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');

  useEffect(() => {
    setState('loading');
  }, [src]);

  return state === 'error' ? (
    <div className="photo-no-data" role="status">
      <span className="photo-empty-mark" aria-hidden="true" />
      <div>
        <strong>{unavailableLabel}</strong>
        <span>Artifact request returned no renderable image.</span>
      </div>
    </div>
  ) : (
    <>
      {state === 'loading' ? (
        <span className="photo-artifact-loading">Loading artifact from API…</span>
      ) : null}
      <img
        src={src}
        alt={alt}
        loading="lazy"
        onLoad={() => setState('ready')}
        onError={() => setState('error')}
      />
    </>
  );
}

function PhotoOverviewBlock() {
  const [photoId, setPhotoId] = useState(() => hashParam('photo_id'));
  const [record, setRecord] = useState<PhotoRecord>();
  const [selectedArtifact, setSelectedArtifact] = useState<ArtifactKind>('original');
  const [state, setState] = useState<PhotoState>('idle');
  const [error, setError] = useState<string>();

  const loadPhoto = async (requestedId = photoId.trim()) => {
    if (!requestedId) {
      setState('error');
      setRecord(undefined);
      setError('Enter a calculated photo ID before requesting photo detail.');
      return;
    }
    setState('loading');
    setRecord(undefined);
    setError(undefined);
    try {
      const source = await loadPhotoSources(requestedId);
      const response = source.record;
      const hasPhotoIdentity = Boolean(
        response.photo_id || response.id || response.source_filename,
      );
      setRecord(hasPhotoIdentity ? response : undefined);
      setState(hasPhotoIdentity ? 'ready' : 'empty');
      setError(source.errors.length ? source.errors.join(' · ') : undefined);
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(photoErrorMessage(requestError));
    }
  };

  const activeId = String(record?.photo_id ?? record?.id ?? photoId.trim());
  const artifact = artifactRecord(record, selectedArtifact);
  const availability = artifactAvailability(record, selectedArtifact);
  const adjacentPrevious = record?.previous_photo_id;
  const adjacentNext = record?.next_photo_id;
  const pairs: readonly unknown[] = Array.isArray(record?.pair_ids) ? record.pair_ids : [];

  return (
    <section className="detail-block detail-block--photo" aria-labelledby="photo-overview-title">
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / photo-detail.overview</span>
          <h3 id="photo-overview-title">Photo overview and artifact viewer</h3>
          <p>
            Identity, chronology, artifact availability, provenance and adjacent navigation stay in
            one source-owned frame context.
          </p>
        </div>
        <DetailStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="photo-query-bar">
        <PhotoIdField value={photoId} onChange={setPhotoId} />
        <div className="photo-query-actions">
          <span>GET /api/v1/photos/{'{photo_id}'}/info_keys + texture.json</span>
          <button
            className="photo-button"
            type="button"
            onClick={() => void loadPhoto()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load calculated photo'}
          </button>
        </div>
      </div>
      {error ? <p className="photo-error-copy">{error}</p> : null}
      {record ? (
        <>
          <div className="photo-identity-strip">
            <PhotoDataCard label="Photo ID" value={record.photo_id ?? record.id} />
            <PhotoDataCard
              label="Date"
              value={record.date ?? record.current_date}
              unit={detailDisplayValue(record.date_provenance_status)}
            />
            <PhotoDataCard
              label="Pose bin"
              value={record.pose_bin ?? record.bucket ?? photoPoseValue(record, 'pose_bin')}
            />
            <PhotoDataCard
              label="Chronology"
              value={record.chronology_index_global}
              unit="global index"
            />
            <PhotoDataCard label="Same-date sequence" value={record.same_date_sequence} />
            <PhotoDataCard
              label="Pose chronology"
              value={record.chronology_index_in_pose}
              unit="pose index"
            />
            <PhotoDataCard
              label="Source filename"
              value={record.source_filename ?? photoPoseValue(record, 'source_filename')}
            />
            <PhotoDataCard
              label="Provenance"
              value={record.provenance_status ?? photoPoseValue(record, 'provenance_status')}
            />
            <PhotoDataCard label="Perceptual dHash" value={record.perceptual_dhash} />
            <PhotoDataCard label="Near duplicate" value={record.near_duplicate_of} />
          </div>
          <div className="photo-artifact-layout">
            <div className="photo-artifact-viewer">
              <div className="photo-subsection-heading">
                <div>
                  <span className="micro-label">Artifact viewer</span>
                  <strong>{ARTIFACTS.find((item) => item.key === selectedArtifact)?.label}</strong>
                </div>
                <DetailStatus value={artifact?.availability ?? artifact?.status} />
              </div>
              <div className="photo-artifact-tabs" role="tablist" aria-label="Artifact kind">
                {ARTIFACTS.map((item) => (
                  <button
                    key={item.key}
                    className={`photo-artifact-tab${selectedArtifact === item.key ? ' is-active' : ''}`}
                    type="button"
                    role="tab"
                    aria-selected={selectedArtifact === item.key}
                    onClick={() => setSelectedArtifact(item.key)}
                  >
                    {item.label}
                    <span>
                      {artifactAvailability(record, item.key) === 'available'
                        ? 'available'
                        : artifactAvailability(record, item.key) === 'unavailable'
                          ? 'unavailable'
                          : 'not checked'}
                    </span>
                  </button>
                ))}
              </div>
              <div className="photo-artifact-stage">
                {availability !== 'unavailable' ? (
                  <PhotoArtifactImage
                    src={artifactUrl(record, selectedArtifact, activeId)}
                    alt={detailDisplayValue(artifact?.alt_text ?? record.alt_text)}
                    unavailableLabel={`${ARTIFACTS.find((item) => item.key === selectedArtifact)?.label ?? selectedArtifact} unavailable`}
                  />
                ) : (
                  <div className="photo-no-data" role="status">
                    <span className="photo-empty-mark" aria-hidden="true" />
                    <div>
                      <strong>
                        {selectedArtifact === 'face_mask'
                          ? 'Face mask not extracted'
                          : `${ARTIFACTS.find((item) => item.key === selectedArtifact)?.label ?? selectedArtifact} unavailable`}
                      </strong>
                      <span>
                        {detailDisplayValue(
                          artifact?.fallback_reason ??
                            artifact?.availability ??
                            record.fallback_reason,
                        )}
                      </span>
                    </div>
                  </div>
                )}
              </div>
              <div className="photo-artifact-meta">
                <span>kind: {selectedArtifact}</span>
                <span>
                  type: {detailDisplayValue(artifact?.artifact_type ?? record.artifact_type)}
                </span>
                <span>
                  path: {detailDisplayValue(artifact?.artifact_path ?? record.artifact_path)}
                </span>
                <span>
                  availability: {detailDisplayValue(artifact?.availability ?? artifact?.status)}
                </span>
                <span>
                  fallback:{' '}
                  {detailDisplayValue(artifact?.fallback_reason ?? record.fallback_reason)}
                </span>
                <span>
                  original equals proxy: {detailDisplayValue(record.original_equals_proxy)}
                </span>
              </div>
              <div className="photo-artifact-links">
                <a
                  href={`/api/v1/photos/${encodeURIComponent(activeId)}/artifacts/info.json`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open info.json
                </a>
                <a
                  href={`/api/v1/photos/${encodeURIComponent(activeId)}/artifacts/texture.json`}
                  target="_blank"
                  rel="noreferrer"
                >
                  Open texture.json
                </a>
              </div>
            </div>
            <div className="photo-navigation-panel">
              <div className="photo-subsection-heading">
                <span className="micro-label">Adjacent context</span>
                <strong>Archive links</strong>
              </div>
              <div className="photo-adjacent-actions">
                <button
                  className="photo-button photo-button--quiet"
                  type="button"
                  onClick={() => navigateTo('timeline', { photo_id: activeId })}
                >
                  Return to Timeline
                </button>
                <button
                  className="photo-text-button"
                  type="button"
                  disabled={typeof adjacentPrevious !== 'string'}
                  onClick={() => {
                    if (typeof adjacentPrevious === 'string') {
                      setPhotoId(adjacentPrevious);
                      void loadPhoto(adjacentPrevious);
                    }
                  }}
                >
                  ← Previous · {detailDisplayValue(adjacentPrevious)}
                </button>
                <button
                  className="photo-text-button"
                  type="button"
                  disabled={typeof adjacentNext !== 'string'}
                  onClick={() => {
                    if (typeof adjacentNext === 'string') {
                      setPhotoId(adjacentNext);
                      void loadPhoto(adjacentNext);
                    }
                  }}
                >
                  Next · {detailDisplayValue(adjacentNext)} →
                </button>
              </div>
              <div className="photo-link-list">
                <span className="micro-label">Pair IDs</span>
                {pairs.length ? (
                  <ul>
                    {pairs.map((pair, index) => {
                      const route = pairRouteParams(pair, activeId);
                      const label = String(
                        pair && typeof pair === 'object' && !Array.isArray(pair)
                          ? ((pair as PhotoRecord).pair_id ?? pair)
                          : pair,
                      );
                      return (
                        <li key={`${label}-${index}`}>
                          {route?.photo_a && route?.photo_b ? (
                            <button
                              className="photo-text-button"
                              type="button"
                              onClick={() => navigateTo('compare', route)}
                            >
                              {label}
                            </button>
                          ) : (
                            <span>{label}</span>
                          )}
                        </li>
                      );
                    })}
                  </ul>
                ) : (
                  <p>No pair links returned.</p>
                )}
              </div>
              <div className="photo-limitation-copy">
                <span className="micro-label">Limitations</span>
                <p>{detailDisplayValue(record.limitations ?? record.fallback_reason)}</p>
              </div>
            </div>
          </div>
          <div className="photo-structured-details-grid">
            <details className="photo-structured-details">
              <summary>Camera</summary>
              <pre>{detailStructuredValue(record.camera)}</pre>
            </details>
            <details className="photo-structured-details">
              <summary>Normalization</summary>
              <pre>{detailStructuredValue(record.normalization)}</pre>
            </details>
            <details className="photo-structured-details">
              <summary>Crop</summary>
              <pre>{detailStructuredValue(record.crop)}</pre>
            </details>
            <details className="photo-structured-details">
              <summary>Source provenance</summary>
              <pre>{detailStructuredValue(record.source_provenance)}</pre>
            </details>
          </div>
          <div className="photo-verdict-note">
            <strong>Source boundary</strong>
            <span>
              Original, proxy, crop, mask and UV artifacts are not interchangeable. Availability and
              fallback reason remain visible.
            </span>
          </div>
        </>
      ) : (
        <div className="photo-no-data" role="status">
          <span className="photo-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty' ? 'Photo record is empty' : 'No calculated photo loaded'}
            </strong>
            <span>
              Nothing is inferred from the route. Enter a returned photo ID and request the API
              source.
            </span>
          </div>
        </div>
      )}
      <PhotoSourceContext
        state={state}
        error={error}
        onRetry={() => void loadPhoto()}
        sourceRefs={photoDetailPage.blocks[0].sourceRefs}
      />
    </section>
  );
}

function PhotoPoseQualityBlock() {
  const [photoId, setPhotoId] = useState(() => hashParam('photo_id'));
  const [record, setRecord] = useState<PhotoRecord>();
  const [state, setState] = useState<PhotoState>('idle');
  const [error, setError] = useState<string>();
  const [gateFocus, setGateFocus] = useState('');

  const loadQuality = async () => {
    const requestedId = photoId.trim();
    if (!requestedId) {
      setState('error');
      setError('Enter a calculated photo ID before requesting pose and quality.');
      return;
    }
    setState('loading');
    setRecord(undefined);
    setError(undefined);
    try {
      const source = await loadPhotoSources(requestedId);
      const response = source.record;
      setRecord(response);
      setState(response.photo_id || response.id || response.source_filename ? 'ready' : 'empty');
      setError(source.errors.length ? source.errors.join(' · ') : undefined);
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(photoErrorMessage(requestError));
    }
  };

  const activeId = String(record?.photo_id ?? record?.id ?? photoId.trim());

  return (
    <section className="detail-block detail-block--photo" aria-labelledby="photo-pose-title">
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / photo-detail.pose-quality</span>
          <h3 id="photo-pose-title">Pose, expression and quality</h3>
          <p>
            Pose and expression are kept with alignment, visibility, authenticity and calibration
            gates so downstream use is qualified.
          </p>
        </div>
        <DetailStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="photo-query-bar">
        <PhotoIdField value={photoId} onChange={setPhotoId} />
        <div className="photo-query-actions">
          <span>GET /api/v1/photos/{'{photo_id}'}/info_keys + texture.json</span>
          <button
            className="photo-button"
            type="button"
            onClick={() => void loadQuality()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load pose and quality'}
          </button>
        </div>
      </div>
      {error ? <p className="photo-error-copy">{error}</p> : null}
      {record ? (
        <>
          <div className="photo-metric-grid">
            {POSE_FIELDS.map((field) => (
              <PhotoDataCard
                key={field.key}
                label={field.label}
                value={photoPoseValue(record, field.key)}
                unit={field.unit}
              />
            ))}
          </div>
          <div className="photo-structured-details-grid">
            <details className="photo-structured-details">
              <summary>Returned skin diagnostics</summary>
              <pre>{detailStructuredValue(record.skin)}</pre>
            </details>
            <details className="photo-structured-details">
              <summary>Returned UV diagnostics</summary>
              <pre>{detailStructuredValue(record.uv)}</pre>
            </details>
            <details className="photo-structured-details">
              <summary>Returned quality summary</summary>
              <pre>{detailStructuredValue(record.quality_summary)}</pre>
            </details>
            <details className="photo-structured-details">
              <summary>Returned reprojection diagnostics</summary>
              <pre>{detailStructuredValue(record.reprojection)}</pre>
            </details>
          </div>
          <div className="photo-gate-panel">
            <div className="photo-subsection-heading">
              <div>
                <span className="micro-label">Quality and applicability gates</span>
                <strong>Selection context</strong>
              </div>
              <label className="photo-gate-select">
                <span>Focus</span>
                <select value={gateFocus} onChange={(event) => setGateFocus(event.target.value)}>
                  <option value="">All gates</option>
                  {POSE_GATES.map((gate) => (
                    <option key={gate.key} value={gate.key}>
                      {gate.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <div className="photo-gate-grid">
              {POSE_GATES.filter((gate) => !gateFocus || gate.key === gateFocus).map((gate) => (
                <div className="photo-gate-card" key={gate.key}>
                  <span>{gate.label}</span>
                  <DetailStatus value={photoPoseValue(record, gate.key)} />
                </div>
              ))}
            </div>
          </div>
          <div className="photo-quality-footnotes">
            <div>
              <span className="micro-label">Coordinate space</span>
              <strong>{detailDisplayValue(record.coordinate_space)}</strong>
            </div>
            <div>
              <span className="micro-label">Limitation refs</span>
              <strong>{detailDisplayValue(record.limitation_refs)}</strong>
            </div>
            <div>
              <span className="micro-label">Calibration</span>
              <strong>
                {detailDisplayValue(record.calibration_status ?? record.calibration_state)}
              </strong>
            </div>
          </div>
          <div className="photo-cross-links" aria-label="Photo context transitions">
            <span className="micro-label">Open related context</span>
            <button
              className="photo-text-button"
              type="button"
              onClick={() => navigateTo('timeline', { photo_id: activeId })}
            >
              Timeline
            </button>
            <button
              className="photo-text-button"
              type="button"
              onClick={() => navigateTo('compare', { photo_a: activeId })}
            >
              Compare as A
            </button>
            <button
              className="photo-text-button"
              type="button"
              onClick={() => navigateTo('research', { photo_a: activeId })}
            >
              Research context
            </button>
          </div>
        </>
      ) : (
        <div className="photo-no-data" role="status">
          <span className="photo-empty-mark" aria-hidden="true" />
          <div>
            <strong>No pose or quality measurements loaded</strong>
            <span>
              Pose, expression and gate values are not synthesized when the calculated record is
              absent.
            </span>
          </div>
        </div>
      )}
      <div className="photo-verdict-note">
        <strong>Interpretation boundary</strong>
        <span>
          Pose, expression, quality and authenticity scores describe measurement conditions. They do
          not identify a person or establish a forensic conclusion.
        </span>
      </div>
      <PhotoSourceContext
        state={state}
        error={error}
        onRetry={() => void loadQuality()}
        sourceRefs={photoDetailPage.blocks[1].sourceRefs}
      />
    </section>
  );
}

function landmarkVisibility(
  point: LandmarkPoint,
  index: number,
  record: PhotoRecord,
  count: '106' | '134',
): boolean | undefined {
  if (typeof point.visible === 'boolean') return point.visible;
  const contract = record.landmark_contract;
  const contractRecord =
    contract && typeof contract === 'object' && !Array.isArray(contract)
      ? (contract as PhotoRecord)
      : undefined;
  const pointSetContract = contractRecord?.[`ldm${count}`] ?? contractRecord?.[count];
  const pointSetRecord =
    pointSetContract && typeof pointSetContract === 'object' && !Array.isArray(pointSetContract)
      ? (pointSetContract as PhotoRecord)
      : undefined;
  const mask =
    record.visible_mask ??
    record[`visible_${count}`] ??
    contractRecord?.visible_mask ??
    contractRecord?.[`visible_${count}`] ??
    pointSetRecord?.visible_mask ??
    pointSetRecord?.[`visible_${count}`];
  if (Array.isArray(mask) && typeof mask[index] === 'boolean') return mask[index] as boolean;
  return undefined;
}

function PhotoLandmarksBlock() {
  const [photoId, setPhotoId] = useState(() => hashParam('photo_id'));
  const [count, setCount] = useState<'106' | '134'>('106');
  const [space, setSpace] = useState<LandmarkSpace>('aligned');
  const [visibility, setVisibility] = useState<VisibilityFilter>('all');
  const [state, setState] = useState<PhotoState>('idle');
  const [record, setRecord] = useState<PhotoRecord>();
  const [error, setError] = useState<string>();

  const loadLandmarks = async () => {
    const requestedId = photoId.trim();
    if (!requestedId) {
      setState('error');
      setError('Enter a calculated photo ID before requesting landmarks.');
      return;
    }
    setState('loading');
    setRecord(undefined);
    setError(undefined);
    try {
      const [landmarkResult, infoResult] = await Promise.allSettled([
        requestJson<PhotoRecord>(
          `/api/v1/photos/${encodeURIComponent(requestedId)}/landmarks/${count}/${space}`,
        ),
        loadPhotoInfoArtifacts(requestedId),
      ]);
      if (landmarkResult.status === 'rejected') throw landmarkResult.reason;
      const response = landmarkResult.value;
      const info = infoResult.status === 'fulfilled' ? infoResult.value : undefined;
      const mergedRecord: PhotoRecord = {
        ...info?.record,
        ...response,
      };
      const hasPoints = Array.isArray(response.points) || Array.isArray(response.landmarks);
      setRecord(mergedRecord);
      setState(hasPoints ? 'ready' : 'empty');
      const sourceErrors = [
        infoResult.status === 'rejected'
          ? `photo info: ${photoErrorMessage(infoResult.reason)}`
          : info?.errors.length
            ? info.errors.join(' · ')
            : undefined,
      ].filter((value): value is string => Boolean(value));
      setError(sourceErrors.length ? sourceErrors.join(' · ') : undefined);
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(photoErrorMessage(requestError));
    }
  };

  const pointsValue = record?.points ?? record?.landmarks;
  const points: readonly LandmarkPoint[] = Array.isArray(pointsValue)
    ? pointsValue.flatMap((point, index) => {
        if (Array.isArray(point)) {
          return [{ point_index: index, x: point[0], y: point[1], z: point[2] }];
        }
        return typeof point === 'object' && point !== null ? [point as LandmarkPoint] : [];
      })
    : [];
  const hasVisibilityMask = points.some(
    (point, index) => landmarkVisibility(point, index, record ?? {}, count) !== undefined,
  );
  const filteredPoints = points.filter((point, index) => {
    const visible = landmarkVisibility(point, index, record ?? {}, count);
    if (visibility === 'all') return true;
    return visibility === 'visible' ? visible === true : visible === false;
  });

  return (
    <section className="detail-block detail-block--photo" aria-labelledby="photo-landmarks-title">
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / photo-detail.landmarks-surface</span>
          <h3 id="photo-landmarks-title">Landmarks and surface diagnostics</h3>
          <p>
            LDM106/LDM134, coordinate space, visibility and texture/UV diagnostics are shown only
            from the selected API response.
          </p>
        </div>
        <DetailStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="photo-landmark-controls">
        <PhotoIdField value={photoId} onChange={setPhotoId} />
        <label className="photo-field">
          <span>Point set</span>
          <select value={count} onChange={(event) => setCount(event.target.value as '106' | '134')}>
            <option value="106">LDM106</option>
            <option value="134">LDM134</option>
          </select>
        </label>
        <label className="photo-field">
          <span>Coordinate space</span>
          <select value={space} onChange={(event) => setSpace(event.target.value as LandmarkSpace)}>
            <option value="raw">Raw</option>
            <option value="aligned">Aligned</option>
            <option value="original">Original</option>
          </select>
        </label>
        <label className="photo-field">
          <span>Visibility</span>
          <select
            value={visibility}
            onChange={(event) => setVisibility(event.target.value as VisibilityFilter)}
          >
            <option value="all">All returned</option>
            <option value="visible">Visible only</option>
            <option value="hidden">Hidden only</option>
          </select>
        </label>
        <div className="photo-query-actions">
          <span>
            GET /api/v1/photos/{'{photo_id}'}/landmarks/{'{count}'}/{'{space}'}
          </span>
          <button
            className="photo-button"
            type="button"
            onClick={() => void loadLandmarks()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load landmarks'}
          </button>
        </div>
      </div>
      {error ? <p className="photo-error-copy">{error}</p> : null}
      {record ? (
        <>
          <div className="photo-landmark-summary">
            <PhotoDataCard
              label="Returned count"
              value={record.count ?? (points.length || undefined)}
            />
            <PhotoDataCard label="Response space" value={record.space ?? record.coordinate_space} />
            <PhotoDataCard label="Visible 106" value={record.visible_106} />
            <PhotoDataCard label="Visible 134" value={record.visible_134} />
            <PhotoDataCard label="Overlay" value={record.overlay_status} />
            <PhotoDataCard
              label="Texture score"
              value={record.texture_score ?? photoPoseValue(record, 'texture_score')}
            />
            <PhotoDataCard label="UV coverage" value={record.uv_observed_coverage} />
          </div>
          {filteredPoints.length ? (
            <div className="photo-landmark-table-wrap">
              <table className="photo-landmark-table">
                <caption>Returned point rows · filter: {visibility}</caption>
                <thead>
                  <tr>
                    <th scope="col">Index</th>
                    <th scope="col">X</th>
                    <th scope="col">Y</th>
                    <th scope="col">Z</th>
                    <th scope="col">Visible</th>
                    <th scope="col">Source ref</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPoints.map((point, index) => {
                    const actualIndex = points.indexOf(point);
                    return (
                      <tr key={`${actualIndex}-${String(point.point_index ?? index)}`}>
                        <th scope="row">{detailDisplayValue(point.point_index ?? actualIndex)}</th>
                        <td>{detailDisplayValue(point.x)}</td>
                        <td>{detailDisplayValue(point.y)}</td>
                        <td>{detailDisplayValue(point.z)}</td>
                        <td>
                          <DetailStatus
                            value={landmarkVisibility(point, actualIndex, record, count)}
                          />
                        </td>
                        <td>{detailDisplayValue(point.source_ref ?? record.source_ref)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="photo-no-data" role="status">
              <span className="photo-empty-mark" aria-hidden="true" />
              <div>
                <strong>
                  {points.length
                    ? hasVisibilityMask
                      ? 'No points match this visibility filter'
                      : 'Visibility mask unavailable'
                    : 'No landmark points returned'}
                </strong>
                <span>
                  {points.length && !hasVisibilityMask
                    ? 'The source returned coordinates without a visibility mask for this request.'
                    : 'Point coordinates are not generated for an unavailable, skipped or empty landmark response.'}
                </span>
              </div>
            </div>
          )}
          <div className="photo-surface-diagnostics">
            <div>
              <span className="micro-label">Texture status</span>
              <strong>
                {detailDisplayValue(
                  record.texture_status ?? photoPoseValue(record, 'texture_status'),
                )}
              </strong>
            </div>
            <div>
              <span className="micro-label">Texture path</span>
              <strong>{detailDisplayValue(record.texture_path ?? record.texture_json)}</strong>
            </div>
            <div>
              <span className="micro-label">UV path</span>
              <strong>{detailDisplayValue(record.uv_path)}</strong>
            </div>
            <div>
              <span className="micro-label">Fallback</span>
              <strong>{detailDisplayValue(record.fallback_reason)}</strong>
            </div>
          </div>
        </>
      ) : (
        <div className="photo-no-data" role="status">
          <span className="photo-empty-mark" aria-hidden="true" />
          <div>
            <strong>No landmark response loaded</strong>
            <span>
              Choose the point set and coordinate space, then request the calculated landmark
              endpoint.
            </span>
          </div>
        </div>
      )}
      <div className="photo-verdict-note">
        <strong>Coordinate boundary</strong>
        <span>
          Raw, aligned, original and chronology spaces are not interchangeable. Visibility masks and
          UV coverage are measurement states, not evidence of identity.
        </span>
      </div>
      <PhotoSourceContext
        state={state}
        error={error}
        onRetry={() => void loadLandmarks()}
        sourceRefs={photoDetailPage.blocks[2].sourceRefs}
      />
    </section>
  );
}

export function PhotoDetailPage() {
  const renderBlock = (block: BlockDefinition) => {
    switch (block.id) {
      case 'photo-detail.overview':
        return <PhotoOverviewBlock />;
      case 'photo-detail.pose-quality':
        return <PhotoPoseQualityBlock />;
      case 'photo-detail.landmarks-surface':
        return <PhotoLandmarksBlock />;
      default:
        return null;
    }
  };

  return <PageBlueprint definition={photoDetailPage} renderBlock={renderBlock} />;
}
