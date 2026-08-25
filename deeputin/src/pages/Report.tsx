import { useState } from 'react';

import { ApiRequestError, isAbortError } from '@/shared/api';
import { PageBlueprint } from '@/shared/PageBlueprint';
import {
  REPORT_SECTION_NAMES,
  reportSectionArtifactName,
  requestUiArtifactJson,
  uiArtifactPayload,
} from '@/shared/uiArtifacts';
import { hashParam, navigateTo } from '@/shared/navigation';
import type { BlockDefinition, PageDefinition } from '@/shared/contracts';

/**
 * PAGE: Report.
 * Blocks are semantic ownership boundaries. Their internal controls and views stay together;
 * the page owner is free to choose the eventual composition.
 */
export const reportPage = {
  id: 'report',
  title: 'Report',
  group: 'research',
  purpose:
    'Технический рабочий отчёт с Run Summary, evidence, narrative, приложениями, источниками и ограничениями.',
  primaryQuestion:
    'Какие рабочие наблюдения собраны, чем они подтверждены и что остаётся нерешённым?',
  blocks: [
    /**
     * BLOCK: Run Summary and working evidence.
     * OWNED ELEMENTS: Run Summary and stage status, working evidence list, timeline, zone and motion attachments, limitations and alternative explanations, source links and transitions to method/review.
     * CONTRACT SURFACE: elements: FDR and quality/calibration context, review decision and provenance context, source key and artifact availability context; actions: open_publication, add_to_publication, open_evidence; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * fdr, q_value, quality, visibility, calibration, pair_metrics, source_stage, relative_path, file_name, artifact_type, availability, created_at, reviewer_id, reviewed_at, decision, rationale.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * run_id, schema_version, status, photo_count, pair_count, generated_at, stage_statuses,
     * public_safety_status, degraded_counts, claim_id, pair_id, photo_ids, metric_refs, zone_refs,
     * evidence_state, review_status, supporting_objects, weakening_objects, source_refs, limitation_refs, timeline_id,
     * pose_bin, date, value, unit, zone_id, motion_map_ref, coordinate_space,
     * source_ref, measurement_state, methodology_ref, metric_catalog_ref, limitation_id, limitation_text, affected_object_ids,
     * alternative_explanations, unresolved_questions, warning_status, main_record_count, calibration_record_count, mesh_pair_count, point_motion_pair_count,
     * texture_pair_count, quality_zone_pair_count, mesh_zone_count, texture_zone_metric_count, zone_measurement_count, expression_gate_summary, pose_bins,
     * anchor_policy_by_bin, limitations, elapsed_seconds, change_point_count, manual_review_count, mesh_calibration_status, calibration_sensitivity_status,
     * pose_leakage_status, lead_registry_status, summary, narrative, timelines, change_points, lead_pairs,
     * lead_registry, zones, motion_maps, methodology, metric_catalog, analysis_manifest.
     */
    {
      id: 'report.run-summary',
      title: 'Run Summary and working evidence',
      purpose:
        'Самостоятельный блок состояния запуска и рабочей доказательной базы: сводка, evidence list, attachments, ограничения и альтернативы.',
      elements: [
        'FDR and quality/calibration context',
        'review decision and provenance context',
        'source key and artifact availability context',
        'Run Summary and stage status',
        'working evidence list',
        'timeline, zone and motion attachments',
        'limitations and alternative explanations',
        'source links and transitions to method/review',
      ],
      keys: [
        'fdr',
        'q_value',
        'quality',
        'visibility',
        'calibration',
        'pair_metrics',
        'source_stage',
        'relative_path',
        'file_name',
        'artifact_type',
        'availability',
        'created_at',
        'reviewer_id',
        'reviewed_at',
        'decision',
        'rationale',
        'source_file',
        'source_key',
        'source_url',
        'api_endpoint',
        'quality_state',
        'visibility_state',
        'calibration_state',
        'schema',
        'source_mode',
        'not_a_verdict',
        'run_id',
        'schema_version',
        'status',
        'photo_count',
        'pair_count',
        'generated_at',
        'stage_statuses',
        'public_safety_status',
        'degraded_counts',
        'claim_id',
        'pair_id',
        'photo_ids',
        'metric_refs',
        'zone_refs',
        'evidence_state',
        'review_status',
        'supporting_objects',
        'weakening_objects',
        'source_refs',
        'limitation_refs',
        'timeline_id',
        'pose_bin',
        'date',
        'value',
        'unit',
        'zone_id',
        'motion_map_ref',
        'coordinate_space',
        'source_ref',
        'measurement_state',
        'methodology_ref',
        'metric_catalog_ref',
        'limitation_id',
        'limitation_text',
        'affected_object_ids',
        'alternative_explanations',
        'unresolved_questions',
        'warning_status',
        'main_record_count',
        'calibration_record_count',
        'mesh_pair_count',
        'point_motion_pair_count',
        'texture_pair_count',
        'quality_zone_pair_count',
        'mesh_zone_count',
        'texture_zone_metric_count',
        'zone_measurement_count',
        'expression_gate_summary',
        'pose_bins',
        'anchor_policy_by_bin',
        'limitations',
        'elapsed_seconds',
        'change_point_count',
        'manual_review_count',
        'mesh_calibration_status',
        'calibration_sensitivity_status',
        'pose_leakage_status',
        'lead_registry_status',
        'summary',
        'narrative',
        'timelines',
        'change_points',
        'lead_pairs',
        'lead_registry',
        'zones',
        'motion_maps',
        'methodology',
        'metric_catalog',
        'analysis_manifest',
      ],
      sourceRefs: [
        'ui_artifacts/report_meta.json',
        'ui_artifacts/report_sections/summary.json',
        'ui_artifacts/report_sections/change_points.json',
        'api/v1/ui_artifacts/report_meta.json',
        'api/v1/ui_artifacts/report_sections/{name}.json',
      ],
      actions: [
        'open_publication',
        'add_to_publication',
        'open_evidence',
        'open_methodology',
        'open_integrity',
        'refresh_report',
        'open_casework',
        'open_compare',
        'open_source',
        'open_timeline',
        'open_zone_atlas',
        'open_calibration',
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
        'fallback',
      ],
    },
    /**
     * BLOCK: Narrative, sources and export.
     * OWNED ELEMENTS: narrative and change-point sequence, technical notes and unresolved questions, source index with exact keys, HTML/JSON/PDF export controls, limitations and not-a-verdict boundary.
     * CONTRACT SURFACE: elements: first and repeated explanation modes, observation, meaning and next-question fields, media slot toggles, signal strengthening and weakening status; actions: set_explanation_mode, add_thumbnail, remove_thumbnail, toggle_table, toggle_chart, toggle_mesh, toggle_texture, toggle_heatmap, mark_signal, open_technical_detail, add_note, export_markdown; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * block_id, template, chronology_index, period, pose_bin, explanation_state, headline, observation, why_it_matters, what_it_does_not_mean, evidence, media_slots, next_question, source_stage, data_snapshot, status, supporting_objects, weakening_objects, unresolved_questions.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * narrative_section_id, order, text, first_mention_state, change_point_id, timeline_refs, pose_refs,
     * evidence_refs, limitation_refs, alternative_explanations, source_ref, stage, relative_path, file_name,
     * json_key, csv_column, export_format, export_status, blocked_reasons, generated_at.
     */
    {
      id: 'report.narrative',
      title: 'Narrative, sources and export',
      purpose:
        'Самостоятельный блок технического нарратива, change points, source index и экспорта отчёта.',
      elements: [
        'first and repeated explanation modes',
        'observation, meaning and next-question fields',
        'media slot toggles',
        'signal strengthening and weakening status',
        'narrative and change-point sequence',
        'technical notes and unresolved questions',
        'source index with exact keys',
        'HTML/JSON/PDF export controls',
        'limitations and not-a-verdict boundary',
      ],
      keys: [
        'block_id',
        'template',
        'chronology_index',
        'period',
        'pose_bin',
        'explanation_state',
        'headline',
        'observation',
        'why_it_matters',
        'what_it_does_not_mean',
        'evidence',
        'media_slots',
        'next_question',
        'source_stage',
        'data_snapshot',
        'status',
        'supporting_objects',
        'weakening_objects',
        'unresolved_questions',
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
        'narrative_section_id',
        'order',
        'text',
        'first_mention_state',
        'change_point_id',
        'timeline_refs',
        'pose_refs',
        'evidence_refs',
        'limitation_refs',
        'alternative_explanations',
        'source_ref',
        'stage',
        'relative_path',
        'file_name',
        'json_key',
        'csv_column',
        'export_format',
        'export_status',
        'blocked_reasons',
        'generated_at',
      ],
      sourceRefs: [
        'ui_artifacts/report_sections/{name}.json',
        'ui_artifacts/report_meta.json',
        'api/v1/ui_artifacts/report_sections/{name}.json',
      ],
      actions: [
        'set_explanation_mode',
        'add_thumbnail',
        'remove_thumbnail',
        'toggle_table',
        'toggle_chart',
        'toggle_mesh',
        'toggle_texture',
        'toggle_heatmap',
        'mark_signal',
        'open_technical_detail',
        'add_note',
        'export_markdown',
        'open_timeline',
        'open_source',
        'add_to_publication',
        'export_html',
        'export_json',
        'export_pdf',
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
      ],
    },
  ],
} satisfies PageDefinition;

