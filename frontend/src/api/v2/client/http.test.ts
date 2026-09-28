import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { v2ApiConfig } from './config';
import { v2ApiGet } from './http';

const server = setupServer();

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

describe('v2 HTTP contract errors', () => {
  it('preserves the backend code and details for a 422 response', async () => {
    server.use(
      http.get(`${v2ApiConfig.baseUrl}/drafts`, () =>
        HttpResponse.json(
          {
            code: 'unsupported_historical_time',
            message: 'Исторический срез недоступен.',
            details: { at: '2024-01-01T00:00:00' },
          },
          { status: 422 },
        ),
      ),
    );

    await expect(v2ApiGet('/drafts')).rejects.toMatchObject({
      status: 422,
      code: 'unsupported_historical_time',
      message: 'Исторический срез недоступен.',
      details: { at: '2024-01-01T00:00:00' },
    });
  });
});
