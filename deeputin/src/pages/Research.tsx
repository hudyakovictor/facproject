import { useMemo, useState } from 'react';

import { ApiRequestError, isAbortError, postJson, requestJson } from '@/shared/api';
import { parseCsvRecords, type CsvRecord } from '@/shared/csv';
import { PageBlueprint } from '@/shared/PageBlueprint';
import {
  requestUiArtifactJson,
  requestUiArtifactText,
  uiArtifactPayload,
} from '@/shared/uiArtifacts';
import { hashParam, navigateTo } from '@/shared/navigation';
import type { BlockDefinition, PageDefinition } from '@/shared/contracts';

/**
 * PAGE: Research.
 * Blocks are semantic ownership boundaries. Their internal controls and views stay together;
 * the page owner is free to choose the eventual composition.
 */
export const researchPage = {
  id: 'research',
  title: 'Research',
  group: 'research',
  purpose:
    'Единая исследовательская область для зон, casework, corroboration, key points, persistence и ручной проверки.',
  primaryQuestion: 'Где локализовано наблюдение, повторяется ли оно и что требует ручной проверки?',
  blocks: [
    /**
     * BLOCK: Zone Atlas and spatial research.
     * OWNED ELEMENTS: zone, period, pose and metric controls, 3×3 zone atlas, zone chronology and coverage, selected zone and pair context, raw/calibrated status, legend and limitations.
     * CONTRACT SURFACE: elements: FDR/status filters, zone and metric status context, plain-language zone meaning; actions: set_fdr_filter, select_metric, open_pair_detail, open_methodology; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * sparse_coverage, zone_status, metric_status, aggregate_metric, metric_catalog_ref, plain_language_meaning.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * run_id, date_from, date_to, pose_bin, zone_id, metric, fdr_filter,
     * measurement_state, coordinate_space, review_status, result_count, zone_name, value, unit,
     * raw_or_calibrated, status, threshold, source_ref, limitation_refs, date, pair_id,
     * fdr, q_value, quality, visibility, calibration.
     */
    {
      id: 'research.zone-atlas',
      title: 'Zone Atlas and spatial research',
      purpose:
        'Самостоятельный зональный блок с выборкой, картой 3×3, chronology зон, метриками, легендой и источниками.',
      elements: [
        'FDR/status filters',
        'zone and metric status context',
        'plain-language zone meaning',
        'zone, period, pose and metric controls',
        '3×3 zone atlas',
        'zone chronology and coverage',
        'selected zone and pair context',
        'raw/calibrated status, legend and limitations',
      ],
      keys: [
        'sparse_coverage',
        'zone_status',
        'metric_status',
        'aggregate_metric',
        'metric_catalog_ref',
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
        'not_a_verdict',
        'run_id',
        'date_from',
        'date_to',
        'pose_bin',
        'zone_id',
        'metric',
        'fdr_filter',
        'measurement_state',
        'coordinate_space',
        'review_status',
        'result_count',
        'zone_name',
        'value',
        'unit',
        'raw_or_calibrated',
        'status',
        'threshold',
        'source_ref',
        'limitation_refs',
        'date',
        'pair_id',
        'fdr',
        'q_value',
        'quality',
        'visibility',
        'calibration',
      ],
      sourceRefs: [
        'ui_artifacts/zone_summary.csv',
        'api/v1/ui_artifacts/zone_summary.csv',
        'api/v1/zones/catalog',
      ],
      actions: [
        'set_fdr_filter',
        'select_metric',
        'open_pair_detail',
        'open_methodology',
        'apply_filter',
        'clear_filter',
        'save_view_state',
        'select_zone',
        'open_pair',
        'open_compare',
        'open_source',
        'select_pair',
        'select_date',
        'open_timeline',
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
        'fallback',
        'long_content',
      ],
    },
    /**
     * BLOCK: Casework review workspace.
     * OWNED ELEMENTS: candidate queue controls, filtering and sorting, FDR candidate table, selected candidate evidence inspector, manual review decision and rationale, review progress and links to Compare/Atlas/Corroboration.
     * CONTRACT SURFACE: elements: decision controls and rationale, review progress by period and pose, contract-version and review-time context, not-a-verdict evidence boundary; actions: accept_for_report, reject_insufficient, request_more_data, save_review, add_note, open_timeline, open_report; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * schema_version, run_id, decision, rationale, reviewer_id, reviewed_at, contract_version, queue_total, resolved_count, unresolved_count, status_by_pose, manual_review_count, alternative_explanations, unresolved_questions, plain_language_meaning.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * candidate_id, pair_id, date_a, date_b, pose_bin, z_value, q_value,
     * fdr_status, signal_type, review_status, priority, photo_a, photo_b, metrics,
     * visual_refs, zones, supporting_objects, weakening_objects, source_refs, limitation_refs.
     */
    {
      id: 'research.casework-queue',
      title: 'Casework review workspace',
      purpose:
        'Самостоятельная очередь ручной проверки, где фильтры, сортировка, inspector кандидата и решение находятся в одном рабочем контексте.',
      elements: [
        'decision controls and rationale',
        'review progress by period and pose',
        'contract-version and review-time context',
        'not-a-verdict evidence boundary',
        'candidate queue controls, filtering and sorting',
        'FDR candidate table',
        'selected candidate evidence inspector',
        'manual review decision and rationale',
        'review progress and links to Compare/Atlas/Corroboration',
      ],
      keys: [
        'schema_version',
        'run_id',
        'decision',
        'rationale',
        'reviewer_id',
        'reviewed_at',
        'contract_version',
        'queue_total',
        'resolved_count',
        'unresolved_count',
        'status_by_pose',
        'manual_review_count',
        'alternative_explanations',
        'unresolved_questions',
        'plain_language_meaning',
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
        'candidate_id',
        'pair_id',
        'date_a',
        'date_b',
        'pose_bin',
        'z_value',
        'q_value',
        'fdr_status',
        'signal_type',
        'review_status',
        'priority',
        'photo_a',
        'photo_b',
        'metrics',
        'visual_refs',
        'zones',
        'supporting_objects',
        'weakening_objects',
        'source_refs',
        'limitation_refs',
      ],
      sourceRefs: [
        'ui_artifacts/report_sections/change_points.json',
        'ui_artifacts/report_sections/zones.json',
        'ui_artifacts/report_meta.json',
        'api/v1/ui_artifacts/report_sections/change_points.json',
        'api/v1/reviews (POST only; no read endpoint)',
      ],
      actions: [
        'accept_for_report',
        'reject_insufficient',
        'request_more_data',
        'save_review',
        'add_note',
        'open_timeline',
        'open_report',
        'select_candidate',
        'filter_queue',
        'sort_queue',
        'open_compare',
        'open_zone_atlas',
        'open_corroboration',
        'open_source',
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
     * BLOCK: Corroboration matrix.
     * OWNED ELEMENTS: period × pose matrix, pair and FDR counts, supporting, weakening, missing and conflict pairs, selected cell detail, coverage legend and pair/timeline transitions.
     * CONTRACT SURFACE: elements: corroboration threshold, independent-line status, missing and conflicting data explanation; actions: set_threshold, filter_status, open_compare, open_casework, open_report; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * corroboration_threshold, corroboration_status, independent_line, selected_cell, cell_status, supporting_pair_count, limited_pairs, conflicting_pairs, fdr_status.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * period, pose_bin, pair_count, fdr_count, status, coverage_state, cell_id,
     * supporting_pairs, weakening_pairs, missing_pairs, conflict_pairs.
     */
    {
      id: 'research.corroboration',
      title: 'Corroboration matrix',
      purpose:
        'Матрица повторяемости в периодах и ракурсах с выбранной ячейкой, поддерживающими, ослабляющими и отсутствующими парами.',
      elements: [
        'corroboration threshold',
        'independent-line status',
        'missing and conflicting data explanation',
        'period × pose matrix',
        'pair and FDR counts',
        'supporting, weakening, missing and conflict pairs',
        'selected cell detail',
        'coverage legend and pair/timeline transitions',
      ],
      keys: [
        'corroboration_threshold',
        'corroboration_status',
        'independent_line',
        'selected_cell',
        'cell_status',
        'supporting_pair_count',
        'limited_pairs',
        'conflicting_pairs',
        'fdr_status',
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
        'period',
        'pose_bin',
        'pair_count',
        'fdr_count',
        'status',
        'coverage_state',
        'cell_id',
        'supporting_pairs',
        'weakening_pairs',
        'missing_pairs',
        'conflict_pairs',
      ],
      sourceRefs: [
        'ui_artifacts/report_sections/zones.json',
        'api/v1/ui_artifacts/report_sections/zones.json',
      ],
      actions: [
        'set_threshold',
        'filter_status',
        'open_compare',
        'open_casework',
        'open_report',
        'select_cell',
        'open_pair',
        'open_timeline',
        'open_source',
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
     * BLOCK: Key Points, persistence and review boundary.
     * OWNED ELEMENTS: LDM106/LDM134 and coordinate controls, landmark map, vectors, table and time view, visibility and pose-leakage guards, persistence chain list and timeline, supporting/weakening links and review decision, limitations and unresolved questions.
     * CONTRACT SURFACE: elements: animation sequence, noise and anomaly threshold controls, point status and time-view controls; actions: toggle_animation, set_noise_threshold, set_anomaly_threshold, open_compare, open_report; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * schema_version, run_id, photo_a, photo_b, animation_sequence, time_view, point_status, noise_threshold.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * pair_id, point_set, coordinate_space, point_index, x_a, y_a, z_a,
     * x_b, y_b, z_b, dx, dy, dz, magnitude,
     * unit, visibility_a, visibility_b, zone_id, source_ref, pose_leakage_limited, pose_distance,
     * expression_influence, coherent_motion_fraction, anomaly_threshold, calibration_status, limitation_refs, chain_id, start_date,
     * end_date, length, max_gap, pose_bin, metric, chain_status, pair_ids,
     * supporting_refs, weakening_refs, not_a_verdict, decision, rationale, reviewer_id, reviewed_at,
     * alternative_explanations, unresolved_questions, review_status.
     */
    {
      id: 'research.motion-persistence',
      title: 'Key Points, persistence and review boundary',
      purpose:
        'Самостоятельный блок движения точек и устойчивости во времени с guardrails, цепочками, review status и нерешёнными вопросами.',
      elements: [
        'animation sequence',
        'noise and anomaly threshold controls',
        'point status and time-view controls',
        'LDM106/LDM134 and coordinate controls',
        'landmark map, vectors, table and time view',
        'visibility and pose-leakage guards',
        'persistence chain list and timeline',
        'supporting/weakening links and review decision',
        'limitations and unresolved questions',
      ],
      keys: [
        'schema_version',
        'run_id',
        'photo_a',
        'photo_b',
        'animation_sequence',
        'time_view',
        'point_status',
        'noise_threshold',
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
        'pair_id',
        'point_set',
        'coordinate_space',
        'point_index',
        'x_a',
        'y_a',
        'z_a',
        'x_b',
        'y_b',
        'z_b',
        'dx',
        'dy',
        'dz',
        'magnitude',
        'unit',
        'visibility_a',
        'visibility_b',
        'zone_id',
        'source_ref',
        'pose_leakage_limited',
        'pose_distance',
        'expression_influence',
        'coherent_motion_fraction',
        'anomaly_threshold',
        'calibration_status',
        'limitation_refs',
        'chain_id',
        'start_date',
        'end_date',
        'length',
        'max_gap',
        'pose_bin',
        'metric',
        'chain_status',
        'pair_ids',
        'supporting_refs',
        'weakening_refs',
        'not_a_verdict',
        'decision',
        'rationale',
        'reviewer_id',
        'reviewed_at',
        'alternative_explanations',
        'unresolved_questions',
        'review_status',
      ],
      sourceRefs: [
        'ui_artifacts/report_sections/motion_maps.json',
        'ui_artifacts/report_sections/change_points.json',
        'api/v1/ui_artifacts/report_sections/motion_maps.json',
        'api/v1/reviews (POST only; no read endpoint)',
      ],
      actions: [
        'toggle_animation',
        'set_noise_threshold',
        'set_anomaly_threshold',
        'open_compare',
        'open_report',
        'switch_point_set',
        'switch_coordinate_space',
        'select_point',
        'open_source',
        'open_methodology',
        'open_calibration',
        'open_limitation',
        'select_chain',
        'open_pair',
        'open_timeline',
        'save_review',
        'request_more_data',
        'send_to_report',
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
        'long_content',
      ],
    },
  ],
} satisfies PageDefinition;

type ResearchState = 'idle' | 'loading' | 'ready' | 'empty' | 'error';
type ResearchRecord = Record<string, unknown>;

function researchRecord(payload: unknown): ResearchRecord {
  return payload && typeof payload === 'object' && !Array.isArray(payload)
    ? (payload as ResearchRecord)
    : {};
}

function hasReturnedFields(record: ResearchRecord): boolean {
  return Object.entries(record).some(
    ([key, value]) =>
      !['schema', 'source_mode', 'not_a_verdict'].includes(key) &&
      value !== null &&
      value !== undefined,
  );
}

function researchRows(payload: unknown, keys: readonly string[]): readonly ResearchRecord[] {
  if (Array.isArray(payload)) {
    return payload.flatMap((entry) => {
      if (entry && typeof entry === 'object') return [entry as ResearchRecord];
      if (typeof entry === 'string' || typeof entry === 'number') return [{ text: entry }];
      return [];
    });
  }
  const source = researchRecord(payload);
  for (const key of keys) {
    if (Array.isArray(source[key])) {
      return (source[key] as unknown[]).flatMap((entry) => {
        if (entry && typeof entry === 'object') return [entry as ResearchRecord];
        if (typeof entry === 'string' || typeof entry === 'number') return [{ text: entry }];
        return [];
      });
    }
  }
  return [];
}

function researchCsvRows(text: string): readonly ResearchRecord[] {
  return parseCsvRecords(text).map((row: CsvRecord) => ({
    ...row,
    source_file: 'ui_artifacts/zone_summary.csv',
  }));
}

function researchList(value: unknown): readonly string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (typeof entry === 'string' || typeof entry === 'number') return [String(entry)];
    if (entry && typeof entry === 'object') {
      const item = entry as ResearchRecord;
      const id = item.pair_id ?? item.candidate_id ?? item.photo_id ?? item.id ?? item.source_ref;
      return id === undefined ? [] : [String(id)];
    }
    return [];
  });
}

function researchValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Unavailable';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return 'Structured value';
  return String(value);
}

