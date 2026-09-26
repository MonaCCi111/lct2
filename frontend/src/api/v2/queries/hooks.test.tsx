import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { act, renderHook, waitFor } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { setupServer } from 'msw/node';
import { v2Handlers } from '../mocks/handlers';
import { v2ForecastDraftFixture } from '../mocks/fixtures';
import { resetV2DecisionStore } from '../mocks/decisions';
import {
  invalidateV2DecisionQueries,
  useCreateV2DraftDecision,
  useV2Draft,
  useV2DraftDecisions,
  useV2DraftEvidence,
  useV2Drafts,
  useV2Meta,
  useV2Object,
  useV2Objects,
} from './hooks';
import { v2DraftDecisionsPath, v2DraftEvidencePath, v2DraftPath } from './paths';
import { v2DraftKeys } from './keys';
import type { V2Decision } from '../domain/types';

const server = setupServer(...v2Handlers);
const requests: string[] = [];
let client: QueryClient;
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
beforeAll(() => {
  server.events.on('request:start', ({ request }) => requests.push(request.url));
  server.listen({ onUnhandledRequest: 'error' });
});
afterEach(() => {
  server.resetHandlers();
  client.clear();
  requests.length = 0;
  resetV2DecisionStore();
});
afterAll(() => server.close());

function mount<T>(hook: () => T) {
  client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return renderHook(hook, { wrapper });
}

describe('API v2 queries and dispatcher decisions', () => {
  it('fetches Meta, object list and object detail through the isolated v2 base URL', async () => {
    const meta = mount(() => useV2Meta());
    await waitFor(() => expect(meta.result.current.isSuccess).toBe(true));
    meta.unmount();

    const objects = mount(() => useV2Objects({ limit: 50, cursor: 'next object' }));
    await waitFor(() => expect(objects.result.current.isSuccess).toBe(true));
    expect(objects.result.current.data?.items[0]?.objectName).toBe('ДУ объект Кси');
    objects.unmount();

    const object = mount(() => useV2Object(5333));
    await waitFor(() => expect(object.result.current.isSuccess).toBe(true));
    expect(object.result.current.data?.objectId).toBe(5333);

    expect(requests.every((url) => url.startsWith('http://localhost:8000/api/v2/'))).toBe(true);
  });

  it('supports flat draft filters and keeps forecast score unchanged', async () => {
    const query = mount(() =>
      useV2Drafts({ basisKind: 'forecast', reviewState: 'pending', objectId: 5003, limit: 20 }),
    );
    await waitFor(() => expect(query.result.current.isSuccess).toBe(true));
    expect(query.result.current.data?.items).toHaveLength(1);
    expect(query.result.current.data?.items[0]?.score).toBe(v2ForecastDraftFixture.score);
    expect(requests[0]).toContain('basis_kind=forecast');
    expect(requests[0]).toContain('review_state=pending');
  });

  it('URL-encodes colon-rich draft IDs for detail and evidence requests', async () => {
    const id = v2ForecastDraftFixture.draft_id;
    expect(v2DraftPath(id)).toBe('/drafts/power_phase_scada_v2%3A178259%3A20251210T090000');
    expect(v2DraftEvidencePath(id, { cursor: 'next:evidence', limit: 10 })).toBe(
      '/drafts/power_phase_scada_v2%3A178259%3A20251210T090000/evidence?limit=10&cursor=next%3Aevidence',
    );

    const draft = mount(() => useV2Draft(id));
    await waitFor(() => expect(draft.result.current.isSuccess).toBe(true));
    expect(draft.result.current.data?.draftId).toBe(id);
    draft.unmount();

    const evidence = mount(() => useV2DraftEvidence(id, { cursor: 'next:evidence', limit: 10 }));
    await waitFor(() => expect(evidence.result.current.isSuccess).toBe(true));
    expect(evidence.result.current.data?.items[0]?.observedValue).toBe('Есть питание');
    expect(requests.some((url) => url.includes('power_phase_scada_v2%3A178259%3A20251210T090000'))).toBe(
      true,
    );
  });

  it('posts a decision and reads it back through append-only history', async () => {
    const id = v2ForecastDraftFixture.draft_id;
    expect(v2DraftDecisionsPath(id)).toContain('power_phase_scada_v2%3A178259%3A20251210T090000');
    const mutation = mount(() => useCreateV2DraftDecision());
    let createdDecision: V2Decision | undefined;
    await act(async () => {
      createdDecision = await mutation.result.current.mutateAsync({
        draftId: id,
        request: { decision: 'approved', reason: 'Проверено', idempotencyKey: 'hook-attempt' },
      });
    });
    expect(createdDecision?.decision).toBe('approved');
    mutation.unmount();

    const history = mount(() => useV2DraftDecisions(id));
    await waitFor(() => expect(history.result.current.isSuccess).toBe(true));
    expect(history.result.current.data).toHaveLength(1);
    expect(history.result.current.data?.[0]?.reason).toBe('Проверено');
  });

  it('invalidates only v2 draft detail, list and decision history keys', () => {
    const queryClient = new QueryClient();
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    invalidateV2DecisionQueries(queryClient, 'draft:1');
    expect(invalidate).toHaveBeenCalledTimes(3);
    expect(invalidate).toHaveBeenNthCalledWith(1, { queryKey: v2DraftKeys.lists() });
    expect(invalidate).toHaveBeenNthCalledWith(2, { queryKey: v2DraftKeys.detail('draft:1') });
    expect(invalidate).toHaveBeenNthCalledWith(3, { queryKey: v2DraftKeys.decisions('draft:1') });
  });
});
