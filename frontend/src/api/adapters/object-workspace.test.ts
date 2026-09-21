import { describe, expect, it } from 'vitest';
import { toObjectDetail } from './object-detail';
import { toObjectTopology } from './object-topology';
import { toPrediction } from './prediction';
import type { PredictionDto } from '../dto/prediction';
import { predictionFixtures } from '../mocks/fixtures';

const detailDto = {
  object_id: 203,
  object_name: 'объект Фита',
  parent_object_id: null,
  object_type: 'Инженерный объект',
  channels_total: 860,
  ml_supported_channels: 722,
  risk_level: 'critical' as const,
  active_predictions: 24,
  critical_predictions: 4,
  high_predictions: 8,
  updated_at: '2026-09-20T15:42:00Z',
};

describe('object detail adapter', () => {
  it('renames fields without deriving risk or counts', () => {
    expect(toObjectDetail(detailDto)).toEqual({
      objectId: 203,
      objectName: 'объект Фита',
      parentObjectId: null,
      objectType: 'Инженерный объект',
      channelsTotal: 860,
      mlSupportedChannels: 722,
      riskLevel: 'critical',
      activePredictions: 24,
      criticalPredictions: 4,
      highPredictions: 8,
      updatedAt: '2026-09-20T15:42:00Z',
    });
  });
});

describe('object topology adapter', () => {
  const dto = {
    object_id: 203,
    object_name: 'объект Фита',
    piket_min: 0,
    piket_max: 120,
    updated_at: '2026-09-20T15:42:00Z',
    segments: [
      {
        segment_id: 'SEG-203-02',
        label: 'Вентшахта ВШ-3',
        piket_from: 88.5,
        piket_to: 112,
        risk_level: 'critical' as const,
        active_predictions: 4,
        critical_predictions: 2,
        high_predictions: 1,
        max_failure_probability: 0.82,
      },
      {
        segment_id: 'SEG-203-01',
        label: 'Входной портал',
        piket_from: 0,
        piket_to: 88.5,
        risk_level: null,
        active_predictions: 0,
        critical_predictions: 0,
        high_predictions: 0,
        max_failure_probability: null,
      },
    ],
  };
  it('maps segments to camelCase and orders them along the piket axis', () => {
    const topology = toObjectTopology(dto);
    expect(topology.segments.map((item) => item.segmentId)).toEqual(['SEG-203-01', 'SEG-203-02']);
    expect(topology.segments[1]).toEqual({
      segmentId: 'SEG-203-02',
      label: 'Вентшахта ВШ-3',
      piketFrom: 88.5,
      piketTo: 112,
      riskLevel: 'critical',
      activePredictions: 4,
      criticalPredictions: 2,
      highPredictions: 1,
      maxFailureProbability: 0.82,
    });
    expect(topology.segments[0]?.riskLevel).toBeNull();
    expect({ min: topology.piketMin, max: topology.piketMax }).toEqual({ min: 0, max: 120 });
  });
});

describe('numeric piket value', () => {
  const base = predictionFixtures[0]!;
  it('keeps the numeric value alongside the display string', () => {
    const prediction = toPrediction({ ...base, piket: 'ПК 88+50', piket_value: 88.5 });
    expect(prediction.piketValue).toBe(88.5);
    expect(prediction.piket).toBe('ПК 88+50');
  });
  it('keeps the location even when ML support is false', () => {
    const unsupported: PredictionDto = {
      ...base,
      prediction_supported: false,
      risk_level: 'low',
      failure_probability: 0.01,
      piket_value: 42,
    };
    const prediction = toPrediction(unsupported);
    expect(prediction.piketValue).toBe(42);
    expect(prediction.riskLevel).toBeNull();
    expect(prediction.failureProbability).toBeNull();
  });
  it.each([[null], [Number.NaN]])('normalises %s to null', (value) => {
    expect(toPrediction({ ...base, piket_value: value }).piketValue).toBeNull();
  });
});
