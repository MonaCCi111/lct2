import type { Prediction } from '../../domain/prediction/types';
import { formatHealthIndex, formatProbability } from '../../utils/formatters';
export interface PredictionRow {
  id: string;
  sensorName: string;
  modelDomain: string;
  supported: boolean;
  probability: string;
  healthIndex: string;
  risk: Prediction['riskLevel'];
  urgency: Prediction['maintenanceUrgency'];
}
export function toPredictionRow(prediction: Prediction): PredictionRow {
  return {
    id: prediction.id,
    sensorName: prediction.sensorName,
    modelDomain: prediction.modelDomain ?? '—',
    supported: prediction.predictionSupported,
    probability: formatProbability(prediction.failureProbability),
    healthIndex: formatHealthIndex(prediction.healthIndex),
    risk: prediction.riskLevel,
    urgency: prediction.maintenanceUrgency,
  };
}
