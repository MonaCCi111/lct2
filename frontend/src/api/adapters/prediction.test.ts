import { describe, expect, it } from 'vitest';
import { predictionFixtures } from '../mocks/fixtures';
import { toPrediction } from './prediction';
import { toPredictionRow } from '../../pages/foundation/predictionRow';
describe('prediction contract', () => {
  it('preserves domain-specific critical risk at 46%', () => {
    const dto = predictionFixtures[0]!;
    const prediction = toPrediction(dto);
    expect(prediction).toMatchObject({
      failureProbability: 0.46,
      riskLevel: 'critical',
      maintenanceUrgency: 'FLASH_1_6H',
      healthIndex: 28,
    });
    expect(toPredictionRow(prediction).probability.replace(/\s/g, '')).toBe('46%');
  });
  it('never derives health or severity from probability', () => {
    expect(toPrediction({ ...predictionFixtures[0]!, failure_probability: 0.01 })).toMatchObject({
      riskLevel: 'critical',
      maintenanceUrgency: 'FLASH_1_6H',
      healthIndex: 28,
    });
  });
  it('suppresses misleading ML values for unsupported sensors', () => {
    const result = toPrediction({
      ...predictionFixtures[5]!,
      failure_probability: 0.01,
      risk_level: 'low',
      health_index_its: 99,
    });
    expect(result).toMatchObject({
      predictionSupported: false,
      failureProbability: null,
      riskLevel: null,
      healthIndex: null,
      modelDomain: null,
    });
    expect(toPredictionRow(result)).toMatchObject({ probability: '—', healthIndex: '—', risk: null });
  });
  it('maps every required scenario without changing backend values', () => {
    expect(predictionFixtures).toHaveLength(6);
    for (const dto of predictionFixtures) {
      const prediction = toPrediction(dto);
      expect(prediction.riskLevel).toBe(dto.risk_level);
      expect(prediction.maintenanceUrgency).toBe(dto.maintenance_urgency);
      expect(prediction.healthIndex).toBe(dto.health_index_its);
    }
  });
});
