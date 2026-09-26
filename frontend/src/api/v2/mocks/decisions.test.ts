import { beforeEach, describe, expect, it } from 'vitest';
import { v2ForecastDraftFixture } from './fixtures';
import {
  applyV2DecisionState,
  createV2Decision,
  listV2Decisions,
  resetV2DecisionStore,
  V2DecisionMockError,
} from './decisions';

describe('v2 decision mock store', () => {
  beforeEach(resetV2DecisionStore);

  it('stores an approved decision and replays the same idempotency key', () => {
    const request = { decision: 'approved' as const, reason: 'Проверено', idempotency_key: 'attempt-1' };
    const first = createV2Decision(v2ForecastDraftFixture.draft_id, request, '2026-09-26T12:00:00Z');
    const replay = createV2Decision(v2ForecastDraftFixture.draft_id, request, '2026-09-26T13:00:00Z');
    expect(replay).toEqual(first);
    expect(listV2Decisions(v2ForecastDraftFixture.draft_id)).toHaveLength(1);
    expect(applyV2DecisionState(v2ForecastDraftFixture)).toMatchObject({
      review_state: 'approved',
      decision: first,
    });
  });

  it('stores a rejected decision without creating a work order', () => {
    const decision = createV2Decision(
      v2ForecastDraftFixture.draft_id,
      { decision: 'rejected', reason: 'Не подтверждается данными', idempotency_key: 'attempt-2' },
      '2026-09-26T12:00:00Z',
    );
    expect(decision.decision).toBe('rejected');
    expect(decision.work_order_id).toBeNull();
  });

  it('rejects a missing reason with contract status 400', () => {
    try {
      createV2Decision(
        v2ForecastDraftFixture.draft_id,
        { decision: 'rejected', reason: ' ', idempotency_key: 'attempt-3' },
        '2026-09-26T12:00:00Z',
      );
      expect.unreachable('missing reason must fail');
    } catch (error) {
      expect(error).toBeInstanceOf(V2DecisionMockError);
      expect((error as V2DecisionMockError).status).toBe(400);
    }
  });

  it('returns 409 for a different attempt on an already decided draft', () => {
    createV2Decision(
      v2ForecastDraftFixture.draft_id,
      { decision: 'approved', reason: 'Проверено', idempotency_key: 'attempt-4' },
      '2026-09-26T12:00:00Z',
    );
    try {
      createV2Decision(
        v2ForecastDraftFixture.draft_id,
        { decision: 'rejected', reason: 'Другая попытка', idempotency_key: 'attempt-5' },
        '2026-09-26T12:01:00Z',
      );
      expect.unreachable('conflicting decision must fail');
    } catch (error) {
      expect(error).toBeInstanceOf(V2DecisionMockError);
      expect((error as V2DecisionMockError).status).toBe(409);
    }
  });
});
