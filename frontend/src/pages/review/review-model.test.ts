import { describe, expect, it } from 'vitest';
import { toV2Draft } from '../../api/v2/adapters';
import { v2ForecastDraftFixture, v2ObservedDraftFixture } from '../../api/v2/mocks/fixtures';
import {
  basisLabels,
  formatForecastHorizon,
  formatIts,
  formatModelScore,
  parseLimitations,
  reviewStateLabels,
  toReviewQueueRows,
} from './review-model';

describe('historical review model', () => {
  it('maps contract labels without legacy risk semantics', () => {
    expect(basisLabels.forecast).toBe('Прогноз модели');
    expect(basisLabels.observed_status).toBe('Наблюдаемое событие');
    expect(reviewStateLabels).toEqual({
      pending: 'Ожидает проверки',
      approved: 'Одобрено',
      rejected: 'Отклонено',
    });
  });

  it('formats a model score as a decimal and preserves null as unavailable', () => {
    expect(formatModelScore(0.9848484848484849)).toBe('0.985');
    expect(formatModelScore(null)).toBe('—');
    expect(formatModelScore(0.9848484848484849)).not.toContain('%');
    expect(formatForecastHorizon(48)).toBe('48 ч');
    expect(formatForecastHorizon(undefined)).toBe('—');
  });

  it('splits limitations into separate contract values', () => {
    expect(parseLimitations('one; two;;three ')).toEqual(['one', 'two', 'three']);
  });

  it('does not turn a missing ITS value into zero', () => {
    expect(formatIts(null)).toBe('ИТС не рассчитан');
    expect(formatIts(0)).toBe('0');
  });

  it('joins draft rows to the v2 object catalogue and falls back to the object id', () => {
    const rows = toReviewQueueRows(
      [toV2Draft(v2ObservedDraftFixture), toV2Draft(v2ForecastDraftFixture)],
      [
        {
          objectId: 5333,
          objectName: 'ДУ объект Кси',
          kind: 'controlHouse',
          parentId: 5327,
          channelCount: 215,
        },
      ],
    );
    expect(rows[0]?.objectName).toBe('ДУ объект Кси');
    expect(rows[1]?.objectName).toBe('Объект 5003');
  });
});
