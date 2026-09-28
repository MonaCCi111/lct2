import { beforeEach, describe, expect, it } from 'vitest';
import { listTickets, resetTicketStore } from '../../mocks/tickets';
import { createV2Decision, latestV2Decision, resetV2DecisionStore } from './decisions';
import { v2ForecastDraftFixture, v2ObservedDraftFixture } from './fixtures';
import {
  createV2WorkOrder,
  findV2WorkOrder,
  listV2WorkOrders,
  resetV2WorkOrderStore,
  V2WorkOrderMockError,
} from './work-orders';

const request = {
  draft_id: v2ForecastDraftFixture.draft_id,
  work_type: 'Диагностика',
  description: 'Проверить цепь питания',
  idempotency_key: 'work-order-attempt-1',
};

function expectStatus(action: () => unknown, status: number) {
  try {
    action();
    expect.unreachable(`expected status ${status}`);
  } catch (error) {
    expect(error).toBeInstanceOf(V2WorkOrderMockError);
    expect((error as V2WorkOrderMockError).status).toBe(status);
  }
}

describe('v2 work-order mock store', () => {
  beforeEach(() => {
    resetV2DecisionStore();
    resetV2WorkOrderStore();
    resetTicketStore();
  });

  it('creates from an approved draft and exposes list/detail and decision relation', () => {
    createV2Decision(
      v2ForecastDraftFixture.draft_id,
      { decision: 'approved', reason: 'Проверено', idempotency_key: 'decision-approved' },
      '2026-09-26T12:00:00Z',
    );
    const created = createV2WorkOrder(request, v2ForecastDraftFixture, '2026-09-26T13:00:00Z');
    expect(created.work_order_id).toBe('WO-V2-0001');
    expect(listV2WorkOrders()).toEqual([created]);
    expect(findV2WorkOrder(created.work_order_id)).toEqual(created);
    expect(latestV2Decision(v2ForecastDraftFixture.draft_id)?.work_order_id).toBe(created.work_order_id);
  });

  it('rejects pending and rejected drafts', () => {
    expectStatus(() => createV2WorkOrder(request, v2ForecastDraftFixture, '2026-09-26T13:00:00Z'), 409);
    createV2Decision(
      v2ObservedDraftFixture.draft_id,
      { decision: 'rejected', reason: 'Отклонено', idempotency_key: 'decision-rejected' },
      '2026-09-26T12:00:00Z',
    );
    expectStatus(
      () =>
        createV2WorkOrder(
          { ...request, draft_id: v2ObservedDraftFixture.draft_id },
          v2ObservedDraftFixture,
          '2026-09-26T13:00:00Z',
        ),
      409,
    );
  });

  it('replays one idempotency key and blocks a duplicate work order', () => {
    createV2Decision(
      v2ForecastDraftFixture.draft_id,
      { decision: 'approved', reason: 'Проверено', idempotency_key: 'decision-approved' },
      '2026-09-26T12:00:00Z',
    );
    const created = createV2WorkOrder(request, v2ForecastDraftFixture, '2026-09-26T13:00:00Z');
    expect(createV2WorkOrder(request, v2ForecastDraftFixture, '2026-09-26T14:00:00Z')).toEqual(created);
    expectStatus(
      () =>
        createV2WorkOrder(
          { ...request, idempotency_key: 'work-order-attempt-2' },
          v2ForecastDraftFixture,
          '2026-09-26T14:00:00Z',
        ),
      409,
    );
  });

  it('does not mutate the legacy v1 ticket store', () => {
    const before = listTickets();
    createV2Decision(
      v2ForecastDraftFixture.draft_id,
      { decision: 'approved', reason: 'Проверено', idempotency_key: 'decision-approved' },
      '2026-09-26T12:00:00Z',
    );
    createV2WorkOrder(request, v2ForecastDraftFixture, '2026-09-26T13:00:00Z');
    expect(listTickets()).toEqual(before);
  });
});
