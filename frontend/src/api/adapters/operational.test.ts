import { describe, expect, it } from 'vitest';
import { operationalPredictions, objectStatusFixtures } from '../mocks/operational';
import { predictionFixtures } from '../mocks/fixtures';
import { toPrediction } from './prediction';
import { toOperationalQueue } from './operational-queue';
import { toObjectStatusList } from './object-status';
describe('operational data adapters', () => {
  it('orders by urgency first, probability descending inside each group', () => {
    const sorted = toOperationalQueue(operationalPredictions.map(toPrediction));
    expect(sorted.slice(0, 5).map((row) => row.id)).toEqual([
      'OP-002',
      'OP-003',
      'OP-004',
      'OP-001',
      'OP-006',
    ]);
    expect(sorted.at(-1)?.id).toBe('OP-022');
    expect(sorted.find((row) => row.id === 'OP-001')).toMatchObject({
      failureProbability: 0.46,
      riskLevel: 'critical',
    });
  });
  it('excludes unsupported and low risk without converting them to active problems', () => {
    const result = toOperationalQueue(predictionFixtures.map(toPrediction));
    expect(result).toHaveLength(4);
    expect(result.some((row) => !row.predictionSupported || row.riskLevel === 'low')).toBe(false);
    expect(predictionFixtures).toHaveLength(6);
  });
  it('keeps null probability last inside its urgency group and does not mutate inputs', () => {
    const rows = operationalPredictions.slice(0, 2).map(toPrediction);
    const result = toOperationalQueue([{ ...rows[0]!, failureProbability: null }, rows[1]!]);
    expect(result.map((row) => row.id)).toEqual(['OP-002', 'OP-001']);
    expect(rows[0]?.id).toBe('OP-001');
  });
  it('orders object aggregates without computing their risk from counts', () => {
    const result = toObjectStatusList([...objectStatusFixtures].reverse());
    expect(result.slice(0, 2).map((row) => row.objectId)).toEqual([203, 201]);
    expect(result.at(-1)?.riskLevel).toBe('medium');
    const [item] = toObjectStatusList([
      { ...objectStatusFixtures[0]!, risk_level: 'medium', critical_predictions: 3 },
    ]);
    expect(item).toMatchObject({ riskLevel: 'medium', criticalPredictions: 3 });
  });
  it('covers all model domains in a separate 24-row demo', () => {
    expect(operationalPredictions).toHaveLength(24);
    expect(new Set(operationalPredictions.map((row) => row.model_domain)).size).toBe(5);
    expect(operationalPredictions.filter((row) => row.risk_level === 'critical')).toHaveLength(5);
    expect(operationalPredictions.filter((row) => row.risk_level === 'high')).toHaveLength(7);
  });
});
