import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { setupServer } from 'msw/node';
import { http, HttpResponse } from 'msw';
import { handlers } from '../mocks/handlers';
import { apiGet, ApiError } from './http';
import { apiConfig } from './config';
import type { PredictionDto } from '../dto/prediction';
const server = setupServer(...handlers);
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
describe('mock API and client', () => {
  it('loads fixtures and applies backend filters', async () => {
    expect(await apiGet<PredictionDto[]>('/predictions')).toHaveLength(6);
    const filtered = await apiGet<PredictionDto[]>('/predictions?risk_level=critical');
    expect(filtered).toHaveLength(2);
    expect(filtered[0]?.failure_probability).toBe(0.46);
    expect(await apiGet('/predictions?object_id=102')).toHaveLength(1);
  });
  it('supports detail, objects, tickets and system endpoints', async () => {
    expect(await apiGet('/predictions/TEMP-001')).toMatchObject({ risk_level: 'critical' });
    expect(await apiGet('/objects')).toHaveLength(2);
    expect(await apiGet('/objects/101')).toMatchObject({ object_id: 101 });
    expect(await apiGet('/tickets')).toEqual([]);
    expect(await apiGet('/system')).toMatchObject({ status: 'operational' });
  });
  it('reports missing records, empty and error responses', async () => {
    await expect(apiGet('/predictions/missing')).rejects.toMatchObject({ status: 404 });
    expect(await apiGet('/predictions?scenario=empty')).toEqual([]);
    await expect(apiGet('/predictions?scenario=error')).rejects.toBeInstanceOf(ApiError);
  });
  it('normalizes network and malformed JSON errors', async () => {
    server.use(http.get(`${apiConfig.baseUrl}/system`, () => HttpResponse.error()));
    await expect(apiGet('/system')).rejects.toMatchObject({ code: 'NETWORK_ERROR' });
    server.use(http.get(`${apiConfig.baseUrl}/system`, () => new HttpResponse('invalid')));
    await expect(apiGet('/system')).rejects.toMatchObject({ code: 'INVALID_RESPONSE' });
  });
  it('preserves cancellation without converting it into a network error', async () => {
    const controller = new AbortController();
    const result = apiGet('/predictions?scenario=slow', controller.signal);
    controller.abort();
    await expect(result).rejects.toMatchObject({ name: 'AbortError' });
  });
});
