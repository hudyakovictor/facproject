import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';

import { ApiRequestError, isAbortError, postJson, requestJson } from '@/shared/api';
import { PageBlueprint } from '@/shared/PageBlueprint';
import { requestUiArtifactJson, uiArtifactPayload } from '@/shared/uiArtifacts';
import { hashParam, navigateTo } from '@/shared/navigation';
import type { BlockDefinition, PageDefinition } from '@/shared/contracts';

/**
 * PAGE: Timeline.
 * Blocks are semantic ownership boundaries. Their internal controls and views stay together;
 * the page owner is free to choose the eventual composition.
 */
export const timelinePage = {
  id: 'timeline',
  title: 'Timeline',
  group: 'analytics',
  purpose:
    'Хронологическая рабочая область архива с кадрами, парами, ракурсами, событиями, метриками и ограничениями.',
  primaryQuestion: 'Какие объекты существуют во времени и в каких условиях их можно анализировать?',
  blocks: [
    /**
     * BLOCK: Archive explorer.
     * OWNED ELEMENTS: date, order and pose controls, chronology canvas with photos, pairs and events, metric and quality context, pose-bin lanes and archive minimap, photo/pair selection and transitions.
     * CONTRACT SURFACE: elements: start-date selection, pose-bin selection, diagnostic layer toggles, pair detail and morphing transitions, casework and report transitions; actions: select_start_date, select_pose_bin, toggle_layer, open_pair_detail, open_morphing, open_casework, open_report, add_note; states: measured, not_computed, skipped, not_applicable, stale.
     * stage1_ready, stage2_ready, stage3_ready, storage_root, stage1_root, stage2_root, stage3_root, photos.
     * DATA KEYS:
     * success_count, count, offset, limit, id, bucket, stage, relative_path, file_name, artifact_type, availability, created_at.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * run_id, date_from, date_to, pose_bin, metric_family, measurement_state, quality_state,
     * visibility_state, coordinate_space, selected_layer, result_count, photo_id, date, same_date_sequence,
     * chronology_index_global, pair_id, pair_type, event_id, source_ref, limitation_refs, metric,
     * value, unit, raw_value, calibrated_value, robust_z, fdr, q_value,
     * quality, visibility, calibration, object_id, limitation, schema_version, status,
     * photo_count, error_count, elapsed_seconds, device, backbone, uv_size, created_at_utc,
     * input_dir, output_dir, photo_list, pitch, yaw, roll, source_filename,
     * date_provenance_status, perceptual_dhash, near_duplicate_of, geometry_status, segmentation_status, uv_status, combined_visible_fraction,
     * skin_mask_coverage, uv_observed_coverage, chronology_index_in_pose.
     */
    {
      id: 'timeline.archive-explorer',
      title: 'Archive explorer',
      purpose:
        'Самостоятельный исследовательский блок для движения по архиву: управление выборкой, хронология, контекст ракурсов, метрики и миникарта находятся в одном месте.',
      elements: [
        'start-date selection',
        'pose-bin selection',
        'diagnostic layer toggles',
        'pair detail and morphing transitions',
        'casework and report transitions',
        'date, order and pose controls',
        'chronology canvas with photos, pairs and events',
        'metric and quality context',
        'pose-bin lanes and archive minimap',
        'photo/pair selection and transitions',
      ],
      keys: [
        'stage1_ready',
        'stage2_ready',
        'stage3_ready',
        'storage_root',
        'stage1_root',
        'stage2_root',
        'stage3_root',
        'photos',
        'success_count',
        'count',
        'offset',
        'limit',
        'id',
        'bucket',
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
        'calibration_state',
        'schema',
        'source_mode',
        'not_a_verdict',
        'run_id',
        'date_from',
        'date_to',
        'pose_bin',
        'metric_family',
        'measurement_state',
        'quality_state',
        'visibility_state',
        'coordinate_space',
        'selected_layer',
        'result_count',
        'photo_id',
        'date',
        'same_date_sequence',
        'chronology_index_global',
        'pair_id',
        'pair_type',
        'event_id',
        'source_ref',
        'limitation_refs',
        'metric',
        'value',
        'unit',
        'raw_value',
        'calibrated_value',
        'robust_z',
        'fdr',
        'q_value',
        'quality',
        'visibility',
        'calibration',
        'object_id',
        'limitation',
        'schema_version',
        'status',
        'photo_count',
        'error_count',
        'elapsed_seconds',
        'device',
        'backbone',
        'uv_size',
        'created_at_utc',
        'input_dir',
        'output_dir',
        'photo_list',
        'pitch',
        'yaw',
        'roll',
        'source_filename',
        'date_provenance_status',
        'perceptual_dhash',
        'near_duplicate_of',
        'geometry_status',
        'segmentation_status',
        'uv_status',
        'combined_visible_fraction',
        'skin_mask_coverage',
        'uv_observed_coverage',
        'chronology_index_in_pose',
      ],
      sourceRefs: [
        'stage1/main_timeline.csv → api/v1/photos',
        'stage1/stage1_manifest.json → api/v1/health',
        'api/v1/health',
        'api/v1/photos?offset={offset}&limit={limit}&pose_bin={pose_bin}',
        'api/v1/photos/{photo_id}',
      ],
      actions: [
        'select_start_date',
        'select_pose_bin',
        'toggle_layer',
        'open_pair_detail',
        'open_morphing',
        'open_casework',
        'open_report',
        'add_note',
        'apply_filter',
        'clear_filter',
        'save_view_state',
        'select_photo',
        'select_pair',
        'open_photo_detail',
        'open_compare',
        'select_metric',
        'open_metric_definition',
        'open_source',
        'sort_by_date',
        'sort_by_chronology',
        'sort_by_pitch',
        'sort_by_yaw',
        'sort_by_roll',
      ],
      requiredStates: [
        'measured',
        'not_computed',
        'skipped',
        'not_applicable',
        'stale',
        'loading',
        'empty',
        'limited',
        'unavailable',
        'error',
        'long_content',
      ],
    },
    /**
     * BLOCK: Timeline Map.
     * OWNED ELEMENTS: year × pose matrix, frame and pair coverage, candidate and corroboration status, aggregate metric legend, year/pose selection and return to Timeline.
     * CONTRACT SURFACE: elements: sparse-coverage indication, metric status and threshold context, corroboration count; actions: open_timeline, apply_filter; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * fdr_status, sparse_coverage, corroboration_count, aggregate_metric_status, metric_value, metric_status.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * year, pose_bin, frame_count, pair_count, fdr_candidate_count, corroboration_status, coverage_state,
     * aggregate_metric, metric_unit, source_ref, limitation_refs.
     */
    {
      id: 'timeline.map',
      title: 'Timeline Map',
      purpose:
        'Стратегическая карта годов и ракурсов с плотностью архива, кандидатами, корроборацией и видимыми sparse-ячейками.',
      elements: [
        'sparse-coverage indication',
        'metric status and threshold context',
        'corroboration count',
        'year × pose matrix',
        'frame and pair coverage',
        'candidate and corroboration status',
        'aggregate metric legend',
        'year/pose selection and return to Timeline',
      ],
      keys: [
        'fdr_status',
        'sparse_coverage',
        'corroboration_count',
        'aggregate_metric_status',
        'metric_value',
        'metric_status',
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
        'year',
        'pose_bin',
        'frame_count',
        'pair_count',
        'fdr_candidate_count',
        'corroboration_status',
        'coverage_state',
        'aggregate_metric',
        'metric_unit',
        'source_ref',
        'limitation_refs',
      ],
      sourceRefs: [
        'ui_artifacts/timeline_matrix.json ← stage1/main_timeline.csv',
        'ui_artifacts/report_meta.json',
        'api/v1/ui_artifacts/timeline_matrix.json',
        'api/v1/ui_artifacts/report_meta.json',
      ],
      actions: [
        'open_timeline',
        'apply_filter',
        'select_year',
        'select_pose_bin',
        'open_timeline_scope',
        'open_corroboration',
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
     * BLOCK: Selection context and session journal.
     * OWNED ELEMENTS: selected photo/pair readout, quality, visibility and calibration status, source and limitation context, researcher session notes, links to detail, compare, research and publication.
     * CONTRACT SURFACE: elements: start-date and pose context, signal explanation status, thumbnail add/remove context, publication transition; actions: delete_note, add_thumbnail, remove_thumbnail, set_explanation_mode, mark_signal, preserve_context, open_publication; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * explanation_state, signal_status, context_state, date_provenance_status.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * selected_object_id, photo_id, pair_id, date_a, date_b, pose_bin, metric_refs,
     * status, quality, visibility, calibration, source_refs, limitation_refs, next_routes,
     * note_id, object_id, note_text, author_id, created_at, updated_at, publication_block_id,
     * note_status.
     */
    {
      id: 'timeline.selection-journal',
      title: 'Selection context and session journal',
      purpose:
        'Самостоятельный контекст выбранного кадра или пары с заметками, статусами, provenance и переходами к связанным рабочим областям.',
      elements: [
        'start-date and pose context',
        'signal explanation status',
        'thumbnail add/remove context',
        'publication transition',
        'selected photo/pair readout',
        'quality, visibility and calibration status',
        'source and limitation context',
        'researcher session notes',
        'links to detail, compare, research and publication',
      ],
      keys: [
        'explanation_state',
        'signal_status',
        'context_state',
        'date_provenance_status',
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
        'selected_object_id',
        'photo_id',
        'pair_id',
        'date_a',
        'date_b',
        'pose_bin',
        'metric_refs',
        'status',
        'quality',
        'visibility',
        'calibration',
        'source_refs',
        'limitation_refs',
        'next_routes',
        'note_id',
        'object_id',
        'note_text',
        'author_id',
        'created_at',
        'updated_at',
        'publication_block_id',
        'note_status',
      ],
      sourceRefs: [
        'stage1/main_timeline.csv → api/v1/photos',
        'api/v1/reviews',
        'ui_artifacts/report_meta.json',
        'ui_artifacts/report_sections/narrative.json',
      ],
      actions: [
        'delete_note',
        'add_thumbnail',
        'remove_thumbnail',
        'set_explanation_mode',
        'mark_signal',
        'preserve_context',
        'open_publication',
        'open_photo_detail',
        'open_pair_detail',
        'open_compare',
        'open_zone_atlas',
        'add_note',
        'create_note',
        'edit_note',
        'link_publication_block',
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

type TimelinePoseBin =
  | 'frontal'
  | 'left_light'
  | 'left_mid'
  | 'left_deep'
  | 'left_profile'
  | 'right_light'
  | 'right_mid'
  | 'right_deep'
  | 'right_profile';

type TimelineSort = 'date' | 'chronology' | 'pitch' | 'yaw' | 'roll';
type TimelineLayer = 'geometry' | 'texture' | 'context';
type AsyncState = 'idle' | 'loading' | 'ready' | 'empty' | 'error';

const POSE_BINS: readonly TimelinePoseBin[] = [
  'frontal',
  'left_light',
  'left_mid',
  'left_deep',
  'left_profile',
  'right_light',
  'right_mid',
  'right_deep',
  'right_profile',
];

const LAYERS: readonly { id: TimelineLayer; label: string; description: string }[] = [
  { id: 'geometry', label: 'Geometry', description: 'alignment, residual and landmark state' },
  { id: 'texture', label: 'Texture', description: 'skin, UV and surface diagnostics' },
  { id: 'context', label: 'Context', description: 'pairs, events and provenance' },
];

const DEFAULT_PHOTO_LIMIT = 200;

interface TimelinePhotoRecord {
  id?: string;
  photo_id?: string;
  date?: string | null;
  bucket?: string | null;
  pose_bin?: string | null;
  metric_family?: string | null;
  pitch?: number | null;
  yaw?: number | null;
  roll?: number | null;
  source_filename?: string | null;
  date_provenance_status?: string | null;
  perceptual_dhash?: string | null;
  near_duplicate_of?: string | null;
  geometry_status?: string | null;
  segmentation_status?: string | null;
  uv_status?: string | null;
  combined_visible_fraction?: number | null;
  skin_mask_coverage?: number | null;
  uv_observed_coverage?: number | null;
  chronology_index_global?: number | null;
  chronology_index_in_pose?: number | null;
  same_date_sequence?: number | null;
  measurement_state?: string | null;
  quality_state?: string | null;
  visibility_state?: string | null;
  calibration_state?: string | null;
  pair_id?: string | null;
  event_id?: string | null;
}

interface TimelinePhotosResponse {
  schema?: string;
  source_mode?: string;
  not_a_verdict?: boolean;
  count?: number;
  offset?: number;
  limit?: number;
  photos?: TimelinePhotoRecord[];
  manifest?: HealthResponse;
}

interface HealthResponse {
  [key: string]: unknown;
  schema?: string;
  source_mode?: string;
  not_a_verdict?: boolean;
  status?: string;
  stage1_ready?: boolean;
  stage2_ready?: boolean;
  stage3_ready?: boolean;
  photo_count?: number;
  pair_count?: number;
}

interface RunSummaryResponse {
  [key: string]: unknown;
  schema?: string;
  source_mode?: string;
  not_a_verdict?: boolean;
  status?: string;
  stage2_status?: string;
  run_id?: string;
  pair_count?: number;
  pose_bins?: Record<string, number>;
  fdr_candidate_count?: number;
}

interface TimelineCoverageRecord {
  [key: string]: unknown;
  year?: string | number | null;
  pose_bin?: string | null;
  frame_count?: number | null;
  pair_count?: number | null;
  fdr_candidate_count?: number | null;
  corroboration_status?: string | null;
  coverage_state?: string | null;
  aggregate_metric?: number | string | null;
  metric_unit?: string | null;
  metric_status?: string | null;
}

function timelineMatrixRecords(payload: unknown): readonly TimelineCoverageRecord[] {
  const unwrapped = payload;
  if (typeof unwrapped !== 'object' || unwrapped === null || Array.isArray(unwrapped)) return [];
  const root = unwrapped as Record<string, unknown>;
  const matrixCandidate =
    root.timeline_matrix && typeof root.timeline_matrix === 'object'
      ? root.timeline_matrix
      : root.matrix && typeof root.matrix === 'object'
        ? root.matrix
        : root;
  if (
    typeof matrixCandidate !== 'object' ||
    matrixCandidate === null ||
    Array.isArray(matrixCandidate)
  ) {
    return [];
  }

  const records: TimelineCoverageRecord[] = [];
  for (const [year, poseMap] of Object.entries(matrixCandidate as Record<string, unknown>)) {
    if (typeof poseMap !== 'object' || poseMap === null || Array.isArray(poseMap)) continue;
    for (const [poseBin, returnedCell] of Object.entries(poseMap as Record<string, unknown>)) {
      if (typeof returnedCell === 'number' && Number.isFinite(returnedCell)) {
        records.push({ year, pose_bin: poseBin, frame_count: returnedCell });
        continue;
      }
      if (
        typeof returnedCell !== 'object' ||
        returnedCell === null ||
        Array.isArray(returnedCell)
      ) {
        continue;
      }
      const cell = returnedCell as TimelineCoverageRecord;
      records.push({
        ...cell,
        year: cell.year ?? year,
        pose_bin: cell.pose_bin ?? poseBin,
      });
    }
  }
  return records;
}

interface TimelineFilters {
  dateFrom: string;
  dateTo: string;
  poseBin: TimelinePoseBin | '';
  metricFamily: '' | 'geometry' | 'texture' | 'point_motion' | 'descriptor';
  sort: TimelineSort;
}

const EMPTY_FILTERS: TimelineFilters = {
  dateFrom: '',
  dateTo: '',
  poseBin: '',
  metricFamily: '',
  sort: 'date',
};

function photoId(photo: TimelinePhotoRecord): string {
  return photo.photo_id ?? photo.id ?? '';
}

function timelinePairRoute(
  row: TimelinePhotoRecord,
): { photo_a?: string; photo_b?: string } | undefined {
  const pairId = row.pair_id;
  const currentId = photoId(row);
  if (typeof pairId !== 'string' || !currentId) return undefined;
  const prefix = `${currentId}__`;
  const suffix = `__${currentId}`;
  if (pairId.startsWith(prefix))
    return { photo_a: currentId, photo_b: pairId.slice(prefix.length) };
  if (pairId.endsWith(suffix))
    return { photo_a: pairId.slice(0, -suffix.length), photo_b: currentId };
  return undefined;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined || value === '') {
    return 'Unavailable';
  }

  if (typeof value === 'boolean') {
    return value ? 'Yes' : 'No';
  }

  return String(value);
}

function displayNumber(value: number | null | undefined, suffix = ''): string {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return 'Unavailable';
  }

  return `${value}${suffix}`;
}

function stateTone(value: string | null | undefined): 'positive' | 'warning' | 'muted' {
  if (!value) return 'muted';
  if (['valid', 'pass', 'measured', 'complete', 'accepted'].includes(value)) return 'positive';
  if (
    [
      'partial',
      'limited',
      'not_computed',
      'skipped',
      'missing',
      'unavailable',
      'fallback',
      'stale',
      'error',
    ].includes(value)
  )
    return 'warning';
  return 'muted';
}

function sortPhotos(rows: TimelinePhotoRecord[], sort: TimelineSort): TimelinePhotoRecord[] {
  const sorted = [...rows];
  const valueFor = (row: TimelinePhotoRecord): string | number => {
    if (sort === 'date') return row.date ?? '';
    if (sort === 'chronology') return row.chronology_index_global ?? Number.POSITIVE_INFINITY;
    return row[sort] ?? Number.POSITIVE_INFINITY;
  };

  return sorted.sort((a, b) => {
    const first = valueFor(a);
    const second = valueFor(b);
    if (first < second) return -1;
    if (first > second) return 1;
    return photoId(a).localeCompare(photoId(b));
  });
}

function filterPhotos(
  rows: TimelinePhotoRecord[],
  filters: TimelineFilters,
): TimelinePhotoRecord[] {
  return sortPhotos(
    rows.filter((row) => {
      const rowDate = row.date ?? '';
      const matchesFrom = !filters.dateFrom || rowDate >= filters.dateFrom;
      const matchesTo = !filters.dateTo || rowDate <= filters.dateTo;
      const matchesPose = !filters.poseBin || (row.pose_bin ?? row.bucket) === filters.poseBin;
      const matchesMetric = !filters.metricFamily || row.metric_family === filters.metricFamily;
      return matchesFrom && matchesTo && matchesPose && matchesMetric;
    }),
    filters.sort,
  );
}

function errorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.detail;
  return 'Источник данных недоступен.';
}

function StatusPill({ value, label }: { value: string | null | undefined; label?: string }) {
  return (
    <span className={`timeline-status timeline-status--${stateTone(value)}`}>
      <span className="timeline-status-dot" aria-hidden="true" />
      {label ?? displayValue(value)}
    </span>
  );
}

function SourceContext({
  state,
  error,
  onRetry,
  sourceRefs,
}: {
  state: AsyncState;
  error?: string;
  onRetry?: () => void;
  sourceRefs: readonly string[];
}) {
  const stateLabel = {
    idle: 'Not requested',
    loading: 'Loading source',
    ready: 'Source connected',
    empty: 'Source returned no records',
    error: 'Source unavailable',
  }[state];

  return (
    <aside className="timeline-source-context" aria-label="Контекст источника">
      <div className="timeline-source-heading">
        <div>
          <span className="micro-label">Source context</span>
          <strong>{stateLabel}</strong>
        </div>
        <StatusPill value={state === 'ready' ? 'valid' : state === 'loading' ? 'limited' : state} />
      </div>
      <p>
        <code>source_mode: research</code>
        <code>not_a_verdict: true</code>
      </p>
      {error ? <p className="timeline-error-copy">{error}</p> : null}
      {state === 'error' && onRetry ? (
        <button className="timeline-button timeline-button--quiet" type="button" onClick={onRetry}>
          Retry source request
        </button>
      ) : null}
      <details className="timeline-source-details">
        <summary>Expected files and endpoints</summary>
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

function FilterSelect({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  children: ReactNode;
}) {
  return (
    <label className="timeline-field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  );
}

function TimelinePlot({
  rows,
  selectedPhotoId,
  onSelect,
  layers,
}: {
  rows: readonly TimelinePhotoRecord[];
  selectedPhotoId: string | null;
  onSelect: (id: string) => void;
  layers: Record<TimelineLayer, boolean>;
}) {
  const activeLayers = LAYERS.filter((layer) => layers[layer.id]);
  const primaryLayer = activeLayers[0]?.id ?? 'none';
  const plottedRows = rows.slice(0, 96);
  const rowWidth = plottedRows.length > 1 ? 100 / (plottedRows.length - 1) : 100;

  return (
    <div className="timeline-plot" aria-label="Хронологическое полотно">
      <div className="timeline-plot-header">
        <div>
          <span className="micro-label">Chronology canvas</span>
          <strong>
            {rows.length ? 'Calculated observations' : 'Awaiting calculated observations'}
          </strong>
        </div>
        <span className="timeline-plot-note">
          {activeLayers.length
            ? `${activeLayers.map((layer) => layer.label).join(' · ')} · returned statuses only`
            : 'No diagnostic layer selected'}
        </span>
      </div>
      {plottedRows.length ? (
        <div className="timeline-plot-canvas">
          <div className="timeline-axis-line" aria-hidden="true" />
          <div className="timeline-lane-labels" aria-hidden="true">
            <span>signals</span>
            <span>frames</span>
            <span>events</span>
          </div>
          <svg className="timeline-svg" viewBox="0 0 100 100" role="img">
            <title>Loaded chronology observations</title>
            <line x1="0" y1="74" x2="100" y2="74" className="timeline-svg-line" />
            {plottedRows.map((row, index) => {
              const x = index * rowWidth;
              const id = photoId(row);
              const selected = id === selectedPhotoId;
              const y = row.event_id ? 20 : row.pair_id ? 36 : 52;
              return (
                <g key={id || `row-${index}`}>
                  <line x1={x} y1="20" x2={x} y2="82" className="timeline-svg-guide" />
                  <circle
                    cx={x}
                    cy={y}
                    r={selected ? 3.4 : 2.2}
                    className={`timeline-svg-point timeline-svg-point--${primaryLayer}${selected ? ' is-selected' : ''}`}
                    tabIndex={0}
                    role="button"
                    aria-label={`Select photo ${displayValue(id)}; layers: ${activeLayers.map((layer) => layer.label).join(', ') || 'none'}`}
                    onClick={() => id && onSelect(id)}
                    onKeyDown={(event) => {
                      if ((event.key === 'Enter' || event.key === ' ') && id) {
                        event.preventDefault();
                        onSelect(id);
                      }
                    }}
                  />
                </g>
              );
            })}
          </svg>
          <div className="timeline-plot-footer">
            <span>{displayValue(plottedRows[0]?.date)}</span>
            <span>{plottedRows.length > 96 ? 'First 96 loaded rows' : 'Loaded rows only'}</span>
            <span>{displayValue(plottedRows.at(-1)?.date)}</span>
          </div>
        </div>
      ) : (
        <div className="timeline-no-data" role="status">
          <span className="timeline-empty-mark" aria-hidden="true" />
          <div>
            <strong>No observations to plot</strong>
            <span>
              Connect the calculated Stage 1/API source. The canvas will not synthesize points.
            </span>
          </div>
        </div>
      )}
    </div>
  );
}

function TimelineRows({
  rows,
  selectedPhotoId,
  onSelect,
  layers,
}: {
  rows: readonly TimelinePhotoRecord[];
  selectedPhotoId: string | null;
  onSelect: (id: string) => void;
  layers: Record<TimelineLayer, boolean>;
}) {
  const activeLayers = LAYERS.filter((layer) => layers[layer.id]);
  if (!rows.length) {
    return (
      <div className="timeline-table-empty" role="status">
        <strong>No calculated photo records</strong>
        <span>Empty is different from zero: the API returned no rows for this scope.</span>
      </div>
    );
  }

  return (
    <div className="timeline-table-wrap">
      <table className="timeline-table">
        <caption>
          Calculated archive records. Values are shown only when returned by the source. Active
          layers:{' '}
          {activeLayers.length ? activeLayers.map((layer) => layer.label).join(', ') : 'none'}.
        </caption>
        <thead>
          <tr>
            <th scope="col">Frame</th>
            {layers.context ? <th scope="col">Pair / event</th> : null}
            {layers.context ? <th scope="col">Date / provenance</th> : null}
            {layers.context ? <th scope="col">Pose</th> : null}
            {layers.geometry ? <th scope="col">Angles</th> : null}
            {layers.geometry ? <th scope="col">Geometry</th> : null}
            {layers.texture ? <th scope="col">Visibility</th> : null}
            {layers.texture ? <th scope="col">UV</th> : null}
            {layers.context ? <th scope="col">Source state</th> : null}
            {!activeLayers.length ? <th scope="col">Diagnostic layer</th> : null}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => {
            const id = photoId(row);
            const selected = id === selectedPhotoId;
            return (
              <tr className={selected ? 'is-selected' : undefined} key={id || `record-${index}`}>
                <td>
                  <button
                    className="timeline-frame-button"
                    type="button"
                    onClick={() => {
                      if (!id) return;
                      onSelect(id);
                      navigateTo('photo-detail', { photo_id: id });
                    }}
                  >
                    <strong>{displayValue(id)}</strong>
                    <span>sequence {displayValue(row.same_date_sequence)}</span>
                  </button>
                </td>
                {layers.context ? (
                  <td>
                    {row.pair_id ? (
                      timelinePairRoute(row)?.photo_a && timelinePairRoute(row)?.photo_b ? (
                        <button
                          className="timeline-text-button"
                          type="button"
                          onClick={() => navigateTo('compare', timelinePairRoute(row))}
                        >
                          {displayValue(row.pair_id)}
                        </button>
                      ) : (
                        <strong>{displayValue(row.pair_id)}</strong>
                      )
                    ) : (
                      <span>Pair unavailable</span>
                    )}
                    <span>event: {displayValue(row.event_id)}</span>
                  </td>
                ) : null}
                {layers.context ? (
                  <td>
                    <strong>{displayValue(row.date)}</strong>
                    <span>{displayValue(row.date_provenance_status)}</span>
                  </td>
                ) : null}
                {layers.context ? (
                  <td>
                    <StatusPill
                      value={row.pose_bin ?? row.bucket}
                      label={displayValue(row.pose_bin ?? row.bucket)}
                    />
                    <span>pose #{displayValue(row.chronology_index_in_pose)}</span>
                    <span>global #{displayValue(row.chronology_index_global)}</span>
                  </td>
                ) : null}
                {layers.geometry ? (
                  <td>
                    <span>pitch {displayNumber(row.pitch, '°')}</span>
                    <span>yaw {displayNumber(row.yaw, '°')}</span>
                    <span>roll {displayNumber(row.roll, '°')}</span>
                  </td>
                ) : null}
                {layers.geometry ? (
                  <td>
                    <StatusPill value={row.geometry_status} />
                    <span>{displayValue(row.quality_state)}</span>
                  </td>
                ) : null}
                {layers.texture ? (
                  <td>
                    <span>{displayNumber(row.combined_visible_fraction)}</span>
                    <span>{displayValue(row.visibility_state)}</span>
                    <span>segmentation {displayValue(row.segmentation_status)}</span>
                    <span>skin mask {displayNumber(row.skin_mask_coverage)}</span>
                  </td>
                ) : null}
                {layers.texture ? (
                  <td>
                    <StatusPill value={row.uv_status} />
                    <span>{displayNumber(row.uv_observed_coverage)}</span>
                  </td>
                ) : null}
                {layers.context ? (
                  <td>
                    <span>{displayValue(row.measurement_state)}</span>
                    <span>{displayValue(row.source_filename)}</span>
                    <span>dHash {displayValue(row.perceptual_dhash)}</span>
                    <span>near duplicate {displayValue(row.near_duplicate_of)}</span>
                  </td>
                ) : null}
                {!activeLayers.length ? <td>No diagnostic layer selected</td> : null}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ArchiveExplorerBlock({
  onSelectPhoto,
  selectedPhotoId,
}: {
  onSelectPhoto: (id: string) => void;
  selectedPhotoId: string | null;
}) {
  const [filters, setFilters] = useState<TimelineFilters>(() => ({
    ...EMPTY_FILTERS,
    dateFrom: hashParam('date_from'),
    dateTo: hashParam('date_to'),
    poseBin: (hashParam('pose_bin') as TimelinePoseBin | '') || '',
  }));
  const [appliedFilters, setAppliedFilters] = useState<TimelineFilters>(() => ({
    ...EMPTY_FILTERS,
    dateFrom: hashParam('date_from'),
    dateTo: hashParam('date_to'),
    poseBin: (hashParam('pose_bin') as TimelinePoseBin | '') || '',
  }));
  const [layers, setLayers] = useState<Record<TimelineLayer, boolean>>({
    geometry: true,
    texture: false,
    context: true,
  });
  const [rows, setRows] = useState<TimelinePhotoRecord[]>([]);
  const [offset, setOffset] = useState(0);
  const [totalCount, setTotalCount] = useState<number>();
  const [state, setState] = useState<AsyncState>('idle');
  const [error, setError] = useState<string>();
  const [health, setHealth] = useState<HealthResponse>();
  const [healthState, setHealthState] = useState<AsyncState>('idle');
  const [healthError, setHealthError] = useState<string>();
  const abortRef = useRef<AbortController | undefined>(undefined);
  const healthAbortRef = useRef<AbortController | undefined>(undefined);

  useEffect(() => {
    return () => {
      abortRef.current?.abort();
      healthAbortRef.current?.abort();
    };
  }, []);

  const visibleRows = useMemo(() => filterPhotos(rows, appliedFilters), [rows, appliedFilters]);
  const hasManifestContext = Boolean(
    health &&
      [
        'schema_version',
        'success_count',
        'error_count',
        'elapsed_seconds',
        'device',
        'backbone',
        'uv_size',
        'created_at_utc',
        'input_dir',
        'output_dir',
      ].some((key) => health[key] !== undefined),
  );

  const loadRows = async (nextFilters: TimelineFilters = filters, nextOffset = 0) => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setState('loading');
    setError(undefined);
    setAppliedFilters(nextFilters);
    setOffset(nextOffset);

    const params = new URLSearchParams({
      offset: String(nextOffset),
      limit: String(DEFAULT_PHOTO_LIMIT),
    });
    if (nextFilters.dateFrom) params.set('date_from', nextFilters.dateFrom);
    if (nextFilters.dateTo) params.set('date_to', nextFilters.dateTo);
    if (nextFilters.poseBin) params.set('pose_bin', nextFilters.poseBin);
    if (nextFilters.metricFamily) params.set('metric_family', nextFilters.metricFamily);

    try {
      const response = await requestJson<TimelinePhotosResponse>(
        `/api/v1/photos?${params.toString()}`,
        { signal: controller.signal },
      );
      const returnedRows = Array.isArray(response.photos) ? response.photos : [];
      setRows(returnedRows);
      setOffset(typeof response.offset === 'number' ? response.offset : nextOffset);
      setTotalCount(typeof response.count === 'number' ? response.count : undefined);
      if (response.manifest && typeof response.manifest === 'object') {
        setHealth(response.manifest);
        setHealthState('ready');
        setHealthError(undefined);
      }
      setState(returnedRows.length ? 'ready' : 'empty');
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setRows([]);
      setOffset(nextOffset);
      setTotalCount(undefined);
      setState('error');
      setError(errorMessage(requestError));
    }
  };

  const loadHealth = async () => {
    healthAbortRef.current?.abort();
    const controller = new AbortController();
    healthAbortRef.current = controller;
    setHealthState('loading');
    setHealth(undefined);
    setHealthError(undefined);

    try {
      const response = await requestJson<HealthResponse>('/api/v1/health', {
        signal: controller.signal,
      });
      setHealth(response);
      setHealthState('ready');
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setHealth(undefined);
      setHealthState('error');
      setHealthError(errorMessage(requestError));
    }
  };

  const clearFilters = () => {
    setFilters(EMPTY_FILTERS);
    setAppliedFilters(EMPTY_FILTERS);
    setRows([]);
    setOffset(0);
    setTotalCount(undefined);
    setState('idle');
    setError(undefined);
  };

  return (
    <section
      className="detail-block detail-block--timeline"
      aria-labelledby="timeline-archive-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / timeline.archive-explorer</span>
          <h3 id="timeline-archive-title">Archive explorer</h3>
          <p>Move through calculated photos and pair context without hiding missing coverage.</p>
        </div>
        <StatusPill
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>

      <div className="timeline-control-bar">
        <div className="timeline-control-heading">
          <span className="micro-label">Selection and scope</span>
          <strong>Controls stay with the chronology they change</strong>
        </div>
        <div className="timeline-fields">
          <label className="timeline-field">
            <span>From date</span>
            <input
              type="date"
              value={filters.dateFrom}
              onChange={(event) =>
                setFilters((current) => ({ ...current, dateFrom: event.target.value }))
              }
            />
          </label>
          <label className="timeline-field">
            <span>To date</span>
            <input
              type="date"
              value={filters.dateTo}
              onChange={(event) =>
                setFilters((current) => ({ ...current, dateTo: event.target.value }))
              }
            />
          </label>
          <FilterSelect
            label="Pose bin"
            value={filters.poseBin}
            onChange={(value) =>
              setFilters((current) => ({ ...current, poseBin: value as TimelinePoseBin | '' }))
            }
          >
            <option value="">All pose bins</option>
            {POSE_BINS.map((pose) => (
              <option key={pose} value={pose}>
                {pose}
              </option>
            ))}
          </FilterSelect>
          <FilterSelect
            label="Metric family"
            value={filters.metricFamily}
            onChange={(value) =>
              setFilters((current) => ({
                ...current,
                metricFamily: value as TimelineFilters['metricFamily'],
              }))
            }
          >
            <option value="">All metric families</option>
            <option value="geometry">Geometry</option>
            <option value="texture">Texture</option>
            <option value="point_motion">Point motion</option>
            <option value="descriptor">Descriptor</option>
          </FilterSelect>
          <FilterSelect
            label="Order"
            value={filters.sort}
            onChange={(value) =>
              setFilters((current) => ({ ...current, sort: value as TimelineSort }))
            }
          >
            <option value="date">Date</option>
            <option value="chronology">Global chronology</option>
            <option value="pitch">Pitch</option>
            <option value="yaw">Yaw</option>
            <option value="roll">Roll</option>
          </FilterSelect>
        </div>
        <div className="timeline-control-actions">
          <button
            className="timeline-button"
            type="button"
            onClick={() => void loadRows()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load calculated data'}
          </button>
          <button
            className="timeline-button timeline-button--quiet"
            type="button"
            onClick={clearFilters}
          >
            Clear scope
          </button>
        </div>
      </div>

      <div className="timeline-layer-row" aria-label="Диагностические слои">
        <span className="micro-label">Diagnostic layers</span>
        {LAYERS.map((layer) => (
          <label className="timeline-layer-toggle" key={layer.id} title={layer.description}>
            <input
              type="checkbox"
              checked={layers[layer.id]}
              onChange={() =>
                setLayers((current) => ({ ...current, [layer.id]: !current[layer.id] }))
              }
            />
            <span>{layer.label}</span>
          </label>
        ))}
        <span className="timeline-layer-note">
          Layer controls change the view context; no values are generated locally.
        </span>
      </div>

      <div className="timeline-summary-row">
        <div className="timeline-summary-card">
          <span className="micro-label">Returned rows</span>
          <strong>
            {state === 'ready' || state === 'empty'
              ? displayValue(visibleRows.length)
              : 'Awaiting source'}
          </strong>
          <span>
            {state === 'ready' ? 'after local date and order scope' : 'No count is inferred'}
          </span>
        </div>
        <div className="timeline-summary-card">
          <span className="micro-label">Selected frame</span>
          <strong>{displayValue(selectedPhotoId)}</strong>
          <span>Selection is independent from pair selection.</span>
        </div>
        <div className="timeline-summary-card timeline-summary-card--action">
          <span className="micro-label">Stage readiness</span>
          <strong>{healthState === 'ready' ? displayValue(health?.status) : 'Not checked'}</strong>
          <button
            className="timeline-text-button"
            type="button"
            onClick={() => void loadHealth()}
            disabled={healthState === 'loading'}
          >
            {healthState === 'loading' ? 'Checking…' : 'Check API health'}
          </button>
          {healthError ? <span className="timeline-error-copy">{healthError}</span> : null}
        </div>
      </div>
      {hasManifestContext ? (
        <div className="timeline-manifest-grid" aria-label="Returned Stage 1 manifest context">
          <div>
            <span className="micro-label">Schema version</span>
            <strong>{displayValue(health?.schema_version)}</strong>
          </div>
          <div>
            <span className="micro-label">Successful photos</span>
            <strong>{displayValue(health?.success_count ?? health?.photo_count)}</strong>
          </div>
          <div>
            <span className="micro-label">Extraction errors</span>
            <strong>{displayValue(health?.error_count)}</strong>
          </div>
          <div>
            <span className="micro-label">Elapsed seconds</span>
            <strong>{displayValue(health?.elapsed_seconds)}</strong>
          </div>
          <div>
            <span className="micro-label">Device / backbone</span>
            <strong>
              {displayValue(health?.device)} / {displayValue(health?.backbone)}
            </strong>
          </div>
          <div>
            <span className="micro-label">UV size</span>
            <strong>{displayValue(health?.uv_size)}</strong>
          </div>
          <div>
            <span className="micro-label">Created UTC</span>
            <strong>{displayValue(health?.created_at_utc)}</strong>
          </div>
          <div>
            <span className="micro-label">Input / output</span>
            <strong>
              {displayValue(health?.input_dir)} → {displayValue(health?.output_dir)}
            </strong>
          </div>
        </div>
      ) : null}

      <TimelinePlot
        rows={visibleRows}
        selectedPhotoId={selectedPhotoId}
        onSelect={onSelectPhoto}
        layers={layers}
      />
      <TimelineRows
        rows={visibleRows}
        selectedPhotoId={selectedPhotoId}
        onSelect={onSelectPhoto}
        layers={layers}
      />
      {state === 'ready' || state === 'empty' ? (
        <div className="timeline-pagination" aria-label="Archive pagination">
          <button
            className="timeline-button timeline-button--quiet"
            type="button"
            onClick={() => void loadRows(appliedFilters, Math.max(0, offset - DEFAULT_PHOTO_LIMIT))}
            disabled={offset <= 0}
          >
            Previous page
          </button>
          <span>
            {rows.length
              ? `Returned page ${offset + 1}–${offset + rows.length}${typeof totalCount === 'number' ? ` of ${totalCount}` : ''} · view ${visibleRows.length}`
              : 'No returned rows'}
          </span>
          <button
            className="timeline-button timeline-button--quiet"
            type="button"
            onClick={() => void loadRows(appliedFilters, offset + DEFAULT_PHOTO_LIMIT)}
            disabled={
              !rows.length ||
              (typeof totalCount === 'number'
                ? offset + rows.length >= totalCount
                : rows.length < DEFAULT_PHOTO_LIMIT)
            }
          >
            Next page
          </button>
        </div>
      ) : null}
      <SourceContext
        state={state}
        error={error}
        onRetry={() => void loadRows(appliedFilters, offset)}
        sourceRefs={timelinePage.blocks[0].sourceRefs}
      />
    </section>
  );
}

function TimelineMapBlock() {
  const [state, setState] = useState<AsyncState>('idle');
  const [summary, setSummary] = useState<RunSummaryResponse>();
  const [coverageRows, setCoverageRows] = useState<readonly TimelineCoverageRecord[]>([]);
  const [coverageSource, setCoverageSource] = useState('Not loaded');
  const [yearFilter, setYearFilter] = useState('');
  const [poseFilter, setPoseFilter] = useState('');
  const [error, setError] = useState<string>();

  const loadSummary = async () => {
    setState('loading');
    setSummary(undefined);
    setError(undefined);
    setCoverageRows([]);
    setCoverageSource('Loading source');
    try {
      const [matrixResponse, metaResponse] = await Promise.all([
        requestUiArtifactJson<unknown>('timeline_matrix.json'),
        requestUiArtifactJson<RunSummaryResponse>('report_meta.json'),
      ]);
      const returnedMeta = uiArtifactPayload(metaResponse);
      const returnedCoverage = timelineMatrixRecords(uiArtifactPayload(matrixResponse));
      const poseBins = returnedMeta.pose_bins;
      setSummary(returnedMeta);
      setCoverageRows(returnedCoverage);
      setCoverageSource(
        'ui_artifacts/timeline_matrix.json · generated from stage1/main_timeline.csv',
      );
      setState(returnedCoverage.length || Object.keys(returnedMeta).length ? 'ready' : 'empty');
      if (!poseBins)
        setCoverageSource('ui_artifacts/timeline_matrix.json · pose bins returned in matrix');
    } catch (requestError) {
      setSummary(undefined);
      setCoverageSource('Source unavailable');
      setState('error');
      setError(errorMessage(requestError));
    }
  };

  const bins = summary?.pose_bins ? Object.entries(summary.pose_bins) : [];
  const visibleCoverageRows = coverageRows.filter(
    (cell) =>
      (!yearFilter || String(cell.year ?? '') === yearFilter) &&
      (!poseFilter || String(cell.pose_bin ?? '') === poseFilter),
  );
  const coverageYears = Array.from(
    new Set(coverageRows.flatMap((cell) => (cell.year === undefined ? [] : [String(cell.year)]))),
  );
  const coveragePoses = Array.from(
    new Set(
      coverageRows.flatMap((cell) =>
        cell.pose_bin === undefined || cell.pose_bin === null ? [] : [String(cell.pose_bin)],
      ),
    ),
  );

  return (
    <section className="detail-block detail-block--timeline" aria-labelledby="timeline-map-title">
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / timeline.map</span>
          <h3 id="timeline-map-title">Timeline Map</h3>
          <p>
            Year × pose coverage belongs to the archive context, not to an invented dashboard grid.
          </p>
        </div>
        <StatusPill
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Not loaded' : undefined}
        />
      </header>
      <div className="timeline-map-toolbar">
        <div>
          <span className="micro-label">Coverage matrix</span>
          <strong>
            {summary
              ? `Run ${displayValue(summary.run_id)} · Stage 2: ${displayValue(summary.stage2_status ?? summary.status)}`
              : 'No run summary loaded'}
          </strong>
          <span className="timeline-map-source-note">Source: {coverageSource}</span>
        </div>
        <div className="timeline-map-filters">
          <label className="timeline-field">
            <span>Year</span>
            <select value={yearFilter} onChange={(event) => setYearFilter(event.target.value)}>
              <option value="">All returned years</option>
              {coverageYears.map((year) => (
                <option key={year} value={year}>
                  {year}
                </option>
              ))}
            </select>
          </label>
          <label className="timeline-field">
            <span>Pose</span>
            <select value={poseFilter} onChange={(event) => setPoseFilter(event.target.value)}>
              <option value="">All returned poses</option>
              {coveragePoses.map((pose) => (
                <option key={pose} value={pose}>
                  {pose}
                </option>
              ))}
            </select>
          </label>
        </div>
        <button
          className="timeline-button"
          type="button"
          onClick={() => void loadSummary()}
          disabled={state === 'loading'}
        >
          {state === 'loading' ? 'Loading…' : 'Load timeline artifacts'}
        </button>
      </div>
      {error ? <p className="timeline-error-copy">{error}</p> : null}
      {coverageRows.length && !visibleCoverageRows.length ? (
        <div className="timeline-no-data timeline-no-data--compact" role="status">
          <span className="timeline-empty-mark" aria-hidden="true" />
          <div>
            <strong>No coverage cells match this scope</strong>
            <span>
              Year and pose filters only narrow returned cells; they do not create empty values.
            </span>
          </div>
        </div>
      ) : visibleCoverageRows.length ? (
        <div className="timeline-coverage-table-wrap">
          <table className="timeline-coverage-table">
            <caption>Returned year × pose coverage cells</caption>
            <thead>
              <tr>
                <th scope="col">Year</th>
                <th scope="col">Pose</th>
                <th scope="col">Frames</th>
                <th scope="col">Pairs</th>
                <th scope="col">FDR candidates</th>
                <th scope="col">Corroboration</th>
                <th scope="col">Aggregate metric</th>
                <th scope="col">Coverage</th>
                <th scope="col">Open context</th>
              </tr>
            </thead>
            <tbody>
              {visibleCoverageRows.map((cell, index) => (
                <tr key={`${String(cell.year ?? index)}-${String(cell.pose_bin ?? index)}`}>
                  <th scope="row">{displayValue(cell.year)}</th>
                  <td>{displayValue(cell.pose_bin)}</td>
                  <td>{displayValue(cell.frame_count)}</td>
                  <td>{displayValue(cell.pair_count)}</td>
                  <td>{displayValue(cell.fdr_candidate_count)}</td>
                  <td>
                    <StatusPill value={cell.corroboration_status} />
                  </td>
                  <td>
                    {displayValue(cell.aggregate_metric)} · {displayValue(cell.metric_unit)}
                  </td>
                  <td>
                    <StatusPill value={cell.coverage_state ?? cell.metric_status} />
                  </td>
                  <td>
                    <button
                      className="timeline-text-button"
                      type="button"
                      onClick={() =>
                        navigateTo('timeline', {
                          date_from:
                            cell.year === undefined ? undefined : `${String(cell.year)}-01-01`,
                          date_to:
                            cell.year === undefined ? undefined : `${String(cell.year)}-12-31`,
                          pose_bin: cell.pose_bin ?? undefined,
                        })
                      }
                    >
                      Open Timeline
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : bins.length ? (
        <div className="timeline-coverage-list" aria-label="Returned pose-bin coverage">
          {bins.map(([pose, count]) => (
            <div className="timeline-coverage-item" key={pose}>
              <span>{pose}</span>
              <strong>{displayValue(count)}</strong>
              <span>source-reported count</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="timeline-no-data timeline-no-data--compact" role="status">
          <span className="timeline-empty-mark" aria-hidden="true" />
          <div>
            <strong>No coverage cells to show</strong>
            <span>
              Empty cells remain visible as unavailable until the run summary supplies coverage.
            </span>
          </div>
        </div>
      )}
      <div className="timeline-cross-links" aria-label="Timeline map context transitions">
        <span className="micro-label">Open related context</span>
        <button
          className="timeline-text-button"
          type="button"
          onClick={() => navigateTo('research')}
        >
          Research
        </button>
        <button
          className="timeline-text-button"
          type="button"
          onClick={() => navigateTo('compare')}
        >
          Compare
        </button>
        <button className="timeline-text-button" type="button" onClick={() => navigateTo('report')}>
          Report
        </button>
        <button
          className="timeline-text-button"
          type="button"
          onClick={() => navigateTo('methodology')}
        >
          Methodology
        </button>
      </div>
      <div className="timeline-verdict-note">
        <strong>Map boundary</strong>
        <span>
          Coverage and corroboration status describe returned archive support; a sparse cell is not
          a negative finding.
        </span>
      </div>
      <SourceContext
        state={state}
        error={error}
        onRetry={() => void loadSummary()}
        sourceRefs={timelinePage.blocks[1].sourceRefs}
      />
    </section>
  );
}

function SelectionJournalBlock({
  selectedPhotoId,
  onClear,
}: {
  selectedPhotoId: string | null;
  onClear: () => void;
}) {
  const [note, setNote] = useState('');
  const [saveState, setSaveState] = useState<AsyncState>('idle');
  const [saveError, setSaveError] = useState<string>();

  const saveNote = async () => {
    if (!selectedPhotoId || !note.trim()) return;
    setSaveState('loading');
    setSaveError(undefined);
    try {
      await postJson('/api/v1/reviews', {
        object_id: selectedPhotoId,
        note_text: note.trim(),
        source_mode: 'research',
        not_a_verdict: true,
      });
      setSaveState('ready');
    } catch (requestError) {
      setSaveState('error');
      setSaveError(errorMessage(requestError));
    }
  };

  return (
    <section
      className="detail-block detail-block--timeline"
      aria-labelledby="timeline-journal-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / timeline.selection-journal</span>
          <h3 id="timeline-journal-title">Selection context and session journal</h3>
          <p>
            Frame context, provenance and a researcher note travel together without becoming a
            route.
          </p>
        </div>
        <StatusPill
          value={selectedPhotoId ? 'measured' : 'unavailable'}
          label={selectedPhotoId ? 'Frame selected' : 'No frame selected'}
        />
      </header>
      <div className="timeline-journal-grid">
        <div className="timeline-selection-card">
          <span className="micro-label">Selected object</span>
          <strong>{displayValue(selectedPhotoId)}</strong>
          <span>
            {selectedPhotoId
              ? 'Open Photo Detail or Compare from this context.'
              : 'Select a returned frame above to populate context.'}
          </span>
          {selectedPhotoId ? (
            <div className="timeline-inline-actions">
              <button
                className="timeline-button timeline-button--quiet"
                type="button"
                onClick={onClear}
              >
                Clear selection
              </button>
              <button
                className="timeline-text-button"
                type="button"
                onClick={() => navigateTo('photo-detail', { photo_id: selectedPhotoId })}
              >
                Open Photo Detail
              </button>
              <button
                className="timeline-text-button"
                type="button"
                onClick={() => navigateTo('compare', { photo_a: selectedPhotoId })}
              >
                Open Compare
              </button>
            </div>
          ) : null}
        </div>
        <form
          className="timeline-note-form"
          onSubmit={(event) => {
            event.preventDefault();
            void saveNote();
          }}
        >
          <label className="timeline-field timeline-field--full">
            <span>Researcher note</span>
            <textarea
              value={note}
              disabled={!selectedPhotoId}
              onChange={(event) => setNote(event.target.value)}
              placeholder={
                selectedPhotoId
                  ? 'Write a note tied to the selected object.'
                  : 'Select an object before adding a note.'
              }
              rows={4}
            />
          </label>
          <div className="timeline-form-footer">
            <span>
              {saveState === 'ready'
                ? 'Review API accepted the note.'
                : saveState === 'error'
                  ? saveError
                  : 'Notes are not analytical measurements.'}
            </span>
            <button
              className="timeline-button"
              type="submit"
              disabled={!selectedPhotoId || !note.trim() || saveState === 'loading'}
            >
              {saveState === 'loading' ? 'Saving…' : 'Save note'}
            </button>
          </div>
        </form>
      </div>
      <SourceContext
        state={saveState}
        error={saveError}
        onRetry={() => void saveNote()}
        sourceRefs={timelinePage.blocks[2].sourceRefs}
      />
    </section>
  );
}

export function TimelinePage() {
  const [selectedPhotoId, setSelectedPhotoId] = useState<string | null>(
    () => hashParam('photo_id') || null,
  );

  const renderBlock = (block: BlockDefinition) => {
    switch (block.id) {
      case 'timeline.archive-explorer':
        return (
          <ArchiveExplorerBlock
            selectedPhotoId={selectedPhotoId}
            onSelectPhoto={setSelectedPhotoId}
          />
        );
      case 'timeline.map':
        return <TimelineMapBlock />;
      case 'timeline.selection-journal':
        return (
          <SelectionJournalBlock
            selectedPhotoId={selectedPhotoId}
            onClear={() => setSelectedPhotoId(null)}
          />
        );
      default:
        return null;
    }
  };

  return <PageBlueprint definition={timelinePage} renderBlock={renderBlock} />;
}