function researchPointSetMatches(value: unknown, selected: string): boolean {
  if (value === undefined || value === null || value === '') return false;
  const normalized = String(value).toLowerCase();
  return normalized === selected || normalized === `ldm${selected}`;
}

function researchSpaceMatches(value: unknown, selected: string): boolean {
  if (value === undefined || value === null || value === '') return false;
  const normalized = String(value).toLowerCase();
  const aliases: Record<string, readonly string[]> = {
    raw: ['raw', 'raw_object_normalized'],
    aligned: ['aligned', 'chronology_aligned'],
    original: ['original', 'original_image_px'],
  };
  return (aliases[selected] ?? [selected]).includes(normalized);
}

function researchDateMatches(row: ResearchRecord, dateFrom: string, dateTo: string): boolean {
  if (!dateFrom && !dateTo) return true;
  const start = String(row.date_from ?? row.date ?? '');
  const end = String(row.date_to ?? row.date ?? '');
  if (!start || !end) return false;
  return (!dateFrom || start >= dateFrom) && (!dateTo || end <= dateTo);
}

function researchPairMatches(row: ResearchRecord, photoA: string, photoB: string): boolean {
  const rowA = row.photo_a ?? row.photoA;
  const rowB = row.photo_b ?? row.photoB;
  if (rowA !== undefined || rowB !== undefined) {
    return String(rowA ?? '') === photoA && String(rowB ?? '') === photoB;
  }
  const pairId = row.pair_id;
  if (typeof pairId === 'string') return pairId === `${photoA}__${photoB}`;
  const pairIds = researchList(row.pair_ids);
  return pairIds.includes(`${photoA}__${photoB}`);
}

function researchStatusTone(value: unknown): 'positive' | 'warning' | 'muted' {
  if (value === true) return 'positive';
  if (value === false) return 'warning';
  if (typeof value !== 'string') return 'muted';
  if (
    ['measured', 'valid', 'pass', 'complete', 'supported', 'accepted', 'resolved'].includes(value)
  )
    return 'positive';
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
      'conflict',
    ].includes(value)
  )
    return 'warning';
  return 'muted';
}

function ResearchStatus({ value, label }: { value: unknown; label?: string }) {
  const tone = researchStatusTone(value);
  return (
    <span className={`research-status research-status--${tone}`}>
      <span className="research-status-dot" aria-hidden="true" />
      {label ?? researchValue(value)}
    </span>
  );
}

function researchErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.detail;
  return 'Источник данных недоступен.';
}

function ResearchSourceContext({
  state,
  error,
  sourceRefs,
  onRetry,
}: {
  state: ResearchState;
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
    <aside className="research-source-context" aria-label="Контекст источника Research">
      <div className="research-source-heading">
        <div>
          <span className="micro-label">Evidence boundary</span>
          <strong>{label}</strong>
        </div>
        <ResearchStatus value={state === 'ready' ? 'measured' : state} />
      </div>
      <div className="research-source-flags">
        <code>source_mode: research</code>
        <code>not_a_verdict: true</code>
      </div>
      {error ? <p className="research-error-copy">{error}</p> : null}
      {state === 'error' && onRetry ? (
        <button className="research-button research-button--quiet" type="button" onClick={onRetry}>
          Retry source request
        </button>
      ) : null}
      <details className="research-source-details">
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

function ResearchTextField({
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
    <label className="research-field">
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

function ResearchDataCard({
  label,
  value,
  unit,
}: {
  label: string;
  value: unknown;
  unit?: string;
}) {
  return (
    <div className="research-data-card">
      <span>{label}</span>
      <strong>{researchValue(value)}</strong>
      <small>{unit ?? 'source field'}</small>
    </div>
  );
}

function ResearchZoneAtlasBlock() {
  const [runId, setRunId] = useState(() => hashParam('run_id'));
  const [dateFrom, setDateFrom] = useState(() => hashParam('date_from'));
  const [dateTo, setDateTo] = useState(() => hashParam('date_to'));
  const [poseBin, setPoseBin] = useState(() => hashParam('pose_bin'));
  const [metric, setMetric] = useState(() => hashParam('metric'));
  const [fdrFilter, setFdrFilter] = useState(() => hashParam('fdr') || 'all');
  const [statusFilter, setStatusFilter] = useState(() => hashParam('status') || 'all');
  const [state, setState] = useState<ResearchState>('idle');
  const [record, setRecord] = useState<ResearchRecord>();
  const [catalog, setCatalog] = useState<readonly ResearchRecord[]>([]);
  const [rows, setRows] = useState<readonly ResearchRecord[]>([]);
  const [selectedKey, setSelectedKey] = useState('');
  const [error, setError] = useState<string>();

  const loadAtlas = async () => {
    setState('loading');
    setRecord(undefined);
    setCatalog([]);
    setRows([]);
    setSelectedKey('');
    setError(undefined);
    try {
      const [catalogResult, zoneSummaryResult] = await Promise.allSettled([
        requestJson<unknown>('/api/v1/zones/catalog'),
        requestUiArtifactText('zone_summary.csv'),
      ]);
      const returnedCatalog =
        catalogResult.status === 'fulfilled'
          ? researchRows(catalogResult.value, ['zone_catalog', 'zones', 'items', 'catalog'])
          : [];
      const returnedRows =
        zoneSummaryResult.status === 'fulfilled' ? researchCsvRows(zoneSummaryResult.value) : [];
      const catalogRecord =
        catalogResult.status === 'fulfilled' ? researchRecord(catalogResult.value) : {};
      const returnedRecord: ResearchRecord = {
        ...catalogRecord,
        source_file: 'ui_artifacts/zone_summary.csv',
      };
      setRecord(returnedRecord);
      setCatalog(returnedCatalog);
      setRows(returnedRows);
      const sourceErrors = [
        catalogResult.status === 'rejected'
          ? `zones/catalog: ${researchErrorMessage(catalogResult.reason)}`
          : undefined,
        zoneSummaryResult.status === 'rejected'
          ? `zone_summary.csv: ${researchErrorMessage(zoneSummaryResult.reason)}`
          : undefined,
      ].filter((value): value is string => Boolean(value));
      setError(sourceErrors.length ? sourceErrors.join(' · ') : undefined);
      setState(
        returnedRows.length || returnedCatalog.length || hasReturnedFields(catalogRecord)
          ? 'ready'
          : sourceErrors.length
            ? 'error'
            : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(researchErrorMessage(requestError));
    }
  };

  const filteredRows = useMemo(
    () =>
      rows.filter((row) => {
        const match = (value: unknown, filter: string) =>
          !filter || filter === 'all' || String(value ?? '') === filter;
        return (
          match(row.run_id, runId.trim()) &&
          researchDateMatches(row, dateFrom.trim(), dateTo.trim()) &&
          match(row.pose_bin, poseBin.trim()) &&
          match(row.metric, metric.trim()) &&
          match(row.fdr_status ?? row.fdr, fdrFilter) &&
          match(row.status ?? row.zone_status ?? row.metric_status, statusFilter)
        );
      }),
    [dateFrom, dateTo, fdrFilter, metric, poseBin, rows, runId, statusFilter],
  );
  const selected = filteredRows.find(
    (row, index) => String(row.pair_id ?? row.zone_id ?? row.id ?? index) === selectedKey,
  );

  return (
    <section className="detail-block detail-block--research" aria-labelledby="research-atlas-title">
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / research.zone-atlas</span>
          <h3 id="research-atlas-title">Zone Atlas and spatial research</h3>
          <p>
            Zone, period, pose, metric and FDR controls own the returned spatial observations and
            their coverage limits.
          </p>
        </div>
        <ResearchStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="research-control-panel">
        <div className="research-field-row">
          <ResearchTextField
            label="Run ID"
            value={runId}
            onChange={setRunId}
            placeholder="calculated run_id"
          />
          <ResearchTextField
            label="Date from"
            value={dateFrom}
            onChange={setDateFrom}
            placeholder="source date"
          />
          <ResearchTextField
            label="Date to"
            value={dateTo}
            onChange={setDateTo}
            placeholder="source date"
          />
          <ResearchTextField
            label="Pose bin"
            value={poseBin}
            onChange={setPoseBin}
            placeholder="returned pose_bin"
          />
          <ResearchTextField
            label="Metric"
            value={metric}
            onChange={setMetric}
            placeholder="returned metric key"
          />
          <label className="research-field">
            <span>FDR filter</span>
            <select value={fdrFilter} onChange={(event) => setFdrFilter(event.target.value)}>
              <option value="all">All returned</option>
              <option value="pass">Pass</option>
              <option value="limited">Limited</option>
              <option value="not_computed">Not computed</option>
            </select>
          </label>
          <label className="research-field">
            <span>Status</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">All returned</option>
              <option value="measured">Measured</option>
              <option value="limited">Limited</option>
              <option value="not_computed">Not computed</option>
            </select>
          </label>
        </div>
        <div className="research-control-footer">
          <span>
            GET /api/v1/zones/catalog + /api/v1/ui_artifacts/zone_summary.csv · filtering is applied
            only to returned aggregate rows.
          </span>
          <button
            className="research-button"
            type="button"
            onClick={() => void loadAtlas()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load zone source'}
          </button>
        </div>
      </div>
      {error ? <p className="research-error-copy">{error}</p> : null}
      {catalog.length ? (
        <details className="research-zone-catalog">
          <summary>Returned zone catalog ({catalog.length})</summary>
          <ul>
            {catalog.map((zone, index) => (
              <li key={String(zone.zone_id ?? zone.id ?? zone.name ?? index)}>
                <code>{researchValue(zone.zone_id ?? zone.id ?? zone.name)}</code>
                <span>{researchValue(zone.zone_name ?? zone.label ?? zone.description)}</span>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      {record ? (
        <div className="research-summary-strip">
          <ResearchDataCard label="Run" value={record.run_id} />
          <ResearchDataCard label="Returned result count" value={record.result_count} />
          <ResearchDataCard
            label="Rows in current view"
            value={filteredRows.length}
            unit="client view count"
          />
          <ResearchDataCard label="Sparse coverage" value={record.sparse_coverage} />
          <ResearchDataCard label="Calibration" value={record.calibration} />
          <ResearchDataCard label="FDR status" value={record.fdr_status} />
          <ResearchDataCard label="q-value" value={record.q_value} />
          <ResearchDataCard label="Quality" value={record.quality_state ?? record.quality} />
          <ResearchDataCard
            label="Visibility"
            value={record.visibility_state ?? record.visibility}
          />
          <ResearchDataCard label="Source mode" value={record.source_mode} />
          <ResearchDataCard label="Not a verdict" value={record.not_a_verdict} />
          <ResearchDataCard
            label="Limitations"
            value={record.limitation_refs ?? record.limitations}
          />
        </div>
      ) : null}
      {filteredRows.length ? (
        <div className="research-zone-layout">
          <div className="research-zone-atlas">
            <div className="research-subsection-heading">
              <div>
                <span className="micro-label">Returned atlas rows</span>
                <strong>{filteredRows.length} source observations</strong>
              </div>
              <span className="research-legend">No cells are created without a returned zone.</span>
            </div>
            <div className="research-zone-list">
              {filteredRows.map((row, index) => {
                const key = String(row.pair_id ?? row.zone_id ?? row.id ?? index);
                return (
                  <button
                    key={key}
                    className={`research-zone-cell${selectedKey === key ? ' is-selected' : ''}`}
                    type="button"
                    onClick={() => setSelectedKey(key)}
                  >
                    <span>{researchValue(row.pair_id ?? row.zone_id ?? row.id)}</span>
                    <strong>{researchValue(row.zone_count)} zones · avg RMSE</strong>
                    <small>
                      {researchValue(row.avg_rmse)} · max {researchValue(row.max_rmse)} · robust-z{' '}
                      {researchValue(row.primary_robust_z)}
                    </small>
                    <ResearchStatus value={row.status ?? row.zone_status ?? row.metric_status} />
                  </button>
                );
              })}
            </div>
          </div>
          <div className="research-zone-inspector">
            <div className="research-subsection-heading">
              <div>
                <span className="micro-label">Selected zone</span>
                <strong>
                  {selected
                    ? researchValue(selected.pair_id ?? selected.zone_id ?? selected.id)
                    : 'No aggregate selected'}
                </strong>
              </div>
              {selected ? (
                <ResearchStatus
                  value={selected.status ?? selected.zone_status ?? selected.metric_status}
                />
              ) : null}
            </div>
            {selected ? (
              <>
                <div className="research-data-stack">
                  <ResearchDataCard
                    label="Zone aggregate"
                    value={selected.zone_name ?? selected.zone_id}
                  />
                  <ResearchDataCard label="Zone count" value={selected.zone_count} />
                  <ResearchDataCard label="Average RMSE" value={selected.avg_rmse} />
                  <ResearchDataCard label="Minimum RMSE" value={selected.min_rmse} />
                  <ResearchDataCard label="Maximum RMSE" value={selected.max_rmse} />
                  <ResearchDataCard label="Primary robust-z" value={selected.primary_robust_z} />
                  <ResearchDataCard label="Status" value={selected.status} />
                  <ResearchDataCard
                    label="Quality"
                    value={selected.quality ?? selected.quality_state}
                  />
                  <ResearchDataCard
                    label="Visibility"
                    value={selected.visibility ?? selected.visibility_state}
                  />
                  <ResearchDataCard
                    label="Calibration"
                    value={selected.calibration ?? selected.calibration_state}
                  />
                  <ResearchDataCard label="Pair" value={selected.pair_id} />
                  <ResearchDataCard label="Photo A" value={selected.photo_a} />
                  <ResearchDataCard label="Photo B" value={selected.photo_b} />
                  <ResearchDataCard label="Source file" value={selected.source_file} />
                  <ResearchDataCard
                    label="Limitation refs"
                    value={selected.limitation_refs ?? selected.limitations}
                  />
                </div>
                <p className="research-limitation-copy">
                  {researchValue(selected.limitations ?? selected.limitation_refs)}
                </p>
                <div className="research-cross-links" aria-label="Zone atlas transitions">
                  <span className="micro-label">Open related context</span>
                  <button
                    className="research-text-button"
                    type="button"
                    onClick={() =>
                      navigateTo('compare', {
                        photo_a: String(selected.photo_a ?? ''),
                        photo_b: String(selected.photo_b ?? ''),
                      })
                    }
                    disabled={!selected.photo_a || !selected.photo_b}
                  >
                    Compare
                  </button>
                  <button
                    className="research-text-button"
                    type="button"
                    onClick={() =>
                      navigateTo('timeline', {
                        date_from: selected.date ? String(selected.date) : undefined,
                        date_to: selected.date ? String(selected.date) : undefined,
                        pose_bin: selected.pose_bin ? String(selected.pose_bin) : undefined,
                      })
                    }
                  >
                    Timeline
                  </button>
                  <button
                    className="research-text-button"
                    type="button"
                    onClick={() => navigateTo('methodology')}
                  >
                    Methodology
                  </button>
                </div>
              </>
            ) : (
              <div className="research-no-data research-no-data--compact">
                Select a returned zone row to inspect its metric and limitation context.
              </div>
            )}
          </div>
        </div>
      ) : rows.length ? (
        <div className="research-no-data" role="status">
          <span className="research-empty-mark" aria-hidden="true" />
          <div>
            <strong>No returned zone observations match these filters</strong>
            <span>
              Filters narrow returned rows; they do not create 3×3 cells or reinterpret a missing
              coordinate, metric or status.
            </span>
          </div>
        </div>
      ) : (
        <div className="research-no-data" role="status">
          <span className="research-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty'
                ? 'No zone observations returned'
                : state === 'ready'
                  ? 'No zone rows returned for this source'
                  : 'No zone source loaded'}
            </strong>
            <span>
              3×3 atlas cells, chronology and coverage are not synthesized when the calculated
              source is absent.
            </span>
          </div>
        </div>
      )}
      <div className="research-verdict-note">
        <strong>Spatial boundary</strong>
        <span>
          Sparse coverage, FDR/q-value and raw/calibrated status stay visible. A zone-level
          observation is not a verdict about a person.
        </span>
      </div>
      <ResearchSourceContext
        state={state}
        error={error}
        onRetry={() => void loadAtlas()}
        sourceRefs={researchPage.blocks[0].sourceRefs}
      />
    </section>
  );
}

function ResearchCaseworkBlock() {
  const [state, setState] = useState<ResearchState>('idle');
  const [summary, setSummary] = useState<ResearchRecord>();
  const [reviews, setReviews] = useState<readonly ResearchRecord[]>([]);
  const [selectedKey, setSelectedKey] = useState(
    () => hashParam('candidate_id') || hashParam('pair_id'),
  );
  const [statusFilter, setStatusFilter] = useState('all');
  const [query, setQuery] = useState('');
  const [sort, setSort] = useState('priority');
  const [decision, setDecision] = useState('');
  const [rationale, setRationale] = useState('');
  const [reviewerId, setReviewerId] = useState('');
  const [saveState, setSaveState] = useState<ResearchState>('idle');
  const [error, setError] = useState<string>();
  const [saveError, setSaveError] = useState<string>();

  const loadQueue = async () => {
    setState('loading');
    setSummary(undefined);
    setReviews([]);
    setError(undefined);
    try {
      const [metaResult, changePointsResult] = await Promise.allSettled([
        requestUiArtifactJson<ResearchRecord>('report_meta.json'),
        requestUiArtifactJson<unknown>('report_sections/change_points.json'),
      ]);
      const returnedMeta =
        metaResult.status === 'fulfilled'
          ? researchRecord(uiArtifactPayload(metaResult.value))
          : {};
      const changePointsPayload =
        changePointsResult.status === 'fulfilled'
          ? uiArtifactPayload(changePointsResult.value)
          : undefined;
      const returnedRows = researchRows(changePointsPayload, [
        'change_points',
        'events',
        'candidates',
        'items',
        'rows',
        'records',
      ]).map((row) => ({
        ...row,
        source_file: row.source_file ?? 'ui_artifacts/report_sections/change_points.json',
      }));
      const returnedSummary: ResearchRecord = {
        ...returnedMeta,
        ...researchRecord(changePointsPayload),
      };
      setSummary(returnedSummary);
      setReviews(returnedRows);
      const sourceErrors = [
        metaResult.status === 'rejected'
          ? `report_meta.json: ${researchErrorMessage(metaResult.reason)}`
          : undefined,
        changePointsResult.status === 'rejected'
          ? `change_points.json: ${researchErrorMessage(changePointsResult.reason)}`
          : undefined,
      ].filter((value): value is string => Boolean(value));
      setError(sourceErrors.length ? sourceErrors.join(' · ') : undefined);
      setState(
        returnedRows.length || hasReturnedFields(returnedSummary)
          ? 'ready'
          : sourceErrors.length
            ? 'error'
            : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setSummary(undefined);
      setState('error');
      setError(researchErrorMessage(requestError));
    }
  };

  const filteredReviews = useMemo(() => {
    const next = reviews.filter((review) => {
      const haystack = [
        review.candidate_id,
        review.pair_id,
        review.photo_a,
        review.photo_b,
        review.pose_bin,
        review.signal_type,
      ]
        .map((item) => String(item ?? ''))
        .join(' ')
        .toLowerCase();
      return (
        (!query.trim() || haystack.includes(query.trim().toLowerCase())) &&
        (statusFilter === 'all' ||
          String(review.review_status ?? review.status ?? '') === statusFilter)
      );
    });
    return [...next].sort((left, right) => {
      if (sort === 'q_value')
        return (
          Number(left.q_value ?? Number.POSITIVE_INFINITY) -
          Number(right.q_value ?? Number.POSITIVE_INFINITY)
        );
      if (sort === 'z_value')
        return (
          Number(right.z_value ?? Number.NEGATIVE_INFINITY) -
          Number(left.z_value ?? Number.NEGATIVE_INFINITY)
        );
      return String(left.priority ?? '').localeCompare(String(right.priority ?? ''));
    });
  }, [query, reviews, sort, statusFilter]);
  const selected = filteredReviews.find(
    (review, index) => String(review.candidate_id ?? review.pair_id ?? index) === selectedKey,
  );

  const saveReview = async () => {
    if (!selected) {
      setSaveState('error');
      setSaveError('Select a returned candidate before saving a review.');
      return;
    }
    if (!decision) {
      setSaveState('error');
      setSaveError('Choose a review decision explicitly.');
      return;
    }
    setSaveState('loading');
    setSaveError(undefined);
    try {
      const response = await postJson<unknown>('/api/v1/reviews', {
        candidate_id: selected.candidate_id,
        pair_id: selected.pair_id,
        photo_a: selected.photo_a,
        photo_b: selected.photo_b,
        decision,
        rationale,
        reviewer_id: reviewerId.trim() || undefined,
        source_mode: 'research',
        not_a_verdict: true,
      });
      const returnedReview = researchRecord(
        response && typeof response === 'object' && 'review' in response
          ? (response as ResearchRecord).review
          : response,
      );
      if (Object.keys(returnedReview).length) {
        setReviews((current) =>
          current.map((item) =>
            item.candidate_id === selected.candidate_id || item.pair_id === selected.pair_id
              ? { ...item, ...returnedReview }
              : item,
          ),
        );
      }
      setSaveState('ready');
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setSaveState('error');
      setSaveError(researchErrorMessage(requestError));
    }
  };

  const selectedSupporting = researchList(selected?.supporting_objects);
  const selectedWeakening = researchList(selected?.weakening_objects);

  return (
    <section
      className="detail-block detail-block--research"
      aria-labelledby="research-casework-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / research.casework-queue</span>
          <h3 id="research-casework-title">Casework review workspace</h3>
          <p>
            Queue filters, candidate evidence, manual decision and rationale remain owned by the
            review block.
          </p>
        </div>
        <ResearchStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="research-control-panel">
        <div className="research-field-row">
          <ResearchTextField
            label="Search queue"
            value={query}
            onChange={setQuery}
            placeholder="candidate, pair or pose"
          />
          <label className="research-field">
            <span>Review status</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">All returned</option>
              <option value="unresolved">Unresolved</option>
              <option value="resolved">Resolved</option>
              <option value="limited">Limited</option>
            </select>
          </label>
          <label className="research-field">
            <span>Sort</span>
            <select value={sort} onChange={(event) => setSort(event.target.value)}>
              <option value="priority">Priority</option>
              <option value="q_value">q-value</option>
              <option value="z_value">z-value</option>
            </select>
          </label>
        </div>
        <div className="research-control-footer">
          <span>
            report_meta.json + report_sections/change_points.json · candidate rows are returned
            section rows; POST /api/v1/reviews only saves an explicit review.
          </span>
          <button
            className="research-button"
            type="button"
            onClick={() => void loadQueue()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load review queue'}
          </button>
        </div>
      </div>
      {error ? <p className="research-error-copy">{error}</p> : null}
      {summary || reviews.length ? (
        <div className="research-review-progress">
          <ResearchDataCard label="Queue total" value={summary?.queue_total} />
          <ResearchDataCard label="Resolved" value={summary?.resolved_count} />
          <ResearchDataCard label="Unresolved" value={summary?.unresolved_count} />
          <ResearchDataCard label="Manual review" value={summary?.manual_review_count} />
          <ResearchDataCard label="Run ID" value={summary?.run_id ?? reviews[0]?.run_id} />
          <ResearchDataCard
            label="Contract"
            value={summary?.contract_version ?? reviews[0]?.contract_version}
          />
          <ResearchDataCard label="Status by pose" value={summary?.status_by_pose} />
        </div>
      ) : null}
      <div className="research-casework-layout">
        <div className="research-queue-table-wrap">
          <table className="research-queue-table">
            <caption>Returned candidate queue</caption>
            <thead>
              <tr>
                <th scope="col">Candidate / pair</th>
                <th scope="col">Dates</th>
                <th scope="col">Pose</th>
                <th scope="col">z / q</th>
                <th scope="col">FDR</th>
                <th scope="col">Review</th>
              </tr>
            </thead>
            <tbody>
              {filteredReviews.map((review, index) => {
                const key = String(review.candidate_id ?? review.pair_id ?? index);
                return (
                  <tr
                    key={key}
                    className={key === selectedKey ? 'is-selected' : ''}
                    onClick={() => {
                      setSelectedKey(key);
                      setDecision(String(review.decision ?? ''));
                      setRationale(String(review.rationale ?? ''));
                    }}
                  >
                    <th scope="row">
                      <button
                        className="research-row-button"
                        type="button"
                        onClick={() => setSelectedKey(key)}
                      >
                        {researchValue(review.candidate_id ?? review.pair_id)}
                        <span>
                          {researchValue(review.photo_a)} → {researchValue(review.photo_b)}
                        </span>
                      </button>
                    </th>
                    <td>
                      {researchValue(review.date_a)}
                      <br />
                      {researchValue(review.date_b)}
                    </td>
                    <td>{researchValue(review.pose_bin)}</td>
                    <td>
                      {researchValue(review.z_value)} / {researchValue(review.q_value)}
                    </td>
                    <td>
                      <ResearchStatus value={review.fdr_status} />
                    </td>
                    <td>
                      <ResearchStatus value={review.review_status ?? review.status} />
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {!filteredReviews.length ? (
            <div className="research-no-data research-no-data--compact" role="status">
              <span className="research-empty-mark" aria-hidden="true" />
              <div>
                <strong>
                  {reviews.length ? 'No candidates match the filters' : 'No review queue loaded'}
                </strong>
                <span>
                  Queue rows appear only when the run summary returns them; saved reviews are not
                  inferred.
                </span>
              </div>
            </div>
          ) : null}
        </div>
        <div className="research-inspector">
          <div className="research-subsection-heading">
            <div>
              <span className="micro-label">Candidate inspector</span>
              <strong>
                {selected
                  ? researchValue(selected.candidate_id ?? selected.pair_id)
                  : 'No candidate selected'}
              </strong>
            </div>
            {selected ? <ResearchStatus value={selected.review_status ?? selected.status} /> : null}
          </div>
          {selected ? (
            <>
              <div className="research-data-stack">
                <ResearchDataCard label="Candidate" value={selected.candidate_id} />
                <ResearchDataCard label="Pair" value={selected.pair_id} />
                <ResearchDataCard label="Signal" value={selected.signal_type} />
                <ResearchDataCard label="Priority" value={selected.priority} />
                <ResearchDataCard label="Date A" value={selected.date_a} />
                <ResearchDataCard label="Date B" value={selected.date_b} />
                <ResearchDataCard label="Pose" value={selected.pose_bin} />
                <ResearchDataCard label="z-value" value={selected.z_value} />
                <ResearchDataCard label="q-value" value={selected.q_value} />
                <ResearchDataCard label="FDR" value={selected.fdr_status} />
                <ResearchDataCard label="Photo A" value={selected.photo_a} />
                <ResearchDataCard label="Photo B" value={selected.photo_b} />
                <ResearchDataCard label="Metrics" value={selected.metrics} />
                <ResearchDataCard label="Visual refs" value={selected.visual_refs} />
                <ResearchDataCard label="Zones" value={selected.zones} />
                <ResearchDataCard label="Source refs" value={selected.source_refs} />
                <ResearchDataCard
                  label="Limitations"
                  value={selected.limitation_refs ?? selected.limitations}
                />
              </div>
              <div className="research-inspector-lists">
                <div>
                  <span className="micro-label">Supporting</span>
                  {selectedSupporting.length ? (
                    <ul>
                      {selectedSupporting.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>Unavailable</p>
                  )}
                </div>
                <div>
                  <span className="micro-label">Weakening</span>
                  {selectedWeakening.length ? (
                    <ul>
                      {selectedWeakening.map((item) => (
                        <li key={item}>{item}</li>
                      ))}
                    </ul>
                  ) : (
                    <p>Unavailable</p>
                  )}
                </div>
              </div>
              <div className="research-explanation-grid">
                <div>
                  <span className="micro-label">Plain-language meaning</span>
                  <p>{researchValue(selected.plain_language_meaning)}</p>
                </div>
                <div>
                  <span className="micro-label">Alternative explanations</span>
                  <p>{researchValue(selected.alternative_explanations)}</p>
                </div>
                <div>
                  <span className="micro-label">Unresolved questions</span>
                  <p>{researchValue(selected.unresolved_questions)}</p>
                </div>
              </div>
              <div className="research-cross-links" aria-label="Candidate transitions">
                <span className="micro-label">Open related context</span>
                <button
                  className="research-text-button"
                  type="button"
                  onClick={() =>
                    navigateTo('compare', {
                      photo_a: String(selected.photo_a ?? ''),
                      photo_b: String(selected.photo_b ?? ''),
                    })
                  }
                  disabled={!selected.photo_a || !selected.photo_b}
                >
                  Compare
                </button>
                <button
                  className="research-text-button"
                  type="button"
                  onClick={() => navigateTo('timeline')}
                >
                  Timeline
                </button>
                <button
                  className="research-text-button"
                  type="button"
                  onClick={() =>
                    navigateTo('report', {
                      pair_id: typeof selected.pair_id === 'string' ? selected.pair_id : undefined,
                    })
                  }
                >
                  Report
                </button>
              </div>
              <div className="research-review-form">
                <label className="research-field">
                  <span>Decision</span>
                  <select value={decision} onChange={(event) => setDecision(event.target.value)}>
                    <option value="">Choose decision</option>
                    <option value="accept_for_report">Accept for report</option>
                    <option value="reject_insufficient">Reject as insufficient</option>
                    <option value="request_more_data">Request more data</option>
                  </select>
                </label>
                <ResearchTextField
                  label="Reviewer ID"
                  value={reviewerId}
                  onChange={setReviewerId}
                  placeholder="reviewer identifier"
                />
                <label className="research-field">
                  <span>Rationale</span>
                  <textarea
                    value={rationale}
                    onChange={(event) => setRationale(event.target.value)}
                    placeholder="record the reasoning or limitation"
                  />
                </label>
                <div className="research-control-footer">
                  <span>
                    {saveState === 'ready'
                      ? 'Review saved by API.'
                      : (saveError ?? 'Save only an explicit decision.')}
                  </span>
                  <button
                    className="research-button"
                    type="button"
                    onClick={() => void saveReview()}
                    disabled={saveState === 'loading'}
                  >
                    {saveState === 'loading' ? 'Saving…' : 'Save review'}
                  </button>
                </div>
              </div>
            </>
          ) : (
            <div className="research-no-data research-no-data--compact">
              Select a returned candidate to inspect its evidence and review controls.
            </div>
          )}
        </div>
      </div>
      <div className="research-verdict-note">
        <strong>Review boundary</strong>
        <span>
          Accepting a candidate for a report is a traceable research action, not an identity or
          forensic verdict.
        </span>
      </div>
      <ResearchSourceContext
        state={state}
        error={error}
        onRetry={() => void loadQueue()}
        sourceRefs={researchPage.blocks[1].sourceRefs}
      />
    </section>
  );
}

function ResearchCorroborationBlock() {
  const [state, setState] = useState<ResearchState>('idle');
  const [record, setRecord] = useState<ResearchRecord>();
  const [cells, setCells] = useState<readonly ResearchRecord[]>([]);
  const [statusFilter, setStatusFilter] = useState(() => hashParam('status') || 'all');
  const [threshold, setThreshold] = useState(() => hashParam('threshold'));
  const [selectedKey, setSelectedKey] = useState(() => hashParam('cell_id'));
  const [error, setError] = useState<string>();

  const loadMatrix = async () => {
    setState('loading');
    setRecord(undefined);
    setCells([]);
    setError(undefined);
    try {
      const response = await requestUiArtifactJson<unknown>('report_sections/zones.json');
      const payload = uiArtifactPayload(response);
      const returnedRecord = researchRecord(payload);
      const returnedCells = researchRows(payload, [
        'corroboration_matrix',
        'matrix',
        'corroboration',
        'cells',
        'rows',
        'results',
      ]).filter((row) =>
        [
          'corroboration_status',
          'cell_status',
          'supporting_pair_count',
          'supporting_pairs',
          'conflicting_pairs',
          'conflict_pairs',
        ].some((key) => key in row),
      );
      setRecord(returnedRecord);
      setCells(returnedCells);
      setState(returnedCells.length || hasReturnedFields(returnedRecord) ? 'ready' : 'empty');
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(researchErrorMessage(requestError));
    }
  };
  const filteredCells = cells.filter(
    (cell) =>
      statusFilter === 'all' || String(cell.status ?? cell.cell_status ?? '') === statusFilter,
  );
  const selected = filteredCells.find(
    (cell, index) =>
      String(cell.cell_id ?? `${cell.period ?? ''}-${cell.pose_bin ?? ''}-${index}`) ===
      selectedKey,
  );

  return (
    <section
      className="detail-block detail-block--research"
      aria-labelledby="research-corroboration-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / research.corroboration</span>
          <h3 id="research-corroboration-title">Corroboration matrix</h3>
          <p>
            Period × pose corroboration keeps supporting, weakening, missing and conflicting pairs
            in the same cell context.
          </p>
        </div>
        <ResearchStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="research-control-panel">
        <div className="research-field-row">
          <ResearchTextField
            label="Corroboration threshold"
            value={threshold}
            onChange={setThreshold}
            placeholder="returned threshold"
          />
          <label className="research-field">
            <span>Cell status</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">All returned</option>
              <option value="supporting">Supporting</option>
              <option value="limited">Limited</option>
              <option value="conflict">Conflict</option>
              <option value="missing">Missing</option>
            </select>
          </label>
        </div>
        <div className="research-control-footer">
          <span>
            report_sections/zones.json · threshold is a view control until the returned section
            supplies a corroboration value.
          </span>
          <button
            className="research-button"
            type="button"
            onClick={() => void loadMatrix()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load corroboration source'}
          </button>
        </div>
      </div>
      {error ? <p className="research-error-copy">{error}</p> : null}
      {record ? (
        <div className="research-summary-strip">
          <ResearchDataCard label="Returned threshold" value={record.corroboration_threshold} />
          <ResearchDataCard label="Requested threshold" value={threshold} unit="view control" />
          <ResearchDataCard label="Status" value={record.corroboration_status} />
          <ResearchDataCard label="Independent line" value={record.independent_line} />
          <ResearchDataCard label="Selected cell" value={record.selected_cell} />
          <ResearchDataCard label="FDR status" value={record.fdr_status} />
          <ResearchDataCard label="Source mode" value={record.source_mode} />
          <ResearchDataCard label="Not a verdict" value={record.not_a_verdict} />
          <ResearchDataCard
            label="Limitations"
            value={record.limitation_refs ?? record.limitations}
          />
        </div>
      ) : null}
      {filteredCells.length ? (
        <div className="research-corroboration-layout">
          <div className="research-cell-list">
            {filteredCells.map((cell, index) => {
              const key = String(
                cell.cell_id ?? `${cell.period ?? ''}-${cell.pose_bin ?? ''}-${index}`,
              );
              return (
                <button
                  className={`research-corroboration-cell${selectedKey === key ? ' is-selected' : ''}`}
                  type="button"
                  key={key}
                  onClick={() => setSelectedKey(key)}
                >
                  <span>{researchValue(cell.period)}</span>
                  <strong>{researchValue(cell.pose_bin)}</strong>
                  <small>
                    {researchValue(cell.pair_count)} pairs · {researchValue(cell.fdr_count)} FDR
                  </small>
                  <ResearchStatus value={cell.status ?? cell.cell_status} />
                </button>
              );
            })}
          </div>
          <div className="research-cell-inspector">
            <div className="research-subsection-heading">
              <div>
                <span className="micro-label">Cell detail</span>
                <strong>
                  {selected
                    ? researchValue(selected.cell_id ?? selected.period)
                    : 'No cell selected'}
                </strong>
              </div>
              {selected ? <ResearchStatus value={selected.status ?? selected.cell_status} /> : null}
            </div>
            {selected ? (
              <>
                <div className="research-data-stack">
                  <ResearchDataCard label="Coverage" value={selected.coverage_state} />
                  <ResearchDataCard
                    label="Supporting count"
                    value={selected.supporting_pair_count}
                  />
                  <ResearchDataCard label="Period" value={selected.period} />
                  <ResearchDataCard label="Pose bin" value={selected.pose_bin} />
                  <ResearchDataCard label="Pair count" value={selected.pair_count} />
                  <ResearchDataCard label="FDR count" value={selected.fdr_count} />
                  <ResearchDataCard label="Coverage" value={selected.coverage_state} />
                  <ResearchDataCard label="Limited pairs" value={selected.limited_pairs} />
                  <ResearchDataCard label="Conflicting pairs" value={selected.conflicting_pairs} />
                  <ResearchDataCard label="Missing pairs" value={selected.missing_pairs} />
                  <ResearchDataCard
                    label="Source refs"
                    value={selected.source_refs ?? selected.source_ref}
                  />
                  <ResearchDataCard
                    label="Limitation refs"
                    value={selected.limitation_refs ?? selected.limitations}
                  />
                </div>
                <div className="research-inspector-lists">
                  <div>
                    <span className="micro-label">Supporting pairs</span>
                    {researchList(selected.supporting_pairs).length ? (
                      <ul>
                        {researchList(selected.supporting_pairs).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p>Unavailable</p>
                    )}
                  </div>
                  <div>
                    <span className="micro-label">Weakening / missing / conflict</span>
                    {researchList(
                      selected.weakening_pairs ?? selected.missing_pairs ?? selected.conflict_pairs,
                    ).length ? (
                      <ul>
                        {researchList(
                          selected.weakening_pairs ??
                            selected.missing_pairs ??
                            selected.conflict_pairs,
                        ).map((item) => (
                          <li key={item}>{item}</li>
                        ))}
                      </ul>
                    ) : (
                      <p>Unavailable</p>
                    )}
                  </div>
                </div>
                <div className="research-cross-links" aria-label="Corroboration transitions">
                  <span className="micro-label">Open related context</span>
                  <button
                    className="research-text-button"
                    type="button"
                    onClick={() => navigateTo('compare')}
                  >
                    Compare
                  </button>
                  <button
                    className="research-text-button"
                    type="button"
                    onClick={() => navigateTo('timeline')}
                  >
                    Timeline
                  </button>
                  <button
                    className="research-text-button"
                    type="button"
                    onClick={() => navigateTo('report')}
                  >
                    Report
                  </button>
                </div>
              </>
            ) : (
              <div className="research-no-data research-no-data--compact">
                Select a returned cell to inspect corroboration status.
              </div>
            )}
          </div>
        </div>
      ) : cells.length ? (
        <div className="research-no-data" role="status">
          <span className="research-empty-mark" aria-hidden="true" />
          <div>
            <strong>No returned corroboration cells match this status filter</strong>
            <span>
              The filter narrows returned cells; it does not turn missing or conflicting rows into a
              supporting result.
            </span>
          </div>
        </div>
      ) : (
        <div className="research-no-data" role="status">
          <span className="research-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty'
                ? 'No corroboration cells returned'
                : state === 'ready'
                  ? 'No corroboration rows returned for this source'
                  : 'No corroboration source loaded'}
            </strong>
            <span>Empty coverage is not a zero cell and is not rendered as corroboration.</span>
          </div>
        </div>
      )}
      <div className="research-verdict-note">
        <strong>Corroboration boundary</strong>
        <span>
          Repeated measurements, missing data and conflict statuses must remain separate;
          corroboration is not proof of identity.
        </span>
      </div>
      <ResearchSourceContext
        state={state}
        error={error}
        onRetry={() => void loadMatrix()}
        sourceRefs={researchPage.blocks[2].sourceRefs}
      />
    </section>
  );
}

function ResearchMotionPersistenceBlock() {
  const [photoA, setPhotoA] = useState(() => hashParam('photo_a'));
  const [photoB, setPhotoB] = useState(() => hashParam('photo_b'));
  const [pointSet, setPointSet] = useState(() => {
    const requested = hashParam('point_set').toLowerCase();
    return requested === '134' || requested === 'ldm134' ? '134' : '106';
  });
  const [space, setSpace] = useState(() => {
    const requested = hashParam('coordinate_space').toLowerCase();
    if (requested === 'raw_object_normalized') return 'raw';
    if (requested === 'original_image_px') return 'original';
    return requested === 'raw' || requested === 'original' ? requested : 'aligned';
  });
  const [timeView, setTimeView] = useState(() => hashParam('time_view') || 'pair');
  const [noiseThreshold, setNoiseThreshold] = useState(() => hashParam('noise_threshold'));
  const [anomalyThreshold, setAnomalyThreshold] = useState(() => hashParam('anomaly_threshold'));
  const [animated, setAnimated] = useState(false);
  const [state, setState] = useState<ResearchState>('idle');
  const [record, setRecord] = useState<ResearchRecord>();
  const [points, setPoints] = useState<readonly ResearchRecord[]>([]);
  const [chains, setChains] = useState<readonly ResearchRecord[]>([]);
  const [error, setError] = useState<string>();

  const loadMotion = async () => {
    const first = photoA.trim();
    const second = photoB.trim();
    if (!first || !second) {
      setState('error');
      setError('Enter both calculated photo IDs before requesting persistence data.');
      return;
    }
    setState('loading');
    setRecord(undefined);
    setPoints([]);
    setChains([]);
    setError(undefined);
    try {
      const [motionResult, changePointsResult] = await Promise.allSettled([
        requestUiArtifactJson<unknown>('report_sections/motion_maps.json'),
        requestUiArtifactJson<unknown>('report_sections/change_points.json'),
      ]);
      const motionPayload =
        motionResult.status === 'fulfilled' ? uiArtifactPayload(motionResult.value) : undefined;
      const changePointsPayload =
        changePointsResult.status === 'fulfilled'
          ? uiArtifactPayload(changePointsResult.value)
          : undefined;
      const motionRecord = researchRecord(motionPayload);
      const metricPoints = researchRows(motionPayload, [
        'motion_maps',
        'maps',
        'points',
        'motion_points',
        'point_status',
        'rows',
      ]).filter((row) => researchPairMatches(row, first, second));
      const metricChains = researchRows(motionPayload, ['persistence_chains', 'chains']).filter(
        (row) => researchPairMatches(row, first, second),
      );
      const artifactPoints = researchRows(changePointsPayload, [
        'change_points',
        'points',
        'events',
        'rows',
      ]).filter((row) => researchPairMatches(row, first, second));
      const artifactChains = researchRows(changePointsPayload, [
        'persistence_chains',
        'chains',
      ]).filter((row) => researchPairMatches(row, first, second));
      const returnedPoints = metricPoints.length ? metricPoints : artifactPoints;
      const returnedChains = metricChains.length ? metricChains : artifactChains;
      const returnedRecord = hasReturnedFields(motionRecord)
        ? motionRecord
        : researchRecord(changePointsPayload);
      setRecord(returnedRecord);
      setPoints(returnedPoints);
      setChains(returnedChains);
      const sourceErrors = [
        motionResult.status === 'rejected'
          ? `motion_maps.json: ${researchErrorMessage(motionResult.reason)}`
          : undefined,
        changePointsResult.status === 'rejected'
          ? `change_points.json: ${researchErrorMessage(changePointsResult.reason)}`
          : undefined,
      ].filter((value): value is string => Boolean(value));
      setError(sourceErrors.length ? sourceErrors.join(' · ') : undefined);
      setState(
        returnedPoints.length || returnedChains.length || hasReturnedFields(returnedRecord)
          ? 'ready'
          : sourceErrors.length
            ? 'error'
            : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(researchErrorMessage(requestError));
    }
  };

  const visiblePoints = points.filter((point) => {
    const returnedPointSet = point.point_set ?? record?.point_set;
    const returnedSpace = point.coordinate_space ?? record?.coordinate_space;
    return (
      researchPointSetMatches(returnedPointSet, pointSet) &&
      researchSpaceMatches(returnedSpace, space)
    );
  });

  return (
    <section
      className="detail-block detail-block--research"
      aria-labelledby="research-motion-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / research.motion-persistence</span>
          <h3 id="research-motion-title">Key Points, persistence and review boundary</h3>
          <p>
            Point-set, coordinate, noise and anomaly controls stay attached to the returned pair
            motion and persistence chain.
          </p>
        </div>
        <ResearchStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="research-control-panel">
        <div className="research-field-row">
          <ResearchTextField
            label="Photo A"
            value={photoA}
            onChange={setPhotoA}
            placeholder="calculated photo_id"
          />
          <ResearchTextField
            label="Photo B"
            value={photoB}
            onChange={setPhotoB}
            placeholder="calculated photo_id"
          />
          <label className="research-field">
            <span>Point set</span>
            <select value={pointSet} onChange={(event) => setPointSet(event.target.value)}>
              <option value="106">LDM106</option>
              <option value="134">LDM134</option>
            </select>
          </label>
          <label className="research-field">
            <span>Coordinate space</span>
            <select value={space} onChange={(event) => setSpace(event.target.value)}>
              <option value="raw">Raw</option>
              <option value="aligned">Aligned</option>
              <option value="original">Original</option>
            </select>
          </label>
          <ResearchTextField
            label="Noise threshold"
            value={noiseThreshold}
            onChange={setNoiseThreshold}
            placeholder="returned threshold"
          />
          <ResearchTextField
            label="Anomaly threshold"
            value={anomalyThreshold}
            onChange={setAnomalyThreshold}
            placeholder="returned threshold"
          />
          <label className="research-field">
            <span>Time view</span>
            <select value={timeView} onChange={(event) => setTimeView(event.target.value)}>
              <option value="pair">Pair</option>
              <option value="chain">Persistence chain</option>
              <option value="timeline">Timeline</option>
            </select>
          </label>
        </div>
        <div className="research-control-footer">
          <span>
            report_sections/motion_maps.json + report_sections/change_points.json · no motion is
            calculated in the browser.
          </span>
          <div className="research-control-actions">
            <label className="research-checkbox">
              <input
                type="checkbox"
                checked={animated}
                onChange={(event) => setAnimated(event.target.checked)}
              />{' '}
              Animation sequence
            </label>
            <button
              className="research-button"
              type="button"
              onClick={() => void loadMotion()}
              disabled={state === 'loading'}
            >
              {state === 'loading' ? 'Loading…' : 'Load persistence source'}
            </button>
          </div>
        </div>
      </div>
      {error ? <p className="research-error-copy">{error}</p> : null}
      {record ? (
        <div className="research-summary-strip">
          <ResearchDataCard label="Pair" value={record.pair_id} />
          <ResearchDataCard label="Point set returned" value={record.point_set} />
          <ResearchDataCard label="Coordinate space returned" value={record.coordinate_space} />
          <ResearchDataCard label="Pose leakage" value={record.pose_leakage_limited} />
          <ResearchDataCard label="Coherent motion" value={record.coherent_motion_fraction} />
          <ResearchDataCard label="Identity-only RMSE" value={record.identity_only_motion_rmse} />
          <ResearchDataCard label="Expression influence" value={record.expression_influence} />
          <ResearchDataCard label="Noise threshold returned" value={record.noise_threshold} />
          <ResearchDataCard label="Anomaly threshold returned" value={record.anomaly_threshold} />
          <ResearchDataCard
            label="Requested noise threshold"
            value={noiseThreshold}
            unit="view control"
          />
          <ResearchDataCard
            label="Requested anomaly threshold"
            value={anomalyThreshold}
            unit="view control"
          />
          <ResearchDataCard label="Point count returned" value={record.point_count} />
          <ResearchDataCard label="Chain count returned" value={record.chain_count} />
          <ResearchDataCard
            label="Point rows in response"
            value={points.length}
            unit="returned rows"
          />
          <ResearchDataCard
            label="Chain rows in response"
            value={chains.length}
            unit="returned rows"
          />
          <ResearchDataCard label="Calibration" value={record.calibration_status} />
          <ResearchDataCard
            label="Limitation refs"
            value={record.limitation_refs ?? record.limitations}
          />
        </div>
      ) : null}
      {visiblePoints.length ? (
        <div className="research-motion-table-wrap">
          <table className="research-motion-table">
            <caption>
              Returned point status · set: {pointSet} · space: {space} · view: {timeView} ·
              animation: {animated ? 'on' : 'off'}
            </caption>
            <thead>
              <tr>
                <th scope="col">Point</th>
                <th scope="col">dx</th>
                <th scope="col">dy</th>
                <th scope="col">dz</th>
                <th scope="col">Magnitude</th>
                <th scope="col">Visibility A/B</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {visiblePoints.map((point, index) => (
                <tr key={String(point.point_index ?? index)}>
                  <th scope="row">{researchValue(point.point_index ?? index)}</th>
                  <td>{researchValue(point.dx)}</td>
                  <td>{researchValue(point.dy)}</td>
                  <td>{researchValue(point.dz)}</td>
                  <td>{researchValue(point.magnitude)}</td>
                  <td>
                    {researchValue(point.visibility_a)} / {researchValue(point.visibility_b)}
                  </td>
                  <td>
                    <ResearchStatus value={point.point_status ?? point.status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      {chains.length ? (
        <div className="research-chain-list">
          <div className="research-subsection-heading">
            <div>
              <span className="micro-label">Persistence chains</span>
              <strong>Returned chains</strong>
            </div>
          </div>
          {chains.map((chain, index) => (
            <div className="research-chain-card" key={String(chain.chain_id ?? index)}>
              <strong>{researchValue(chain.chain_id)}</strong>
              <span>
                {researchValue(chain.start_date)} → {researchValue(chain.end_date)}
              </span>
              <span>
                length: {researchValue(chain.length)} · max gap: {researchValue(chain.max_gap)}
              </span>
              <ResearchStatus value={chain.chain_status} />
            </div>
          ))}
        </div>
      ) : null}
      <div className="research-cross-links" aria-label="Motion context transitions">
        <span className="micro-label">Open related context</span>
        <button
          className="research-text-button"
          type="button"
          onClick={() => navigateTo('compare', { photo_a: photoA.trim(), photo_b: photoB.trim() })}
          disabled={!photoA.trim() || !photoB.trim()}
        >
          Compare
        </button>
        <button
          className="research-text-button"
          type="button"
          onClick={() => navigateTo('timeline')}
        >
          Timeline
        </button>
        <button
          className="research-text-button"
          type="button"
          onClick={() => navigateTo('methodology')}
        >
          Methodology
        </button>
      </div>
      {points.length && !visiblePoints.length ? (
        <div className="research-no-data research-no-data--compact" role="status">
          <span className="research-empty-mark" aria-hidden="true" />
          <div>
            <strong>No returned points match the selected set or coordinate space</strong>
            <span>Filters narrow returned point rows; they do not transform coordinates.</span>
          </div>
        </div>
      ) : null}
      {!points.length && !chains.length ? (
        <div className="research-no-data" role="status">
          <span className="research-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty'
                ? 'No point or chain records returned'
                : 'No persistence source loaded'}
            </strong>
            <span>
              Landmark vectors, anomaly rows and persistence chains are not synthesized without
              calculated response data.
            </span>
          </div>
        </div>
      ) : null}
      <div className="research-verdict-note">
        <strong>Motion boundary</strong>
        <span>
          Visibility, pose leakage, expression influence, calibration and coordinate space qualify
          any motion reading. A persistent vector is not an identity conclusion.
        </span>
      </div>
      <ResearchSourceContext
        state={state}
        error={error}
        onRetry={() => void loadMotion()}
        sourceRefs={researchPage.blocks[3].sourceRefs}
      />
    </section>
  );
}

export function ResearchPage() {
  const renderBlock = (block: BlockDefinition) => {
    switch (block.id) {
      case 'research.zone-atlas':
        return <ResearchZoneAtlasBlock />;
      case 'research.casework-queue':
        return <ResearchCaseworkBlock />;
      case 'research.corroboration':
        return <ResearchCorroborationBlock />;
      case 'research.motion-persistence':
        return <ResearchMotionPersistenceBlock />;
      default:
        return null;
    }
  };

  return <PageBlueprint definition={researchPage} renderBlock={renderBlock} />;
}
