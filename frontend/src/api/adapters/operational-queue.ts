import type { MaintenanceUrgency, Prediction } from '../../domain/prediction/types';
const priority: Record<MaintenanceUrgency, number> = {
  FLASH_1_6H: 0,
  URGENT_6_24H: 1,
  PLANNED_24_48H: 2,
  NORMAL: 3,
};
// Shared operational ordering: ready urgency values first, then probability DESC, then a stable ID.
export const compareByUrgency = (a: Prediction, b: Prediction) =>
  (a.maintenanceUrgency ? priority[a.maintenanceUrgency] : 4) -
    (b.maintenanceUrgency ? priority[b.maintenanceUrgency] : 4) ||
  (b.failureProbability ?? -1) - (a.failureProbability ?? -1) ||
  a.id.localeCompare(b.id);
export function toOperationalQueue(predictions: readonly Prediction[]): Prediction[] {
  return predictions
    .filter((item) => item.predictionSupported && item.riskLevel !== null && item.riskLevel !== 'low')
    .sort(compareByUrgency);
}