type ReportState = 'idle' | 'loading' | 'ready' | 'empty' | 'error';
type ReportRecord = Record<string, unknown>;

function reportRecord(payload: unknown): ReportRecord {
  return payload && typeof payload === 'object' && !Array.isArray(payload)
    ? (payload as ReportRecord)
    : {};
}

function hasReportFields(record: ReportRecord): boolean {
  return Object.entries(record).some(
    ([key, value]) =>
      !['schema', 'source_mode', 'not_a_verdict'].includes(key) &&
      value !== null &&
      value !== undefined,
  );
}

function runSummaryRecord(payload: unknown): ReportRecord {
  const source = reportRecord(payload);
  const flattened: ReportRecord = { ...source };
  const copyFields = (value: unknown) => {
    if (!value || typeof value !== 'object' || Array.isArray(value)) return;
    for (const [key, entry] of Object.entries(value)) {
      if (flattened[key] === undefined) flattened[key] = entry;
    }
  };
  const categories = source.categories;
  if (categories && typeof categories === 'object' && !Array.isArray(categories)) {
    for (const category of Object.values(categories as Record<string, unknown>)) {
      if (!category || typeof category !== 'object' || Array.isArray(category)) continue;
      for (const group of Object.values(category as Record<string, unknown>)) copyFields(group);
    }
  }
  copyFields(source.technical_summary);
  copyFields(source.postprocess_summary);
  copyFields(source.analysis_manifest);
  return flattened;
}

