import type { MaintenanceUrgency, Prediction } from '../../domain/prediction/types';
import {
  formatDateTime,
  formatHealthIndex,
  formatOperationalTime,
  formatProbability,
} from '../../utils/formatters';
export interface QueueFilters {
  urgency: MaintenanceUrgency | 'all';
  objectId: string;
  search: string;
}
export const initialQueueFilters: QueueFilters = { urgency: 'all', objectId: 'all', search: '' };
export interface RiskQueueRow {
  id: string;
  objectName: string;
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
export function filterQueue(predictions: readonly Prediction[], filters: QueueFilters) {
  const search = filters.search.trim().toLocaleLowerCase('ru-RU');
  return predictions.filter(
    (item) =>
      (filters.urgency === 'all' || item.maintenanceUrgency === filters.urgency) &&
      (filters.objectId === 'all' || String(item.objectId) === filters.objectId) &&
      (!search ||
        `${item.sensorName} ${item.objectName} ${item.piket ?? ''}`
          .toLocaleLowerCase('ru-RU')
          .includes(search)),
  );
}
export function queueObjectOptions(predictions: readonly Prediction[]) {
  const objects = new Map(predictions.map((item) => [String(item.objectId), item.objectName]));
  return [
    { value: 'all', label: 'Все объекты' },
    ...Array.from(objects, ([value, label]) => ({ value, label })).sort((a, b) =>
      a.label.localeCompare(b.label, 'ru'),
    ),
  ];
}
export function toRiskQueueRow(item: Prediction): RiskQueueRow {
  return {
    id: item.id,
    objectName: item.objectName,
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
