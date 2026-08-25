import type { ReactElement } from 'react';

export type PageId =
  | 'timeline'
  | 'photo-detail'
  | 'compare'
  | 'research'
  | 'methodology'
  | 'report'
  | 'publications';

export type SourceStage = 'stage1' | 'stage2' | 'stage2b' | 'stage3' | 'api';

export type SourceMode = 'research';

export type MeasurementState =
  | 'measured'
  | 'limited'
  | 'unavailable'
  | 'not_computed'
  | 'skipped'
  | 'error'
  | 'not_applicable'
  | 'fallback'
  | 'stale'
  | 'missing';

export type ResourceState =
  | 'loading'
  | 'ready'
  | 'empty'
  | 'limited'
  | 'unavailable'
  | 'error'
  | 'stale'
  | 'missing';

export type ArtifactAvailability =
  | 'available'
  | 'measured'
  | 'limited'
  | 'not_computed'
  | 'skipped'
  | 'not_applicable'
  | 'stale'
  | 'missing'
  | 'unavailable'
  | 'fallback'
  | 'error';

export type CoordinateSpace =
  | 'raw_object_normalized'
  | 'chronology_aligned'
  | 'original_image_px'
  | 'mesh'
  | 'uv';

export interface SourceRef {
  sourceMode: SourceMode;
  stage: SourceStage;
  relativePath: string;
  fileName: string;
  jsonKey?: string;
  csvColumn?: string;
  artifactType?: string;
  availability: ArtifactAvailability;
}

export interface Limitation {
  code: string;
  message: string;
  severity: 'info' | 'warning' | 'blocking';
}

/**
 * Shared semantic contract for a self-contained page block.
 * `elements` lists the controls, views and context owned by the block.
 * Layout, width and visual treatment remain implementation decisions for the page owner.
 */
export interface BlockDefinition {
  id: string;
  title: string;
  purpose: string;
  elements: readonly string[];
  keys: readonly string[];
  sourceRefs: readonly string[];
  actions: readonly string[];
  requiredStates: readonly string[];
}

export interface PageDefinition {
  id: PageId;
  title: string;
  group: 'analytics' | 'research' | 'output';
  purpose: string;
  primaryQuestion: string;
  blocks: readonly BlockDefinition[];
}

export interface PageEntry {
  definition: PageDefinition;
  component: () => ReactElement;
}

export interface MeasurementContext {
  sourceMode: SourceMode;
  notAVerdict: true;
  value: number | null;
  metric: string;
  unit: string | null;
  coordinateSpace: CoordinateSpace | null;
  objectId: string;
  sourceRef: SourceRef;
  measurementState: MeasurementState;
  qualityState: string | null;
  visibilityState: string | null;
  calibrationState: string | null;
  limitations: readonly Limitation[];
}

export interface EvidenceContext {
  sourceMode: SourceMode;
  notAVerdict: true;
  claimId: string;
  plainLanguageMeaning: string;
  supportingObjects: readonly string[];
  weakeningObjects: readonly string[];
  sourceRefs: readonly SourceRef[];
  limitations: readonly Limitation[];
  status: MeasurementState;
  explanationState: 'first_mention' | 'explained' | 'repeated' | 'corroborated' | 'reversed';
}
