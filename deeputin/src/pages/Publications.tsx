import { useMemo, useState, type ReactNode } from 'react';

import { ApiRequestError, isAbortError } from '@/shared/api';
import { PageBlueprint } from '@/shared/PageBlueprint';
import { requestUiArtifactJson, uiArtifactPayload } from '@/shared/uiArtifacts';
import type { BlockDefinition, PageDefinition } from '@/shared/contracts';

/**
 * PAGE: Publications.
 * Blocks are semantic ownership boundaries. Their internal controls and views stay together;
 * the page owner is free to choose the eventual composition.
 */
export const publicationsPage = {
  id: 'publications',
  title: 'Publications',
  group: 'output',
  purpose:
    'Редакционная рабочая область для сборки длинного материала из evidence-aware текста, media, источников и ограничений.',
  primaryQuestion:
    'Как превратить проверенные наблюдения в самодостаточный текст, не теряя provenance?',
  blocks: [
    /**
     * BLOCK: Authoring workspace.
     * OWNED ELEMENTS: publication context and snapshot, outline hierarchy, draft canvas, selected-block inspector, template gallery, source, evidence and limitation links.
     * CONTRACT SURFACE: elements: material, audience, narrative, media and technical settings, claim and plain-language meaning context, self-contained source and safety controls; actions: add_thumbnail, remove_thumbnail, set_explanation_mode, set_transition_style, toggle_media_slot, set_audience, set_density, show_unresolved, show_alternatives, show_negative_results, preserve_weak_signal; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * version, draft_version, snapshot_run, mode, block_count, auto_pagination, narrative_template, first_mention, repeated_mention, transition_style, show_unresolved_questions, show_alternative_explanations, show_negative_results, preserve_early_weak_signals, media_slots, media_type, media_source, label, value, unit, plain_language_meaning, headline, observation, why_it_matters, what_it_does_not_mean, next_question, source_stage, relative_path, file_name, artifact_type, availability, created_at, private_hypothesis_status, quarantine_status, show_source_mode, show_not_a_verdict, stale.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * publication_id, title, author, editor, audience, language, density,
     * narrative_mode, date_range, pose_bins, run_id, data_snapshot, output_mode, chapter_id,
     * parent_id, block_id, block_type, order, completion_status, source_status, archived,
     * children, editorial_text, technical_note, evidence_refs, media_refs, source_refs, limitation_refs,
     * explanation_state, publication_status, template, explanation_density, coordinate_space, visibility_status, calibration_status,
     * linked_photo_ids, linked_pair_ids, linked_zone_ids, readiness_status, template_id, template_type, editorial_purpose,
     * required_keys, required_sources, blocking_states, allowed_audiences, serializer_id.
     */
    {
      id: 'publications.authoring',
      title: 'Authoring workspace',
      purpose:
        'Самостоятельный редакторский блок: контекст материала, outline, draft canvas, шаблоны и инспекция выбранного блока работают как единая feature.',
      elements: [
        'material, audience, narrative, media and technical settings',
        'claim and plain-language meaning context',
        'self-contained source and safety controls',
        'publication context and snapshot',
        'outline hierarchy',
        'draft canvas',
        'selected-block inspector',
        'template gallery',
        'source, evidence and limitation links',
      ],
      keys: [
        'version',
        'draft_version',
        'snapshot_run',
        'mode',
        'block_count',
        'auto_pagination',
        'narrative_template',
        'first_mention',
        'repeated_mention',
        'transition_style',
        'show_unresolved_questions',
        'show_alternative_explanations',
        'show_negative_results',
        'preserve_early_weak_signals',
        'media_slots',
        'media_type',
        'media_source',
        'label',
        'value',
        'unit',
        'plain_language_meaning',
        'headline',
        'observation',
        'why_it_matters',
        'what_it_does_not_mean',
        'next_question',
        'source_stage',
        'relative_path',
        'file_name',
        'artifact_type',
        'availability',
        'created_at',
        'private_hypothesis_status',
        'quarantine_status',
        'show_source_mode',
        'show_not_a_verdict',
        'stale',
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
        'publication_id',
        'title',
        'author',
        'editor',
        'audience',
        'language',
        'density',
        'narrative_mode',
        'date_range',
        'pose_bins',
        'run_id',
        'data_snapshot',
        'output_mode',
        'chapter_id',
        'parent_id',
        'block_id',
        'block_type',
        'order',
        'completion_status',
        'source_status',
        'archived',
        'children',
        'editorial_text',
        'technical_note',
        'evidence_refs',
        'media_refs',
        'source_refs',
        'limitation_refs',
        'explanation_state',
        'publication_status',
        'template',
        'explanation_density',
        'coordinate_space',
        'visibility_status',
        'calibration_status',
        'linked_photo_ids',
        'linked_pair_ids',
        'linked_zone_ids',
        'readiness_status',
        'template_id',
        'template_type',
        'editorial_purpose',
        'required_keys',
        'required_sources',
        'blocking_states',
        'allowed_audiences',
        'serializer_id',
      ],
      sourceRefs: [
        'ui_artifacts/report_meta.json',
        'ui_artifacts/report_sections/narrative.json',
        'api/v1/ui_artifacts/report_meta.json',
        'api/v1/ui_artifacts/report_sections/narrative.json',
      ],
      actions: [
        'add_thumbnail',
        'remove_thumbnail',
        'set_explanation_mode',
        'set_transition_style',
        'toggle_media_slot',
        'set_audience',
        'set_density',
        'show_unresolved',
        'show_alternatives',
        'show_negative_results',
        'preserve_weak_signal',
        'create_publication',
        'edit_context',
        'select_snapshot',
        'save_draft',
        'select_block',
        'reorder_block',
        'duplicate_block',
        'archive_block',
        'restore_block',
        'edit_text',
        'insert_template',
        'edit_block_metadata',
        'open_source',
        'open_evidence',
        'open_limitation',
        'filter_templates',
        'inspect_template_contract',
      ],
      requiredStates: [
        'measured',
        'not_computed',
        'skipped',
        'not_applicable',
        'stale',
        'empty',
        'unavailable',
        'error',
        'long_content',
        'limited',
      ],
    },
    /**
     * BLOCK: Evidence Map.
     * OWNED ELEMENTS: claim-to-evidence relationships, plain-language meaning, source, coordinate, quality, visibility and calibration status, unlinked claims and missing sources, editorial status and evidence transitions.
     * CONTRACT SURFACE: elements: claim meaning and interpretation boundary, stale and missing-source warning, source and limitation detail; actions: open_limitation, open_compare, add_note, mark_unlinked_resolved; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * source_stage, explanation_state, status, data_snapshot, stale, allowed_interpretation, what_it_does_not_mean, supporting_objects, weakening_objects, alternative_explanations.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * claim_id, plain_language_meaning, evidence_id, object_id, metric_ref, zone_ref, chart_ref,
     * source_ref, coordinate_space, quality_status, visibility_status, calibration_status, limitation_ref, editorial_status.
     */
    {
      id: 'publications.evidence-map',
      title: 'Evidence Map',
      purpose:
        'Самостоятельная карта связей claim → meaning → evidence → source → limitation с поиском разрывов traceability.',
      elements: [
        'claim meaning and interpretation boundary',
        'stale and missing-source warning',
        'source and limitation detail',
        'claim-to-evidence relationships',
        'plain-language meaning',
        'source, coordinate, quality, visibility and calibration status',
        'unlinked claims and missing sources',
        'editorial status and evidence transitions',
      ],
      keys: [
        'source_stage',
        'explanation_state',
        'status',
        'data_snapshot',
        'stale',
        'allowed_interpretation',
        'what_it_does_not_mean',
        'supporting_objects',
        'weakening_objects',
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
        'not_a_verdict',
        'claim_id',
        'plain_language_meaning',
        'evidence_id',
        'object_id',
        'metric_ref',
        'zone_ref',
        'chart_ref',
        'source_ref',
        'coordinate_space',
        'quality_status',
        'visibility_status',
        'calibration_status',
        'limitation_ref',
        'editorial_status',
      ],
      sourceRefs: [
        'ui_artifacts/report_meta.json',
        'ui_artifacts/report_sections/change_points.json',
        'ui_artifacts/report_sections/zones.json',
        'api/v1/ui_artifacts/report_meta.json',
        'api/v1/ui_artifacts/report_sections/{name}.json',
      ],
      actions: [
        'open_limitation',
        'open_compare',
        'add_note',
        'mark_unlinked_resolved',
        'select_claim',
        'open_evidence',
        'open_source',
        'find_unlinked_claims',
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
    /**
     * BLOCK: Reader, QA and export.
     * OWNED ELEMENTS: reader and print preview, captions, legends, units and source notes, pre-flight QA and visible warnings, blocked export reasons, HTML/Markdown/PDF/JSON/DOCX package actions.
     * CONTRACT SURFACE: elements: self-contained reader and print output, accessibility and QA score context, export package manifest and safety status; actions: open_limitation, open_qa_check, select_page_break, set_pagination, open_export_manifest; states: measured, not_computed, skipped, not_applicable, stale.
     * DATA KEYS:
     * source_stage, explanation_state, coordinate_space, data_snapshot, stale, accessibility_status, qa_score, qa_factors, checks_total, warnings, errors, self_contained, package_path, plain_language_meaning, what_it_does_not_mean, private_hypothesis_status, quarantine_status.
     * schema, source_mode, not_a_verdict, source_file, source_key, source_url, api_endpoint,
     * limitations, measurement_state, quality_state, visibility_state, calibration_state,
     * chapter_order, block_order, heading, body, caption, alt_text, legend,
     * unit, source_note, limitation_note, page_break, table_headers, check_id, category,
     * block_id, severity, status, message, source_ref, limitation_ref, remediation,
     * export_blocked, export_format, publication_id, snapshot_id, source_index, limitation_index, manifest_path,
     * export_status, blocked_reasons, generated_at.
     */
    {
      id: 'publications.reader-preview',
      title: 'Reader, QA and export',
      purpose:
        'Самостоятельный блок финального чтения и выпуска: preview, captions, source notes, pre-flight checks и export package связаны в одном месте.',
      elements: [
        'self-contained reader and print output',
        'accessibility and QA score context',
        'export package manifest and safety status',
        'reader and print preview',
        'captions, legends, units and source notes',
        'pre-flight QA and visible warnings',
        'blocked export reasons',
        'HTML/Markdown/PDF/JSON/DOCX package actions',
      ],
      keys: [
        'source_stage',
        'explanation_state',
        'coordinate_space',
        'data_snapshot',
        'stale',
        'accessibility_status',
        'qa_score',
        'qa_factors',
        'checks_total',
        'warnings',
        'errors',
        'self_contained',
        'package_path',
        'plain_language_meaning',
        'what_it_does_not_mean',
        'private_hypothesis_status',
        'quarantine_status',
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
        'chapter_order',
        'block_order',
        'heading',
        'body',
        'caption',
        'alt_text',
        'legend',
        'unit',
        'source_note',
        'limitation_note',
        'page_break',
        'table_headers',
        'check_id',
        'category',
        'block_id',
        'severity',
        'status',
        'message',
        'source_ref',
        'limitation_ref',
        'remediation',
        'export_blocked',
        'export_format',
        'publication_id',
        'snapshot_id',
        'source_index',
        'limitation_index',
        'manifest_path',
        'export_status',
        'blocked_reasons',
        'generated_at',
      ],
      sourceRefs: [
        'ui_artifacts/report_meta.json',
        'ui_artifacts/report_sections/narrative.json',
        'api/v1/ui_artifacts/report_meta.json',
        'api/v1/ui_artifacts/report_sections/narrative.json',
      ],
      actions: [
        'open_limitation',
        'open_qa_check',
        'select_page_break',
        'set_pagination',
        'open_export_manifest',
        'switch_reader_mode',
        'open_source_note',
        'print_preview',
        'check_pagination',
        'run_qa',
        'open_failed_block',
        'resolve_warning',
        'recheck',
        'select_export_format',
        'run_export',
        'download_export',
        'open_manifest',
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

type PublicationState = 'idle' | 'loading' | 'ready' | 'empty' | 'error';
type PublicationRecord = Record<string, unknown>;

type DraftSettings = {
  title: string;
  author: string;
  audience: string;
  language: string;
  density: string;
  narrativeMode: string;
  transitionStyle: string;
  mode: string;
  dateRange: string;
  poseBins: string;
  snapshotRun: string;
  outputMode: string;
  firstMention: string;
  repeatedMention: string;
  coordinateSpace: string;
  pointSet: string;
  visibility: string;
  expressionGate: string;
  qualityGate: string;
  calibrationMode: string;
  heatmapThresholds: string;
  colorScheme: string;
  gamma: string;
  blur: string;
  autoPagination: boolean;
  showFootnotes: boolean;
  showAppendix: boolean;
  thumbnails: boolean;
  photo_ab: boolean;
  mesh: boolean;
  textured_mesh: boolean;
  morph_sequence: boolean;
  heatmap_3x3: boolean;
  LDM106: boolean;
  LDM134: boolean;
  timeline_chart: boolean;
  metric_table: boolean;
  appendix_table: boolean;
  showUnresolved: boolean;
  showAlternatives: boolean;
  showNegative: boolean;
  preserveWeak: boolean;
  showSourceMode: boolean;
  showNotAVerdict: boolean;
};

function publicationRecord(payload: unknown): PublicationRecord {
  return payload && typeof payload === 'object' && !Array.isArray(payload)
    ? (payload as PublicationRecord)
    : {};
}

function hasPublicationFields(record: PublicationRecord): boolean {
  return Object.entries(record).some(
    ([key, value]) =>
      !['schema', 'source_mode', 'not_a_verdict'].includes(key) &&
      value !== null &&
      value !== undefined,
  );
}

function publicationRows(payload: unknown, keys: readonly string[]): readonly PublicationRecord[] {
  if (Array.isArray(payload))
    return payload.flatMap((entry) => {
      if (entry && typeof entry === 'object') return [entry as PublicationRecord];
      if (typeof entry === 'string' || typeof entry === 'number') return [{ text: entry }];
      return [];
    });
  const record = publicationRecord(payload);
  for (const key of keys) {
    if (Array.isArray(record[key])) return publicationRows(record[key], keys);
  }
  if (record.payload !== undefined) return publicationRows(record.payload, keys);
  return [];
}

function publicationList(value: unknown): readonly string[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((entry) => {
    if (typeof entry === 'string' || typeof entry === 'number') return [String(entry)];
    if (entry && typeof entry === 'object') {
      const item = entry as PublicationRecord;
      const id = item.source_ref ?? item.evidence_id ?? item.claim_id ?? item.object_id ?? item.id;
      return id === undefined ? [] : [String(id)];
    }
    return [];
  });
}

function publicationValue(value: unknown): string {
  if (value === null || value === undefined || value === '') return 'Unavailable';
  if (typeof value === 'boolean') return value ? 'Yes' : 'No';
  if (typeof value === 'object') return 'Structured value';
  return String(value);
}

function publicationField(record: PublicationRecord | undefined, key: string): unknown {
  if (!record) return undefined;
  if (record[key] !== undefined && record[key] !== null) return record[key];
  for (const parentKey of ['summary', 'analysis_manifest', 'postprocess_summary']) {
    const parent = record[parentKey];
    if (parent && typeof parent === 'object' && !Array.isArray(parent)) {
      const value = (parent as PublicationRecord)[key];
      if (value !== undefined && value !== null) return value;
    }
  }
  return undefined;
}

function publicationTone(value: unknown): 'positive' | 'warning' | 'muted' {
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
      'self_contained',
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
      'error',
      'blocking',
      'stale',
      'not_applicable',
    ].includes(value)
  )
    return 'warning';
  return 'muted';
}

function PublicationStatus({ value, label }: { value: unknown; label?: string }) {
  const tone = publicationTone(value);
  return (
    <span className={`publication-status publication-status--${tone}`}>
      <span className="publication-status-dot" aria-hidden="true" />
      {label ?? publicationValue(value)}
    </span>
  );
}

function publicationErrorMessage(error: unknown): string {
  if (error instanceof ApiRequestError) return error.detail;
  return 'Источник данных недоступен.';
}

function PublicationSourceContext({
  state,
  error,
  sourceRefs,
  onRetry,
}: {
  state: PublicationState;
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
    <aside className="publication-source-context" aria-label="Контекст источника Publications">
      <div className="publication-source-heading">
        <div>
          <span className="micro-label">Evidence boundary</span>
          <strong>{label}</strong>
        </div>
        <PublicationStatus value={state === 'ready' ? 'measured' : state} />
      </div>
      <div className="publication-source-flags">
        <code>source_mode: research</code>
        <code>not_a_verdict: true</code>
      </div>
      {error ? <p className="publication-error-copy">{error}</p> : null}
      {state === 'error' && onRetry ? (
        <button
          className="publication-button publication-button--quiet"
          type="button"
          onClick={onRetry}
        >
          Retry source request
        </button>
      ) : null}
      <details className="publication-source-details">
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

function PublicationDataCard({
  label,
  value,
  unit,
}: {
  label: string;
  value: unknown;
  unit?: string;
}) {
  return (
    <div className="publication-data-card">
      <span>{label}</span>
      <strong>{publicationValue(value)}</strong>
      <small>{unit ?? 'source field'}</small>
    </div>
  );
}

function PublicationField({
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
    <label className="publication-field">
      <span>{label}</span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
      />
    </label>
  );
}

function publicationBlockKey(block: PublicationRecord, index: number): string {
  return String(block.block_id ?? block.chapter_id ?? block.narrative_section_id ?? index);
}

function localPublicationBlockId(): string {
  if (typeof crypto !== 'undefined' && 'randomUUID' in crypto)
    return `local-${crypto.randomUUID()}`;
  return `local-${Date.now()}`;
}

function PublicationSelect({
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
    <label className="publication-field">
      <span>{label}</span>
      <select value={value} onChange={(event) => onChange(event.target.value)}>
        {children}
      </select>
    </label>
  );
}

function PublicationsAuthoringBlock() {
  const [state, setState] = useState<PublicationState>('idle');
  const [record, setRecord] = useState<PublicationRecord>();
  const [blocks, setBlocks] = useState<PublicationRecord[]>([]);
  const [archivedBlocks, setArchivedBlocks] = useState<PublicationRecord[]>([]);
  const [selectedKey, setSelectedKey] = useState('');
  const [draftText, setDraftText] = useState('');
  const [technicalNote, setTechnicalNote] = useState('');
  const [templateFilter, setTemplateFilter] = useState('');
  const [selectedTemplateKey, setSelectedTemplateKey] = useState('');
  const [saveMessage, setSaveMessage] = useState(
    'Draft save is local until a publication API contract is supplied.',
  );
  const [error, setError] = useState<string>();
  const [settings, setSettings] = useState<DraftSettings>({
    title: '',
    author: '',
    audience: '',
    language: '',
    density: '',
    narrativeMode: '',
    transitionStyle: '',
    mode: '',
    dateRange: '',
    poseBins: '',
    snapshotRun: '',
    outputMode: '',
    firstMention: '',
    repeatedMention: '',
    coordinateSpace: '',
    pointSet: '',
    visibility: '',
    expressionGate: '',
    qualityGate: '',
    calibrationMode: '',
    heatmapThresholds: '',
    colorScheme: '',
    gamma: '',
    blur: '',
    autoPagination: true,
    showFootnotes: true,
    showAppendix: true,
    thumbnails: false,
    photo_ab: false,
    mesh: false,
    textured_mesh: false,
    morph_sequence: false,
    heatmap_3x3: false,
    LDM106: false,
    LDM134: false,
    timeline_chart: false,
    metric_table: false,
    appendix_table: false,
    showUnresolved: false,
    showAlternatives: false,
    showNegative: false,
    preserveWeak: false,
    showSourceMode: true,
    showNotAVerdict: true,
  });

  const loadSnapshot = async () => {
    setState('loading');
    setRecord(undefined);
    setBlocks([]);
    setArchivedBlocks([]);
    setSelectedKey('');
    setSelectedTemplateKey('');
    setDraftText('');
    setTechnicalNote('');
    setError(undefined);
    try {
      const [metaResult, narrativeResult] = await Promise.allSettled([
        requestUiArtifactJson<unknown>('report_meta.json'),
        requestUiArtifactJson<unknown>('report_sections/narrative.json'),
      ]);
      const metaPayload =
        metaResult.status === 'fulfilled' ? uiArtifactPayload(metaResult.value) : undefined;
      const narrativePayload =
        narrativeResult.status === 'fulfilled'
          ? uiArtifactPayload(narrativeResult.value)
          : undefined;
      const returnedRecord = publicationRecord(metaPayload);
      const returnedBlocks = publicationRows(narrativePayload, [
        'blocks',
        'chapters',
        'narrative',
        'sections',
        'items',
        'rows',
      ]);
      setRecord(returnedRecord);
      setBlocks([...returnedBlocks]);
      setSettings((current) => {
        const snapshot =
          returnedRecord.data_snapshot ?? returnedRecord.snapshot_run ?? returnedRecord.run_id;
        return snapshot === undefined || snapshot === null
          ? current
          : { ...current, snapshotRun: String(snapshot) };
      });
      const sourceErrors = [
        metaResult.status === 'rejected'
          ? `report_meta.json: ${publicationErrorMessage(metaResult.reason)}`
          : undefined,
        narrativeResult.status === 'rejected'
          ? `narrative.json: ${publicationErrorMessage(narrativeResult.reason)}`
          : undefined,
      ].filter((value): value is string => Boolean(value));
      setError(sourceErrors.length ? sourceErrors.join(' · ') : undefined);
      setState(
        returnedBlocks.length || hasPublicationFields(returnedRecord)
          ? 'ready'
          : sourceErrors.length
            ? 'error'
            : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(publicationErrorMessage(requestError));
    }
  };
  const selectedIndex = blocks.findIndex(
    (block, index) => publicationBlockKey(block, index) === selectedKey,
  );
  const selected = selectedIndex >= 0 ? blocks[selectedIndex] : undefined;
  const templates = publicationRows(record?.templates, ['items', 'templates']);
  const selectedTemplate = templates.find(
    (template, index) =>
      String(template.template_id ?? template.id ?? index) === selectedTemplateKey,
  );
  const filteredTemplates = templates.filter(
    (template) =>
      !templateFilter.trim() ||
      JSON.stringify(template).toLowerCase().includes(templateFilter.trim().toLowerCase()),
  );
  const toggleSetting = (key: keyof DraftSettings) =>
    setSettings((current) => ({ ...current, [key]: !current[key] }));
  const selectBlock = (key: string, block?: PublicationRecord) => {
    setSelectedKey(key);
    setDraftText(String(block?.editorial_text ?? block?.text ?? ''));
    setTechnicalNote(String(block?.technical_note ?? ''));
  };
  const updateSelectedBlock = (changes: PublicationRecord) => {
    if (selectedIndex < 0) return;
    setBlocks((current) =>
      current.map((block, index) => (index === selectedIndex ? { ...block, ...changes } : block)),
    );
  };
  const updateDraftText = (value: string) => {
    setDraftText(value);
    updateSelectedBlock({ editorial_text: value });
    setSaveMessage('Unsaved local draft changes.');
  };
  const updateTechnicalNote = (value: string) => {
    setTechnicalNote(value);
    updateSelectedBlock({ technical_note: value });
    setSaveMessage('Unsaved local technical note changes.');
  };
  const createBlankBlock = () => {
    const id = localPublicationBlockId();
    const block: PublicationRecord = {
      block_id: id,
      block_type: 'text',
      completion_status: 'draft',
      source_status: 'unavailable',
      archived: false,
      editorial_text: '',
      technical_note: '',
      source_refs: [],
      limitation_refs: [],
      evidence_refs: [],
      media_refs: [],
    };
    setBlocks((current) => [...current, block]);
    selectBlock(id, block);
    setSaveMessage('Blank local draft block created without source content.');
  };
  const insertTemplate = () => {
    if (!selectedTemplate) return;
    const id = localPublicationBlockId();
    const block: PublicationRecord = {
      block_id: id,
      block_type: selectedTemplate.template_type ?? selectedTemplate.block_type ?? 'editorial',
      template: selectedTemplate.template_id ?? selectedTemplate.id,
      completion_status: 'draft',
      source_status: 'unavailable',
      archived: false,
      editorial_text: '',
      technical_note: '',
      source_refs: [],
      limitation_refs: [],
      evidence_refs: [],
      media_refs: [],
    };
    setBlocks((current) => [...current, block]);
    selectBlock(id, block);
    setSaveMessage('Template inserted as an empty local block; source binding is still required.');
  };
  const duplicateSelected = () => {
    if (!selected) return;
    const id = localPublicationBlockId();
    const copy: PublicationRecord = {
      ...selected,
      block_id: id,
      order: undefined,
      completion_status: 'draft',
      archived: false,
    };
    setBlocks((current) => [...current, copy]);
    selectBlock(id, copy);
    setSaveMessage('Selected block duplicated locally; source references remain inspectable.');
  };
  const archiveSelected = () => {
    if (!selected || selectedIndex < 0) return;
    setArchivedBlocks((current) => [...current, { ...selected, archived: true }]);
    setBlocks((current) => current.filter((_, index) => index !== selectedIndex));
    setSelectedKey('');
    setDraftText('');
    setTechnicalNote('');
    setSaveMessage('Selected block archived locally.');
  };
  const restoreBlock = (block: PublicationRecord, index: number) => {
    const restored = { ...block, archived: false };
    setBlocks((current) => [...current, restored]);
    setArchivedBlocks((current) => current.filter((_, itemIndex) => itemIndex !== index));
    selectBlock(publicationBlockKey(restored, blocks.length), restored);
    setSaveMessage('Archived block restored locally.');
  };
  const moveSelected = (delta: -1 | 1) => {
    if (selectedIndex < 0) return;
    const targetIndex = selectedIndex + delta;
    if (targetIndex < 0 || targetIndex >= blocks.length) return;
    setBlocks((current) => {
      const next = [...current];
      const [moved] = next.splice(selectedIndex, 1);
      if (moved) next.splice(targetIndex, 0, moved);
      return next;
    });
    setSaveMessage('Outline order changed locally.');
  };
  const saveDraft = () => {
    setSaveMessage(
      'Draft state kept locally. No publication write endpoint is declared by the API contract.',
    );
  };

  return (
    <section
      className="detail-block detail-block--publication"
      aria-labelledby="publication-authoring-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / publications.authoring</span>
          <h3 id="publication-authoring-title">Authoring workspace</h3>
          <p>
            Material context, outline, draft block and source/safety controls stay together without
            inventing publication persistence endpoints.
          </p>
        </div>
        <PublicationStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="publication-control-panel">
        <div className="publication-field-row">
          <PublicationField
            label="Title"
            value={settings.title}
            onChange={(value) => setSettings((current) => ({ ...current, title: value }))}
            placeholder="publication title"
          />
          <PublicationField
            label="Author / editor"
            value={settings.author}
            onChange={(value) => setSettings((current) => ({ ...current, author: value }))}
            placeholder="editorial owner"
          />
          <PublicationField
            label="Audience"
            value={settings.audience}
            onChange={(value) => setSettings((current) => ({ ...current, audience: value }))}
            placeholder="allowed audience"
          />
          <PublicationField
            label="Language"
            value={settings.language}
            onChange={(value) => setSettings((current) => ({ ...current, language: value }))}
            placeholder="language"
          />
          <PublicationField
            label="Density"
            value={settings.density}
            onChange={(value) => setSettings((current) => ({ ...current, density: value }))}
            placeholder="returned density"
          />
          <PublicationField
            label="Narrative mode"
            value={settings.narrativeMode}
            onChange={(value) => setSettings((current) => ({ ...current, narrativeMode: value }))}
            placeholder="first or repeated"
          />
        </div>
        <div className="publication-field-row">
          <PublicationField
            label="Date range"
            value={settings.dateRange}
            onChange={(value) => setSettings((current) => ({ ...current, dateRange: value }))}
            placeholder="returned date range"
          />
          <PublicationField
            label="Pose bins"
            value={settings.poseBins}
            onChange={(value) => setSettings((current) => ({ ...current, poseBins: value }))}
            placeholder="returned pose bins"
          />
          <PublicationField
            label="Snapshot run"
            value={settings.snapshotRun}
            onChange={(value) => setSettings((current) => ({ ...current, snapshotRun: value }))}
            placeholder="run_id from source"
          />
          <PublicationField
            label="Heatmap thresholds"
            value={settings.heatmapThresholds}
            onChange={(value) =>
              setSettings((current) => ({ ...current, heatmapThresholds: value }))
            }
            placeholder="returned thresholds"
          />
        </div>
        <div className="publication-field-row">
          <PublicationSelect
            label="Material mode"
            value={settings.mode}
            onChange={(value) => setSettings((current) => ({ ...current, mode: value }))}
          >
            <option value="">Not selected</option>
            <option value="chronology">Chronology</option>
            <option value="compare">Compare</option>
            <option value="thematic">Thematic</option>
          </PublicationSelect>
          <PublicationSelect
            label="Output mode"
            value={settings.outputMode}
            onChange={(value) => setSettings((current) => ({ ...current, outputMode: value }))}
          >
            <option value="">Not selected</option>
            <option value="wide">Public / wide audience</option>
            <option value="editorial">Newsroom / editor</option>
            <option value="technical">Technical appendix</option>
          </PublicationSelect>
          <PublicationSelect
            label="First mention"
            value={settings.firstMention}
            onChange={(value) => setSettings((current) => ({ ...current, firstMention: value }))}
          >
            <option value="">Not selected</option>
            <option value="detailed">Detailed</option>
            <option value="compact">Compact</option>
          </PublicationSelect>
          <PublicationSelect
            label="Repeated mention"
            value={settings.repeatedMention}
            onChange={(value) => setSettings((current) => ({ ...current, repeatedMention: value }))}
          >
            <option value="">Not selected</option>
            <option value="full">Full</option>
            <option value="reference">Reference</option>
            <option value="delta">Delta only</option>
          </PublicationSelect>
          <PublicationSelect
            label="Transition style"
            value={settings.transitionStyle}
            onChange={(value) => setSettings((current) => ({ ...current, transitionStyle: value }))}
          >
            <option value="">Not selected</option>
            <option value="chronological">Chronological</option>
            <option value="cross_pose">Cross-pose</option>
            <option value="period">Period</option>
          </PublicationSelect>
        </div>
        <div className="publication-field-row">
          <PublicationSelect
            label="Coordinate space"
            value={settings.coordinateSpace}
            onChange={(value) => setSettings((current) => ({ ...current, coordinateSpace: value }))}
          >
            <option value="">Not selected</option>
            <option value="raw">Raw</option>
            <option value="aligned">Aligned</option>
            <option value="original">Original</option>
          </PublicationSelect>
          <PublicationSelect
            label="Point set"
            value={settings.pointSet}
            onChange={(value) => setSettings((current) => ({ ...current, pointSet: value }))}
          >
            <option value="">Not selected</option>
            <option value="LDM106">LDM106</option>
            <option value="LDM134">LDM134</option>
            <option value="both">Both, separate panes</option>
          </PublicationSelect>
          <PublicationSelect
            label="Visibility"
            value={settings.visibility}
            onChange={(value) => setSettings((current) => ({ ...current, visibility: value }))}
          >
            <option value="">Not selected</option>
            <option value="all">All</option>
            <option value="visible">Visible</option>
            <option value="common_visible">Common visible</option>
          </PublicationSelect>
          <PublicationSelect
            label="Expression gate"
            value={settings.expressionGate}
            onChange={(value) => setSettings((current) => ({ ...current, expressionGate: value }))}
          >
            <option value="">Not selected</option>
            <option value="show">Show status</option>
            <option value="filter">Filter</option>
            <option value="explain">Explain</option>
          </PublicationSelect>
          <PublicationSelect
            label="Quality gate"
            value={settings.qualityGate}
            onChange={(value) => setSettings((current) => ({ ...current, qualityGate: value }))}
          >
            <option value="">Not selected</option>
            <option value="show">Show</option>
            <option value="filter">Filter</option>
            <option value="explain">Explain</option>
          </PublicationSelect>
          <PublicationSelect
            label="Calibration"
            value={settings.calibrationMode}
            onChange={(value) => setSettings((current) => ({ ...current, calibrationMode: value }))}
          >
            <option value="">Not selected</option>
            <option value="status">Show status</option>
            <option value="apply">Apply when available</option>
          </PublicationSelect>
        </div>
        <div className="publication-toggle-row">
          <span className="micro-label">Safety and narrative controls</span>
          {(
            [
              ['showUnresolved', 'Show unresolved'],
              ['showAlternatives', 'Show alternatives'],
              ['showNegative', 'Show negative results'],
              ['preserveWeak', 'Preserve weak signal'],
              ['showSourceMode', 'Show source mode'],
              ['showNotAVerdict', 'Show not-a-verdict'],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <input type="checkbox" checked={settings[key]} onChange={() => toggleSetting(key)} />{' '}
              {label}
            </label>
          ))}
        </div>
        <div className="publication-toggle-row publication-toggle-row--media">
          <span className="micro-label">Media slots</span>
          {(
            [
              'thumbnails',
              'photo_ab',
              'mesh',
              'textured_mesh',
              'morph_sequence',
              'heatmap_3x3',
              'LDM106',
              'LDM134',
              'timeline_chart',
              'metric_table',
              'appendix_table',
            ] as const
          ).map((slot) => (
            <label key={slot}>
              <input
                type="checkbox"
                checked={settings[slot as keyof DraftSettings] === true}
                onChange={() =>
                  setSettings((current) => ({
                    ...current,
                    [slot]: !current[slot as keyof DraftSettings],
                  }))
                }
              />{' '}
              {slot}
            </label>
          ))}
        </div>
        <div className="publication-field-row">
          <PublicationField
            label="Color scheme"
            value={settings.colorScheme}
            onChange={(value) => setSettings((current) => ({ ...current, colorScheme: value }))}
            placeholder="returned scheme"
          />
          <PublicationField
            label="Gamma"
            value={settings.gamma}
            onChange={(value) => setSettings((current) => ({ ...current, gamma: value }))}
            placeholder="returned gamma"
          />
          <PublicationField
            label="Blur"
            value={settings.blur}
            onChange={(value) => setSettings((current) => ({ ...current, blur: value }))}
            placeholder="returned blur"
          />
        </div>
        <div className="publication-toggle-row">
          <span className="micro-label">Output safeguards</span>
          {(
            [
              ['autoPagination', 'Auto-pagination'],
              ['showFootnotes', 'Show footnotes'],
              ['showAppendix', 'Show appendix'],
            ] as const
          ).map(([key, label]) => (
            <label key={key}>
              <input type="checkbox" checked={settings[key]} onChange={() => toggleSetting(key)} />{' '}
              {label}
            </label>
          ))}
        </div>
        <div className="publication-control-footer">
          <span>
            report_meta.json + report_sections/narrative.json · publication write APIs are not
            declared; edits remain local.
          </span>
          <div className="publication-control-actions">
            <button
              className="publication-button publication-button--quiet"
              type="button"
              onClick={saveDraft}
            >
              Save draft
            </button>
            <button
              className="publication-button"
              type="button"
              onClick={() => void loadSnapshot()}
              disabled={state === 'loading'}
            >
              {state === 'loading' ? 'Loading…' : 'Load report snapshot'}
            </button>
          </div>
        </div>
      </div>
      {error ? <p className="publication-error-copy">{error}</p> : null}
      <div className="publication-draft-status">
        <span className="micro-label">Draft state</span>
        <strong>{saveMessage}</strong>
      </div>
      {record ? (
        <div className="publication-summary-strip">
          <PublicationDataCard
            label="Snapshot run"
            value={publicationField(record, 'snapshot_run') ?? publicationField(record, 'run_id')}
          />
          <PublicationDataCard
            label="Publication ID"
            value={publicationField(record, 'publication_id')}
          />
          <PublicationDataCard
            label="Block count"
            value={publicationField(record, 'block_count')}
          />
          <PublicationDataCard
            label="Readiness"
            value={publicationField(record, 'readiness_status')}
          />
          <PublicationDataCard label="Stale" value={publicationField(record, 'stale')} />
        </div>
      ) : null}
      <div className="publication-authoring-layout">
        <div className="publication-outline">
          <div className="publication-subsection-heading">
            <div>
              <span className="micro-label">Outline hierarchy</span>
              <strong>
                {blocks.length ? `${blocks.length} active blocks` : 'No blocks loaded'}
              </strong>
            </div>
            <div className="publication-inline-actions">
              <button
                className="publication-button publication-button--quiet"
                type="button"
                onClick={createBlankBlock}
              >
                New blank block
              </button>
              <span className="publication-inline-count">archived: {archivedBlocks.length}</span>
            </div>
          </div>
          {blocks.length ? (
            blocks.map((block, index) => {
              const key = String(
                block.block_id ?? block.chapter_id ?? block.narrative_section_id ?? index,
              );
              return (
                <button
                  key={key}
                  className={`publication-outline-item${selectedKey === key ? ' is-selected' : ''}`}
                  type="button"
                  onClick={() => selectBlock(key, block)}
                >
                  <span>{publicationValue(block.order ?? index)}</span>
                  <strong>
                    {publicationValue(
                      block.headline ?? block.heading ?? block.block_id ?? block.chapter_id,
                    )}
                  </strong>
                  <small>
                    {publicationValue(
                      block.block_type ?? block.template ?? block.completion_status,
                    )}
                  </small>
                </button>
              );
            })
          ) : (
            <div className="publication-no-data publication-no-data--compact">
              Load a returned Stage 3 snapshot to populate the outline.
            </div>
          )}
        </div>
        <div className="publication-draft-canvas">
          <div className="publication-subsection-heading">
            <div>
              <span className="micro-label">Draft canvas</span>
              <strong>
                {selected
                  ? publicationValue(selected.headline ?? selected.heading ?? selected.block_id)
                  : 'No block selected'}
              </strong>
            </div>
            {selected ? (
              <div className="publication-inline-actions">
                <PublicationStatus value={selected.completion_status ?? selected.status} />
                <button
                  className="publication-button publication-button--quiet"
                  type="button"
                  onClick={() => moveSelected(-1)}
                  disabled={selectedIndex <= 0}
                >
                  Move up
                </button>
                <button
                  className="publication-button publication-button--quiet"
                  type="button"
                  onClick={() => moveSelected(1)}
                  disabled={selectedIndex < 0 || selectedIndex >= blocks.length - 1}
                >
                  Move down
                </button>
                <button
                  className="publication-button publication-button--quiet"
                  type="button"
                  onClick={duplicateSelected}
                >
                  Duplicate
                </button>
                <button
                  className="publication-button publication-button--quiet"
                  type="button"
                  onClick={archiveSelected}
                >
                  Archive
                </button>
              </div>
            ) : null}
          </div>
          {selected ? (
            <>
              <textarea
                value={draftText}
                onChange={(event) => updateDraftText(event.target.value)}
                placeholder="Editorial text from the selected source block"
              />
              <label className="publication-field publication-field--full">
                <span>Technical note</span>
                <textarea
                  value={technicalNote}
                  onChange={(event) => updateTechnicalNote(event.target.value)}
                  placeholder="Technical note, gate or limitation context"
                  rows={3}
                />
              </label>
              <div className="publication-draft-meta">
                <span>observation: {publicationValue(selected.observation ?? selected.text)}</span>
                <span>
                  source: {publicationValue(selected.source_ref ?? selected.source_stage)}
                </span>
                <span>
                  limitations: {publicationValue(selected.limitation_refs ?? selected.limitations)}
                </span>
              </div>
            </>
          ) : (
            <div className="publication-no-data publication-no-data--compact">
              Select a returned block. Empty draft text is not replaced with sample prose.
            </div>
          )}
        </div>
        <div className="publication-template-panel">
          <div className="publication-subsection-heading">
            <div>
              <span className="micro-label">Template gallery</span>
              <strong>Returned templates only</strong>
            </div>
          </div>
          <PublicationField
            label="Filter templates"
            value={templateFilter}
            onChange={setTemplateFilter}
            placeholder="template type or purpose"
          />
          {filteredTemplates.length ? (
            <ul>
              {filteredTemplates.map((template, index) => {
                const key = String(template.template_id ?? template.id ?? index);
                return (
                  <li key={key}>
                    <button
                      className={`publication-template-item${selectedTemplateKey === key ? ' is-selected' : ''}`}
                      type="button"
                      onClick={() => setSelectedTemplateKey(key)}
                    >
                      <strong>{publicationValue(template.template_id ?? template.id)}</strong>
                      <span>
                        {publicationValue(template.template_type ?? template.editorial_purpose)}
                      </span>
                      <PublicationStatus value={template.readiness_status ?? template.status} />
                    </button>
                  </li>
                );
              })}
            </ul>
          ) : (
            <p className="publication-muted-copy">
              No template records returned. No template is created in the client.
            </p>
          )}
          {selectedTemplate ? (
            <div className="publication-template-inspector">
              <span className="micro-label">Selected template contract</span>
              <strong>
                {publicationValue(selectedTemplate.template_id ?? selectedTemplate.id)}
              </strong>
              <span>
                {publicationValue(
                  selectedTemplate.editorial_purpose ?? selectedTemplate.description,
                )}
              </span>
              <span>required keys: {publicationValue(selectedTemplate.required_keys)}</span>
              <span>required sources: {publicationValue(selectedTemplate.required_sources)}</span>
              <span>blocking states: {publicationValue(selectedTemplate.blocking_states)}</span>
              <button className="publication-button" type="button" onClick={insertTemplate}>
                Insert empty block
              </button>
            </div>
          ) : (
            <p className="publication-muted-copy">
              Select a returned template to inspect its contract.
            </p>
          )}
        </div>
      </div>
      <div className="publication-inspector-panel">
        <div className="publication-subsection-heading">
          <div>
            <span className="micro-label">Inspector / selected block</span>
            <strong>
              {selected
                ? publicationValue(selected.block_id ?? selected.chapter_id)
                : 'No block selected'}
            </strong>
          </div>
          {selected ? (
            <PublicationStatus
              value={selected.readiness_status ?? selected.publication_status ?? selected.status}
            />
          ) : null}
        </div>
        {selected ? (
          <div className="publication-inspector-grid">
            <PublicationDataCard
              label="Template"
              value={selected.template ?? selected.block_type}
            />
            <PublicationDataCard label="Explanation state" value={selected.explanation_state} />
            <PublicationDataCard label="Audience" value={selected.audience} />
            <PublicationDataCard
              label="Explanation density"
              value={selected.explanation_density ?? selected.density}
            />
            <PublicationDataCard label="Coordinate space" value={selected.coordinate_space} />
            <PublicationDataCard label="Visibility" value={selected.visibility_status} />
            <PublicationDataCard label="Calibration" value={selected.calibration_status} />
            <PublicationDataCard
              label="Readiness"
              value={selected.readiness_status ?? selected.publication_status}
            />
            <PublicationDataCard label="Evidence refs" value={selected.evidence_refs} />
            <PublicationDataCard label="Media refs" value={selected.media_refs} />
            <PublicationDataCard label="Source refs" value={selected.source_refs} />
            <PublicationDataCard
              label="Limitations"
              value={selected.limitation_refs ?? selected.limitations}
            />
            <PublicationDataCard label="Linked photos" value={selected.linked_photo_ids} />
            <PublicationDataCard label="Linked pairs" value={selected.linked_pair_ids} />
            <PublicationDataCard label="Linked zones" value={selected.linked_zone_ids} />
            <PublicationDataCard label="Source status" value={selected.source_status} />
          </div>
        ) : (
          <div className="publication-no-data publication-no-data--compact">
            Select a returned block or create an empty local block to inspect metadata.
          </div>
        )}
      </div>
      {archivedBlocks.length ? (
        <details className="publication-archived-panel">
          <summary>Archived local blocks ({archivedBlocks.length})</summary>
          <ul>
            {archivedBlocks.map((block, index) => (
              <li key={publicationBlockKey(block, index)}>
                <span>{publicationValue(block.block_id ?? block.chapter_id)}</span>
                <button
                  className="publication-button publication-button--quiet"
                  type="button"
                  onClick={() => restoreBlock(block, index)}
                >
                  Restore
                </button>
              </li>
            ))}
          </ul>
        </details>
      ) : null}
      <div className="publication-verdict-note">
        <strong>Editorial boundary</strong>
        <span>
          The publication editor can preserve source text and limitations, but it cannot turn a weak
          signal, a private hypothesis or a quarantined artifact into a public conclusion.
        </span>
      </div>
      <PublicationSourceContext
        state={state}
        error={error}
        onRetry={() => void loadSnapshot()}
        sourceRefs={publicationsPage.blocks[0].sourceRefs}
      />
    </section>
  );
}

function PublicationsEvidenceMapBlock() {
  const [state, setState] = useState<PublicationState>('idle');
  const [record, setRecord] = useState<PublicationRecord>();
  const [claims, setClaims] = useState<readonly PublicationRecord[]>([]);
  const [query, setQuery] = useState('');
  const [selectedKey, setSelectedKey] = useState('');
  const [error, setError] = useState<string>();

  const loadEvidenceMap = async () => {
    setState('loading');
    setRecord(undefined);
    setClaims([]);
    setError(undefined);
    try {
      const [metaResult, changePointsResult, zonesResult] = await Promise.allSettled([
        requestUiArtifactJson<unknown>('report_meta.json'),
        requestUiArtifactJson<unknown>('report_sections/change_points.json'),
        requestUiArtifactJson<unknown>('report_sections/zones.json'),
      ]);
      const metaPayload =
        metaResult.status === 'fulfilled' ? uiArtifactPayload(metaResult.value) : undefined;
      const changePointsPayload =
        changePointsResult.status === 'fulfilled'
          ? uiArtifactPayload(changePointsResult.value)
          : undefined;
      const zonesPayload =
        zonesResult.status === 'fulfilled' ? uiArtifactPayload(zonesResult.value) : undefined;
      const returnedRecord = publicationRecord(metaPayload);
      const returnedClaims = [
        ...publicationRows(changePointsPayload, ['change_points', 'changes', 'items', 'rows']),
        ...publicationRows(zonesPayload, ['zones', 'items', 'rows']),
      ];
      setRecord(returnedRecord);
      setClaims(returnedClaims);
      const sourceErrors = [
        metaResult.status === 'rejected'
          ? `report_meta.json: ${publicationErrorMessage(metaResult.reason)}`
          : undefined,
        changePointsResult.status === 'rejected'
          ? `change_points.json: ${publicationErrorMessage(changePointsResult.reason)}`
          : undefined,
        zonesResult.status === 'rejected'
          ? `zones.json: ${publicationErrorMessage(zonesResult.reason)}`
          : undefined,
      ].filter((value): value is string => Boolean(value));
      setError(sourceErrors.length ? sourceErrors.join(' · ') : undefined);
      setState(
        returnedClaims.length || hasPublicationFields(returnedRecord)
          ? 'ready'
          : sourceErrors.length
            ? 'error'
            : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(publicationErrorMessage(requestError));
    }
  };
  const filteredClaims = useMemo(
    () =>
      claims.filter(
        (claim) =>
          !query.trim() || JSON.stringify(claim).toLowerCase().includes(query.trim().toLowerCase()),
      ),
    [claims, query],
  );
  const selected = filteredClaims.find(
    (claim, index) =>
      String(claim.claim_id ?? claim.evidence_id ?? claim.object_id ?? index) === selectedKey,
  );
  const supporting = publicationList(selected?.supporting_objects);
  const weakening = publicationList(selected?.weakening_objects);

  return (
    <section
      className="detail-block detail-block--publication"
      aria-labelledby="publication-evidence-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / publications.evidence-map</span>
          <h3 id="publication-evidence-title">Evidence Map</h3>
          <p>
            Claim → meaning → evidence → source → limitation remains inspectable, including unlinked
            and stale relationships.
          </p>
        </div>
        <PublicationStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="publication-control-panel">
        <div className="publication-field-row">
          <PublicationField
            label="Find claim or source"
            value={query}
            onChange={setQuery}
            placeholder="claim, evidence, source"
          />
        </div>
        <div className="publication-control-footer">
          <span>
            report_meta.json + selected report_sections/change_points.json and zones.json ·
            relationships are shown only when returned by a derived section.
          </span>
          <button
            className="publication-button"
            type="button"
            onClick={() => void loadEvidenceMap()}
            disabled={state === 'loading'}
          >
            {state === 'loading' ? 'Loading…' : 'Load evidence snapshot'}
          </button>
        </div>
      </div>
      {error ? <p className="publication-error-copy">{error}</p> : null}
      {record ? (
        <div className="publication-summary-strip">
          <PublicationDataCard
            label="Snapshot"
            value={
              publicationField(record, 'data_snapshot') ?? publicationField(record, 'snapshot_run')
            }
          />
          <PublicationDataCard
            label="Evidence count"
            value={publicationField(record, 'evidence_count')}
          />
          <PublicationDataCard label="Stale" value={publicationField(record, 'stale')} />
          <PublicationDataCard
            label="Unlinked"
            value={publicationField(record, 'unlinked_claim_count')}
          />
        </div>
      ) : null}
      {filteredClaims.length ? (
        <div className="publication-evidence-layout">
          <div className="publication-claim-list">
            {filteredClaims.map((claim, index) => {
              const key = String(claim.claim_id ?? claim.evidence_id ?? claim.object_id ?? index);
              return (
                <button
                  key={key}
                  className={`publication-claim-item${selectedKey === key ? ' is-selected' : ''}`}
                  type="button"
                  onClick={() => setSelectedKey(key)}
                >
                  <span>{publicationValue(claim.claim_id ?? claim.evidence_id)}</span>
                  <strong>
                    {publicationValue(claim.plain_language_meaning ?? claim.headline)}
                  </strong>
                  <small>{publicationValue(claim.editorial_status ?? claim.status)}</small>
                  <PublicationStatus value={claim.stale ?? claim.source_status} />
                </button>
              );
            })}
          </div>
          <div className="publication-claim-inspector">
            <div className="publication-subsection-heading">
              <div>
                <span className="micro-label">Selected relationship</span>
                <strong>
                  {selected
                    ? publicationValue(selected.claim_id ?? selected.evidence_id)
                    : 'No claim selected'}
                </strong>
              </div>
              {selected ? (
                <PublicationStatus value={selected.editorial_status ?? selected.status} />
              ) : null}
            </div>
            {selected ? (
              <>
                <div className="publication-data-stack">
                  <PublicationDataCard label="Meaning" value={selected.plain_language_meaning} />
                  <PublicationDataCard
                    label="Evidence"
                    value={selected.evidence_id ?? selected.object_id}
                  />
                  <PublicationDataCard label="Metric ref" value={selected.metric_ref} />
                  <PublicationDataCard label="Zone ref" value={selected.zone_ref} />
                  <PublicationDataCard label="Coordinate" value={selected.coordinate_space} />
                  <PublicationDataCard label="Quality" value={selected.quality_status} />
                  <PublicationDataCard label="Visibility" value={selected.visibility_status} />
                  <PublicationDataCard label="Calibration" value={selected.calibration_status} />
                  <PublicationDataCard label="Source" value={selected.source_ref} />
                  <PublicationDataCard label="Limitation" value={selected.limitation_ref} />
                </div>
                <div className="publication-evidence-links">
                  <div>
                    <span className="micro-label">Supporting</span>
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
                    <span className="micro-label">Weakening</span>
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
                </div>
                <div className="publication-verdict-note">
                  <strong>Claim boundary</strong>
                  <span>
                    {publicationValue(
                      selected.what_it_does_not_mean ?? selected.allowed_interpretation,
                    )}
                  </span>
                </div>
              </>
            ) : (
              <div className="publication-no-data publication-no-data--compact">
                Select a returned claim relationship to inspect its source chain.
              </div>
            )}
          </div>
        </div>
      ) : (
        <div className="publication-no-data" role="status">
          <span className="publication-empty-mark" aria-hidden="true" />
          <div>
            <strong>
              {state === 'empty'
                ? 'No evidence relationships returned'
                : 'No evidence snapshot loaded'}
            </strong>
            <span>Unlinked claims and missing sources are not silently resolved.</span>
          </div>
        </div>
      )}
      <div className="publication-verdict-note">
        <strong>Traceability boundary</strong>
        <span>
          Plain-language meaning does not remove technical source, coordinate, quality, visibility,
          calibration or limitation context.
        </span>
      </div>
      <PublicationSourceContext
        state={state}
        error={error}
        onRetry={() => void loadEvidenceMap()}
        sourceRefs={publicationsPage.blocks[1].sourceRefs}
      />
    </section>
  );
}

function PublicationsReaderBlock() {
  const [state, setState] = useState<PublicationState>('idle');
  const [record, setRecord] = useState<PublicationRecord>();
  const [chapters, setChapters] = useState<readonly PublicationRecord[]>([]);
  const [format, setFormat] = useState('html');
  const [pagination, setPagination] = useState('auto');
  const [error, setError] = useState<string>();
  const [exportMessage, setExportMessage] = useState('No export requested.');

  const loadReader = async () => {
    setState('loading');
    setRecord(undefined);
    setChapters([]);
    setError(undefined);
    try {
      const [metaResult, narrativeResult] = await Promise.allSettled([
        requestUiArtifactJson<unknown>('report_meta.json'),
        requestUiArtifactJson<unknown>('report_sections/narrative.json'),
      ]);
      const metaPayload =
        metaResult.status === 'fulfilled' ? uiArtifactPayload(metaResult.value) : undefined;
      const narrativePayload =
        narrativeResult.status === 'fulfilled'
          ? uiArtifactPayload(narrativeResult.value)
          : undefined;
      const returnedRecord = publicationRecord(metaPayload);
      const returnedChapters = publicationRows(narrativePayload, [
        'chapters',
        'narrative',
        'blocks',
        'sections',
        'items',
        'rows',
      ]);
      setRecord(returnedRecord);
      setChapters(returnedChapters);
      const sourceErrors = [
        metaResult.status === 'rejected'
          ? `report_meta.json: ${publicationErrorMessage(metaResult.reason)}`
          : undefined,
        narrativeResult.status === 'rejected'
          ? `narrative.json: ${publicationErrorMessage(narrativeResult.reason)}`
          : undefined,
      ].filter((value): value is string => Boolean(value));
      setError(sourceErrors.length ? sourceErrors.join(' · ') : undefined);
      setState(
        returnedChapters.length || hasPublicationFields(returnedRecord)
          ? 'ready'
          : sourceErrors.length
            ? 'error'
            : 'empty',
      );
    } catch (requestError) {
      if (isAbortError(requestError)) return;
      setState('error');
      setError(publicationErrorMessage(requestError));
    }
  };
  const runExport = () => {
    const exportUrls = publicationField(record, 'export_urls');
    const url =
      exportUrls && typeof exportUrls === 'object'
        ? (exportUrls as PublicationRecord)[format]
        : undefined;
    if (typeof url === 'string' && url) {
      window.open(url, '_blank', 'noopener,noreferrer');
      setExportMessage(`${format} export opened from returned source.`);
      return;
    }
    setExportMessage(`${format} export unavailable: no URL returned; no file generated.`);
  };
  const qaFactors = publicationField(record, 'qa_factors');

  return (
    <section
      className="detail-block detail-block--publication"
      aria-labelledby="publication-reader-title"
    >
      <header className="detail-block-header">
        <div>
          <span className="micro-label">Block / publications.reader-preview</span>
          <h3 id="publication-reader-title">Reader, QA and export</h3>
          <p>
            Reader/print view, captions, source notes, QA findings and export package status are one
            release gate.
          </p>
        </div>
        <PublicationStatus
          value={state === 'ready' ? 'measured' : state}
          label={state === 'idle' ? 'Ready to query' : undefined}
        />
      </header>
      <div className="publication-control-panel">
        <div className="publication-field-row">
          <label className="publication-field">
            <span>Pagination</span>
            <select value={pagination} onChange={(event) => setPagination(event.target.value)}>
              <option value="auto">Auto</option>
              <option value="manual">Manual page breaks</option>
            </select>
          </label>
          <label className="publication-field">
            <span>Export format</span>
            <select value={format} onChange={(event) => setFormat(event.target.value)}>
              <option value="html">HTML</option>
              <option value="markdown">Markdown</option>
              <option value="pdf">PDF</option>
              <option value="json">JSON</option>
              <option value="docx">DOCX</option>
            </select>
          </label>
        </div>
        <div className="publication-control-footer">
          <span>
            report_meta.json + report_sections/narrative.json · render, QA and export remain
            unavailable until returned URLs or artifacts are provided.
          </span>
          <div className="publication-control-actions">
            <button
              className="publication-button publication-button--quiet"
              type="button"
              onClick={() => window.print()}
            >
              Print preview
            </button>
            <button
              className="publication-button publication-button--quiet"
              type="button"
              onClick={runExport}
            >
              Run export
            </button>
            <button
              className="publication-button"
              type="button"
              onClick={() => void loadReader()}
              disabled={state === 'loading'}
            >
              {state === 'loading' ? 'Loading…' : 'Load reader snapshot'}
            </button>
          </div>
        </div>
      </div>
      {error ? <p className="publication-error-copy">{error}</p> : null}
      {record ? (
        <div className="publication-summary-strip">
          <PublicationDataCard label="QA score" value={publicationField(record, 'qa_score')} />
          <PublicationDataCard
            label="Accessibility"
            value={publicationField(record, 'accessibility_status')}
          />
          <PublicationDataCard label="Warnings" value={publicationField(record, 'warnings')} />
          <PublicationDataCard label="Errors" value={publicationField(record, 'errors')} />
          <PublicationDataCard
            label="Self-contained"
            value={publicationField(record, 'self_contained')}
          />
          <PublicationDataCard
            label="Export blocked"
            value={publicationField(record, 'export_blocked')}
          />
        </div>
      ) : null}
      <div className="publication-reader-layout">
        <div className="publication-reader-preview">
          <div className="publication-subsection-heading">
            <div>
              <span className="micro-label">Reader / print preview</span>
              <strong>
                {chapters.length ? `${chapters.length} returned blocks` : 'No preview loaded'}
              </strong>
            </div>
            <PublicationStatus value={publicationField(record, 'self_contained')} />
          </div>
          {chapters.length ? (
            chapters.map((chapter, index) => (
              <article
                className="publication-reader-card"
                key={String(chapter.block_id ?? chapter.chapter_id ?? index)}
              >
                <h4>{publicationValue(chapter.heading ?? chapter.headline ?? chapter.block_id)}</h4>
                <p>{publicationValue(chapter.body ?? chapter.editorial_text ?? chapter.text)}</p>
                <small>
                  caption: {publicationValue(chapter.caption)} · alt:{' '}
                  {publicationValue(chapter.alt_text)} · unit: {publicationValue(chapter.unit)}
                </small>
                <small>
                  source note: {publicationValue(chapter.source_note ?? chapter.source_ref)} ·
                  limitation: {publicationValue(chapter.limitation_note ?? chapter.limitation_ref)}
                </small>
              </article>
            ))
          ) : (
            <div className="publication-no-data publication-no-data--compact">
              Reader content appears only after the calculated snapshot returns blocks.
            </div>
          )}
        </div>
        <div className="publication-qa-panel">
          <div className="publication-subsection-heading">
            <div>
              <span className="micro-label">Pre-flight QA</span>
              <strong>Visible check results</strong>
            </div>
          </div>
          {Array.isArray(qaFactors) && qaFactors.length ? (
            <ul>
              {(qaFactors as unknown[]).map((factor, index) => {
                const item =
                  factor && typeof factor === 'object' ? (factor as PublicationRecord) : {};
                return (
                  <li key={String(item.check_id ?? index)}>
                    <div>
                      <strong>{publicationValue(item.check_id ?? item.category)}</strong>
                      <span>{publicationValue(item.message ?? item.remediation)}</span>
                    </div>
                    <PublicationStatus value={item.status ?? item.severity} />
                  </li>
                );
              })}
            </ul>
          ) : (
            <div className="publication-no-data publication-no-data--compact">
              No QA factor rows returned.
            </div>
          )}
          <div className="publication-export-state">
            <span className="micro-label">Export</span>
            <strong>{exportMessage}</strong>
            <span>
              pagination: {pagination} · format: {format}
            </span>
          </div>
        </div>
      </div>
      <div className="publication-verdict-note">
        <strong>Release boundary</strong>
        <span>
          Export remains blocked or unavailable when source, limitation, safety or QA status is
          missing. No DOCX/PDF/HTML is fabricated in the client.
        </span>
      </div>
      <PublicationSourceContext
        state={state}
        error={error}
        onRetry={() => void loadReader()}
        sourceRefs={publicationsPage.blocks[2].sourceRefs}
      />
    </section>
  );
}

export function PublicationsPage() {
  const renderBlock = (block: BlockDefinition) => {
    switch (block.id) {
      case 'publications.authoring':
        return <PublicationsAuthoringBlock />;
      case 'publications.evidence-map':
        return <PublicationsEvidenceMapBlock />;
      case 'publications.reader-preview':
        return <PublicationsReaderBlock />;
      default:
        return null;
    }
  };

  return <PageBlueprint definition={publicationsPage} renderBlock={renderBlock} />;
}
