import { useEffect, useRef, useState, type CSSProperties } from 'react';

import { ApiRequestError, isAbortError, requestJson } from '@/shared/api';
import { parseCsvRecords, type CsvRecord } from '@/shared/csv';
import { PageBlueprint } from '@/shared/PageBlueprint';
import { requestUiArtifactText } from '@/shared/uiArtifacts';
import { hashParam, navigateTo } from '@/shared/navigation';
import type { BlockDefinition, PageDefinition } from '@/shared/contracts';

/**
 * PAGE: Compare.
 * Blocks are semantic ownership boundaries. Their internal controls and views stay together;
 * the page owner is free to choose the eventual composition.
 */
export const comparePage = {
  id: 'compare',
  title: 'Compare',
  group: 'analytics',
  purpose:
    'Единая рабочая область сравнения пары A → B с data-first и visual-first сценариями, gate-контекстом и evidence.',
  primaryQuestion:
    'Что измерено между A и B, какие условия применимости действуют и что видно в визуальных слоях?',
  blocks: [
    /**
     * BLOCK: Pair Detail and data-first analysis.
     * OWNED ELEMENTS: pair and mode controls, A/B context and dates, data-first metric table, raw, calibrated, robust-z, FDR and q-value context, quality, visibility, expression, pose and calibration gates, Pair Detail readout with sources and limitations.
     * CONTRACT SURFACE: elements: pair family and baseline/rolling role, plain-language evidence meaning, supporting and weakening context; actions: select_pair, set_scope, open_pair_detail, open_morphing, open_evidence; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * pair_role, pair_family, baseline_pair, rolling_pair, stage, relative_path, file_name, artifact_type, availability, created_at, supporting_objects, weakening_objects, plain_language_meaning.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * pair_id, photo_a, photo_b, date_a, date_b, pose_bin, pair_type,
     * comparison_mode, run_id, not_a_verdict, scope_filters, metric, label, raw_value,
     * calibrated_value, robust_z, unit, coordinate_space, fdr_significant, q_value, measurement_state,
     * source_ref, limitation_refs, alignment_quality_a, alignment_quality_b, expression_gate_confidence, expression_gate_stratum, quality_status_a,
     * quality_status_b, visibility_gate_accepted106, visibility_gate_accepted134, pose_distance, pitch_gap_deg, yaw_gap_deg, roll_gap_deg,
     * calibration_limited, pose_leakage_limited, texture_conclusions_allowed, mesh_status, evidence_state, raw_metrics, calibrated_metrics,
     * fdr, gate_statuses, zone_refs, source_refs, status, qc_skip_reason, quality_limited,
     * primary_robust_z, primary_calibration_p95, mesh_rmse, mesh_median, mesh_p95, mesh_point_to_plane_rmse, mesh_calibrated_metric_count,
     * mesh_calibrated_summary, texture_score_0_1, ldm106_rmse, ldm106_median, ldm106_p95, ldm134_rmse, ldm134_median,
     * ldm134_p95, descriptor_significant_fraction, descriptor_p95_z, cross_bin_corroboration_status, calibration_limitation_reason, coherent_motion_fraction, identity_only_motion_rmse,
     * expression_influence, lead_overlap, lead_priority, lead_events, mt_significant_fdr10, mt_q_value.
     */
    {
      id: 'compare.pair-detail',
      title: 'Pair Detail and data-first analysis',
      purpose:
        'Самостоятельный блок пары: выбор A/B и режима, таблица метрик, raw/calibrated context, gates и полная структура Pair Detail.',
      elements: [
        'pair family and baseline/rolling role',
        'plain-language evidence meaning',
        'supporting and weakening context',
        'pair and mode controls',
        'A/B context and dates',
        'data-first metric table',
        'raw, calibrated, robust-z, FDR and q-value context',
        'quality, visibility, expression, pose and calibration gates',
        'Pair Detail readout with sources and limitations',
      ],
      keys: [
        'pair_role',
        'pair_family',
        'baseline_pair',
        'rolling_pair',
        'stage',
        'relative_path',
        'file_name',
        'artifact_type',
        'availability',
        'created_at',
        'supporting_objects',
        'weakening_objects',
        'plain_language_meaning',
        'source_file',
        'source_key',
        'source_url',
        'api_endpoint',
        'limitations',
        'quality_state',
        'visibility_state',
        'calibration_state',
        'schema',
        'source_mode',
        'pair_id',
        'photo_a',
        'photo_b',
        'date_a',
        'date_b',
        'pose_bin',
        'pair_type',
        'comparison_mode',
        'run_id',
        'not_a_verdict',
        'scope_filters',
        'metric',
        'label',
        'raw_value',
        'calibrated_value',
        'robust_z',
        'unit',
        'coordinate_space',
        'fdr_significant',
        'q_value',
        'measurement_state',
        'source_ref',
        'limitation_refs',
        'alignment_quality_a',
        'alignment_quality_b',
        'expression_gate_confidence',
        'expression_gate_stratum',
        'quality_status_a',
        'quality_status_b',
        'visibility_gate_accepted106',
        'visibility_gate_accepted134',
        'pose_distance',
        'pitch_gap_deg',
        'yaw_gap_deg',
        'roll_gap_deg',
        'calibration_limited',
        'pose_leakage_limited',
        'texture_conclusions_allowed',
        'mesh_status',
        'motion_file',
        'motion_status',
        'evidence_state',
        'raw_metrics',
        'calibrated_metrics',
        'fdr',
        'gate_statuses',
        'zone_refs',
        'source_refs',
        'status',
        'qc_skip_reason',
        'quality_limited',
        'primary_robust_z',
        'primary_calibration_p95',
        'mesh_rmse',
        'mesh_median',
        'mesh_p95',
        'mesh_point_to_plane_rmse',
        'mesh_calibrated_metric_count',
        'mesh_calibrated_summary',
        'texture_score_0_1',
        'ldm106_rmse',
        'ldm106_median',
        'ldm106_p95',
        'ldm134_rmse',
        'ldm134_median',
        'ldm134_p95',
        'descriptor_significant_fraction',
        'descriptor_p95_z',
        'cross_bin_corroboration_status',
        'calibration_limitation_reason',
        'coherent_motion_fraction',
        'identity_only_motion_rmse',
        'expression_influence',
        'lead_overlap',
        'lead_priority',
        'lead_events',
        'mt_significant_fdr10',
        'mt_q_value',
      ],
      sourceRefs: [
        'ui_artifacts/pair_metrics_preview.csv',
        'ui_artifacts/zone_summary.csv',
        'api/v1/ui_artifacts/pair_metrics_preview.csv',
        'api/v1/ui_artifacts/zone_summary.csv',
        'api/v1/compare',
        'api/v1/pairs/{photo_a}/{photo_b}/metrics',
      ],
      actions: [
        'select_pair',
        'set_scope',
        'open_pair_detail',
        'open_morphing',
        'open_evidence',
        'switch_data_first',
        'switch_visual_first',
        'open_photo_a',
        'open_photo_b',
        'select_metric',
        'open_metric_definition',
        'open_source',
        'open_visual_layer',
        'open_methodology',
        'open_calibration',
        'open_limitation',
        'open_photo_detail',
        'open_zone_atlas',
        'open_casework',
        'open_corroboration',
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
        'long_content',
      ],
    },
    /**
     * BLOCK: Visual-first comparison and Morphing.
     * OWNED ELEMENTS: A/B viewer with side-by-side and overlay modes, divider, zoom and pan controls, 2D morph and 3D mesh modes, landmark, zone, heatmap and texture layers, artifact availability and 2D fallback, legend, captions and interpretation boundary.
     * CONTRACT SURFACE: elements: playback controls, camera and color-threshold controls, exact artifact/API source context; actions: set_zoom, set_pan, toggle_zone_heatmap, toggle_texture, toggle_uv, set_playback_speed, play, pause, reset, set_camera, switch_coordinate_space, set_color_threshold; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * texture_json, ldm106_source, ldm134_source, zones_overlay, uv_texture, image_kind, stage, relative_path, file_name, artifact_type, availability, created_at.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * image_a_ref, image_b_ref, artifact_status_a, artifact_status_b, overlay_alpha, divider_position, zoom,
     * pan, landmark_overlay, zone_overlay, heatmap_ref, alt_text, caption, scene_mode,
     * progress, playback_speed, camera_state, mesh_ref, texture_ref, mesh_available, uv_available,
     * reconstruction_model, layer_refs, coordinate_space, source_refs, limitation_refs, mesh_file, motion_file.
     */
    {
      id: 'compare.morphing',
      title: 'Visual-first comparison and Morphing',
      purpose:
        'Самостоятельный визуальный блок Compare для A/B, overlay, divider, 2D morphing и доступного 3D mesh режима.',
      elements: [
        'playback controls',
        'camera and color-threshold controls',
        'exact artifact/API source context',
        'A/B viewer with side-by-side and overlay modes',
        'divider, zoom and pan controls',
        '2D morph and 3D mesh modes',
        'landmark, zone, heatmap and texture layers',
        'artifact availability and 2D fallback',
        'legend, captions and interpretation boundary',
      ],
      keys: [
        'texture_json',
        'ldm106_source',
        'ldm134_source',
        'zones_overlay',
        'uv_texture',
        'image_kind',
        'stage',
        'relative_path',
        'file_name',
        'artifact_type',
        'availability',
        'created_at',
        'source_file',
        'source_key',
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
        'image_a_ref',
        'image_b_ref',
        'artifact_status_a',
        'artifact_status_b',
        'overlay_alpha',
        'divider_position',
        'zoom',
        'pan',
        'landmark_overlay',
        'zone_overlay',
        'heatmap_ref',
        'alt_text',
        'caption',
        'scene_mode',
        'progress',
        'playback_speed',
        'camera_state',
        'mesh_ref',
        'texture_ref',
        'mesh_available',
        'uv_available',
        'reconstruction_model',
        'layer_refs',
        'coordinate_space',
        'source_refs',
        'limitation_refs',
        'mesh_file',
        'motion_file',
      ],
      sourceRefs: [
        'stage1/<photo_id>/face_mask.png',
        'stage1/<photo_id>/texture.json',
        'stage1/<photo_id>/uv_texture.png',
        'stage1/<photo_id>/ldm106_aligned.csv',
        'stage1/<photo_id>/ldm134_aligned.csv',
        'api/v1/photos/{photo_id}/image?kind={kind}',
        'api/v1/photos/{photo_id}/artifacts/{name}',
      ],
      actions: [
        'set_zoom',
        'set_pan',
        'toggle_zone_heatmap',
        'toggle_texture',
        'toggle_uv',
        'set_playback_speed',
        'play',
        'pause',
        'reset',
        'set_camera',
        'switch_coordinate_space',
        'set_color_threshold',
        'switch_view_mode',
        'set_overlay_alpha',
        'set_divider',
        'toggle_landmarks',
        'open_source',
        'select_scene_mode',
        'set_progress',
        'toggle_layer',
        'switch_to_2d_fallback',
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
        'fallback',
        'error',
      ],
    },
    /**
     * BLOCK: Zones, evidence and next actions.
     * OWNED ELEMENTS: zone map and zone metrics, supporting and weakening evidence, corroboration state and alternatives, source, limitation and not-a-verdict context, links to research, report and publication.
     * CONTRACT SURFACE: elements: plain-language evidence meaning, quality, visibility and calibration context, supporting and weakening links; actions: select_zone, open_evidence, add_note, open_publication; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * plain_language_meaning, quality, visibility, calibration, fdr, q_value, coordinate_space, supporting_refs, weakening_refs, alternative_explanations.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * primary_zone_status, primary_zone_rmse, primary_zone_names, raw_rmse, robust_z, zone_id, supporting_objects,
     * weakening_objects, corroboration_status, source_refs, limitation_refs, pair_id, next_routes, evidence_state,
     * not_a_verdict, public_safety_status, export_status, unresolved_questions.
     */
    {
      id: 'compare.zones-evidence',
      title: 'Zones, evidence and next actions',
      purpose:
        'Самостоятельный evidence-контекст пары: локализация по зонам, поддерживающие и ослабляющие объекты, ограничения и связанные действия.',
      elements: [
        'plain-language evidence meaning',
        'quality, visibility and calibration context',
        'supporting and weakening links',
        'zone map and zone metrics',
        'supporting and weakening evidence',
        'corroboration state and alternatives',
        'source, limitation and not-a-verdict context',
        'links to research, report and publication',
      ],
      keys: [
        'plain_language_meaning',
        'quality',
        'visibility',
        'calibration',
        'fdr',
        'q_value',
        'coordinate_space',
        'supporting_refs',
        'weakening_refs',
        'alternative_explanations',
        'source_file',
        'source_key',
        'source_url',
        'api_endpoint',
        'limitations',
        'measurement_state',
        'quality_state',
        'visibility_state',
        'calibration_state',
        'schema',
        'source_mode',
        'primary_zone_status',
        'primary_zone_rmse',
        'primary_zone_names',
        'raw_rmse',
        'robust_z',
        'zone_id',
        'supporting_objects',
        'weakening_objects',
        'corroboration_status',
        'source_refs',
        'limitation_refs',
        'pair_id',
        'next_routes',
        'evidence_state',
        'not_a_verdict',
        'public_safety_status',
        'export_status',
        'unresolved_questions',
      ],
      sourceRefs: [
        'ui_artifacts/zone_summary.csv',
        'ui_artifacts/pair_metrics_preview.csv',
        'api/v1/ui_artifacts/zone_summary.csv',
        'api/v1/pairs/{photo_a}/{photo_b}/metrics',
      ],
      actions: [
        'select_zone',
        'open_evidence',
        'add_note',
        'open_publication',
        'open_zone_atlas',
        'open_corroboration',
        'open_source',
        'open_casework',
        'open_report',
        'add_evidence_to_publication',
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
  ],
} satisfies PageDefinition;

type CompareState = 'idle' | 'loading' | 'ready' | 'partial' | 'empty' | 'error';
type CompareMode = 'data-first' | 'visual-first';

type VisualMode = 'side_by_side' | 'overlay' | 'divider' | 'morph_2d' | 'mesh_3d';

const VISUAL_MODES: readonly VisualMode[] = [
  'side_by_side',
  'overlay',
  'divider',
  'morph_2d',
  'mesh_3d',
];

function routeVisualMode(): VisualMode {
  const requested = hashParam('visual_mode') as VisualMode;
  return VISUAL_MODES.includes(requested) ? requested : 'side_by_side';
}

interface PairMetricsRecord {
  [key: string]: unknown;
}

interface PhotoMetadataRecord {
  [key: string]: unknown;
}

interface PairRequestResponse {
  [key: string]: unknown;
}

const PAIR_METRIC_ROWS: readonly { label: string; key: string; unit: string }[] = [
  { label: 'Raw value', key: 'raw_value', unit: 'source value' },
  { label: 'Calibrated value', key: 'calibrated_value', unit: 'source value' },
  { label: 'Robust-z', key: 'robust_z', unit: 'robust z' },
  { label: 'FDR significant', key: 'fdr_significant', unit: 'boolean' },
  { label: 'q-value', key: 'q_value', unit: 'q-value' },
  { label: 'Measurement state', key: 'measurement_state', unit: 'status' },
  { label: 'Primary robust-z', key: 'primary_robust_z', unit: 'robust z' },
  { label: 'Primary calibration P95', key: 'primary_calibration_p95', unit: 'reference' },
  { label: 'Alignment delta', key: 'alignment_delta', unit: 'source unit' },
  { label: 'Expression delta', key: 'expression_delta', unit: 'source unit' },
  { label: 'Quality delta', key: 'quality_delta', unit: 'source status' },
  { label: 'Visibility delta', key: 'visibility_delta', unit: 'source status' },
  { label: 'LDM106 RMSE', key: 'ldm106_rmse', unit: 'source unit' },
  { label: 'LDM106 median', key: 'ldm106_median', unit: 'source unit' },
  { label: 'LDM106 P95', key: 'ldm106_p95', unit: 'source unit' },
  { label: 'LDM134 RMSE', key: 'ldm134_rmse', unit: 'source unit' },
  { label: 'LDM134 median', key: 'ldm134_median', unit: 'source unit' },
  { label: 'LDM134 P95', key: 'ldm134_p95', unit: 'source unit' },
  { label: 'Mesh RMSE', key: 'mesh_rmse', unit: 'source unit' },
  { label: 'Mesh median', key: 'mesh_median', unit: 'source unit' },
  { label: 'Mesh P95', key: 'mesh_p95', unit: 'source unit' },
  { label: 'Primary zone RMSE', key: 'primary_zone_rmse', unit: 'source unit' },
  { label: 'Primary zone names', key: 'primary_zone_names', unit: 'zone ref' },
  { label: 'Mesh point-to-plane RMSE', key: 'mesh_point_to_plane_rmse', unit: 'source unit' },
  { label: 'Mesh calibrated metric count', key: 'mesh_calibrated_metric_count', unit: 'count' },
  { label: 'Mesh calibrated summary', key: 'mesh_calibrated_summary', unit: 'source text' },
  {
    label: 'Descriptor significant fraction',
    key: 'descriptor_significant_fraction',
    unit: '0..1',
  },
  { label: 'Descriptor P95 z', key: 'descriptor_p95_z', unit: 'z' },
  { label: 'Coherent motion fraction', key: 'coherent_motion_fraction', unit: '0..1' },
  { label: 'Identity-only motion RMSE', key: 'identity_only_motion_rmse', unit: 'source unit' },
  { label: 'Expression influence', key: 'expression_influence', unit: 'source unit' },
  { label: 'Lead overlap', key: 'lead_overlap', unit: 'event count' },
  { label: 'Lead events', key: 'lead_events', unit: 'event ref' },
  { label: 'FDR 10% significant', key: 'mt_significant_fdr10', unit: 'boolean' },
  { label: 'Multiple-testing q-value', key: 'mt_q_value', unit: 'q-value' },
  { label: 'Raw metrics', key: 'raw_metrics', unit: 'source object' },
  { label: 'Calibrated metrics', key: 'calibrated_metrics', unit: 'source object' },
  { label: 'Texture score', key: 'texture_score_0_1', unit: '0..1' },
  { label: 'Calibration limitation', key: 'calibration_limitation_reason', unit: 'source text' },
];

const GATE_FIELDS: readonly { label: string; key: string }[] = [
  { label: 'Quality A', key: 'quality_status_a' },
  { label: 'Quality B', key: 'quality_status_b' },
  { label: 'Quality limited', key: 'quality_limited' },
  { label: 'Visibility 106', key: 'visibility_gate_accepted106' },
  { label: 'Visibility 134', key: 'visibility_gate_accepted134' },
  { label: 'Expression stratum', key: 'expression_gate_stratum' },
  { label: 'Expression confidence', key: 'expression_gate_confidence' },
  { label: 'Calibration limited', key: 'calibration_limited' },
  { label: 'Pose leakage', key: 'pose_leakage_limited' },
  { label: 'Texture conclusions', key: 'texture_conclusions_allowed' },
  { label: 'Mesh status', key: 'mesh_status' },
  { label: 'Evidence state', key: 'evidence_state' },
  { label: 'Cross-bin corroboration', key: 'cross_bin_corroboration_status' },
];

function hasCompareValues(record: PairMetricsRecord): boolean {
  return Object.entries(record).some(
    ([key, value]) =>
      !['schema', 'source_mode', 'not_a_verdict'].includes(key) &&
      value !== null &&
      value !== undefined,
  );
}

function flattenPairMetrics(payload: unknown): PairMetricsRecord {
  const source =
    payload && typeof payload === 'object' && !Array.isArray(payload)
      ? (payload as PairMetricsRecord)
      : {};
  const nested = source.metrics;
  const record =
    nested && typeof nested === 'object' && !Array.isArray(nested)
      ? (nested as PairMetricsRecord)
      : source;
  const flattened: PairMetricsRecord = { ...record };
  const categories = record.categories;
  if (categories && typeof categories === 'object' && !Array.isArray(categories)) {
    for (const category of Object.values(categories as Record<string, unknown>)) {
      if (!category || typeof category !== 'object' || Array.isArray(category)) continue;
      for (const group of Object.values(category as Record<string, unknown>)) {
        if (!group || typeof group !== 'object' || Array.isArray(group)) continue;
        Object.assign(flattened, group);
      }
    }
  }
  return flattened;
}

function compareDisplayValue(value: unknown) {
  if (value === null || value === undefined || value === '') return 'Unavailable';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return 'Structured value';
  return String(value);
}

function compareStructuredValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Unavailable';
  if (typeof value !== 'object') return compareDisplayValue(value);
  try {
    const serialized = JSON.stringify(value, null, 2);
    return serialized && serialized !== '{}' && serialized !== '[]' ? serialized : 'Unavailable';
  } catch {
    return 'Structured value unavailable';
  }
}

function compareStatusTone(value: unknown): 'positive' | 'warning' | 'muted' {
  if (value === true) return 'positive';
  if (value === false) return 'warning';
  if (typeof value !== 'string') return 'muted';
  if (['measured', 'valid', 'pass', 'complete', 'supported', 'accepted'].includes(value)) {
    return 'positive';
  }
  if (
    [
      'limited',
      'partial',
      'not_computed',
      'skipped',
      'missing',
      'stale',
      'fallback',
      'review',
      'none',
      'unavailable',
      'error',
      'blocking',
      'disabled',
      'not_applicable',
    ].includes(value)
  ) {
    return 'warning';
  }
  return 'muted';
}

function CompareStatusPill({ value, label }: { value: unknown; label?: string }) {
  const tone = compareStatusTone(value);
  return (
    <span className={`compare-status compare-status--${tone}`}>
      <span className="compare-status-dot" aria-hidden="true" />
      {label ?? compareDisplayValue(value)}
    </span>
  );
}

function compareErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.detail;
  return 'Источник данных недоступен.';
}

