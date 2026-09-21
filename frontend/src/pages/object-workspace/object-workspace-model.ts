import { ApiError } from '../../api/client/http';
import type { ObjectTopology, TopologySegment } from '../../domain/object/topology';
import type { MaintenanceUrgency, Prediction, RiskLevel } from '../../domain/prediction/types';
import {
  formatDateTime,
  formatHealthIndex,
  formatOperationalTime,
  formatProbability,
} from '../../utils/formatters';

export const TOPOLOGY_FALLBACK_WIDTH = 1200;
export const TOPOLOGY_HEIGHT = 100;
export const TOPOLOGY_PADDING_X = 32;
export const TOPOLOGY_AXIS_Y = 52;
export const TOPOLOGY_LABEL_Y = 24;
export const TOPOLOGY_PIKET_LABEL_Y = 82;
const MIN_SEGMENT_WIDTH = 5;
const MIN_PIKET_LABEL_GAP = 64;
const MIN_SEGMENT_LABEL_GAP = 168;

export interface SegmentLayout {
  segment: TopologySegment;
  x: number;
  width: number;
  center: number;
}
export interface TopologyLayout {
  width: number;
  piketFrom: number;
  piketTo: number;
  segments: readonly SegmentLayout[];
  piketLabels: readonly { value: number; x: number }[];
  segmentLabels: readonly { segmentId: string; label: string; x: number }[];
}

const isProblem = (risk: RiskLevel | null) => risk === 'high' || risk === 'critical';

// Keeps required anchors, then fills optional labels that do not collide with what is kept.
function thinLabels<T>(
  candidates: readonly T[],
  position: (item: T) => number,
  required: (item: T) => boolean,
  preferred: (item: T) => boolean,
  minGap: number,
): T[] {
  const kept = candidates.filter(required);
  for (const group of [candidates.filter(preferred), candidates]) {
    for (const item of group) {
      if (kept.includes(item)) continue;
      if (kept.every((other) => Math.abs(position(other) - position(item)) >= minGap)) kept.push(item);
    }
  }
  return kept.sort((a, b) => position(a) - position(b));
}

export function buildTopologyLayout(
  topology: ObjectTopology,
  width: number,
  selected: TopologySegment | null,
): TopologyLayout {
  const first = topology.segments[0];
  const last = topology.segments.at(-1);
  const piketFrom = topology.piketMin ?? first?.piketFrom ?? 0;
  const rawTo = topology.piketMax ?? last?.piketTo ?? piketFrom;
  const piketTo = rawTo > piketFrom ? rawTo : piketFrom + 1;
  const inner = Math.max(width - TOPOLOGY_PADDING_X * 2, 1);
  const scale = (piket: number) => TOPOLOGY_PADDING_X + ((piket - piketFrom) / (piketTo - piketFrom)) * inner;

  const segments = topology.segments.map((segment) => {
    const x = scale(segment.piketFrom);
    const segmentWidth = Math.max(scale(segment.piketTo) - x, MIN_SEGMENT_WIDTH);
    return { segment, x, width: segmentWidth, center: x + segmentWidth / 2 };
  });

  const boundaries = [
    ...new Set([piketFrom, piketTo, ...topology.segments.flatMap((s) => [s.piketFrom, s.piketTo])]),
  ].sort((a, b) => a - b);
  const problemBoundaries = new Set(
    topology.segments.filter((s) => isProblem(s.riskLevel)).flatMap((s) => [s.piketFrom, s.piketTo]),
  );
  const piketLabels = thinLabels(
    boundaries.map((value) => ({ value, x: scale(value) })),
    (item) => item.x,
    (item) =>
      item.value === piketFrom ||
      item.value === piketTo ||
      item.value === selected?.piketFrom ||
      item.value === selected?.piketTo,
    (item) => problemBoundaries.has(item.value),
    MIN_PIKET_LABEL_GAP,
  );

  const segmentLabels = thinLabels(
    segments
      .filter((item) => isProblem(item.segment.riskLevel) || item.segment.segmentId === selected?.segmentId)
      .map((item) => ({ segmentId: item.segment.segmentId, label: item.segment.label, x: item.center })),
    (item) => item.x,
    (item) => item.segmentId === selected?.segmentId,
    () => false,
    MIN_SEGMENT_LABEL_GAP,
  );

  return { width, piketFrom, piketTo, segments, piketLabels, segmentLabels };
}

export interface ObjectPredictionFilterState {
  urgency: MaintenanceUrgency | 'all';
  risk: RiskLevel | 'all';
  search: string;
}
export const initialObjectPredictionFilters: ObjectPredictionFilterState = {
  urgency: 'all',
  risk: 'all',
  search: '',
};
export const hasActiveFilters = (filters: ObjectPredictionFilterState) =>
  filters.urgency !== 'all' || filters.risk !== 'all' || filters.search.trim() !== '';

// Numeric piket only: predictions without a piket value never fall into a segment range.
export const isInSegment = (prediction: Prediction, segment: TopologySegment) =>
  prediction.piketValue !== null &&
  prediction.piketValue >= segment.piketFrom &&
  prediction.piketValue <= segment.piketTo;

export function filterObjectPredictions(
  predictions: readonly Prediction[],
  filters: ObjectPredictionFilterState,
  segment: TopologySegment | null,
) {
  const search = filters.search.trim().toLocaleLowerCase('ru-RU');
  return predictions.filter(
    (item) =>
      (filters.urgency === 'all' || item.maintenanceUrgency === filters.urgency) &&
      (filters.risk === 'all' || item.riskLevel === filters.risk) &&
      (segment === null || isInSegment(item, segment)) &&
      (!search ||
        `${item.sensorName} ${item.sensorType} ${item.piket ?? ''}`
          .toLocaleLowerCase('ru-RU')
          .includes(search)),
  );
}

export interface ObjectPredictionRow {
  id: string;
  piket: string;
  sensorName: string;
  sensorType: string;
  urgency: Prediction['maintenanceUrgency'];
  risk: Prediction['riskLevel'];
  probability: string;
  health: string;
  updated: string;
  fullUpdated: string;
}
export function toObjectPredictionRow(item: Prediction): ObjectPredictionRow {
  return {
    id: item.id,
    piket: item.piket ?? '—',
    sensorName: item.sensorName,
    sensorType: item.sensorType,
    urgency: item.maintenanceUrgency,
    risk: item.riskLevel,
    probability: formatProbability(item.failureProbability),
    health: formatHealthIndex(item.healthIndex),
    updated: formatOperationalTime(item.generatedAt),
    fullUpdated: formatDateTime(item.generatedAt),
  };
}

const predictionForms = ['прогноз', 'прогноза', 'прогнозов'] as const;
export function formatPredictionCount(count: number) {
  const tens = count % 100;
  const ones = count % 10;
  const form = tens > 10 && tens < 20 ? 2 : ones === 1 ? 0 : ones >= 2 && ones <= 4 ? 1 : 2;
  return `${count} ${predictionForms[form]}`;
}

export const isObjectNotFound = (error: unknown) => error instanceof ApiError && error.status === 404;
export const mlCoveragePercent = (supported: number, total: number) =>
  total > 0 ? Math.round((supported / total) * 100) : 0;