function reportRowsCombined(payload: unknown, keys: readonly string[]): readonly ReportRecord[] {
  if (Array.isArray(payload)) {
    return payload.flatMap((entry) => {
      if (entry && typeof entry === 'object') return [entry as ReportRecord];
      if (typeof entry === 'string' || typeof entry === 'number') return [{ text: entry }];
      return [];
    });
  }
  const record = reportRecord(payload);
  const candidates = [
    record,
    ...['payload', 'summary']
      .map((key) => record[key])
      .filter((value): value is ReportRecord =>
        Boolean(value && typeof value === 'object' && !Array.isArray(value)),
      ),
  ];
  const payloadRows = Array.isArray(record.payload) ? reportRowsCombined(record.payload, keys) : [];
  const rows: ReportRecord[] = [];
  for (const candidate of candidates) {
    for (const key of keys) {
      const value = candidate[key];
      if (!Array.isArray(value)) continue;
      rows.push(
        ...(value as unknown[]).flatMap((entry) => {
          if (entry && typeof entry === 'object') return [entry as ReportRecord];
          if (typeof entry === 'string' || typeof entry === 'number') return [{ text: entry }];
          return [];
        }),
      );
    }
  }
  return [...payloadRows, ...rows];
}

function reportList(value: unknown): readonly string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (typeof entry === 'string' || typeof entry === 'number') return [String(entry)];
    if (entry && typeof entry === 'object') {
      const item = entry as ReportRecord;
      const id = item.pair_id ?? item.claim_id ?? item.source_ref ?? item.id;
      return id === undefined ? [] : [String(id)];
    }
    return [];
  });
}

function reportValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Unavailable';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return 'Structured value';
  return String(value);
}

function reportField(record: ReportRecord | undefined, key: string): unknown {
  if (!record) return undefined;
  if (record[key] !== undefined && record[key] !== null) return record[key];
  for (const parentKey of ['summary', 'analysis_manifest', 'postprocess_summary']) {
    const parent = record[parentKey];
    if (parent && typeof parent === 'object' && !Array.isArray(parent)) {
      const value = (parent as ReportRecord)[key];
      if (value !== undefined && value !== null) return value;
    }
  }
  return undefined;
}

function reportTone(value: unknown): 'positive' | 'warning' | 'muted' {
  if (value === true) return 'positive';
  if (value === false) return 'warning';
  if (typeof value !== 'string') return 'muted';
  if (
    [
      'measured',
      'valid',
      'pass',
      'complete',
      'supported',
      'available',
      'resolved',
      'ready',
    ].includes(value)
  )
    return 'positive';
  if (
    [
      'limited',
      'partial',
      'skipped',
      'fallback',
      'review',
      'none',
      'unavailable',
      'error',
      'blocking',
    ].includes(value)
  )
    return 'warning';
  return 'muted';
}

