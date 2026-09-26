import type { V2DecisionDto, V2DecisionRequestDto, V2DraftDto } from '../dto/types';

let decisions: V2DecisionDto[] = [];
let sequence = 0;

export class V2DecisionMockError extends Error {
  constructor(
    message: string,
    public readonly status: number,
  ) {
    super(message);
  }
}

export function resetV2DecisionStore() {
  decisions = [];
  sequence = 0;
}

export const listV2Decisions = (draftId: string) =>
  decisions.filter((item) => item.draft_id === draftId).map((item) => ({ ...item }));

export function createV2Decision(draftId: string, body: V2DecisionRequestDto, now: string): V2DecisionDto {
  const idempotent = decisions.find((item) => item.idempotency_key === body.idempotency_key);
  if (idempotent) return { ...idempotent };

  if (body.decision !== 'approved' && body.decision !== 'rejected')
    throw new V2DecisionMockError('Допустимы только решения approved и rejected.', 400);
  if (body.reason?.trim() === '') throw new V2DecisionMockError('Укажите причину решения диспетчера.', 400);
  if (!body.idempotency_key?.trim())
    throw new V2DecisionMockError('Для решения требуется idempotency_key.', 400);
  if (decisions.some((item) => item.draft_id === draftId))
    throw new V2DecisionMockError('По этому черновику уже сохранено решение.', 409);

  sequence += 1;
  const decision: V2DecisionDto = {
    decision_id: `review-decision-${String(sequence).padStart(4, '0')}`,
    draft_id: draftId,
    decision: body.decision,
    reason: body.reason.trim(),
    author_id: 'dispatcher.demo',
    decided_at: now,
    idempotency_key: body.idempotency_key,
    supersedes_decision_id: null,
    work_order_id: null,
  };
  decisions = [...decisions, decision];
  return { ...decision };
}

export function applyV2DecisionState(draft: V2DraftDto): V2DraftDto {
  const history = listV2Decisions(draft.draft_id);
  const current = history.at(-1);
  return current ? { ...draft, review_state: current.decision, decision: current } : { ...draft };
}
