import type { V2BasisKind, V2ReviewState } from '../../api/v2/dto/types';
import type { V2Draft, V2Object } from '../../api/v2/domain/types';

export const basisLabels: Record<V2BasisKind, string> = {
  forecast: 'Прогноз модели',
  observed_status: 'Наблюдаемое событие',
};

export const reviewStateLabels: Record<V2ReviewState, string> = {
  pending: 'Ожидает проверки',
  approved: 'Одобрено',
  rejected: 'Отклонено',
};

export const formatModelScore = (score: number | null | undefined) =>
  score === null || score === undefined || !Number.isFinite(score) ? '—' : score.toFixed(3);

export const formatForecastHorizon = (hours: number | null | undefined) =>
  hours === null || hours === undefined || !Number.isFinite(hours) ? '—' : `${hours} ч`;

export const parseLimitations = (value: string | null | undefined) =>
  (value ?? '')
    .split(';')
    .map((item) => item.trim())
    .filter(Boolean);

export const formatIts = (value: number | null | undefined) =>
  value === null || value === undefined || !Number.isFinite(value) ? 'ИТС не рассчитан' : String(value);

export interface ReviewQueueRow extends V2Draft {
  objectName: string;
}

export function toReviewQueueRows(
  drafts: readonly V2Draft[],
  objects: readonly V2Object[],
): ReviewQueueRow[] {
  const names = new Map(objects.map((object) => [object.objectId, object.objectName]));
  return drafts.map((draft) => ({
    ...draft,
    objectName: names.get(draft.objectId) ?? `Объект ${draft.objectId}`,
  }));
}
