import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../../api/client/http';
import { beginDecisionAttempt, decisionErrorMessage, validateDecisionReason } from './decision-workflow';

describe('dispatcher decision workflow', () => {
  it('keeps one idempotency key throughout the same user attempt', () => {
    const createKey = vi.fn().mockReturnValueOnce('attempt-1').mockReturnValueOnce('attempt-2');
    const first = beginDecisionAttempt(null, 'approved', createKey);
    const rerendered = beginDecisionAttempt(first, 'approved', createKey);
    expect(rerendered).toBe(first);
    expect(rerendered.idempotencyKey).toBe('attempt-1');
    expect(createKey).toHaveBeenCalledOnce();
    expect(beginDecisionAttempt(null, 'approved', createKey).idempotencyKey).toBe('attempt-2');
  });

  it('requires a reason for approved and rejected contract requests', () => {
    expect(validateDecisionReason('')).toBe('Укажите причину решения диспетчера.');
    expect(validateDecisionReason('   ')).toBe('Укажите причину решения диспетчера.');
    expect(validateDecisionReason('Проверено диспетчером')).toBeNull();
  });

  it('turns a 409 into the dedicated conflict state', () => {
    expect(decisionErrorMessage(new ApiError('conflict', 409, 'HTTP_ERROR'))).toBe(
      'По этому черновику уже сохранено решение.',
    );
  });
});
