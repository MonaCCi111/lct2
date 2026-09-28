import type { ReactNode } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook, waitFor } from '@testing-library/react';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { handlers } from '../mocks/handlers';
import { dashboardSummaryFixture } from '../mocks/dashboard';
import { toDashboardSummary } from '../adapters/dashboard';
import { apiConfig } from '../client/config';
import { useDashboardSummary } from './hooks';
import { dashboardKeys } from './keys';

const server = setupServer(...handlers);
const requests: string[] = [];
const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
function wrapper({ children }: { children: ReactNode }) {
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
beforeAll(() => {
  server.events.on('request:start', ({ request }) => requests.push(new URL(request.url).pathname));
  server.listen({ onUnhandledRequest: 'error' });
});
afterEach(() => {
  server.resetHandlers();
  client.clear();
  requests.length = 0;
});
afterAll(() => server.close());

describe('Dashboard Summary query with MSW', () => {
  it('fetches only the summary endpoint and caches an adapted domain model', async () => {
    const { result } = renderHook(() => useDashboardSummary(), { wrapper });
    expect(result.current.isPending).toBe(true);
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(toDashboardSummary(dashboardSummaryFixture));
    expect(requests).toEqual(['/api/v1/dashboard/summary']);
    expect(client.getQueryData(dashboardKeys.summary())).toEqual(result.current.data);
  });

  it('exposes summary errors without falling back to predictions or other lists', async () => {
    server.use(
      http.get(`${apiConfig.baseUrl}/dashboard/summary`, () =>
        HttpResponse.json({ message: 'Сводка временно недоступна.' }, { status: 503 }),
      ),
    );
    const { result } = renderHook(() => useDashboardSummary(), { wrapper });
    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toMatchObject({ status: 503, message: 'Сводка временно недоступна.' });
    expect(result.current.data).toBeUndefined();
    expect(requests).toEqual(['/api/v1/dashboard/summary']);
  });
});
