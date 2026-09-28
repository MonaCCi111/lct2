import { ApiError } from '../../api/client/http';
import type { V2DecisionValue } from '../../api/v2/dto/types';

export interface DecisionAttempt {
  decision: V2DecisionValue;
  idempotencyKey: string;
}

export const createDecisionIdempotencyKey = () => crypto.randomUUID();

export function beginDecisionAttempt(
  current: DecisionAttempt | null,
  decision: V2DecisionValue,
  createKey: () => string = createDecisionIdempotencyKey,
): DecisionAttempt {
  return current?.decision === decision ? current : { decision, idempotencyKey: createKey() };
}

export const validateDecisionReason = (reason: string) =>
  reason.trim() === '' ? 'Укажите причину решения диспетчера.' : null;

export const decisionErrorMessage = (error: unknown) =>
  error instanceof ApiError && error.status === 409
    ? 'По этому черновику уже сохранено решение.'
    : error instanceof Error
      ? error.message
      : 'Не удалось сохранить решение.';
