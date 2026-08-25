import { useMemo, useState } from 'react';

import {
  ApiRequestError,
  isAbortError,
  postJson,
  requestJson,
  unwrapArtifactPayload,
} from '@/shared/api';
import { PageBlueprint } from '@/shared/PageBlueprint';
import { navigateTo } from '@/shared/navigation';
import type { BlockDefinition, PageDefinition } from '@/shared/contracts';

/**
 * PAGE: Methodology.
 * Blocks are semantic ownership boundaries. Their internal controls and views stay together;
 * the page owner is free to choose the eventual composition.
 */
export const methodologyPage = {
  id: 'methodology',
  title: 'Methodology',
  group: 'research',
  purpose:
    'Единый справочный слой pipeline, качества, coordinate spaces, gates, calibration, metrics и integrity.',
  primaryQuestion:
    'Можно ли понять происхождение, качество и ограничения каждого аналитического результата?',
  blocks: [
    /**
     * BLOCK: Pipeline, archive quality and gates.
     * OWNED ELEMENTS: Stage 1/2/2B/3 pipeline status, archive date and pose coverage, coordinate-space reference, quality, visibility, expression, pose and calibration gates, source and integrity transitions.
     * CONTRACT SURFACE: elements: multiple-testing and texture eligibility gates, legacy/private quarantine policy, source key and artifact availability context; actions: open_calibration, open_metrics, open_quarantine_policy; states: measured, not_computed, skipped, not_applicable, stale.
     * stage1_ready, stage2_ready, stage3_ready, storage_root, stage1_root, stage2_root, stage3_root, health_status.
     * DATA KEYS:
     * multiple_testing_status, texture_eligibility, expression_gate_status, pose_distance, calibration_status, private_hypothesis_status, legacy_status, quarantine_status, artifact_status, stage_status, relative_path, file_name, artifact_type, availability, created_at.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * stage_id, stage_name, status, input_refs, output_refs, schema_version, generated_at,
     * error_count, date_coverage, pose_coverage, frame_count, pair_count, missing_count, early_period_density,
     * late_period_density, quality_state, space_id, label, dimensions, unit, transform_ref,
     * valid_metrics, invalid_mixes, gate_id, threshold, gate_status, affected_metrics, reason.
     */
    {
      id: 'methodology.pipeline',
      title: 'Pipeline, archive quality and gates',
      purpose:
        'Самостоятельный справочный блок происхождения анализа: этапы, покрытие архива, пространства координат и условия применимости.',
      elements: [
        'multiple-testing and texture eligibility gates',
        'legacy/private quarantine policy',
        'source key and artifact availability context',
        'Stage 1/2/2B/3 pipeline status',
        'archive date and pose coverage',
        'coordinate-space reference',
        'quality, visibility, expression, pose and calibration gates',
        'source and integrity transitions',
      ],
      keys: [
        'stage1_ready',
        'stage2_ready',
        'stage3_ready',
        'storage_root',
        'stage1_root',
        'stage2_root',
        'stage3_root',
        'health_status',
        'multiple_testing_status',
        'texture_eligibility',
        'expression_gate_status',
        'pose_distance',
        'calibration_status',
        'private_hypothesis_status',
        'legacy_status',
        'quarantine_status',
        'artifact_status',
        'stage_status',
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
        'visibility_state',
        'calibration_state',
        'schema',
        'source_mode',
        'not_a_verdict',
        'stage_id',
        'stage_name',
        'status',
        'input_refs',
        'output_refs',
        'schema_version',
        'generated_at',
        'error_count',
        'date_coverage',
        'pose_coverage',
        'frame_count',
        'pair_count',
        'missing_count',
        'early_period_density',
        'late_period_density',
        'quality_state',
        'space_id',
        'label',
        'dimensions',
        'unit',
        'transform_ref',
        'valid_metrics',
        'invalid_mixes',
        'gate_id',
        'threshold',
        'gate_status',
        'affected_metrics',
        'reason',
      ],
      sourceRefs: [
        'stage1/stage1_manifest.json → api/v1/health',
        'stage2/analysis_manifest.json → ui_artifacts/report_meta.json',
        'stage2b/stage2b_manifest.json',
        'stage1/main_timeline.csv → api/v1/photos',
        'stage1/<photo_id>/info.json → api/v1/photos/{photo_id}/info_keys',
        'ui_artifacts/report_meta.json',
        'api/v1/health',
        'api/v1/system/health',
        'api/v1/settings',
      ],
      actions: [
        'open_calibration',
        'open_metrics',
        'open_quarantine_policy',
        'open_stage_source',
        'open_integrity',
        'open_timeline',
        'select_space',
        'select_gate',
        'open_metric_definition',
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
     * BLOCK: Calibration and metrics reference.
     * OWNED ELEMENTS: metric catalog and family filtering, permitted and forbidden interpretation, calibration values and reference lines, metric, pose and zone selection, sensitivity status, source and limitations.
     * CONTRACT SURFACE: elements: pose-bin health and elevated counts, proxy/confidence explanation, noise-model and sensitivity controls, calibration artifact list; actions: open_health, match_calibration_frames, subtract_noise, open_noise_model, select_zone, open_pair; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * bin_health, elevated_count, proxy_status, confidence, recommendations, calibration_artifacts, dataset_size, dataset_composition, tolerance, compensated_metrics, uncompensated_metrics, noise_model, coverage, matched_frames, photo_id, yaw, pitch, roll, sample, relative_path, file_name, artifact_type, availability, created_at.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * calibration_dataset_id, metric, pose_bin, zone_id, sample_count, values, unit,
     * median, p90, p95, max, reference_line, threshold, health_status,
     * sensitivity_status, limitation_refs, metric_name, label, family, status, pair_coverage_fraction,
     * pair_value_count, purpose, plain_language_meaning, formula, coordinate_space, allowed_interpretation, forbidden_interpretation.
     */
    {
      id: 'methodology.calibration',
      title: 'Calibration and metrics reference',
      purpose:
        'Самостоятельный reference-блок для calibration distributions, sensitivity, каталога метрик и допустимых интерпретаций.',
      elements: [
        'pose-bin health and elevated counts',
        'proxy/confidence explanation',
        'noise-model and sensitivity controls',
        'calibration artifact list',
        'metric catalog and family filtering',
        'permitted and forbidden interpretation',
        'calibration values and reference lines',
        'metric, pose and zone selection',
        'sensitivity status, source and limitations',
      ],
      keys: [
        'bin_health',
        'elevated_count',
        'proxy_status',
        'confidence',
        'recommendations',
        'calibration_artifacts',
        'dataset_size',
        'dataset_composition',
        'tolerance',
        'compensated_metrics',
        'uncompensated_metrics',
        'noise_model',
        'coverage',
        'matched_frames',
        'photo_id',
        'yaw',
        'pitch',
        'roll',
        'sample',
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
        'calibration_dataset_id',
        'metric',
        'pose_bin',
        'zone_id',
        'sample_count',
        'values',
        'unit',
        'median',
        'p90',
        'p95',
        'max',
        'reference_line',
        'threshold',
        'health_status',
        'sensitivity_status',
        'limitation_refs',
        'metric_name',
        'label',
        'family',
        'status',
        'pair_coverage_fraction',
        'pair_value_count',
        'purpose',
        'plain_language_meaning',
        'formula',
        'coordinate_space',
        'allowed_interpretation',
        'forbidden_interpretation',
      ],
      sourceRefs: [
        'stage2/analysis_manifest.json → ui_artifacts/report_meta.json',
        'stage2/metric_catalog.json → api/v1/run/artifacts/metric_catalog',
        'api/v1/calibration/health',
        'api/v1/calibration/match',
        'api/v1/calibration/subtract_noise',
        'api/v1/calibration/noise_model',
        'ui_artifacts/report_meta.json',
      ],
      actions: [
        'open_health',
        'match_calibration_frames',
        'subtract_noise',
        'open_noise_model',
        'select_zone',
        'open_pair',
        'select_metric',
        'select_pose_bin',
        'open_source',
        'open_limitation',
        'filter_by_family',
        'copy_metric_ref',
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
        'loading',
        'long_content',
      ],
    },
    /**
     * BLOCK: Integrity, connectivity and source registry.
     * OWNED ELEMENTS: integrity status and schema checks, connectivity and coverage checks, exceptions and quarantine registry, source registry with exact paths and keys, remediation and affected-area context.
     * CONTRACT SURFACE: elements: q-value and identifier checks, missing-artifact and manifest-count checks, private/legacy and proxy registry; actions: open_quarantine_policy, open_manifest, open_metric_definition; states: measured, not_computed, skipped, not_applicable, stale.
     * detail, http_status, error_code, error_detail.
     * DATA KEYS:
     * q_value, identifier_status, missing_artifacts, manifest_counts, blocking, private_legacy_status, proxy_status.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * overall_status, schema_version, warning_count, error_count, review_count, generated_at, run_id,
     * check_id, field_name, expected_type, actual_type, required, enum_values, status,
     * error_message, relation_type, source_id, target_id, orphan_type, expected_count, actual_count,
     * coverage_type, available_count, fraction, date_range, pose_bins, ldm_status, mesh_status,
     * texture_status, calibration_status, exception_id, module, severity, reason, affected_routes,
     * artifact_ref, can_recalculate, remediation, material_type, quarantine_status, allowed_contexts, forbidden_contexts,
     * recheck_route, stage, relative_path, file_name, json_key, csv_column, artifact_type,
     * created_at, availability, data_snapshot.
     */
    {
      id: 'methodology.integrity',
      title: 'Integrity, connectivity and source registry',
      purpose:
        'Самостоятельный операционный блок проверки схемы, связности, покрытия, исключений, quarantine и исходных файлов.',
      elements: [
        'q-value and identifier checks',
        'missing-artifact and manifest-count checks',
        'private/legacy and proxy registry',
        'integrity status and schema checks',
        'connectivity and coverage checks',
        'exceptions and quarantine registry',
        'source registry with exact paths and keys',
        'remediation and affected-area context',
      ],
      keys: [
        'detail',
        'http_status',
        'error_code',
        'error_detail',
        'q_value',
        'identifier_status',
        'missing_artifacts',
        'manifest_counts',
        'blocking',
        'private_legacy_status',
        'proxy_status',
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
        'overall_status',
        'schema_version',
        'warning_count',
        'error_count',
        'review_count',
        'generated_at',
        'run_id',
        'check_id',
        'field_name',
        'expected_type',
        'actual_type',
        'required',
        'enum_values',
        'status',
        'error_message',
        'relation_type',
        'source_id',
        'target_id',
        'orphan_type',
        'expected_count',
        'actual_count',
        'coverage_type',
        'available_count',
        'fraction',
        'date_range',
        'pose_bins',
        'ldm_status',
        'mesh_status',
        'texture_status',
        'calibration_status',
        'exception_id',
        'module',
        'severity',
        'reason',
        'affected_routes',
        'artifact_ref',
        'can_recalculate',
        'remediation',
        'material_type',
        'quarantine_status',
        'allowed_contexts',
        'forbidden_contexts',
        'recheck_route',
        'stage',
        'relative_path',
        'file_name',
        'json_key',
        'csv_column',
        'artifact_type',
        'created_at',
        'availability',
        'data_snapshot',
      ],
      sourceRefs: [
        'stage1/stage1_manifest.json',
        'stage2/analysis_manifest.json → ui_artifacts/report_meta.json',
        'stage2/metric_catalog.json',
        'stage1/main_timeline.csv → api/v1/photos',
        'stage2/artifact_index.json',
        'stage2b/private_summary.json',
        'ui_artifacts/report_meta.json',
        'api/v1/system/health',
        'api/v1/settings',
      ],
      actions: [
        'open_quarantine_policy',
        'open_manifest',
        'open_metric_definition',
        'refresh_checks',
        'select_check',
        'open_source',
        'mark_for_repair',
        'open_object',
        'open_timeline',
        'open_affected_route',
        'request_recalculation',
        'request_recheck',
        'copy_source_ref',
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
  ],
} satisfies PageDefinition;

type MethodologyState = 'idle' | 'loading' | 'ready' | 'empty' | 'error';
type MethodologyRecord = Record<string, unknown>;

function methodologyRecord(payload: unknown): MethodologyRecord {
  return payload && typeof payload === 'object' && !Array.isArray(payload)
    ? (payload as MethodologyRecord)
    : {};
}

function hasMethodologyFields(record: MethodologyRecord): boolean {
  return Object.entries(record).some(
    ([key, value]) =>
      !['schema', 'source_mode', 'not_a_verdict'].includes(key) &&
      value !== null &&
      value !== undefined,
  );
}

function methodologyRows(payload: unknown, keys: readonly string[]): readonly MethodologyRecord[] {
  if (Array.isArray(payload))
    return payload.flatMap((entry) =>
      entry && typeof entry === 'object' ? [entry as MethodologyRecord] : [],
    );
  const record = methodologyRecord(payload);
  for (const key of keys) {
    if (Array.isArray(record[key]))
      return (record[key] as unknown[]).flatMap((entry) =>
        entry && typeof entry === 'object' ? [entry as MethodologyRecord] : [],
      );
    const mapped = record[key];
    if (mapped && typeof mapped === 'object' && !Array.isArray(mapped)) {
      return Object.entries(mapped).flatMap(([mapKey, entry]) => {
        if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return [];
        const row = { ...(entry as MethodologyRecord) };
        if (row.pose_bin === undefined) row.pose_bin = mapKey;
        if (row.id === undefined) row.id = mapKey;
        return [row];
      });
    }
  }
  return [];
}

function methodologyValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Unavailable';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return 'Structured value';
  return String(value);
}

function methodologyTone(value: unknown): 'positive' | 'warning' | 'muted' {
  if (value === true) return 'positive';
  if (value === false) return 'warning';
  if (typeof value !== 'string') return 'muted';
  if (
    [
      'ready',
      'valid',
      'pass',
      'complete',
      'supported',
      'available',
      'measured',
      'ok',
      'matched',
    ].includes(value)
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
      'blocking',
      'not_applicable',
      'no_candidates',
    ].includes(value)
  )
    return 'warning';
  return 'muted';
}

function MethodologyStatus({ value, label }: { value: unknown; label?: string }) {
  const tone = methodologyTone(value);
  return (
    <span className={`methodology-status methodology-status--${tone}`}>
      <span className="methodology-status-dot" aria-hidden="true" />
      {label ?? methodologyValue(value)}
    </span>
  );
}

function methodologyErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.detail;
  return 'Источник данных недоступен.';
}

function MethodologySourceContext({
  state,
  error,
  sourceRefs,
  onRetry,
}: {
  state: MethodologyState;
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
    <aside className="methodology-source-context" aria-label="Контекст источника Methodology">
      <div className="methodology-source-heading">
        <div>
          <span className="micro-label">Evidence boundary</span>
          <strong>{label}</strong>
        </div>
        <MethodologyStatus value={state === 'ready' ? 'measured' : state} />
      </div>
      <div className="methodology-source-flags">
        <code>source_mode: research</code>
        <code>not_a_verdict: true</code>
      </div>
      {error ? <p className="methodology-error-copy">{error}</p> : null}
      {state === 'error' && onRetry ? (
        <button
          className="methodology-button methodology-button--quiet"
          type="button"
          onClick={onRetry}
        >
          Retry source request
        </button>
      ) : null}
      <details className="methodology-source-details">
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

function MethodologyDataCard({
  label,
  value,
  unit,
}: {
  label: string;
  value: unknown;
  unit?: string;
}) {
  return (
    <div className="methodology-data-card">
      <span>{label}</span>
      <strong>{methodologyValue(value)}</strong>
      <small>{unit ?? 'source field'}</small>
    </div>
  );
}

function MethodologyField({
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
    <label className="methodology-field">
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

function MethodologyPipelineBlock() {
  const [stageFilter, setStageFilter] = useState('all');
  const [gateFilter, setGateFilter] = useState('all');
  const [state, setState] = useState<MethodologyState>('idle');
  const [record, setRecord] = useState<MethodologyRecord>();
  const [stages, setStages] = useState<readonly MethodologyRecord[]>([]);
  const [gates, setGates] = useState<readonly MethodologyRecord[]>([]);
  const [error, setError] = useState<string>();

  const loadPipeline = async () => {
    setState('loading');
    setRecord(undefined);
    setStages([]);
    setGates([]);
    setError(undefined);
    try {
      const response = await requestJson<unknown>('/api/v1/health');
      const returnedPayload = unwrapArtifactPayload(response);
      const returnedRecord = methodologyRecord(returnedPayload);
      const returnedStages = methodologyRows(returnedPayload, [
        'stages',
        'pipeline',
        'stage_status',
      ]);
      const returnedGates = methodologyRows(returnedPayload, ['gates', 'gate_status', 'checks']);
      setRecord(returnedRecord);
      setStages(returnedStages);
      setGates(returnedGates);
      setState(
        returnedStages.length || returnedGates.length || hasMethodologyFields(returnedRecord)
          ? 'ready'
          : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(methodologyErrorMessage(requestError));
    }
  };
  const filteredStages = stages.filter(
    (stage) =>
      stageFilter === 'all' ||
      String(stage.stage_id ?? stage.stage_name ?? stage.id ?? '') === stageFilter,
  );
  const filteredGates = gates.filter(
    (gate) =>
      gateFilter === 'all' ||
      String(gate.gate_id ?? gate.field_name ?? gate.id ?? '') === gateFilter,
  );

  return (
    <section
      className="detail-block detail-block--methodology"
      aria-labelledby="methodology-pipeline-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / methodology.pipeline</span>
          <h3 id="methodology-pipeline-title">Pipeline, archive quality and gates</h3>
          <p>
            Stage readiness, archive coverage, coordinate spaces and applicability gates stay
            attached to their health source.
          </p>
        </div>
        <MethodologyStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="methodology-control-panel">
        <div className="methodology-field-row">
          <label className="methodology-field">
            <span>Stage</span>
            <select value={stageFilter} onChange={(event) => setStageFilter(event.target.value)}>
              <option value="all">All returned stages</option>
              {stages.map((stage, index) => {
                const key = String(stage.stage_id ?? stage.stage_name ?? stage.id ?? index);
                return (
                  <option key={key} value={key}>
                    {key}
                  </option>
                );
              })}
            </select>
          </label>
          <label className="methodology-field">
            <span>Gate</span>
            <select value={gateFilter} onChange={(event) => setGateFilter(event.target.value)}>
              <option value="all">All returned gates</option>
              {gates.map((gate, index) => {
                const key = String(gate.gate_id ?? gate.field_name ?? gate.id ?? index);
                return (
                  <option key={key} value={key}>
                    {key}
                  </option>
                );
              })}
            </select>
          </label>
        </div>
        <div className="methodology-control-footer">
          <span>
            GET /api/v1/health · no readiness status is assumed before the source returns.
          </span>
          <button
            className="methodology-button"
            type="button"
            onClick={() => void loadPipeline()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load health and gates'}
          </button>
        </div>
      </div>
      {error ? <p className="methodology-error-copy">{error}</p> : null}
      {record ? (
        <div className="methodology-summary-strip">
          <MethodologyDataCard
            label="Overall"
            value={record.health_status ?? record.status ?? record.overall_status}
          />
          <MethodologyDataCard label="Stage 1" value={record.stage1_ready} />
          <MethodologyDataCard label="Stage 2" value={record.stage2_ready} />
          <MethodologyDataCard label="Stage 3" value={record.stage3_ready} />
          <MethodologyDataCard label="Stage 2 status" value={record.stage2_status} />
          <MethodologyDataCard label="Run ID" value={record.run_id} />
          <MethodologyDataCard label="Date coverage" value={record.date_coverage} />
          <MethodologyDataCard label="Pose coverage" value={record.pose_coverage} />
          <MethodologyDataCard label="Frame count" value={record.frame_count} />
          <MethodologyDataCard label="Pair count" value={record.pair_count} />
          <MethodologyDataCard
            label="Quality gate"
            value={record.quality_gate ?? record.quality_status}
          />
          <MethodologyDataCard
            label="Visibility gate"
            value={record.visibility_gate ?? record.visibility_status}
          />
          <MethodologyDataCard
            label="Calibration gate"
            value={record.calibration_gate ?? record.calibration_status}
          />
          <MethodologyDataCard
            label="Expression gate"
            value={record.expression_gate ?? record.expression_status}
          />
          <MethodologyDataCard label="Source mode" value={record.source_mode} />
          <MethodologyDataCard label="Not a verdict" value={record.not_a_verdict} />
          <MethodologyDataCard
            label="Limitations"
            value={record.limitation_refs ?? record.limitations}
          />
        </div>
      ) : null}
      {filteredStages.length || filteredGates.length ? (
        <div className="methodology-pipeline-layout">
          <div className="methodology-pipeline-list">
            <div className="methodology-subsection-heading">
              <div>
                <span className="micro-label">Stages</span>
                <strong>Returned pipeline state</strong>
              </div>
            </div>
            {filteredStages.length ? (
              filteredStages.map((stage, index) => (
                <div
                  className="methodology-stage-row"
                  key={String(stage.stage_id ?? stage.stage_name ?? index)}
                >
                  <div>
                    <strong>{methodologyValue(stage.stage_name ?? stage.stage_id)}</strong>
                    <span>
                      {methodologyValue(stage.schema_version)} · generated{' '}
                      {methodologyValue(stage.generated_at)}
                    </span>
                  </div>
                  <MethodologyStatus value={stage.status ?? stage.stage_status} />
                </div>
              ))
            ) : (
              <div className="methodology-no-data methodology-no-data--compact">
                No stage rows returned.
              </div>
            )}
          </div>
          <div className="methodology-gate-list">
            <div className="methodology-subsection-heading">
              <div>
                <span className="micro-label">Applicability gates</span>
                <strong>Returned gate state</strong>
              </div>
            </div>
            {filteredGates.length ? (
              filteredGates.map((gate, index) => (
                <div
                  className="methodology-gate-row"
                  key={String(gate.gate_id ?? gate.field_name ?? index)}
                >
                  <div>
                    <strong>{methodologyValue(gate.gate_id ?? gate.field_name)}</strong>
                    <span>{methodologyValue(gate.reason ?? gate.affected_metrics)}</span>
                  </div>
                  <MethodologyStatus value={gate.gate_status ?? gate.status} />
                </div>
              ))
            ) : (
              <div className="methodology-no-data methodology-no-data--compact">
                No gate rows returned.
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="methodology-no-data" role="status">
          <span className="methodology-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty'
                ? 'No health fields returned'
                : state === 'ready'
                  ? 'No stage or gate rows returned by the health endpoint'
                  : 'No health source loaded'}
            </strong>
            <span>
              Stage, gate and coverage values are not invented when the health endpoint is empty.
            </span>
          </div>
        </div>
      )}
      <div className="methodology-cross-links" aria-label="Methodology context transitions">
        <span className="micro-label">Open related context</span>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('timeline')}
        >
          Timeline
        </button>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('research')}
        >
          Research
        </button>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('compare')}
        >
          Compare
        </button>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('report')}
        >
          Report
        </button>
      </div>
      <div className="methodology-verdict-note">
        <strong>Method boundary</strong>
        <span>
          Readiness, quality, visibility, expression, pose and calibration gates qualify later
          results; they do not produce an identity verdict.
        </span>
      </div>
      <MethodologySourceContext
        state={state}
        error={error}
        onRetry={() => void loadPipeline()}
        sourceRefs={methodologyPage.blocks[0].sourceRefs}
      />
    </section>
  );
}

function MethodologyCalibrationBlock() {
  const [metric, setMetric] = useState('');
  const [poseBin, setPoseBin] = useState('');
  const [zoneId, setZoneId] = useState('');
  const [family, setFamily] = useState('');
  const [photoId, setPhotoId] = useState('');
  const [yaw, setYaw] = useState('');
  const [pitch, setPitch] = useState('');
  const [roll, setRoll] = useState('');
  const [sample, setSample] = useState('');
  const [photoA, setPhotoA] = useState('');
  const [photoB, setPhotoB] = useState('');
  const [toleranceYaw, setToleranceYaw] = useState('');
  const [tolerancePitch, setTolerancePitch] = useState('');
  const [toleranceRoll, setToleranceRoll] = useState('');
  const [state, setState] = useState<MethodologyState>('idle');
  const [record, setRecord] = useState<MethodologyRecord>();
  const [rows, setRows] = useState<readonly MethodologyRecord[]>([]);
  const [metricCatalog, setMetricCatalog] = useState<readonly MethodologyRecord[]>([]);
  const [metricCatalogState, setMetricCatalogState] = useState<MethodologyState>('idle');
  const [metricCatalogError, setMetricCatalogError] = useState<string>();
  const [matchedFrames, setMatchedFrames] = useState<readonly MethodologyRecord[]>([]);
  const [matchStatus, setMatchStatus] = useState<unknown>();
  const [matchState, setMatchState] = useState<MethodologyState>('idle');
  const [matchError, setMatchError] = useState<string>();
  const [noiseModel, setNoiseModel] = useState<MethodologyRecord>();
  const [noiseState, setNoiseState] = useState<MethodologyState>('idle');
  const [noiseError, setNoiseError] = useState<string>();
  const [subtracted, setSubtracted] = useState<MethodologyRecord>();
  const [subtractState, setSubtractState] = useState<MethodologyState>('idle');
  const [subtractError, setSubtractError] = useState<string>();
  const [error, setError] = useState<string>();

  const loadCalibration = async () => {
    setState('loading');
    setRecord(undefined);
    setRows([]);
    setError(undefined);
    try {
      const response = await requestJson<unknown>('/api/v1/calibration/health');
      const returnedPayload = unwrapArtifactPayload(response);
      const returnedRecord = methodologyRecord(returnedPayload);
      const returnedRows = methodologyRows(returnedPayload, [
        'bin_health',
        'buckets',
        'calibration_artifacts',
        'metrics',
        'values',
        'rows',
      ]);
      setRecord(returnedRecord);
      setRows(returnedRows);
      setState(returnedRows.length || hasMethodologyFields(returnedRecord) ? 'ready' : 'empty');
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(methodologyErrorMessage(requestError));
    }
  };

  const loadMetricCatalog = async () => {
    setMetricCatalogState('loading');
    setMetricCatalogError(undefined);
    try {
      const response = await requestJson<unknown>('/api/v1/run/artifacts/metric_catalog');
      const returnedPayload = unwrapArtifactPayload(response);
      const returnedRows = methodologyRows(returnedPayload, ['metrics', 'items', 'catalog']);
      const returnedRecord = methodologyRecord(returnedPayload);
      setMetricCatalog(returnedRows);
      setMetricCatalogState(
        returnedRows.length || hasMethodologyFields(returnedRecord) ? 'ready' : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setMetricCatalog([]);
      setMetricCatalogState('error');
      setMetricCatalogError(methodologyErrorMessage(requestError));
    }
  };

  const loadMatchedFrames = async () => {
    const params = new URLSearchParams();
    if (photoId.trim()) params.set('photo_id', photoId.trim());
    if (poseBin.trim()) params.set('pose_bin', poseBin.trim());
    if (yaw.trim()) params.set('yaw', yaw.trim());
    if (pitch.trim()) params.set('pitch', pitch.trim());
    if (roll.trim()) params.set('roll', roll.trim());
    if (!params.size) {
      setMatchState('error');
      setMatchStatus(undefined);
      setMatchError(
        'Enter a returned photo_id or pose context before matching calibration frames.',
      );
      setMatchedFrames([]);
      return;
    }
    setMatchState('loading');
    setMatchStatus(undefined);
    setMatchError(undefined);
    try {
      const response = await requestJson<unknown>(`/api/v1/calibration/match?${params.toString()}`);
      const returnedPayload = unwrapArtifactPayload(response);
      const returnedRecord = methodologyRecord(returnedPayload);
      const returnedRows = methodologyRows(returnedPayload, [
        'matched_frames',
        'frames',
        'matches',
        'candidates',
        'rows',
      ]);
      setMatchedFrames(returnedRows);
      setMatchStatus(returnedRecord.status);
      setMatchState(
        returnedRows.length || hasMethodologyFields(returnedRecord) ? 'ready' : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setMatchState('error');
      setMatchStatus(undefined);
      setMatchError(methodologyErrorMessage(requestError));
      setMatchedFrames([]);
    }
  };

  const loadNoiseModel = async () => {
    const params = new URLSearchParams();
    if (yaw.trim()) params.set('yaw', yaw.trim());
    if (pitch.trim()) params.set('pitch', pitch.trim());
    if (roll.trim()) params.set('roll', roll.trim());
    if (sample.trim()) params.set('sample', sample.trim());
    if (!params.size) {
      setNoiseState('error');
      setNoiseError('Enter returned pose or sample parameters before requesting the noise model.');
      setNoiseModel(undefined);
      return;
    }
    setNoiseState('loading');
    setNoiseError(undefined);
    try {
      const response = await requestJson<unknown>(
        `/api/v1/calibration/noise_model?${params.toString()}`,
      );
      const returnedRecord = methodologyRecord(unwrapArtifactPayload(response));
      setNoiseModel(returnedRecord);
      setNoiseState(hasMethodologyFields(returnedRecord) ? 'ready' : 'empty');
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setNoiseState('error');
      setNoiseError(methodologyErrorMessage(requestError));
      setNoiseModel(undefined);
    }
  };

  const subtractNoise = async () => {
    if (!photoA.trim() || !photoB.trim()) {
      setSubtractState('error');
      setSubtractError('Enter both returned photo identifiers before subtracting noise.');
      setSubtracted(undefined);
      return;
    }
    const tolerance: MethodologyRecord = {};
    if (toleranceYaw.trim()) tolerance.yaw = Number(toleranceYaw);
    if (tolerancePitch.trim()) tolerance.pitch = Number(tolerancePitch);
    if (toleranceRoll.trim()) tolerance.roll = Number(toleranceRoll);
    if (Object.values(tolerance).some((value) => !Number.isFinite(value as number))) {
      setSubtractState('error');
      setSubtractError('Tolerance values must be numeric when provided.');
      setSubtracted(undefined);
      return;
    }
    setSubtractState('loading');
    setSubtractError(undefined);
    try {
      const response = await postJson<unknown>('/api/v1/calibration/subtract_noise', {
        photo_a: photoA.trim(),
        photo_b: photoB.trim(),
        tolerance,
      });
      const returnedRecord = methodologyRecord(unwrapArtifactPayload(response));
      setSubtracted(returnedRecord);
      setSubtractState(hasMethodologyFields(returnedRecord) ? 'ready' : 'empty');
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setSubtractState('error');
      setSubtractError(methodologyErrorMessage(requestError));
      setSubtracted(undefined);
    }
  };

  const filteredRows = useMemo(
    () =>
      rows.filter(
        (row) =>
          (!metric.trim() || String(row.metric ?? row.metric_name ?? '') === metric.trim()) &&
          (!poseBin.trim() || String(row.pose_bin ?? '') === poseBin.trim()) &&
          (!zoneId.trim() || String(row.zone_id ?? '') === zoneId.trim()) &&
          (!family.trim() || String(row.family ?? '') === family.trim()),
      ),
    [family, metric, poseBin, rows, zoneId],
  );
  const filteredCatalog = metricCatalog.filter(
    (row) => !family.trim() || String(row.family ?? '') === family.trim(),
  );

  return (
    <section
      className="detail-block detail-block--methodology"
      aria-labelledby="methodology-calibration-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / methodology.calibration</span>
          <h3 id="methodology-calibration-title">Calibration and metrics reference</h3>
          <p>
            Calibration distributions, pose-bin health, sensitivity and metric interpretation remain
            reference data, not a browser-side calculation.
          </p>
        </div>
        <MethodologyStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="methodology-control-panel">
        <div className="methodology-field-row">
          <MethodologyField
            label="Metric"
            value={metric}
            onChange={setMetric}
            placeholder="returned metric key"
          />
          <MethodologyField
            label="Pose bin"
            value={poseBin}
            onChange={setPoseBin}
            placeholder="returned pose_bin"
          />
          <MethodologyField
            label="Zone ID"
            value={zoneId}
            onChange={setZoneId}
            placeholder="returned zone_id"
          />
          <MethodologyField
            label="Family"
            value={family}
            onChange={setFamily}
            placeholder="returned family"
          />
        </div>
        <div className="methodology-action-panel">
          <div className="methodology-action-card">
            <div>
              <span className="micro-label">Match calibration frames</span>
              <strong>Use returned photo or pose context</strong>
            </div>
            <div className="methodology-field-row">
              <MethodologyField
                label="Photo ID"
                value={photoId}
                onChange={setPhotoId}
                placeholder="returned photo_id"
              />
              <MethodologyField
                label="Yaw"
                value={yaw}
                onChange={setYaw}
                placeholder="returned yaw"
              />
              <MethodologyField
                label="Pitch"
                value={pitch}
                onChange={setPitch}
                placeholder="returned pitch"
              />
              <MethodologyField
                label="Roll"
                value={roll}
                onChange={setRoll}
                placeholder="returned roll"
              />
            </div>
            <div className="methodology-action-footer">
              <span>GET /api/v1/calibration/match</span>
              <button
                className="methodology-button methodology-button--quiet"
                type="button"
                onClick={() => void loadMatchedFrames()}
                disabled={matchState === 'loading'}
              >
                {matchState === 'loading' ? 'Matching…' : 'Match frames'}
              </button>
            </div>
            {matchError ? <p className="methodology-error-copy">{matchError}</p> : null}
            {matchedFrames.length ? (
              <div className="methodology-result-list">
                {matchedFrames.map((frame, index) => (
                  <div key={String(frame.photo_id ?? frame.frame_id ?? frame.record_id ?? index)}>
                    <strong>
                      {methodologyValue(frame.photo_id ?? frame.frame_id ?? frame.record_id)}
                    </strong>
                    <span>
                      pose: {methodologyValue(frame.pose_bin)} · distance:{' '}
                      {methodologyValue(
                        frame.distance ?? frame.pose_distance ?? frame.angle_distance,
                      )}
                    </span>
                    <MethodologyStatus value={frame.status ?? frame.availability ?? matchStatus} />
                  </div>
                ))}
              </div>
            ) : matchState === 'empty' ? (
              <p className="methodology-muted-copy">
                No calibration frames returned for this context.
              </p>
            ) : null}
          </div>
          <div className="methodology-action-card">
            <div>
              <span className="micro-label">Noise model</span>
              <strong>Request returned coverage and state</strong>
            </div>
            <MethodologyField
              label="Sample"
              value={sample}
              onChange={setSample}
              placeholder="returned sample"
            />
            <div className="methodology-action-footer">
              <span>GET /api/v1/calibration/noise_model</span>
              <button
                className="methodology-button methodology-button--quiet"
                type="button"
                onClick={() => void loadNoiseModel()}
                disabled={noiseState === 'loading'}
              >
                {noiseState === 'loading' ? 'Loading…' : 'Load noise model'}
              </button>
            </div>
            {noiseError ? <p className="methodology-error-copy">{noiseError}</p> : null}
            {noiseModel ? (
              <div className="methodology-result-grid">
                <MethodologyDataCard
                  label="State"
                  value={noiseModel.status ?? noiseModel.noise_model_status}
                />
                <MethodologyDataCard label="Coverage" value={noiseModel.coverage} />
                <MethodologyDataCard
                  label="Sample"
                  value={noiseModel.sample ?? noiseModel.sample_count}
                />
                <MethodologyDataCard
                  label="Reference"
                  value={noiseModel.reference_line ?? noiseModel.threshold}
                />
              </div>
            ) : noiseState === 'empty' ? (
              <p className="methodology-muted-copy">Noise model returned no fields.</p>
            ) : null}
          </div>
          <div className="methodology-action-card">
            <div>
              <span className="micro-label">Subtract noise</span>
              <strong>Compare compensated and uncompensated metrics</strong>
            </div>
            <div className="methodology-field-row">
              <MethodologyField
                label="Photo A"
                value={photoA}
                onChange={setPhotoA}
                placeholder="returned photo_id"
              />
              <MethodologyField
                label="Photo B"
                value={photoB}
                onChange={setPhotoB}
                placeholder="returned photo_id"
              />
              <MethodologyField
                label="Yaw tolerance"
                value={toleranceYaw}
                onChange={setToleranceYaw}
                placeholder="returned tolerance"
              />
              <MethodologyField
                label="Pitch tolerance"
                value={tolerancePitch}
                onChange={setTolerancePitch}
                placeholder="returned tolerance"
              />
              <MethodologyField
                label="Roll tolerance"
                value={toleranceRoll}
                onChange={setToleranceRoll}
                placeholder="returned tolerance"
              />
            </div>
            <div className="methodology-action-footer">
              <span>POST /api/v1/calibration/subtract_noise</span>
              <button
                className="methodology-button methodology-button--quiet"
                type="button"
                onClick={() => void subtractNoise()}
                disabled={subtractState === 'loading'}
              >
                {subtractState === 'loading' ? 'Subtracting…' : 'Subtract noise'}
              </button>
            </div>
            {subtractError ? <p className="methodology-error-copy">{subtractError}</p> : null}
            {subtracted ? (
              <div className="methodology-result-grid">
                <MethodologyDataCard
                  label="Status"
                  value={subtracted.status ?? subtracted.measurement_state}
                />
                <MethodologyDataCard label="Compensated" value={subtracted.compensated_metrics} />
                <MethodologyDataCard
                  label="Uncompensated"
                  value={subtracted.uncompensated_metrics}
                />
                <MethodologyDataCard
                  label="Limitations"
                  value={subtracted.limitations ?? subtracted.limitation_refs}
                />
              </div>
            ) : subtractState === 'empty' ? (
              <p className="methodology-muted-copy">Noise subtraction returned no fields.</p>
            ) : null}
          </div>
        </div>
        <div className="methodology-control-footer">
          <span>
            GET /api/v1/calibration/health · calibration artifacts remain explicitly unresolved when
            the source does not return them.
          </span>
          <button
            className="methodology-button"
            type="button"
            onClick={() => void loadCalibration()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load calibration source'}
          </button>
        </div>
      </div>
      {error ? <p className="methodology-error-copy">{error}</p> : null}
      {record ? (
        <div className="methodology-summary-strip">
          <MethodologyDataCard label="Dataset" value={record.calibration_dataset_id} />
          <MethodologyDataCard label="Dataset size" value={record.dataset_size} />
          <MethodologyDataCard label="Proxy status" value={record.proxy_status} />
          <MethodologyDataCard label="Confidence" value={record.confidence} />
          <MethodologyDataCard label="Noise model" value={record.noise_model} />
          <MethodologyDataCard label="Coverage" value={record.coverage} />
          <MethodologyDataCard label="Sensitivity" value={record.sensitivity_status} />
        </div>
      ) : null}
      {filteredRows.length ? (
        <div className="methodology-calibration-table-wrap">
          <table className="methodology-calibration-table">
            <caption>Returned calibration rows</caption>
            <thead>
              <tr>
                <th scope="col">Metric</th>
                <th scope="col">Pose</th>
                <th scope="col">Zone</th>
                <th scope="col">Sample</th>
                <th scope="col">Median</th>
                <th scope="col">P95</th>
                <th scope="col">Reference</th>
                <th scope="col">Status</th>
              </tr>
            </thead>
            <tbody>
              {filteredRows.map((row, index) => (
                <tr key={String(row.metric ?? row.metric_name ?? index)}>
                  <th scope="row">{methodologyValue(row.metric ?? row.metric_name)}</th>
                  <td>{methodologyValue(row.pose_bin)}</td>
                  <td>{methodologyValue(row.zone_id)}</td>
                  <td>{methodologyValue(row.sample_count ?? row.sample)}</td>
                  <td>{methodologyValue(row.median)}</td>
                  <td>{methodologyValue(row.p95)}</td>
                  <td>{methodologyValue(row.reference_line ?? row.threshold)}</td>
                  <td>
                    <MethodologyStatus value={row.status ?? row.health_status ?? row.bin_health} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="methodology-no-data" role="status">
          <span className="methodology-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty'
                ? 'No calibration rows returned'
                : state === 'ready'
                  ? 'No calibration rows returned for this source'
                  : 'No calibration source loaded'}
            </strong>
            <span>
              Metric values, reference lines and sensitivity status are not computed in the
              interface.
            </span>
          </div>
        </div>
      )}
      <div className="methodology-catalog-panel">
        <div className="methodology-subsection-heading">
          <div>
            <span className="micro-label">Metric catalog</span>
            <strong>Definitions and interpretation limits</strong>
          </div>
          <button
            className="methodology-button"
            type="button"
            onClick={() => void loadMetricCatalog()}
            disabled={metricCatalogState === 'loading'}
          >
            {metricCatalogState === 'loading' ? 'Loading…' : 'Load metric catalog'}
          </button>
        </div>
        <p className="methodology-muted-copy">
          Source: GET /api/v1/run/artifacts/metric_catalog · the catalog is displayed only when the
          run returns it; no definitions are authored in the interface.
        </p>
        {metricCatalogError ? <p className="methodology-error-copy">{metricCatalogError}</p> : null}
        {filteredCatalog.length ? (
          <div className="methodology-table-wrap">
            <table className="methodology-table">
              <thead>
                <tr>
                  <th scope="col">Metric</th>
                  <th scope="col">Family</th>
                  <th scope="col">Purpose</th>
                  <th scope="col">Coordinate space</th>
                  <th scope="col">Allowed / forbidden</th>
                </tr>
              </thead>
              <tbody>
                {filteredCatalog.map((row, index) => (
                  <tr key={String(row.metric ?? row.metric_name ?? row.id ?? index)}>
                    <th scope="row">{methodologyValue(row.metric ?? row.metric_name)}</th>
                    <td>{methodologyValue(row.family)}</td>
                    <td>{methodologyValue(row.purpose ?? row.plain_language_meaning)}</td>
                    <td>{methodologyValue(row.coordinate_space ?? row.space)}</td>
                    <td>
                      <span>{methodologyValue(row.allowed_interpretation)}</span>
                      <br />
                      <span>{methodologyValue(row.forbidden_interpretation)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="methodology-no-data methodology-no-data--compact" role="status">
            {metricCatalogState === 'empty'
              ? 'Metric catalog returned no records.'
              : metricCatalogState === 'error'
                ? 'Metric catalog unavailable.'
                : 'No metric catalog loaded.'}
          </div>
        )}
      </div>
      <div className="methodology-interpretation-grid">
        <div>
          <span className="micro-label">Allowed interpretation</span>
          <strong>{methodologyValue(record?.allowed_interpretation)}</strong>
        </div>
        <div>
          <span className="micro-label">Forbidden interpretation</span>
          <strong>{methodologyValue(record?.forbidden_interpretation)}</strong>
        </div>
        <div>
          <span className="micro-label">Formula</span>
          <strong>{methodologyValue(record?.formula)}</strong>
        </div>
      </div>
      <div className="methodology-cross-links" aria-label="Calibration context transitions">
        <span className="micro-label">Open related context</span>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('compare')}
        >
          Compare
        </button>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('research')}
        >
          Research
        </button>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('report')}
        >
          Report
        </button>
      </div>
      <div className="methodology-verdict-note">
        <strong>Calibration boundary</strong>
        <span>
          Proxy, confidence, noise model and reference-line availability determine how a metric may
          be read. Unavailable calibration is not a passing result.
        </span>
      </div>
      <MethodologySourceContext
        state={state}
        error={error}
        onRetry={() => void loadCalibration()}
        sourceRefs={methodologyPage.blocks[1].sourceRefs}
      />
    </section>
  );
}

function MethodologyIntegrityBlock() {
  const [statusFilter, setStatusFilter] = useState('all');
  const [state, setState] = useState<MethodologyState>('idle');
  const [record, setRecord] = useState<MethodologyRecord>();
  const [checks, setChecks] = useState<readonly MethodologyRecord[]>([]);
  const [exceptions, setExceptions] = useState<readonly MethodologyRecord[]>([]);
  const [sources, setSources] = useState<readonly MethodologyRecord[]>([]);
  const [error, setError] = useState<string>();

  const loadIntegrity = async () => {
    setState('loading');
    setRecord(undefined);
    setChecks([]);
    setExceptions([]);
    setSources([]);
    setError(undefined);
    try {
      const response = await requestJson<unknown>('/api/v1/system/health');
      const returnedRecord = methodologyRecord(response);
      const returnedChecks = methodologyRows(response, ['checks', 'integrity_checks', 'relations']);
      const returnedExceptions = methodologyRows(response, ['exceptions', 'quarantine', 'issues']);
      const returnedSources = methodologyRows(response, [
        'source_registry',
        'sources',
        'artifacts',
      ]);
      setRecord(returnedRecord);
      setChecks(returnedChecks);
      setExceptions(returnedExceptions);
      setSources(returnedSources);
      setState(
        returnedChecks.length ||
          returnedExceptions.length ||
          returnedSources.length ||
          hasMethodologyFields(returnedRecord)
          ? 'ready'
          : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(methodologyErrorMessage(requestError));
    }
  };
  const visibleChecks = checks.filter(
    (check) => statusFilter === 'all' || String(check.status ?? '') === statusFilter,
  );
  const visibleExceptions = exceptions.filter(
    (item) => statusFilter === 'all' || String(item.severity ?? item.status ?? '') === statusFilter,
  );

  return (
    <section
      className="detail-block detail-block--methodology"
      aria-labelledby="methodology-integrity-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / methodology.integrity</span>
          <h3 id="methodology-integrity-title">Integrity, connectivity and source registry</h3>
          <p>
            Schema, linkage, coverage, exceptions, quarantine and exact source refs are checked
            without concealing missing artifacts.
          </p>
        </div>
        <MethodologyStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="methodology-control-panel">
        <div className="methodology-field-row">
          <label className="methodology-field">
            <span>Check status</span>
            <select value={statusFilter} onChange={(event) => setStatusFilter(event.target.value)}>
              <option value="all">All returned</option>
              <option value="pass">Pass</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
              <option value="blocking">Blocking</option>
            </select>
          </label>
        </div>
        <div className="methodology-control-footer">
          <span>
            GET /api/v1/system/health · source registry rows are shown only when returned.
          </span>
          <button
            className="methodology-button"
            type="button"
            onClick={() => void loadIntegrity()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load integrity source'}
          </button>
        </div>
      </div>
      {error ? <p className="methodology-error-copy">{error}</p> : null}
      {record ? (
        <div className="methodology-summary-strip">
          <MethodologyDataCard label="Overall" value={record.overall_status ?? record.status} />
          <MethodologyDataCard label="Schema" value={record.schema_version} />
          <MethodologyDataCard label="Warnings" value={record.warning_count} />
          <MethodologyDataCard label="Errors" value={record.error_count} />
          <MethodologyDataCard label="Review count" value={record.review_count} />
          <MethodologyDataCard label="Generated" value={record.generated_at} />
          <MethodologyDataCard label="Source mode" value={record.source_mode} />
          <MethodologyDataCard label="Not a verdict" value={record.not_a_verdict} />
          <MethodologyDataCard
            label="Limitations"
            value={record.limitation_refs ?? record.limitations}
          />
        </div>
      ) : null}
      {visibleChecks.length || visibleExceptions.length || sources.length ? (
        <div className="methodology-integrity-layout">
          <div className="methodology-integrity-column">
            <div className="methodology-subsection-heading">
              <div>
                <span className="micro-label">Integrity checks</span>
                <strong>Schema and connectivity</strong>
              </div>
            </div>
            {visibleChecks.length ? (
              visibleChecks.map((check, index) => (
                <div
                  className="methodology-check-row"
                  key={String(check.check_id ?? check.field_name ?? index)}
                >
                  <div>
                    <strong>
                      {methodologyValue(check.check_id ?? check.field_name ?? check.relation_type)}
                    </strong>
                    <span>
                      {methodologyValue(
                        check.error_message ?? check.expected_type ?? check.actual_type,
                      )}
                    </span>
                  </div>
                  <MethodologyStatus value={check.status} />
                </div>
              ))
            ) : (
              <div className="methodology-no-data methodology-no-data--compact">
                No check rows match the filter.
              </div>
            )}
          </div>
          <div className="methodology-integrity-column">
            <div className="methodology-subsection-heading">
              <div>
                <span className="micro-label">Exceptions and quarantine</span>
                <strong>Affected context</strong>
              </div>
            </div>
            {visibleExceptions.length ? (
              visibleExceptions.map((item, index) => (
                <div
                  className="methodology-check-row"
                  key={String(item.exception_id ?? item.artifact_ref ?? index)}
                >
                  <div>
                    <strong>
                      {methodologyValue(item.exception_id ?? item.module ?? item.artifact_ref)}
                    </strong>
                    <span>
                      {methodologyValue(item.reason ?? item.remediation ?? item.affected_routes)}
                    </span>
                  </div>
                  <MethodologyStatus
                    value={item.severity ?? item.quarantine_status ?? item.status}
                  />
                </div>
              ))
            ) : (
              <div className="methodology-no-data methodology-no-data--compact">
                No exception rows match the filter.
              </div>
            )}
          </div>
          <div className="methodology-source-registry">
            <div className="methodology-subsection-heading">
              <div>
                <span className="micro-label">Source registry</span>
                <strong>Exact returned refs</strong>
              </div>
            </div>
            {sources.length ? (
              <ul>
                {sources.map((source, index) => (
                  <li key={String(source.source_id ?? source.source_file ?? index)}>
                    <code>
                      {methodologyValue(
                        source.source_file ?? source.relative_path ?? source.artifact_ref,
                      )}
                    </code>
                    <span>
                      {methodologyValue(source.source_key ?? source.json_key ?? source.csv_column)}
                    </span>
                    <MethodologyStatus value={source.availability ?? source.status} />
                  </li>
                ))}
              </ul>
            ) : (
              <div className="methodology-no-data methodology-no-data--compact">
                No source registry rows returned.
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="methodology-no-data" role="status">
          <span className="methodology-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty'
                ? 'No integrity rows returned'
                : state === 'ready'
                  ? 'No integrity rows returned by the system health endpoint'
                  : 'No integrity source loaded'}
            </strong>
            <span>
              Schema, linkage, missing-artifact and quarantine status is never replaced with a clean
              default.
            </span>
          </div>
        </div>
      )}
      <div className="methodology-cross-links" aria-label="Integrity context transitions">
        <span className="micro-label">Open related context</span>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('methodology')}
        >
          Methodology
        </button>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('report')}
        >
          Report
        </button>
        <button
          className="methodology-text-button"
          type="button"
          onClick={() => navigateTo('publications')}
        >
          Publication Studio
        </button>
      </div>
      <div className="methodology-verdict-note">
        <strong>Integrity boundary</strong>
        <span>
          Integrity, connectivity and quarantine status describe whether a result can be used and
          traced; they do not transform a missing source into evidence.
        </span>
      </div>
      <MethodologySourceContext
        state={state}
        error={error}
        onRetry={() => void loadIntegrity()}
        sourceRefs={methodologyPage.blocks[2].sourceRefs}
      />
    </section>
  );
}

export function MethodologyPage() {
  const renderBlock = (block: BlockDefinition) => {
    switch (block.id) {
      case 'methodology.pipeline':
        return <MethodologyPipelineBlock />;
      case 'methodology.calibration':
        return <MethodologyCalibrationBlock />;
      case 'methodology.integrity':
        return <MethodologyIntegrityBlock />;
      default:
        return null;
    }
  };

  return <PageBlueprint definition={methodologyPage} renderBlock={renderBlock} />;
}