function CompareSourceContext({
  state,
  error,
  sourceRefs,
  onRetry,
}: {
  state: CompareState;
  error?: string;
  sourceRefs: readonly string[];
  onRetry?: () => void;
}) {
  const stateLabel = {
    idle: 'Not requested',
    loading: 'Loading source',
    ready: 'Calculated source returned',
    partial: 'Partial calculated source',
    empty: 'No calculated record',
    error: 'Source unavailable',
  }[state];

  return (
    <aside className="compare-source-context" aria-label="Контекст источника Compare">
      <div className="compare-source-header">
        <div>
          <span className="micro-label">Evidence boundary</span>
          <strong>{stateLabel}</strong>
        </div>
        <CompareStatusPill value={state === 'ready' ? 'measured' : state} />
      </div>
      <div className="compare-source-flags">
        <code>source_mode: research</code>
        <code>not_a_verdict: true</code>
      </div>
      {error ? <p className="compare-error-copy">{error}</p> : null}
      {state === 'error' && onRetry ? (
        <button className="compare-button compare-button--quiet" type="button" onClick={onRetry}>
          Retry source request
        </button>
      ) : null}
      <details className="compare-source-details">
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

function CompareTextField({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}) {
  return (
    <label className="compare-field">
      <span>{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        spellCheck={false}
      />
    </label>
  );
}

function CompareDataCard({ label, value, unit }: { label: string; value: unknown; unit?: string }) {
  return (
    <div className="compare-data-card">
      <span>{label}</span>
      <strong>{compareDisplayValue(value)}</strong>
      <small>{unit ?? 'source field'}</small>
    </div>
  );
}

function CompareMetricTable({ metrics }: { metrics: PairMetricsRecord }) {
  return (
    <>
      <div className="compare-separation-grid" aria-label="Raw and calibrated value separation">
        <div>
          <span className="micro-label">Raw value</span>
          <strong>{compareDisplayValue(metrics.raw_value)}</strong>
          <small>source field: raw_value</small>
        </div>
        <div>
          <span className="micro-label">Calibrated value</span>
          <strong>{compareDisplayValue(metrics.calibrated_value)}</strong>
          <small>source field: calibrated_value</small>
        </div>
        <div>
          <span className="micro-label">Robust-z</span>
          <strong>{compareDisplayValue(metrics.robust_z ?? metrics.primary_robust_z)}</strong>
          <small>source field: robust_z / primary_robust_z</small>
        </div>
        <div>
          <span className="micro-label">Calibration P95</span>
          <strong>{compareDisplayValue(metrics.primary_calibration_p95)}</strong>
          <small>source field: primary_calibration_p95</small>
        </div>
      </div>
      <div className="compare-table-wrap">
        <table className="compare-metric-table">
          <caption>Returned pair metrics; absent fields stay unavailable.</caption>
          <thead>
            <tr>
              <th scope="col">Metric field</th>
              <th scope="col">Returned value</th>
              <th scope="col">Unit / interpretation</th>
            </tr>
          </thead>
          <tbody>
            {PAIR_METRIC_ROWS.map((row) => (
              <tr key={row.key}>
                <th scope="row">{row.label}</th>
                <td>{compareDisplayValue(metrics[row.key])}</td>
                <td>{row.unit}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <details className="compare-structured-details compare-all-fields">
        <summary>
          All returned pair fields (
          {
            Object.keys(metrics).filter(
              (key) => !['schema', 'source_mode', 'not_a_verdict'].includes(key),
            ).length
          }
          )
        </summary>
        <pre>{compareStructuredValue(metrics)}</pre>
      </details>
    </>
  );
}

function ComparePairArtifactReferences({ metrics }: { metrics: PairMetricsRecord }) {
  const artifacts = [
    { label: 'Pair mesh', value: metrics.mesh_file, status: metrics.mesh_status },
    { label: 'Pair motion', value: metrics.motion_file, status: metrics.motion_status },
  ];

  return (
    <details className="compare-artifact-reference-panel">
      <summary>Pair artifact references and availability</summary>
      <div className="compare-artifact-reference-list">
        {artifacts.map((artifact) => {
          const href = returnedArtifactHref(artifact.value);
          return (
            <div className="compare-artifact-reference" key={artifact.label}>
              <span className="micro-label">{artifact.label}</span>
              <code>{compareDisplayValue(artifact.value)}</code>
              <CompareStatusPill
                value={
                  artifact.status ?? (artifact.value === undefined ? 'unavailable' : 'not checked')
                }
              />
              {href ? (
                <a className="compare-artifact-link" href={href} target="_blank" rel="noreferrer">
                  Open returned artifact
                </a>
              ) : null}
            </div>
          );
        })}
      </div>
      <p className="compare-artifact-reference-note">
        Links are created only from returned artifact references; status-only values never become
        guessed URLs.
      </p>
    </details>
  );
}

function GateGrid({ metrics }: { metrics: PairMetricsRecord }) {
  return (
    <div className="compare-gate-grid" aria-label="Quality and applicability gates">
      {GATE_FIELDS.map((gate) => (
        <div className="compare-gate-card" key={gate.key}>
          <span>{gate.label}</span>
          <CompareStatusPill value={metrics[gate.key]} />
        </div>
      ))}
    </div>
  );
}

function CompareVisualFirstSummary({
  metrics,
  photoA,
  photoB,
}: {
  metrics: PairMetricsRecord;
  photoA: string;
  photoB: string;
}) {
  return (
    <div className="compare-visual-first-summary" aria-label="Visual-first pair context">
      <div className="compare-subsection-heading">
        <div>
          <span className="micro-label">Visual-first context</span>
          <strong>Inspect returned artifacts before expanding metrics</strong>
        </div>
        <CompareStatusPill value={metrics.status} />
      </div>
      <div className="compare-detail-grid">
        <CompareDataCard label="Photo A" value={metrics.photo_a ?? photoA} />
        <CompareDataCard label="Photo B" value={metrics.photo_b ?? photoB} />
        <CompareDataCard label="Date A" value={metrics.date_a} />
        <CompareDataCard label="Date B" value={metrics.date_b} />
        <CompareDataCard label="Pose bin" value={metrics.pose_bin} />
        <CompareDataCard label="Evidence state" value={metrics.evidence_state} />
        <CompareDataCard label="Raw value" value={metrics.raw_value} />
        <CompareDataCard label="Calibrated value" value={metrics.calibrated_value} />
        <CompareDataCard label="Robust-z" value={metrics.robust_z ?? metrics.primary_robust_z} />
        <CompareDataCard
          label="FDR / q-value"
          value={`${compareDisplayValue(metrics.fdr)} / ${compareDisplayValue(metrics.q_value ?? metrics.mt_q_value)}`}
        />
      </div>
      <div className="compare-visual-first-note">
        <strong>Visual priority</strong>
        <span>
          The visual-first mode keeps image and artifact context ahead of the full metric table. It
          does not create a mesh, landmark, heatmap or texture layer; the visual block below checks
          returned references and shows unavailable states where none are supplied.
        </span>
      </div>
      <CompareArtifactReferencePanel metadata={undefined} photoA={photoA} photoB={photoB} />
      <div className="compare-structured-details-grid">
        <details>
          <summary>Gate context</summary>
          <pre>{compareStructuredValue(metrics.gate_statuses)}</pre>
        </details>
        <details>
          <summary>Source and limitation refs</summary>
          <pre>
            {compareStructuredValue({
              source_refs: metrics.source_refs ?? metrics.source_ref,
              limitation_refs: metrics.limitation_refs ?? metrics.limitations,
            })}
          </pre>
        </details>
      </div>
    </div>
  );
}

function PairPreviewPanel({
  onSelectPair,
}: {
  onSelectPair: (photoA: string, photoB: string) => void;
}) {
  const [state, setState] = useState<CompareState>('idle');
  const [rows, setRows] = useState<readonly CsvRecord[]>([]);
  const [filter, setFilter] = useState('');
  const [error, setError] = useState<string>();

  const loadPreview = async () => {
    setState('loading');
    setRows([]);
    setError(undefined);
    try {
      const text = await requestUiArtifactText('pair_metrics_preview.csv');
      const returnedRows = parseCsvRecords(text);
      setRows(returnedRows);
      setState(returnedRows.length ? 'ready' : 'empty');
    } catch (requestError) {
      setState('error');
      setError(compareErrorMessage(requestError));
    }
  };

  const normalizedFilter = filter.trim().toLowerCase();
  const visibleRows = normalizedFilter
    ? rows.filter((row) =>
        Object.values(row).some((value) => value.toLowerCase().includes(normalizedFilter)),
      )
    : rows;
  const previewColumns = [
    ['pair_id', 'Pair'],
    ['photo_a', 'Photo A'],
    ['photo_b', 'Photo B'],
    ['pose_bin', 'Pose'],
    ['status', 'Status'],
    ['mesh_rmse', 'Mesh RMSE'],
    ['texture_score_0_1', 'Texture 0..1'],
    ['primary_robust_z', 'Primary robust-z'],
    ['quality_limited', 'Quality limited'],
    ['calibration_limited', 'Calibration limited'],
  ] as const;

  return (
    <section className="compare-preview-panel" aria-labelledby="compare-pair-preview-title">
      <div className="compare-subsection-heading">
        <div>
          <span className="micro-label">Derived pair list</span>
          <strong id="compare-pair-preview-title">Pair metrics preview</strong>
          <span>
            Lightweight first-500 preview for choosing a pair. Full pair metrics load only after A/B
            selection.
          </span>
        </div>
        <CompareStatusPill
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Not loaded' : undefined}
        />
      </div>
      <div className="compare-preview-controls">
        <label className="compare-field">
          <span>Find pair or photo</span>
          <input
            value={filter}
            onChange={(event) => setFilter(event.target.value)}
            placeholder="pair_id or photo_id"
            spellCheck={false}
          />
        </label>
        <button
          className="compare-button compare-button--quiet"
          type="button"
          onClick={() => void loadPreview()}
          disabled={state === 'loading'}
        >
          {state === 'loading' ? 'Loading…' : 'Load pair preview'}
        </button>
      </div>
      {error ? <p className="compare-error-copy">{error}</p> : null}
      {visibleRows.length ? (
        <div className="compare-table-wrap compare-preview-table-wrap">
          <table className="compare-metric-table compare-preview-table">
            <caption>ui_artifacts/pair_metrics_preview.csv · returned rows only</caption>
            <thead>
              <tr>
                {previewColumns.map(([, label]) => (
                  <th scope="col" key={label}>
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {visibleRows.map((row, index) => (
                <tr key={`${row.pair_id ?? row.photo_a ?? 'pair'}-${index}`}>
                  {previewColumns.map(([key]) => (
                    <td key={key}>
                      {key === 'pair_id' && row.photo_a && row.photo_b ? (
                        <button
                          className="compare-text-button"
                          type="button"
                          onClick={() => onSelectPair(row.photo_a, row.photo_b)}
                        >
                          {compareDisplayValue(row[key])}
                        </button>
                      ) : (
                        compareDisplayValue(row[key])
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="compare-no-data compare-no-data--compact" role="status">
          <span className="compare-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty' ? 'Preview contains no rows' : 'No pair preview loaded'}
            </strong>
            <span>
              The preview is not a substitute for a pair-specific metric request; empty values are
              not filled locally.
            </span>
          </div>
        </div>
      )}
      <div className="compare-source-flags">
        <code>source: ui_artifacts/pair_metrics_preview.csv</code>
        <code>endpoint: /api/v1/ui_artifacts/pair_metrics_preview.csv</code>
        <code>
          rows shown: {visibleRows.length} / {rows.length}
        </code>
      </div>
    </section>
  );
}

function PairDetailBlock() {
  const [photoA, setPhotoA] = useState(() => hashParam('photo_a'));
  const [photoB, setPhotoB] = useState(() => hashParam('photo_b'));
  const [mode, setMode] = useState<CompareMode>('data-first');
  const [state, setState] = useState<CompareState>('idle');
  const [metrics, setMetrics] = useState<PairMetricsRecord>();
  const [error, setError] = useState<string>();
  const abortRef = useRef<AbortController | undefined>(undefined);

  useEffect(() => {
    return () => abortRef.current?.abort();
  }, []);

  const loadMetrics = async () => {
    const first = photoA.trim();
    const second = photoB.trim();
    if (!first || !second) {
      setState('error');
      setMetrics(undefined);
      setError('Enter both photo IDs from the calculated archive before requesting a pair.');
      return;
    }

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState('loading');
    setMetrics(undefined);
    setError(undefined);

    try {
      const response = await requestJson<PairRequestResponse>(
        `/api/v1/pairs/${encodeURIComponent(first)}/${encodeURIComponent(second)}/metrics`,
        { signal: controller.signal },
      );
      const returnedMetrics = flattenPairMetrics(response);
      const hasPairIdentity = Boolean(
        returnedMetrics.pair_id ||
          returnedMetrics.photo_a ||
          returnedMetrics.photo_b ||
          hasCompareValues(returnedMetrics),
      );
      setMetrics(returnedMetrics);
      setState(hasPairIdentity ? 'ready' : 'empty');
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setMetrics(undefined);
      setState('error');
      setError(compareErrorMessage(requestError));
    }
  };

  const hasMetrics = state === 'ready' && metrics;

  return (
    <section className="detail-block detail-block--compare" aria-labelledby="compare-pair-title">
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / compare.pair-detail</span>
          <h3 id="compare-pair-title">Pair Detail and data-first analysis</h3>
          <p>
            Start with measurements, then inspect the visual confirmation without turning either
            into a verdict.
          </p>
        </div>
        <CompareStatusPill
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>

      <div className={`compare-pair-controls compare-pair-controls--${mode}`}>
        <div className="compare-control-heading">
          <div>
            <span className="micro-label">Pair scope</span>
            <strong>A and B remain explicit inputs</strong>
          </div>
          <label className="compare-mode-field">
            <span>Scenario</span>
            <select value={mode} onChange={(event) => setMode(event.target.value as CompareMode)}>
              <option value="data-first">Data-first</option>
              <option value="visual-first">Visual-first</option>
            </select>
          </label>
        </div>
        <div className="compare-fields">
          <CompareTextField
            label="Photo A"
            value={photoA}
            onChange={setPhotoA}
            placeholder="calculated photo_id"
          />
          <CompareTextField
            label="Photo B"
            value={photoB}
            onChange={setPhotoB}
            placeholder="calculated photo_id"
          />
        </div>
        <div className="compare-control-footer">
          <span>
            GET /api/v1/pairs/{'{photo_a}'}/{'{photo_b}'}/metrics · 222 returned columns; no pair is
            inferred from an empty scope.
          </span>
          <button
            className="compare-button"
            type="button"
            onClick={() => void loadMetrics()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load pair metrics'}
          </button>
        </div>
      </div>

      <PairPreviewPanel
        onSelectPair={(nextPhotoA, nextPhotoB) => {
          setPhotoA(nextPhotoA);
          setPhotoB(nextPhotoB);
        }}
      />
      {error ? <p className="compare-error-copy">{error}</p> : null}
      {hasMetrics && mode === 'data-first' ? (
        <>
          <div className="compare-identity-strip">
            <div>
              <span className="micro-label">Pair</span>
              <strong>{compareDisplayValue(metrics.pair_id) || `${photoA} → ${photoB}`}</strong>
            </div>
            <div>
              <span className="micro-label">Status</span>
              <CompareStatusPill value={metrics.status} />
            </div>
            <div>
              <span className="micro-label">Pose bin</span>
              <strong>{compareDisplayValue(metrics.pose_bin)}</strong>
            </div>
            <div>
              <span className="micro-label">FDR / q-value</span>
              <strong>
                {compareDisplayValue(metrics.fdr)} /{' '}
                {compareDisplayValue(metrics.q_value ?? metrics.mt_q_value)}
              </strong>
            </div>
          </div>
          <div className="compare-detail-grid" aria-label="Pair context details">
            <CompareDataCard label="Photo A" value={metrics.photo_a ?? photoA} />
            <CompareDataCard label="Photo B" value={metrics.photo_b ?? photoB} />
            <CompareDataCard label="Date A" value={metrics.date_a} />
            <CompareDataCard label="Date B" value={metrics.date_b} />
            <CompareDataCard label="Pair type" value={metrics.pair_type} />
            <CompareDataCard label="Pair role" value={metrics.pair_role} />
            <CompareDataCard label="Pair family" value={metrics.pair_family} />
            <CompareDataCard label="Baseline pair" value={metrics.baseline_pair} />
            <CompareDataCard label="Rolling pair" value={metrics.rolling_pair} />
            <CompareDataCard label="Evidence state" value={metrics.evidence_state} />
            <CompareDataCard label="QC skip reason" value={metrics.qc_skip_reason} />
            <CompareDataCard label="Alignment A" value={metrics.alignment_quality_a} unit="0..1" />
            <CompareDataCard label="Alignment B" value={metrics.alignment_quality_b} unit="0..1" />
            <CompareDataCard
              label="Pose distance"
              value={metrics.pose_distance}
              unit="source unit"
            />
            <CompareDataCard label="Pitch gap" value={metrics.pitch_gap_deg} unit="deg" />
            <CompareDataCard label="Yaw gap" value={metrics.yaw_gap_deg} unit="deg" />
            <CompareDataCard label="Roll gap" value={metrics.roll_gap_deg} unit="deg" />
            <CompareDataCard
              label="Mesh calibrated count"
              value={metrics.mesh_calibrated_metric_count}
            />
            <CompareDataCard label="Mesh status" value={metrics.mesh_status} />
            <CompareDataCard label="Texture score" value={metrics.texture_score_0_1} unit="0..1" />
            <CompareDataCard label="Lead priority" value={metrics.lead_priority} />
            <CompareDataCard label="Lead overlap" value={metrics.lead_overlap} />
            <CompareDataCard label="Expression influence" value={metrics.expression_influence} />
            <CompareDataCard label="Coordinate space" value={metrics.coordinate_space} />
            <CompareDataCard label="Measurement state" value={metrics.measurement_state} />
            <CompareDataCard label="Quality state" value={metrics.quality_state} />
            <CompareDataCard label="Visibility state" value={metrics.visibility_state} />
            <CompareDataCard label="Calibration state" value={metrics.calibration_state} />
            <CompareDataCard
              label="Source refs"
              value={metrics.source_refs ?? metrics.source_ref}
            />
            <CompareDataCard
              label="Limitations"
              value={metrics.limitation_refs ?? metrics.limitations}
            />
            <CompareDataCard
              label="Coherent motion"
              value={metrics.coherent_motion_fraction}
              unit="0..1"
            />
          </div>
          <div className="compare-cross-links" aria-label="Pair context transitions">
            <span className="micro-label">Open related context</span>
            <button
              className="compare-text-button"
              type="button"
              onClick={() =>
                navigateTo('photo-detail', { photo_id: String(metrics.photo_a ?? photoA) })
              }
              disabled={!String(metrics.photo_a ?? photoA).trim()}
            >
              Photo A detail
            </button>
            <button
              className="compare-text-button"
              type="button"
              onClick={() =>
                navigateTo('photo-detail', { photo_id: String(metrics.photo_b ?? photoB) })
              }
              disabled={!String(metrics.photo_b ?? photoB).trim()}
            >
              Photo B detail
            </button>
            <button
              className="compare-text-button"
              type="button"
              onClick={() =>
                navigateTo('research', {
                  photo_a: String(metrics.photo_a ?? photoA),
                  photo_b: String(metrics.photo_b ?? photoB),
                })
              }
              disabled={
                !String(metrics.photo_a ?? photoA).trim() ||
                !String(metrics.photo_b ?? photoB).trim()
              }
            >
              Research context
            </button>
            <button
              className="compare-text-button"
              type="button"
              onClick={() =>
                navigateTo('compare', {
                  photo_a: String(metrics.photo_a ?? photoA),
                  photo_b: String(metrics.photo_b ?? photoB),
                  visual_mode: 'morph_2d',
                })
              }
            >
              Open Morphing
            </button>
            <button
              className="compare-text-button"
              type="button"
              onClick={() =>
                navigateTo('research', {
                  photo_a: String(metrics.photo_a ?? photoA),
                  photo_b: String(metrics.photo_b ?? photoB),
                })
              }
            >
              Zone Atlas
            </button>
            <button
              className="compare-text-button"
              type="button"
              onClick={() =>
                navigateTo('research', { candidate_id: String(metrics.pair_id ?? '') })
              }
              disabled={!String(metrics.pair_id ?? '').trim()}
            >
              Casework
            </button>
            <button
              className="compare-text-button"
              type="button"
              onClick={() => navigateTo('research', { pair_id: String(metrics.pair_id ?? '') })}
              disabled={!String(metrics.pair_id ?? '').trim()}
            >
              Corroboration
            </button>
            <button
              className="compare-text-button"
              type="button"
              onClick={() =>
                navigateTo('report', {
                  pair_id: typeof metrics.pair_id === 'string' ? metrics.pair_id : undefined,
                })
              }
            >
              Open Report
            </button>
            <button
              className="compare-text-button"
              type="button"
              onClick={() =>
                navigateTo('publications', { claim_id: String(metrics.pair_id ?? '') })
              }
              disabled={!String(metrics.pair_id ?? '').trim()}
            >
              Add to Publication
            </button>
          </div>
          <GateGrid metrics={metrics} />
          <div className="compare-structured-details-grid">
            <details>
              <summary>Raw metrics</summary>
              <pre>{compareStructuredValue(metrics.raw_metrics)}</pre>
            </details>
            <details>
              <summary>Calibrated metrics</summary>
              <pre>{compareStructuredValue(metrics.calibrated_metrics)}</pre>
            </details>
            <details>
              <summary>Gate statuses</summary>
              <pre>{compareStructuredValue(metrics.gate_statuses)}</pre>
            </details>
            <details>
              <summary>Source and limitation refs</summary>
              <pre>
                {compareStructuredValue({
                  source_refs: metrics.source_refs ?? metrics.source_ref,
                  limitation_refs: metrics.limitation_refs ?? metrics.limitations,
                })}
              </pre>
            </details>
          </div>
          <CompareMetricTable metrics={metrics} />
          <ComparePairArtifactReferences metrics={metrics} />
        </>
      ) : hasMetrics ? (
        <CompareVisualFirstSummary metrics={metrics} photoA={photoA} photoB={photoB} />
      ) : (
        <div className="compare-no-data" role="status">
          <span className="compare-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty'
                ? 'Pair record has no comparable fields'
                : 'No pair metrics loaded'}
            </strong>
            <span>
              Raw, calibrated and robust values appear only when returned by the Stage 2/API source.
            </span>
          </div>
        </div>
      )}
      <div className="compare-verdict-note">
        <strong>Interpretation boundary</strong>
        <span>
          FDR, q-value, visual similarity and reconstructed geometry are measurements with gates and
          limitations, not identity conclusions.
        </span>
      </div>
      <CompareSourceContext
        state={state}
        error={error}
        onRetry={() => void loadMetrics()}
        sourceRefs={comparePage.blocks[0].sourceRefs}
      />
    </section>
  );
}

function returnedArtifactHref(value: unknown): string | undefined {
  if (typeof value !== 'string' || !value.trim()) return undefined;
  const normalized = value.trim().toLowerCase();
  if (
    [
      'available',
      'unavailable',
      'missing',
      'not checked',
      'not_checked',
      'valid',
      'invalid',
      'partial',
      'limited',
      'fallback',
      'error',
      'true',
      'false',
    ].includes(normalized)
  ) {
    return undefined;
  }
  // A returned absolute URL is authoritative. Relative filesystem references are shown as
  // references only; this block never guesses a browser URL for a heavy source.
  return /^(https?:)?\//.test(value) ? value : undefined;
}

function CompareArtifactImage({ photoId }: { photoId: string }) {
  const [state, setState] = useState<'loading' | 'ready' | 'error'>('loading');
  const source = `/api/v1/photos/${encodeURIComponent(photoId)}/image?kind=original`;

  useEffect(() => {
    setState('loading');
  }, [source]);

  if (state === 'error') {
    return <span className="compare-artifact-unavailable">Original image unavailable</span>;
  }

  return (
    <>
      {state === 'loading' ? (
        <span className="compare-artifact-loading">Loading original artifact…</span>
      ) : null}
      <img
        className="compare-artifact-image"
        src={source}
        alt={`Original artifact for ${photoId}`}
        onLoad={() => setState('ready')}
        onError={() => setState('error')}
      />
    </>
  );
}

function CompareVisualComposite({
  visualMode,
  photoA,
  photoB,
  progress,
  zoom,
  panX,
  panY,
}: {
  visualMode: VisualMode;
  photoA: string;
  photoB: string;
  progress: number;
  zoom: number;
  panX: number;
  panY: number;
}) {
  const transform = `translate(${panX}px, ${panY}px) scale(${zoom})`;
  const progressRatio = progress / 100;
  const topStyle: CSSProperties =
    visualMode === 'divider'
      ? { clipPath: `inset(0 0 0 ${progress}%)` }
      : { opacity: progressRatio };
  return (
    <div className={`compare-composite compare-composite--${visualMode}`}>
      <div className="compare-composite-layer compare-composite-layer--a" style={{ transform }}>
        <span className="micro-label">A · original</span>
        <CompareArtifactImage photoId={photoA} />
      </div>
      <div
        className="compare-composite-layer compare-composite-layer--b"
        style={{ ...topStyle, transform }}
      >
        <span className="micro-label">B · original</span>
        <CompareArtifactImage photoId={photoB} />
      </div>
      <div className="compare-composite-caption">
        <strong>
          {visualMode === 'morph_2d'
            ? '2D crossfade proxy'
            : visualMode === 'divider'
              ? 'A | B divider'
              : 'Overlay'}
        </strong>
        <span>
          {visualMode === 'morph_2d'
            ? 'No morph artifact is synthesized; the slider changes returned image opacity only.'
            : 'Original artifacts remain separate source layers; slider controls visibility only.'}
        </span>
      </div>
    </div>
  );
}

function CompareLayerStatus({
  label,
  enabled,
  value,
  explanation,
}: {
  label: string;
  enabled: boolean;
  value: unknown;
  explanation: string;
}) {
  const href = enabled ? returnedArtifactHref(value) : undefined;
  return (
    <div className="compare-layer-status-card">
      <div>
        <span className="micro-label">{label}</span>
        <CompareStatusPill
          value={enabled ? value : 'disabled'}
          label={enabled ? compareDisplayValue(value) : 'Off'}
        />
      </div>
      <span>{explanation}</span>
      {href ? (
        <a className="compare-artifact-link" href={href} target="_blank" rel="noreferrer">
          Open returned layer artifact
        </a>
      ) : null}
    </div>
  );
}

function CompareArtifactReferencePanel({
  metadata,
  photoA,
  photoB,
}: {
  metadata?: { a: PhotoMetadataRecord; b: PhotoMetadataRecord };
  photoA: string;
  photoB: string;
}) {
  const references = [
    {
      side: 'A',
      photoId: photoA,
      record: metadata?.a,
    },
    {
      side: 'B',
      photoId: photoB,
      record: metadata?.b,
    },
  ].flatMap(({ side, photoId, record }) => {
    const source = (key: string) => record?.[key];
    const returnedPhotoId = source('photo_id') ?? source('id');
    const originalRef = source('original_image_ref') ?? source('image_ref');
    const originalLink =
      returnedPhotoId !== undefined && String(returnedPhotoId) === photoId
        ? (returnedArtifactHref(originalRef) ??
          `/api/v1/photos/${encodeURIComponent(photoId)}/image?kind=original`)
        : undefined;
    return [
      {
        label: `${side} original`,
        value: originalRef ?? originalLink,
        status: source('original_image_status') ?? source('artifact_status'),
        link: originalLink,
      },
      {
        label: `${side} mesh`,
        value: source('mesh_ref') ?? source('mesh_file'),
        status: source('mesh_status') ?? source('full_mesh_available'),
      },
      {
        label: `${side} landmarks`,
        value: source('ldm106_source') ?? source('landmark_source'),
        status: source('landmark_status'),
      },
      {
        label: `${side} zones`,
        value: source('zones_overlay') ?? source('zone_ref'),
        status: source('zone_status'),
      },
      {
        label: `${side} texture / UV`,
        value: source('uv_texture') ?? source('texture_json'),
        status: source('texture_status') ?? source('uv_status'),
      },
    ];
  });

  return (
    <details className="compare-artifact-reference-panel">
      <summary>Artifact references and availability</summary>
      <div className="compare-artifact-reference-list">
        {references.map((reference) => {
          const value = compareDisplayValue(reference.value);
          const href = returnedArtifactHref(reference.value) ?? reference.link;
          return (
            <div className="compare-artifact-reference" key={reference.label}>
              <span className="micro-label">{reference.label}</span>
              <code>{value}</code>
              <CompareStatusPill
                value={reference.status ?? (metadata ? 'not checked' : 'unavailable')}
                label={
                  reference.status === undefined
                    ? metadata
                      ? 'not checked'
                      : 'unavailable'
                    : undefined
                }
              />
              {href && reference.value !== undefined ? (
                <a className="compare-artifact-link" href={href} target="_blank" rel="noreferrer">
                  Open returned reference
                </a>
              ) : null}
            </div>
          );
        })}
      </div>
      <p className="compare-artifact-reference-note">
        The original image endpoint is a source route, not a generated image. Other links appear
        only when the photo response returns a reference.
      </p>
    </details>
  );
}

function VisualArtifactBlock() {
  const [photoA, setPhotoA] = useState(() => hashParam('photo_a'));
  const [photoB, setPhotoB] = useState(() => hashParam('photo_b'));
  const [visualMode, setVisualMode] = useState<VisualMode>(routeVisualMode());
  const [progress, setProgress] = useState(50);
  const [speed, setSpeed] = useState(1);
  const [zoom, setZoom] = useState(1);
  const [panX, setPanX] = useState(0);
  const [panY, setPanY] = useState(0);
  const [camera, setCamera] = useState('source');
  const [coordinateSpace, setCoordinateSpace] = useState('original');
  const [colorThreshold, setColorThreshold] = useState('');
  const [playing, setPlaying] = useState(false);
  const [landmarks, setLandmarks] = useState(false);
  const [zones, setZones] = useState(false);
  const [heatmap, setHeatmap] = useState(false);
  const [texture, setTexture] = useState(false);
  const [smoothing, setSmoothing] = useState('source');
  const [normalization, setNormalization] = useState('source');
  const [state, setState] = useState<CompareState>('idle');
  const [metadata, setMetadata] = useState<{ a: PhotoMetadataRecord; b: PhotoMetadataRecord }>();
  const [error, setError] = useState<string>();

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setProgress((current) => Math.min(100, current + Math.max(1, speed * 2)));
    }, 80);
    return () => window.clearInterval(timer);
  }, [playing, speed]);

  useEffect(() => {
    if (progress >= 100 && playing) setPlaying(false);
  }, [playing, progress]);

  const loadArtifacts = async () => {
    const first = photoA.trim();
    const second = photoB.trim();
    if (!first || !second) {
      setState('error');
      setError('Enter both photo IDs before checking visual artifacts.');
      return;
    }

    setState('loading');
    setPlaying(false);
    setMetadata(undefined);
    setError(undefined);
    try {
      const [firstRecord, secondRecord] = await Promise.all([
        requestJson<PhotoMetadataRecord>(`/api/v1/photos/${encodeURIComponent(first)}`),
        requestJson<PhotoMetadataRecord>(`/api/v1/photos/${encodeURIComponent(second)}`),
      ]);
      setMetadata({ a: firstRecord, b: secondRecord });
      setState(
        firstRecord.photo_id || firstRecord.id || secondRecord.photo_id || secondRecord.id
          ? 'ready'
          : 'empty',
      );
    } catch (requestError) {
      setState('error');
      setError(compareErrorMessage(requestError));
    }
  };

  const meshA = metadata?.a.full_mesh_available;
  const meshB = metadata?.b.full_mesh_available;
  const meshRefA = returnedArtifactHref(metadata?.a.mesh_file ?? metadata?.a.mesh_ref);
  const meshRefB = returnedArtifactHref(metadata?.b.mesh_file ?? metadata?.b.mesh_ref);
  const visualState = metadata ? 'measured' : state === 'error' ? 'unavailable' : 'unavailable';
  const landmarkA =
    metadata?.a.landmarks_106 ?? metadata?.a.ldm106_source ?? metadata?.a.landmark_contract;
  const landmarkB =
    metadata?.b.landmarks_106 ?? metadata?.b.ldm106_source ?? metadata?.b.landmark_contract;
  const zoneA = metadata?.a.zones_overlay ?? metadata?.a.zones ?? metadata?.a.zone_status;
  const zoneB = metadata?.b.zones_overlay ?? metadata?.b.zones ?? metadata?.b.zone_status;
  const heatmapA = metadata?.a.heatmap_ref ?? metadata?.a.heatmap;
  const heatmapB = metadata?.b.heatmap_ref ?? metadata?.b.heatmap;
  const textureA = metadata?.a.uv_texture ?? metadata?.a.texture_json ?? metadata?.a.texture_status;
  const textureB = metadata?.b.uv_texture ?? metadata?.b.texture_json ?? metadata?.b.texture_status;

  return (
    <section className="detail-block detail-block--compare" aria-labelledby="compare-morph-title">
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / compare.morphing</span>
          <h3 id="compare-morph-title">Visual-first comparison and Morphing</h3>
          <p>
            Viewer modes, layers and playback stay with the A/B artifact context they interpret.
          </p>
        </div>
        <CompareStatusPill
          value={visualState}
          label={state === 'ready' ? 'Artifacts checked' : 'No artifacts loaded'}
        />
      </header>

      <div className="compare-visual-controls">
        <div className="compare-fields">
          <CompareTextField
            label="Photo A"
            value={photoA}
            onChange={setPhotoA}
            placeholder="calculated photo_id"
          />
          <CompareTextField
            label="Photo B"
            value={photoB}
            onChange={setPhotoB}
            placeholder="calculated photo_id"
          />
          <label className="compare-field">
            <span>View mode</span>
            <select
              value={visualMode}
              onChange={(event) => setVisualMode(event.target.value as VisualMode)}
            >
              <option value="side_by_side">Side by side</option>
              <option value="overlay">Overlay</option>
              <option value="divider">A | B divider</option>
              <option value="morph_2d">2D morph</option>
              <option value="mesh_3d">3D mesh</option>
            </select>
          </label>
        </div>
        <div className="compare-range-row">
          <label className="compare-range-field">
            <span>
              Progress <strong>{progress}%</strong>
            </span>
            <input
              type="range"
              min="0"
              max="100"
              value={progress}
              onChange={(event) => setProgress(Number(event.target.value))}
            />
          </label>
          <label className="compare-range-field">
            <span>
              Speed <strong>{speed}×</strong>
            </span>
            <input
              type="range"
              min="0.25"
              max="2"
              step="0.25"
              value={speed}
              onChange={(event) => setSpeed(Number(event.target.value))}
            />
          </label>
          <label className="compare-range-field">
            <span>
              Zoom <strong>{zoom}×</strong>
            </span>
            <input
              type="range"
              min="1"
              max="4"
              step="0.5"
              value={zoom}
              onChange={(event) => setZoom(Number(event.target.value))}
            />
          </label>
          <label className="compare-range-field">
            <span>
              Pan X <strong>{panX}px</strong>
            </span>
            <input
              type="range"
              min="-80"
              max="80"
              step="1"
              value={panX}
              onChange={(event) => setPanX(Number(event.target.value))}
            />
          </label>
          <label className="compare-range-field">
            <span>
              Pan Y <strong>{panY}px</strong>
            </span>
            <input
              type="range"
              min="-80"
              max="80"
              step="1"
              value={panY}
              onChange={(event) => setPanY(Number(event.target.value))}
            />
          </label>
        </div>
        <div className="compare-fields compare-fields--secondary">
          <label className="compare-field">
            <span>Coordinate space</span>
            <select
              value={coordinateSpace}
              onChange={(event) => setCoordinateSpace(event.target.value)}
            >
              <option value="original">Original image px</option>
              <option value="aligned">Chronology aligned</option>
              <option value="raw">Raw object normalized</option>
              <option value="mesh">Mesh</option>
              <option value="uv">UV</option>
            </select>
          </label>
          <label className="compare-field">
            <span>3D camera</span>
            <select value={camera} onChange={(event) => setCamera(event.target.value)}>
              <option value="source">Source camera</option>
              <option value="front">Front</option>
              <option value="left">Left</option>
              <option value="right">Right</option>
              <option value="top">Top</option>
            </select>
          </label>
          <label className="compare-field">
            <span>Smoothing</span>
            <select value={smoothing} onChange={(event) => setSmoothing(event.target.value)}>
              <option value="source">Source setting</option>
              <option value="off">Off</option>
              <option value="returned">Returned only</option>
            </select>
          </label>
          <label className="compare-field">
            <span>Normalization</span>
            <select
              value={normalization}
              onChange={(event) => setNormalization(event.target.value)}
            >
              <option value="source">Source setting</option>
              <option value="none">None</option>
              <option value="returned">Returned only</option>
            </select>
          </label>
          <label className="compare-field">
            <span>Color threshold</span>
            <input
              value={colorThreshold}
              onChange={(event) => setColorThreshold(event.target.value)}
              placeholder="returned threshold"
            />
          </label>
          <div className="compare-playback-actions" aria-label="Morph playback controls">
            <button
              className="compare-button compare-button--quiet"
              type="button"
              onClick={() => {
                if (progress >= 100) setProgress(0);
                setPlaying(true);
              }}
              disabled={playing}
            >
              Play
            </button>
            <button
              className="compare-button compare-button--quiet"
              type="button"
              onClick={() => setPlaying(false)}
              disabled={!playing}
            >
              Pause
            </button>
            <button
              className="compare-button compare-button--quiet"
              type="button"
              onClick={() => {
                setPlaying(false);
                setProgress(0);
                setZoom(1);
                setPanX(0);
                setPanY(0);
                setSmoothing('source');
                setNormalization('source');
                setColorThreshold('');
              }}
            >
              Reset view
            </button>
          </div>
        </div>
        <div className="compare-layer-row">
          <span className="micro-label">Layers</span>
          <label>
            <input
              type="checkbox"
              checked={landmarks}
              onChange={(event) => setLandmarks(event.target.checked)}
            />{' '}
            Landmarks
          </label>
          <label>
            <input
              type="checkbox"
              checked={zones}
              onChange={(event) => setZones(event.target.checked)}
            />{' '}
            Zones
          </label>
          <label>
            <input
              type="checkbox"
              checked={heatmap}
              onChange={(event) => setHeatmap(event.target.checked)}
            />{' '}
            Heatmap
          </label>
          <label>
            <input
              type="checkbox"
              checked={texture}
              onChange={(event) => setTexture(event.target.checked)}
            />{' '}
            Texture / UV
          </label>
          <button
            className="compare-button"
            type="button"
            onClick={() => void loadArtifacts()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Checking…' : 'Check artifact availability'}
          </button>
        </div>
      </div>

      {error ? <p className="compare-error-copy">{error}</p> : null}
      <div
        className={`compare-visual-stage compare-visual-stage--${visualMode}`}
        style={
          {
            '--compare-progress': `${progress}%`,
            '--compare-zoom': zoom,
            '--compare-pan-x': `${panX}px`,
            '--compare-pan-y': `${panY}px`,
          } as CSSProperties
        }
      >
        {visualMode === 'side_by_side' || visualMode === 'mesh_3d' ? (
          <>
            <div className="compare-visual-pane">
              <span className="micro-label">
                A · {visualMode === 'mesh_3d' ? 'mesh' : 'source image'}
              </span>
              <strong>{photoA.trim() || 'No photo A selected'}</strong>
              {visualMode === 'mesh_3d' ? (
                <div className="compare-mesh-state" role="status">
                  <strong>3D mesh artifact</strong>
                  <span>
                    {metadata && (meshA === true || Boolean(meshRefA))
                      ? meshRefA
                        ? 'Mesh reference returned; open the source artifact to inspect it outside this 2D viewer.'
                        : 'full_mesh_available returned; no mesh_ref was returned for this view.'
                      : 'Mesh availability was not returned for this photo.'}
                  </span>
                  {meshRefA ? (
                    <a
                      className="compare-artifact-link"
                      href={meshRefA}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open returned mesh artifact
                    </a>
                  ) : null}
                </div>
              ) : state === 'ready' && photoA.trim() ? (
                <CompareArtifactImage photoId={photoA.trim()} />
              ) : null}
              <span>
                {metadata
                  ? `mesh: ${compareDisplayValue(meshA)} · space: ${coordinateSpace}`
                  : 'Artifact availability not checked'}
              </span>
            </div>
            <div className="compare-visual-divider" aria-hidden="true" />
            <div className="compare-visual-pane">
              <span className="micro-label">
                B · {visualMode === 'mesh_3d' ? 'mesh' : 'source image'}
              </span>
              <strong>{photoB.trim() || 'No photo B selected'}</strong>
              {visualMode === 'mesh_3d' ? (
                <div className="compare-mesh-state" role="status">
                  <strong>3D mesh artifact</strong>
                  <span>
                    {metadata && (meshB === true || Boolean(meshRefB))
                      ? meshRefB
                        ? 'Mesh reference returned; open the source artifact to inspect it outside this 2D viewer.'
                        : 'full_mesh_available returned; no mesh_ref was returned for this view.'
                      : 'Mesh availability was not returned for this photo.'}
                  </span>
                  {meshRefB ? (
                    <a
                      className="compare-artifact-link"
                      href={meshRefB}
                      target="_blank"
                      rel="noreferrer"
                    >
                      Open returned mesh artifact
                    </a>
                  ) : null}
                </div>
              ) : state === 'ready' && photoB.trim() ? (
                <CompareArtifactImage photoId={photoB.trim()} />
              ) : null}
              <span>
                {metadata
                  ? `mesh: ${compareDisplayValue(meshB)} · camera: ${camera}`
                  : 'Artifact availability not checked'}
              </span>
            </div>
          </>
        ) : metadata && state === 'ready' ? (
          <CompareVisualComposite
            visualMode={visualMode}
            photoA={photoA.trim()}
            photoB={photoB.trim()}
            progress={progress}
            zoom={zoom}
            panX={panX}
            panY={panY}
          />
        ) : (
          <div className="compare-visual-empty" role="status">
            <strong>Composite view unavailable</strong>
            <span>
              Check both original artifacts before using overlay, divider or 2D crossfade.
            </span>
          </div>
        )}
        <div className="compare-visual-center-label">
          {progress}% A → B · {coordinateSpace} · camera: {camera} · smoothing: {smoothing} ·
          normalization: {normalization}
        </div>
      </div>
      <div className="compare-layer-status-grid" aria-label="Visual layer availability">
        <CompareLayerStatus
          label="Landmarks"
          enabled={landmarks}
          value={landmarkA ?? landmarkB}
          explanation="Only returned LDM references can be overlaid; no points are generated here."
        />
        <CompareLayerStatus
          label="Zones"
          enabled={zones}
          value={zoneA ?? zoneB}
          explanation="Zone overlays require a returned zones_overlay or zone metric artifact."
        />
        <CompareLayerStatus
          label="Heatmap"
          enabled={heatmap}
          value={heatmapA ?? heatmapB}
          explanation="Heatmap colors require a returned heatmap reference; colors are not computed in the client."
        />
        <CompareLayerStatus
          label="Texture / UV"
          enabled={texture}
          value={textureA ?? textureB}
          explanation="Texture eligibility and UV availability remain separate from original images."
        />
      </div>
      <CompareArtifactReferencePanel
        metadata={metadata}
        photoA={photoA.trim()}
        photoB={photoB.trim()}
      />
      <div className="compare-cross-links" aria-label="Visual comparison transitions">
        <span className="micro-label">Open related context</span>
        <button
          className="compare-text-button"
          type="button"
          onClick={() => navigateTo('compare', { photo_a: photoA.trim(), photo_b: photoB.trim() })}
          disabled={!photoA.trim() || !photoB.trim()}
        >
          Pair metrics
        </button>
        <button
          className="compare-text-button"
          type="button"
          onClick={() => navigateTo('photo-detail', { photo_id: photoA.trim() })}
          disabled={!photoA.trim()}
        >
          Photo A detail
        </button>
        <button
          className="compare-text-button"
          type="button"
          onClick={() => navigateTo('photo-detail', { photo_id: photoB.trim() })}
          disabled={!photoB.trim()}
        >
          Photo B detail
        </button>
      </div>
      <div className="compare-visual-legend">
        <span>
          <i className="compare-legend-swatch compare-legend-swatch--a" /> A is source context
        </span>
        <span>
          <i className="compare-legend-swatch compare-legend-swatch--b" /> B is source context
        </span>
        <span>
          <i className="compare-legend-swatch compare-legend-swatch--limited" /> missing or fallback
          is explicit
        </span>
      </div>
      <div className="compare-verdict-note">
        <strong>Visual interpretation boundary</strong>
        <span>
          A reconstructed mesh is not an original image. A color layer is not an identity score.
          Visual agreement does not replace statistical context.
        </span>
      </div>
      <CompareSourceContext
        state={state}
        error={error}
        onRetry={() => void loadArtifacts()}
        sourceRefs={comparePage.blocks[1].sourceRefs}
      />
    </section>
  );
}

function readObjectList(value: unknown): readonly string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (typeof entry === 'string' || typeof entry === 'number') return [String(entry)];
    if (typeof entry === 'object' && entry !== null) {
      const candidate = entry as { object_id?: unknown; id?: unknown; zone_id?: unknown };
      const label = candidate.object_id ?? candidate.id ?? candidate.zone_id;
      return label === undefined ? [] : [String(label)];
    }
    return [];
  });
}

function ZonesEvidenceBlock() {
  const [photoA, setPhotoA] = useState(() => hashParam('photo_a'));
  const [photoB, setPhotoB] = useState(() => hashParam('photo_b'));
  const [state, setState] = useState<CompareState>('idle');
  const [record, setRecord] = useState<PairMetricsRecord>();
  const [zoneRows, setZoneRows] = useState<readonly PairMetricsRecord[]>([]);
  const [error, setError] = useState<string>();

  const loadEvidence = async () => {
    const first = photoA.trim();
    const second = photoB.trim();
    if (!first || !second) {
      setState('error');
      setError('Enter both photo IDs before loading zone evidence.');
      return;
    }

    setState('loading');
    setRecord(undefined);
    setZoneRows([]);
    setError(undefined);
    try {
      const [metricsResult, zoneSummaryResult] = await Promise.allSettled([
        requestJson<PairRequestResponse>(
          `/api/v1/pairs/${encodeURIComponent(first)}/${encodeURIComponent(second)}/metrics`,
        ),
        requestUiArtifactText('zone_summary.csv'),
      ]);
      const returnedRecord =
        metricsResult.status === 'fulfilled' ? flattenPairMetrics(metricsResult.value) : {};
      const zoneSummaryRows =
        zoneSummaryResult.status === 'fulfilled' ? parseCsvRecords(zoneSummaryResult.value) : [];
      const returnedPairId =
        typeof returnedRecord.pair_id === 'string' ? returnedRecord.pair_id : undefined;
      const returnedZones = zoneSummaryRows.filter((row) => {
        const rowPairId = row.pair_id?.trim();
        const matchesPairId = Boolean(returnedPairId && rowPairId === returnedPairId);
        const matchesPhotos = row.photo_a?.trim() === first && row.photo_b?.trim() === second;
        return matchesPairId || matchesPhotos;
      });
      const hasPair = hasCompareValues(returnedRecord);
      setRecord(returnedRecord);
      setZoneRows(returnedZones);
      setState(hasPair || returnedZones.length ? (hasPair ? 'ready' : 'partial') : 'empty');

      const sourceErrors = [
        metricsResult.status === 'rejected' ? compareErrorMessage(metricsResult.reason) : undefined,
        zoneSummaryResult.status === 'rejected'
          ? `zone_summary.csv: ${compareErrorMessage(zoneSummaryResult.reason)}`
          : undefined,
      ].filter((value): value is string => Boolean(value));
      setError(sourceErrors.length ? sourceErrors.join(' · ') : undefined);
    } catch (requestError) {
      setRecord(undefined);
      setZoneRows([]);
      setState('error');
      setError(compareErrorMessage(requestError));
    }
  };

  const zones = zoneRows;
  const selectedZoneSummary = zones[0];
  const supporting = readObjectList(record?.supporting_objects);
  const weakening = readObjectList(record?.weakening_objects);

  return (
    <section
      className="detail-block detail-block--compare"
      aria-labelledby="compare-evidence-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / compare.zones-evidence</span>
          <h3 id="compare-evidence-title">Zones, evidence and next actions</h3>
          <p>
            Local evidence, corroboration and limitations stay attached to the pair that produced
            them.
          </p>
        </div>
        <CompareStatusPill
          value={record?.evidence_state ?? state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="compare-evidence-controls">
        <div className="compare-fields">
          <CompareTextField
            label="Photo A"
            value={photoA}
            onChange={setPhotoA}
            placeholder="calculated photo_id"
          />
          <CompareTextField
            label="Photo B"
            value={photoB}
            onChange={setPhotoB}
            placeholder="calculated photo_id"
          />
        </div>
        <div className="compare-control-footer">
          <span>
            Pair metrics are requested for this pair; zone_summary.csv supplies only the returned
            pair-level zone aggregate.
          </span>
          <button
            className="compare-button"
            type="button"
            onClick={() => void loadEvidence()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load zone evidence'}
          </button>
        </div>
      </div>
      {error ? <p className="compare-error-copy">{error}</p> : null}
      <div className="compare-evidence-grid">
        <div className="compare-zone-surface">
          <div className="compare-subsection-heading">
            <div>
              <span className="micro-label">Zone evidence</span>
              <strong>{zones.length ? 'Returned zones' : 'No zone metrics returned'}</strong>
            </div>
            <CompareStatusPill value={record?.primary_zone_status ?? selectedZoneSummary?.status} />
          </div>
          {zones.length ? (
            <ul className="compare-zone-list">
              {zones.map((zone, index) => {
                const zoneRecord =
                  typeof zone === 'object' && zone !== null ? (zone as PairMetricsRecord) : {};
                const key = String(
                  zoneRecord.pair_id ?? zoneRecord.zone_id ?? zoneRecord.id ?? index,
                );
                return (
                  <li key={key}>
                    <span>{key}</span>
                    <strong>
                      {compareDisplayValue(zoneRecord.zone_count)} zones · avg RMSE:{' '}
                      {compareDisplayValue(zoneRecord.avg_rmse)}
                    </strong>
                    <span>
                      min RMSE: {compareDisplayValue(zoneRecord.min_rmse)} · max RMSE:{' '}
                      {compareDisplayValue(zoneRecord.max_rmse)} · primary robust-z:{' '}
                      {compareDisplayValue(zoneRecord.primary_robust_z)}
                    </span>
                    <CompareStatusPill value={zoneRecord.status ?? zoneRecord.measurement_state} />
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="compare-no-data compare-no-data--compact" role="status">
              <span className="compare-empty-mark" aria-hidden="true" />
              <span>Empty is not zero. The source has not returned a zone list for this pair.</span>
            </div>
          )}
        </div>
        <div className="compare-evidence-column">
          <div className="compare-evidence-list">
            <div className="compare-subsection-heading">
              <span className="micro-label">Supporting objects</span>
              <strong>{supporting.length ? 'Returned support' : 'Unavailable'}</strong>
            </div>
            {supporting.length ? (
              <ul>
                {supporting.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>No supporting objects returned.</p>
            )}
          </div>
          <div className="compare-evidence-list compare-evidence-list--weakening">
            <div className="compare-subsection-heading">
              <span className="micro-label">Weakening objects</span>
              <strong>{weakening.length ? 'Returned limitations' : 'Unavailable'}</strong>
            </div>
            {weakening.length ? (
              <ul>
                {weakening.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            ) : (
              <p>No weakening objects returned.</p>
            )}
          </div>
        </div>
      </div>
      <div className="compare-evidence-footer">
        <div>
          <span className="micro-label">Corroboration</span>
          <CompareStatusPill value={record?.corroboration_status} />
        </div>
        <div>
          <span className="micro-label">Public safety</span>
          <CompareStatusPill value={record?.public_safety_status} />
        </div>
        <div>
          <span className="micro-label">Unresolved</span>
          <strong>{compareDisplayValue(record?.unresolved_questions)}</strong>
        </div>
        <div>
          <span className="micro-label">FDR / q-value</span>
          <strong>
            {compareDisplayValue(record?.fdr)} /{' '}
            {compareDisplayValue(record?.q_value ?? record?.mt_q_value)}
          </strong>
        </div>
        <div>
          <span className="micro-label">Primary zone RMSE</span>
          <strong>
            {compareDisplayValue(record?.primary_zone_rmse ?? selectedZoneSummary?.avg_rmse)}
          </strong>
        </div>
        <div>
          <span className="micro-label">Quality / visibility / calibration</span>
          <strong>
            {compareDisplayValue(record?.quality_state ?? record?.quality)} ·{' '}
            {compareDisplayValue(record?.visibility_state ?? record?.visibility)} ·{' '}
            {compareDisplayValue(record?.calibration_state ?? record?.calibration)}
          </strong>
        </div>
        <div>
          <span className="micro-label">Source refs</span>
          <strong>{compareDisplayValue(record?.source_refs ?? record?.source_ref)}</strong>
        </div>
      </div>
      <div className="compare-cross-links" aria-label="Zone evidence transitions">
        <span className="micro-label">Open related context</span>
        <button
          className="compare-text-button"
          type="button"
          onClick={() => navigateTo('compare', { photo_a: photoA.trim(), photo_b: photoB.trim() })}
          disabled={!photoA.trim() || !photoB.trim()}
        >
          Pair metrics
        </button>
        <button
          className="compare-text-button"
          type="button"
          onClick={() => navigateTo('research', { photo_a: photoA.trim(), photo_b: photoB.trim() })}
          disabled={!photoA.trim() || !photoB.trim()}
        >
          Research context
        </button>
        <button
          className="compare-text-button"
          type="button"
          onClick={() => navigateTo('timeline')}
        >
          Timeline
        </button>
      </div>
      <div className="compare-verdict-note">
        <strong>Evidence boundary</strong>
        <span>
          Supporting and weakening objects are displayed together. A zone highlight never becomes a
          verdict by itself.
        </span>
      </div>
      <CompareSourceContext
        state={state}
        error={error}
        onRetry={() => void loadEvidence()}
        sourceRefs={comparePage.blocks[2].sourceRefs}
      />
    </section>
  );
}

export function ComparePage() {
  const renderBlock = (block: BlockDefinition) => {
    switch (block.id) {
      case 'compare.pair-detail':
        return <PairDetailBlock />;
      case 'compare.morphing':
        return <VisualArtifactBlock />;
      case 'compare.zones-evidence':
        return <ZonesEvidenceBlock />;
      default:
        return null;
    }
  };

  return <PageBlueprint definition={comparePage} renderBlock={renderBlock} />;
}
