import type { MaintenanceUrgency, Prediction } from '../../domain/prediction/types';
import {
  formatDateTime,
  formatHealthIndex,
  formatOperationalTime,
  formatProbability,
} from '../../utils/formatters';
import { healthIndexTone, probabilityTone, type MetricTone } from '../../utils/metric-tone';
import { formatObjectName, objectSearchText } from '../../utils/object-name';
export interface QueueFilters {
  urgency: MaintenanceUrgency | 'all';
  objectId: string;
  search: string;
}
export const initialQueueFilters: QueueFilters = { urgency: 'all', objectId: 'all', search: '' };
export interface RiskQueueRow {
  id: string;
  objectId: number;
  objectName: string;
  /** Raw name, kept for tooltips and accessible labels where the letter alone is too terse. */
  objectFullName: string;
  piket: string;
  sensorName: string;
  sensorType: string;
  urgency: Prediction['maintenanceUrgency'];
  risk: Prediction['riskLevel'];
  probability: string;
  probabilityTone: MetricTone;
  health: string;
  healthTone: MetricTone;
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
        `${item.sensorName} ${objectSearchText(item.objectName)} ${item.piket ?? ''}`
          .toLocaleLowerCase('ru-RU')
          .includes(search)),
  );
}
export function queueObjectOptions(predictions: readonly Prediction[]) {
  const objects = new Map(predictions.map((item) => [String(item.objectId), item.objectName]));
  return [
    { value: 'all', label: 'Все объекты' },
    // Sorted by the raw Russian name so the order stays alphabetical for an operator reading the
    // list, while the option itself shows the letter.
    ...Array.from(objects, ([value, name]) => ({ value, label: formatObjectName(name), name }))
      .sort((a, b) => a.name.localeCompare(b.name, 'ru'))
      .map(({ value, label }) => ({ value, label })),
  ];
}
export function toRiskQueueRow(item: Prediction): RiskQueueRow {
  return {
    id: item.id,
    objectId: item.objectId,
    objectName: formatObjectName(item.objectName),
    objectFullName: item.objectName,
    piket: item.piket ?? '—',
    sensorName: item.sensorName,
    sensorType: item.sensorType,
    urgency: item.maintenanceUrgency,
    risk: item.riskLevel,
    probability: formatProbability(item.failureProbability),
    probabilityTone: probabilityTone(item.failureProbability),
    health: formatHealthIndex(item.healthIndex),
    healthTone: healthIndexTone(item.healthIndex),
    updated: formatOperationalTime(item.generatedAt),
    fullUpdated: formatDateTime(item.generatedAt),
  };
}
