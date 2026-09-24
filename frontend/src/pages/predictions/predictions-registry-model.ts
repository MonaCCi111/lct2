import type { Prediction, RiskLevel, MaintenanceUrgency, ReviewStatus } from '../../domain/prediction/types';
import type { SortState } from '../../components/data-display/DataTable';
import { compareByUrgency } from '../../api/adapters/operational-queue';
import { reviewStatusLabels } from '../../utils/formatters';
import { formatObjectName, objectSearchText } from '../../utils/object-name';

export interface RegistryFilters {
  search: string;
  risk: RiskLevel | 'all';
  urgency: MaintenanceUrgency | 'all';
  objectId: string;
}
export const initialFilters: RegistryFilters = { search: '', risk: 'all', urgency: 'all', objectId: 'all' };
// Shared with Prediction Investigation; the label map lives with the other domain formatters.
export const reviewLabels = reviewStatusLabels;
/**
 * Compact column labels for the registry. The domain status values are untouched and the full
 * wording stays reachable through the cell title.
 */
export const reviewShortLabels: Record<ReviewStatus, string> = {
  pending_review: 'Ожидает',
  acknowledged: 'Подтверждён',
  rejected: 'Отклонён',
  ticket_created: 'Наряд создан',
};
export const hasFilters = (filters: RegistryFilters) =>
  filters.search.trim() !== '' ||
  filters.risk !== 'all' ||
  filters.urgency !== 'all' ||
  filters.objectId !== 'all';
export function objectOptions(rows: readonly Prediction[]) {
  return [
    { value: 'all', label: 'Все объекты' },
    // Ordered by the raw Russian name; shown as the Greek letter the objects are marked with.
    ...Array.from(new Map(rows.map((row) => [String(row.objectId), row.objectName])), ([value, name]) => ({
      value,
      label: formatObjectName(name),
      name,
    }))
      .sort((a, b) => a.name.localeCompare(b.name, 'ru'))
      .map(({ value, label }) => ({ value, label })),
  ];
}
function compareNullable(a: number | null, b: number | null, direction: number) {
  if (a === null) return b === null ? 0 : 1;
  if (b === null) return -1;
  return (a - b) * direction;
}
function instant(value: string) {
  const time = /T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? Date.parse(value) : NaN;
  return Number.isFinite(time) ? time : null;
}
export function selectPredictions(rows: readonly Prediction[], filters: RegistryFilters, sort?: SortState) {
  const term = filters.search.trim().toLocaleLowerCase('ru');
  return rows
    .filter(
      (row) =>
        (filters.risk === 'all' || row.riskLevel === filters.risk) &&
        (filters.urgency === 'all' || row.maintenanceUrgency === filters.urgency) &&
        (filters.objectId === 'all' || String(row.objectId) === filters.objectId) &&
        `${row.sensorName} ${row.sensorType} ${objectSearchText(row.objectName)} ${row.piket ?? ''}`
          .toLocaleLowerCase('ru')
          .includes(term),
    )
    .sort((a, b) => {
      if (!sort) return compareByUrgency(a, b);
      const direction = sort.direction === 'asc' ? 1 : -1;
      const comparison =
        sort.column === 'probability'
          ? compareNullable(
              a.predictionSupported ? a.failureProbability : null,
              b.predictionSupported ? b.failureProbability : null,
              direction,
            )
          : sort.column === 'updated'
            ? compareNullable(instant(a.generatedAt), instant(b.generatedAt), direction)
            : sort.column === 'object'
              ? a.objectName.localeCompare(b.objectName, 'ru') * direction
              : 0;
      return comparison || compareByUrgency(a, b);
    });
}
