import { requestJson, requestText } from './api';

export const REPORT_SECTION_NAMES = [
  'summary',
  'narrative',
  'timelines',
  'change_points',
  'zones',
  'motion_maps',
] as const;

export type ReportSectionName = (typeof REPORT_SECTION_NAMES)[number];

export type UiArtifactName =
  | 'timeline_matrix.json'
  | 'pair_metrics_preview.csv'
  | 'zone_summary.csv'
  | 'report_meta.json'
  | `report_sections/${ReportSectionName}.json`;

export type UiArtifactJsonName = Exclude<
  UiArtifactName,
  'pair_metrics_preview.csv' | 'zone_summary.csv'
>;

export interface UiArtifactEnvelope<T> {
  name: UiArtifactJsonName;
  format: 'json';
  payload: T;
  schema: 'deeputin-ui-artifact-envelope-v1';
  source_mode: 'research';
  not_a_verdict: true;
  source_file: `ui_artifacts/${UiArtifactJsonName}`;
}

const UI_ARTIFACT_PREFIX = '/api/v1/ui_artifacts';

function encodeArtifactPath(name: UiArtifactName): string {
  return name
    .split('/')
    .map((part) => encodeURIComponent(part))
    .join('/');
}

export function uiArtifactUrl(name: UiArtifactName): string {
  return `${UI_ARTIFACT_PREFIX}/${encodeArtifactPath(name)}`;
}

export function reportSectionArtifactName(name: string): UiArtifactJsonName | undefined {
  return REPORT_SECTION_NAMES.includes(name as ReportSectionName)
    ? `report_sections/${name as ReportSectionName}.json`
    : undefined;
}

function isUiArtifactEnvelope(value: unknown): value is UiArtifactEnvelope<unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return false;
  const record = value as Record<string, unknown>;
  return record.format === 'json' && typeof record.name === 'string' && 'payload' in record;
}

export async function requestUiArtifactJson<T>(
  name: UiArtifactJsonName,
): Promise<UiArtifactEnvelope<T>> {
  const response = await requestJson<unknown>(uiArtifactUrl(name));
  if (isUiArtifactEnvelope(response)) return response as UiArtifactEnvelope<T>;
  return {
    name,
    format: 'json',
    payload: response as T,
    schema: 'deeputin-ui-artifact-envelope-v1',
    source_mode: 'research',
    not_a_verdict: true,
    source_file: `ui_artifacts/${name}`,
  };
}

export function uiArtifactPayload<T>(envelope: UiArtifactEnvelope<T>): T {
  const payload = envelope.payload;
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) return payload;
  const record = payload as Record<string, unknown>;
  return {
    ...record,
    schema: record.schema ?? envelope.schema,
    source_mode: record.source_mode ?? envelope.source_mode,
    not_a_verdict: record.not_a_verdict ?? envelope.not_a_verdict,
    source_file: record.source_file ?? envelope.source_file,
  } as T;
}

export function requestUiArtifactText(
  name: 'pair_metrics_preview.csv' | 'zone_summary.csv',
): Promise<string> {
  return requestText(uiArtifactUrl(name));
}
