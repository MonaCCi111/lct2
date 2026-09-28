import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client/http';
import { beginWorkOrderAttempt, validateWorkOrderFields, workOrderErrorMessage } from './work-order-workflow';

describe('v2 work-order form workflow', () => {
  it('keeps one idempotency key for the current create attempt', () => {
    const createKey = vi.fn().mockReturnValue('work-attempt-1');
    const first = beginWorkOrderAttempt(null, createKey);
    expect(beginWorkOrderAttempt(first, createKey)).toBe(first);
    expect(createKey).toHaveBeenCalledOnce();
  });

  it('validates only the two required user fields', () => {
    expect(validateWorkOrderFields('', ' ')).toEqual({
      workType: 'Укажите тип работ.',
      description: 'Добавьте описание работ.',
    });
    expect(validateWorkOrderFields('Осмотр', 'Проверить оборудование')).toEqual({
      workType: null,
      description: null,
    });
  });

  it('maps 409 to the dedicated duplicate state', () => {
    expect(workOrderErrorMessage(new ApiError('conflict', 409, 'HTTP_ERROR'))).toBe(
      'Для этого решения уже создан наряд.',
    );
  });
});
