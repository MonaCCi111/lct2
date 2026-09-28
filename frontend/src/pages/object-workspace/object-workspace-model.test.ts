import { describe, expect, it } from 'vitest';
import type { ObjectTopology, TopologySegment } from '../../domain/object/topology';
import type { Prediction } from '../../domain/prediction/types';
import { ApiError } from '../../api/client/http';
import { formatPiket } from '../../utils/formatters';
import {
  TOPOLOGY_PADDING_X,
  buildTopologyLayout,
  filterObjectPredictions,
  formatPredictionCount,
  initialObjectPredictionFilters,
  isObjectNotFound,
  mlCoveragePercent,
} from './object-workspace-model';

const segment = (
  segmentId: string,
  piketFrom: number,
  piketTo: number,
  extra: Partial<TopologySegment> = {},
): TopologySegment => ({
  segmentId,
  label: segmentId,
  piketFrom,
  piketTo,
  riskLevel: 'low',
  activePredictions: 0,
  criticalPredictions: 0,
  highPredictions: 0,
  maxFailureProbability: null,
  ...extra,
});
const topology = (segments: TopologySegment[]): ObjectTopology => ({
  objectId: 203,
  objectName: 'объект Фита',
  piketMin: segments[0]?.piketFrom ?? null,
  piketMax: segments.at(-1)?.piketTo ?? null,
  updatedAt: '2026-09-20T15:42:00Z',
  segments,
});
const prediction = (id: string, piketValue: number | null, extra: Partial<Prediction> = {}): Prediction => ({
  id,
  channelId: 1,
  sensorName: `Датчик ${id}`,
  sensorType: 'Температура',
  subsystem: 'Инженерные системы',
  tag: id,
  objectId: 203,
  objectName: 'объект Фита',
  parentObjectId: null,
  piket: formatPiket(piketValue),
  piketValue,
  predictionSupported: true,
  modelDomain: 'ANALOG_TEMP',
  modelVersion: '7.2',
  failureProbability: 0.46,
  riskLevel: 'critical',
  maintenanceUrgency: 'FLASH_1_6H',
  leadTimeHours: null,
  healthIndex: 54,
  topRiskFactors: [],
  recommendation: null,
  generatedAt: '2026-09-20T15:42:00Z',
  reviewStatus: 'pending_review',
  ticketId: null,
  ...extra,
});

describe('topology layout', () => {
  const layout = () =>
    buildTopologyLayout(
      topology([
        segment('a', 0, 100),
        segment('b', 100, 150),
        segment('c', 150, 400, { riskLevel: 'critical' }),
      ]),
      1200,
      null,
    );
  it('sizes segments in proportion to their piket range', () => {
    const [a, b, c] = layout().segments;
    expect(a!.width / b!.width).toBeCloseTo(2, 6);
    expect(c!.width / b!.width).toBeCloseTo(5, 6);
    expect(a!.x).toBe(TOPOLOGY_PADDING_X);
    expect(b!.x).toBeCloseTo(a!.x + a!.width, 6);
  });
  it('spans the full drawing area between the padded edges', () => {
    const { segments, piketFrom, piketTo } = layout();
    expect({ piketFrom, piketTo }).toEqual({ piketFrom: 0, piketTo: 400 });
    expect(segments.at(-1)!.x + segments.at(-1)!.width).toBeCloseTo(1200 - TOPOLOGY_PADDING_X, 6);
  });
  it('always labels the first and last piket and keeps labels apart', () => {
    const dense = topology(
      Array.from({ length: 20 }, (_, index) => segment(`s${index}`, index * 5, index * 5 + 5)),
    );
    const { piketLabels } = buildTopologyLayout(dense, 600, null);
    expect(piketLabels[0]?.value).toBe(0);
    expect(piketLabels.at(-1)?.value).toBe(100);
    expect(piketLabels.length).toBeLessThan(21);
    const gaps = piketLabels.slice(1).map((item, index) => item.x - piketLabels[index]!.x);
    expect(Math.min(...gaps)).toBeGreaterThan(0);
  });
  it('always labels the boundaries of the selected segment', () => {
    const dense = topology(
      Array.from({ length: 20 }, (_, index) => segment(`s${index}`, index * 5, index * 5 + 5)),
    );
    const selected = dense.segments[7]!;
    const { piketLabels, segmentLabels } = buildTopologyLayout(dense, 600, selected);
    const values = piketLabels.map((item) => item.value);
    expect(values).toContain(selected.piketFrom);
    expect(values).toContain(selected.piketTo);
    expect(segmentLabels.map((item) => item.segmentId)).toContain(selected.segmentId);
  });
});

describe('segment prediction filtering', () => {
  const rows = [
    prediction('in-start', 88.5),
    prediction('inside', 96.4),
    prediction('in-end', 112),
    prediction('outside', 140),
    prediction('unlocated', null),
  ];
  const range = segment('SEG', 88.5, 112, { riskLevel: 'critical' });
  it('keeps predictions inside the range, including both boundaries', () => {
    const visible = filterObjectPredictions(rows, initialObjectPredictionFilters, range);
    expect(visible.map((item) => item.id)).toEqual(['in-start', 'inside', 'in-end']);
  });
  it('never places a prediction without a piket value into a numeric range', () => {
    expect(
      filterObjectPredictions(rows, initialObjectPredictionFilters, range).some(
        (item) => item.piketValue === null,
      ),
    ).toBe(false);
    expect(
      filterObjectPredictions(rows, initialObjectPredictionFilters, null).map((item) => item.id),
    ).toContain('unlocated');
  });
  it('combines the segment range with urgency, risk and search filters', () => {
    const mixed = [
      prediction('a', 90, { sensorName: 'Насос Н-2', sensorType: 'Насос' }),
      prediction('b', 95, { riskLevel: 'medium', maintenanceUrgency: 'PLANNED_24_48H' }),
    ];
    expect(
      filterObjectPredictions(mixed, { ...initialObjectPredictionFilters, risk: 'medium' }, range),
    ).toHaveLength(1);
    expect(
      filterObjectPredictions(mixed, { ...initialObjectPredictionFilters, search: 'НАСОС' }, range).map(
        (item) => item.id,
      ),
    ).toEqual(['a']);
  });
});

describe('object workspace helpers', () => {
  it('rounds ML coverage for display and tolerates an empty channel list', () => {
    expect(mlCoveragePercent(722, 860)).toBe(84);
    expect(mlCoveragePercent(0, 0)).toBe(0);
  });
  it('detects a missing object only from a 404 response', () => {
    expect(isObjectNotFound(new ApiError('Нет объекта', 404, 'HTTP_ERROR'))).toBe(true);
    expect(isObjectNotFound(new ApiError('Сбой', 503, 'HTTP_ERROR'))).toBe(false);
    expect(isObjectNotFound(new Error('boom'))).toBe(false);
  });
  it.each([
    [1, '1 прогноз'],
    [3, '3 прогноза'],
    [11, '11 прогнозов'],
    [24, '24 прогноза'],
    [0, '0 прогнозов'],
  ])('pluralises %i predictions', (count, expected) => {
    expect(formatPredictionCount(count)).toBe(expected);
  });
  it.each([
    [0, 'ПК 0'],
    [88.5, 'ПК 88+50'],
    [96, 'ПК 96'],
    [140.08, 'ПК 140+08'],
    [null, '—'],
  ])('formats piket %s for display only', (value, expected) => {
    expect(formatPiket(value)).toBe(expected);
  });
});