function ReportStatus({ value, label }: { value: unknown; label?: string }) {
  const tone = reportTone(value);
  return (
    <span className={`report-status report-status--${tone}`}>
      <span className="report-status-dot" aria-hidden="true" />
      {label ?? reportValue(value)}
    </span>
  );
}

function reportErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.detail;
  return 'Источник данных недоступен.';
}

function ReportSourceContext({
  state,
  error,
  sourceRefs,
  onRetry,
}: {
  state: ReportState;
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
    <aside className="report-source-context" aria-label="Контекст источника Report">
      <div className="report-source-heading">
        <div>
          <span className="micro-label">Evidence boundary</span>
          <strong>{label}</strong>
        </div>
        <ReportStatus value={state === 'ready' ? 'measured' : state} />
      </div>
      <div className="report-source-flags">
        <code>source_mode: research</code>
        <code>not_a_verdict: true</code>
      </div>
      {error ? <p className="report-error-copy">{error}</p> : null}
      {state === 'error' && onRetry ? (
        <button className="report-button report-button--quiet" type="button" onClick={onRetry}>
          Retry source request
        </button>
      ) : null}
      <details className="report-source-details">
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

function ReportDataCard({ label, value, unit }: { label: string; value: unknown; unit?: string }) {
  return (
    <div className="report-data-card">
      <span>{label}</span>
      <strong>{reportValue(value)}</strong>
      <small>{unit ?? 'source field'}</small>
    </div>
  );
}

function ReportRunSummaryBlock() {
  const [focusPairId] = useState(() => hashParam('pair_id'));
  const [state, setState] = useState<ReportState>('idle');
  const [record, setRecord] = useState<ReportRecord>();
  const [evidence, setEvidence] = useState<readonly ReportRecord[]>([]);
  const [error, setError] = useState<string>();

  const loadSummary = async () => {
    setState('loading');
    setRecord(undefined);
    setEvidence([]);
    setError(undefined);
    try {
      const [metaResult, summaryResult, changePointsResult] = await Promise.allSettled([
        requestUiArtifactJson<unknown>('report_meta.json'),
        requestUiArtifactJson<unknown>('report_sections/summary.json'),
        requestUiArtifactJson<unknown>('report_sections/change_points.json'),
      ]);
      const metaPayload =
        metaResult.status === 'fulfilled' ? uiArtifactPayload(metaResult.value) : undefined;
      const summaryPayload =
        summaryResult.status === 'fulfilled' ? uiArtifactPayload(summaryResult.value) : undefined;
      const changePointsPayload =
        changePointsResult.status === 'fulfilled'
          ? uiArtifactPayload(changePointsResult.value)
          : undefined;
      const returnedRecord = runSummaryRecord({
        ...runSummaryRecord(metaPayload),
        ...runSummaryRecord(summaryPayload),
      });
      const returnedEvidence = [
        ...reportRowsCombined(summaryPayload, [
          'evidence',
          'zones',
          'motion_maps',
          'timelines',
          'change_points',
          'items',
          'rows',
        ]),
        ...reportRowsCombined(changePointsPayload, ['change_points', 'events', 'items', 'rows']),
      ].map((row) => ({
        ...row,
        source_file: row.source_file ?? 'ui_artifacts/report_sections',
      }));
      setRecord(returnedRecord);
      setEvidence(returnedEvidence);
      const sourceErrors = [
        metaResult.status === 'rejected'
          ? `report_meta.json: ${reportErrorMessage(metaResult.reason)}`
          : undefined,
        summaryResult.status === 'rejected'
          ? `summary.json: ${reportErrorMessage(summaryResult.reason)}`
          : undefined,
        changePointsResult.status === 'rejected'
          ? `change_points.json: ${reportErrorMessage(changePointsResult.reason)}`
          : undefined,
      ].filter((value): value is string => Boolean(value));
      setError(sourceErrors.length ? sourceErrors.join(' · ') : undefined);
      setState(
        returnedEvidence.length || hasReportFields(returnedRecord)
          ? 'ready'
          : sourceErrors.length
            ? 'error'
            : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(reportErrorMessage(requestError));
    }
  };
  const supporting = reportList(reportField(record, 'supporting_objects'));
  const weakening = reportList(reportField(record, 'weakening_objects'));
  const stageStatuses = reportField(record, 'stage_statuses');

  return (
    <section className="detail-block detail-block--report" aria-labelledby="report-summary-title">
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / report.run-summary</span>
          <h3 id="report-summary-title">Run Summary and working evidence</h3>
          <p>
            Run status, stage evidence, attachments, limitations and review context are displayed as
            returned by the calculated source.
          </p>
        </div>
        <ReportStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="report-control-panel">
        <div className="report-control-footer">
          <span>
            report_meta.json + selected report_sections/summary.json and change_points.json · the
            browser never loads a full report source.
          </span>
          <button
            className="report-button"
            type="button"
            onClick={() => void loadSummary()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load report summary'}
          </button>
        </div>
      </div>
      {error ? <p className="report-error-copy">{error}</p> : null}
      {record ? (
        <div className="report-summary-strip">
          <ReportDataCard label="Run ID" value={reportField(record, 'run_id')} />
          <ReportDataCard label="Schema" value={reportField(record, 'schema_version')} />
          <ReportDataCard label="Status" value={reportField(record, 'status')} />
          <ReportDataCard label="Photos" value={reportField(record, 'photo_count')} />
          <ReportDataCard label="Pairs" value={reportField(record, 'pair_count')} />
          <ReportDataCard label="Generated" value={reportField(record, 'generated_at')} />
          <ReportDataCard
            label="Manual review"
            value={reportField(record, 'manual_review_count')}
          />
          <ReportDataCard
            label="Public safety"
            value={reportField(record, 'public_safety_status')}
          />
          <ReportDataCard label="FDR" value={reportField(record, 'fdr')} />
          <ReportDataCard label="q-value" value={reportField(record, 'q_value')} />
          <ReportDataCard
            label="Quality"
            value={reportField(record, 'quality_state') ?? reportField(record, 'quality')}
          />
          <ReportDataCard
            label="Visibility"
            value={reportField(record, 'visibility_state') ?? reportField(record, 'visibility')}
          />
          <ReportDataCard
            label="Calibration"
            value={reportField(record, 'calibration_state') ?? reportField(record, 'calibration')}
          />
          <ReportDataCard label="Source mode" value={reportField(record, 'source_mode')} />
          <ReportDataCard label="Not a verdict" value={reportField(record, 'not_a_verdict')} />
          <ReportDataCard
            label="Limitations"
            value={reportField(record, 'limitation_refs') ?? reportField(record, 'limitations')}
          />
          <ReportDataCard label="Main records" value={reportField(record, 'main_record_count')} />
          <ReportDataCard
            label="Calibration records"
            value={reportField(record, 'calibration_record_count')}
          />
          <ReportDataCard label="Mesh pairs" value={reportField(record, 'mesh_pair_count')} />
          <ReportDataCard
            label="Point-motion pairs"
            value={reportField(record, 'point_motion_pair_count')}
          />
          <ReportDataCard label="Texture pairs" value={reportField(record, 'texture_pair_count')} />
          <ReportDataCard label="Change points" value={reportField(record, 'change_point_count')} />
          {focusPairId ? <ReportDataCard label="Route pair context" value={focusPairId} /> : null}
        </div>
      ) : null}
      {record ? (
        <div className="report-stage-list">
          <div className="report-subsection-heading">
            <div>
              <span className="micro-label">Stage status</span>
              <strong>Returned run state</strong>
            </div>
          </div>
          {Array.isArray(stageStatuses) && stageStatuses.length ? (
            (stageStatuses as unknown[]).map((stage, index) => {
              const item = stage && typeof stage === 'object' ? (stage as ReportRecord) : {};
              return (
                <div
                  className="report-stage-row"
                  key={String(item.stage_id ?? item.stage_name ?? index)}
                >
                  <div>
                    <strong>{reportValue(item.stage_name ?? item.stage_id)}</strong>
                    <span>{reportValue(item.generated_at ?? item.status)}</span>
                  </div>
                  <ReportStatus value={item.status ?? item.stage_status} />
                </div>
              );
            })
          ) : (
            <div className="report-no-data report-no-data--compact">
              No stage-status rows returned.
            </div>
          )}
        </div>
      ) : null}
      {Array.isArray(reportField(record, 'sections')) ? (
        <div className="report-stage-list report-section-navigation">
          <div className="report-subsection-heading">
            <div>
              <span className="micro-label">Report navigation</span>
              <strong>Sections returned by report_meta.json</strong>
            </div>
          </div>
          {(reportField(record, 'sections') as unknown[]).map((section, index) => {
            const item = section && typeof section === 'object' ? (section as ReportRecord) : {};
            const name = typeof item.name === 'string' ? item.name : undefined;
            return (
              <div className="report-stage-row" key={String(name ?? index)}>
                <div>
                  <strong>{reportValue(item.label ?? item.name)}</strong>
                  <span>size: {reportValue(item.size)}</span>
                </div>
                {name ? (
                  <button
                    className="report-text-button"
                    type="button"
                    onClick={() => navigateTo('report', { section: name })}
                  >
                    Open section
                  </button>
                ) : (
                  <ReportStatus value="unavailable" label="No section name" />
                )}
              </div>
            );
          })}
        </div>
      ) : null}
      {evidence.length ? (
        <div className="report-evidence-table-wrap">
          <table className="report-evidence-table">
            <caption>Returned working evidence attachments</caption>
            <thead>
              <tr>
                <th scope="col">Claim / pair</th>
                <th scope="col">Date</th>
                <th scope="col">Pose</th>
                <th scope="col">Metric</th>
                <th scope="col">Unit</th>
                <th scope="col">Meaning</th>
                <th scope="col">Evidence</th>
                <th scope="col">Review</th>
                <th scope="col">Source</th>
                <th scope="col">Limitations</th>
              </tr>
            </thead>
            <tbody>
              {evidence.map((item, index) => (
                <tr key={String(item.claim_id ?? item.pair_id ?? item.timeline_id ?? index)}>
                  <th scope="row">
                    {reportValue(item.claim_id ?? item.pair_id ?? item.timeline_id)}
                  </th>
                  <td>{reportValue(item.date)}</td>
                  <td>{reportValue(item.pose_bin)}</td>
                  <td>{reportValue(item.value ?? item.metric_refs)}</td>
                  <td>{reportValue(item.unit ?? item.metric_unit)}</td>
                  <td>
                    {reportValue(
                      item.plain_language_meaning ?? item.metric_meaning ?? item.why_it_matters,
                    )}
                  </td>
                  <td>
                    <ReportStatus value={item.evidence_state ?? item.status} />
                  </td>
                  <td>
                    <ReportStatus value={item.review_status ?? item.decision} />
                  </td>
                  <td>{reportValue(item.source_ref ?? item.source_stage ?? item.source_refs)}</td>
                  <td>{reportValue(item.limitation_refs ?? item.limitations)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
      <div className="report-evidence-lists">
        <div>
          <span className="micro-label">Supporting objects</span>
          {supporting.length ? (
            <ul>
              {supporting.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>Unavailable</p>
          )}
        </div>
        <div>
          <span className="micro-label">Weakening objects</span>
          {weakening.length ? (
            <ul>
              {weakening.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          ) : (
            <p>Unavailable</p>
          )}
        </div>
        <div>
          <span className="micro-label">Alternative explanations</span>
          <p>{reportValue(reportField(record, 'alternative_explanations'))}</p>
        </div>
        <div>
          <span className="micro-label">Unresolved questions</span>
          <p>{reportValue(reportField(record, 'unresolved_questions'))}</p>
        </div>
      </div>
      {!record ? (
        <div className="report-no-data" role="status">
          <span className="report-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty' ? 'No run summary returned' : 'No calculated summary loaded'}
            </strong>
            <span>Stage, evidence and limitations are not filled with placeholders.</span>
          </div>
        </div>
      ) : null}
      <div className="report-cross-links" aria-label="Report context transitions">
        <span className="micro-label">Open related context</span>
        <button className="report-text-button" type="button" onClick={() => navigateTo('timeline')}>
          Timeline
        </button>
        <button className="report-text-button" type="button" onClick={() => navigateTo('research')}>
          Research
        </button>
        <button
          className="report-text-button"
          type="button"
          onClick={() => navigateTo('methodology')}
        >
          Methodology
        </button>
        <button
          className="report-text-button"
          type="button"
          onClick={() => navigateTo('publications')}
        >
          Publication Studio
        </button>
      </div>
      <div className="report-verdict-note">
        <strong>Report boundary</strong>
        <span>
          This is a working evidence summary. It retains FDR/q-value, quality, visibility,
          calibration and review status rather than presenting a conclusion.
        </span>
      </div>
      <ReportSourceContext
        state={state}
        error={error}
        onRetry={() => void loadSummary()}
        sourceRefs={reportPage.blocks[0].sourceRefs}
      />
    </section>
  );
}

function ReportNarrativeBlock() {
  const [section, setSection] = useState(() => hashParam('section'));
  const [offset, setOffset] = useState(() => hashParam('offset') || '0');
  const [limit, setLimit] = useState(() => hashParam('limit') || '20');
  const [explanationMode, setExplanationMode] = useState(() => hashParam('explanation') || 'first');
  const [media, setMedia] = useState({
    thumbnail: false,
    table: false,
    chart: false,
    mesh: false,
    texture: false,
    heatmap: false,
  });
  const [state, setState] = useState<ReportState>('idle');
  const [record, setRecord] = useState<ReportRecord>();
  const [sections, setSections] = useState<readonly ReportRecord[]>([]);
  const [error, setError] = useState<string>();
  const [exportMessage, setExportMessage] = useState('No export requested.');

  const loadNarrative = async () => {
    const requestedSection = section.trim();
    const artifactName = reportSectionArtifactName(requestedSection);
    if (!artifactName) {
      setRecord(undefined);
      setSections([]);
      setState('error');
      setError(`Choose one returned section: ${REPORT_SECTION_NAMES.join(', ')}.`);
      return;
    }
    const parsedOffset = Number(offset);
    const parsedLimit = Number(limit);
    if (
      !Number.isInteger(parsedOffset) ||
      parsedOffset < 0 ||
      !Number.isInteger(parsedLimit) ||
      parsedLimit <= 0
    ) {
      setRecord(undefined);
      setSections([]);
      setState('error');
      setError('Offset must be a non-negative integer and limit must be a positive integer.');
      return;
    }
    setState('loading');
    setRecord(undefined);
    setSections([]);
    setError(undefined);
    try {
      const response = await requestUiArtifactJson<unknown>(artifactName);
      const payload = uiArtifactPayload(response);
      const returnedRecord = reportRecord(payload);
      const allSections = reportRowsCombined(payload, [
        requestedSection,
        'sections',
        'items',
        'narrative',
        'timelines',
        'change_points',
        'zones',
        'motion_maps',
        'rows',
      ]);
      const returnedSections = allSections.slice(parsedOffset, parsedOffset + parsedLimit);
      setRecord(returnedRecord);
      setSections(returnedSections);
      setState(returnedSections.length || hasReportFields(returnedRecord) ? 'ready' : 'empty');
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(reportErrorMessage(requestError));
    }
  };
  const handleExport = (format: string) => {
    const exportUrls = record?.export_urls;
    const url =
      exportUrls && typeof exportUrls === 'object'
        ? (exportUrls as ReportRecord)[format]
        : undefined;
    if (typeof url === 'string' && url) {
      window.open(url, '_blank', 'noopener,noreferrer');
      setExportMessage(`${format} export opened from the returned source.`);
      return;
    }
    setExportMessage(`${format} export unavailable: no export URL returned; no file generated.`);
  };

  return (
    <section className="detail-block detail-block--report" aria-labelledby="report-narrative-title">
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / report.narrative</span>
          <h3 id="report-narrative-title">Narrative, sources and export</h3>
          <p>
            Technical narrative blocks, change points, source keys, media slots and export
            availability remain source-owned.
          </p>
        </div>
        <ReportStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="report-control-panel">
        <div className="report-field-row">
          <label className="report-field">
            <span>Section name</span>
            <input
              value={section}
              onChange={(event) => setSection(event.target.value)}
              placeholder="returned section name"
            />
          </label>
          <label className="report-field">
            <span>Offset</span>
            <input
              type="number"
              min="0"
              step="1"
              value={offset}
              onChange={(event) => setOffset(event.target.value)}
            />
          </label>
          <label className="report-field">
            <span>Limit</span>
            <input
              type="number"
              min="1"
              step="1"
              value={limit}
              onChange={(event) => setLimit(event.target.value)}
            />
          </label>
          <label className="report-field">
            <span>Explanation</span>
            <select
              value={explanationMode}
              onChange={(event) => setExplanationMode(event.target.value)}
            >
              <option value="first">First mention</option>
              <option value="repeat">Repeated context</option>
            </select>
          </label>
        </div>
        <div className="report-media-controls">
          <span className="micro-label">Media slots</span>
          {Object.entries(media).map(([key, checked]) => (
            <label key={key}>
              <input
                type="checkbox"
                checked={checked}
                onChange={(event) =>
                  setMedia((current) => ({ ...current, [key]: event.target.checked }))
                }
              />{' '}
              {key}
            </label>
          ))}
        </div>
        <div className="report-control-footer">
          <span>
            GET /api/v1/ui_artifacts/report_sections/{'{name}'}.json · offset/limit narrow returned
            section rows in this view
          </span>
          <div className="report-control-actions">
            <button
              className="report-button report-button--quiet"
              type="button"
              onClick={() => handleExport('markdown')}
            >
              Export Markdown
            </button>
            <button
              className="report-button report-button--quiet"
              type="button"
              onClick={() => handleExport('json')}
            >
              Export JSON
            </button>
            <button
              className="report-button"
              type="button"
              onClick={() => void loadNarrative()}
              disabled={state === 'loading'}
            >
              {state === 'loading' ? 'Loading…' : 'Load report section'}
            </button>
          </div>
        </div>
      </div>
      {error ? <p className="report-error-copy">{error}</p> : null}
      {state !== 'idle' || record || sections.length ? (
        <div className="report-export-state">
          <span className="micro-label">Export state</span>
          <strong>{exportMessage}</strong>
        </div>
      ) : null}
      {sections.length ? (
        <div className="report-narrative-list">
          {sections.map((item, index) => {
            const observation =
              explanationMode === 'repeat'
                ? (item.delta_text ??
                  item.repeated_text ??
                  item.repeated_observation ??
                  item.observation ??
                  item.text)
                : (item.first_observation ?? item.observation ?? item.text);
            return (
              <article
                className="report-narrative-card"
                key={String(
                  item.narrative_section_id ?? item.block_id ?? item.change_point_id ?? index,
                )}
              >
                <div className="report-subsection-heading">
                  <div>
                    <span className="micro-label">
                      {reportValue(item.template ?? item.explanation_state ?? explanationMode)}
                    </span>
                    <strong>
                      {reportValue(item.headline ?? item.block_id ?? item.change_point_id)}
                    </strong>
                  </div>
                  <ReportStatus value={item.status ?? item.first_mention_state} />
                </div>
                <div className="report-copy-grid">
                  <div>
                    <span className="micro-label">
                      {explanationMode === 'repeat' ? 'Repeated context' : 'First observation'}
                    </span>
                    <p>{reportValue(observation)}</p>
                  </div>
                  <div>
                    <span className="micro-label">Why it matters</span>
                    <p>{reportValue(item.why_it_matters)}</p>
                  </div>
                  <div>
                    <span className="micro-label">What it does not mean</span>
                    <p>{reportValue(item.what_it_does_not_mean)}</p>
                  </div>
                  <div>
                    <span className="micro-label">Next question</span>
                    <p>{reportValue(item.next_question)}</p>
                  </div>
                </div>
                <div className="report-narrative-meta">
                  <span>evidence: {reportValue(item.evidence_refs ?? item.evidence)}</span>
                  <span>source: {reportValue(item.source_ref ?? item.source_stage)}</span>
                  <span>limitations: {reportValue(item.limitation_refs ?? item.limitations)}</span>
                  <span>measurement: {reportValue(item.measurement_state)}</span>
                  <span>
                    quality / visibility / calibration: {reportValue(item.quality_state)} /{' '}
                    {reportValue(item.visibility_state)} / {reportValue(item.calibration_state)}
                  </span>
                  {Object.entries(media)
                    .filter(([, enabled]) => enabled)
                    .map(([key]) => {
                      const slots = item.media_slots;
                      const slotValue =
                        slots && typeof slots === 'object' && !Array.isArray(slots)
                          ? (slots as ReportRecord)[key]
                          : undefined;
                      return (
                        <span key={key}>
                          {key} slot: {reportValue(slotValue)}
                        </span>
                      );
                    })}
                </div>
              </article>
            );
          })}
        </div>
      ) : (
        <div className="report-no-data" role="status">
          <span className="report-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty' ? 'No narrative items returned' : 'No report section loaded'}
            </strong>
            <span>
              Observations, explanations and change points are not invented without Stage 3/report
              source data.
            </span>
          </div>
        </div>
      )}
      <div className="report-cross-links" aria-label="Narrative context transitions">
        <span className="micro-label">Open related context</span>
        <button className="report-text-button" type="button" onClick={() => navigateTo('timeline')}>
          Timeline
        </button>
        <button className="report-text-button" type="button" onClick={() => navigateTo('compare')}>
          Compare
        </button>
        <button className="report-text-button" type="button" onClick={() => navigateTo('research')}>
          Research
        </button>
        <button
          className="report-text-button"
          type="button"
          onClick={() => navigateTo('publications')}
        >
          Publication Studio
        </button>
      </div>
      <div className="report-verdict-note">
        <strong>Narrative boundary</strong>
        <span>
          Observation, meaning and what-it-does-not-mean remain separate. Media slots are view
          controls; they do not create images or charts.
        </span>
      </div>
      <ReportSourceContext
        state={state}
        error={error}
        onRetry={() => void loadNarrative()}
        sourceRefs={reportPage.blocks[1].sourceRefs}
      />
    </section>
  );
}

export function ReportPage() {
  const renderBlock = (block: BlockDefinition) => {
    switch (block.id) {
      case 'report.run-summary':
        return <ReportRunSummaryBlock />;
      case 'report.narrative':
        return <ReportNarrativeBlock />;
      default:
        return null;
    }
  };

  return <PageBlueprint definition={reportPage} renderBlock={renderBlock} />;
}
