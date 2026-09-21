import { delay, http, HttpResponse } from 'msw';
import { apiConfig } from '../client/config';
import { objectFixtures, predictionFixtures, ticketFixtures } from './fixtures';
import { dashboardSummaryFixture } from './dashboard';
import { operationalPredictions, objectStatusFixtures } from './operational';
import { objectDetailFixtures, objectTopologyFixture, objectWorkspacePredictions } from './object-workspace';

const endpoint = (path: string) => `${apiConfig.baseUrl}${path}`;
const missing = () => HttpResponse.json({ message: 'Запись не найдена.' }, { status: 404 });
const objectMissing = () =>
  HttpResponse.json(
    { message: 'Объект с указанным идентификатором отсутствует или недоступен.' },
    { status: 404 },
  );
// Operational queue, object workspace and foundation fixtures are separate demo selections.
function predictionSource(params: URLSearchParams) {
  if (params.get('view') === 'operational') return operationalPredictions;
  const objectId = params.get('object_id');
  if (objectId === null) return predictionFixtures;
  const scoped = objectWorkspacePredictions.filter((item) => String(item.object_id) === objectId);
  return scoped.length > 0 ? scoped : predictionFixtures;
}
// Optional ?scenario=empty|error|slow provides repeatable API-state checks.
async function scenario(request: Request) {
  const value = new URL(request.url).searchParams.get('scenario');
  await delay(value === 'slow' ? 2500 : 250);
  if (value === 'error')
    return HttpResponse.json({ message: 'Сервис временно недоступен.' }, { status: 503 });
  if (value === 'empty') return HttpResponse.json([]);
  return null;
}
export const handlers = [
  http.get(endpoint('/dashboard/summary'), async () => {
    await delay(250);
    return HttpResponse.json(dashboardSummaryFixture);
  }),
  http.get(endpoint('/system'), async () => {
    await delay(150);
    return HttpResponse.json({ status: 'operational', updated_at: new Date().toISOString() });
  }),
  http.get(endpoint('/predictions'), async ({ request }) => {
    const result = await scenario(request);
    if (result) return result;
    const params = new URL(request.url).searchParams;
    return HttpResponse.json(
      predictionSource(params).filter(
        (item) =>
          (!params.has('object_id') || String(item.object_id) === params.get('object_id')) &&
          (!params.has('risk_level') || item.risk_level === params.get('risk_level')),
      ),
    );
  }),
  http.get(endpoint('/predictions/:id'), async ({ params }) => {
    await delay(250);
    const item = [...predictionFixtures, ...operationalPredictions, ...objectWorkspacePredictions].find(
      (item) => item.prediction_id === params.id,
    );
    return item ? HttpResponse.json(item) : missing();
  }),
  http.get(
    endpoint('/objects'),
    async ({ request }) => (await scenario(request)) ?? HttpResponse.json(objectFixtures),
  ),
  http.get(
    endpoint('/objects/status-summary'),
    async ({ request }) => (await scenario(request)) ?? HttpResponse.json(objectStatusFixtures),
  ),
  // Static and nested object routes must stay above the `/objects/:id` pattern.
  http.get(endpoint('/objects/:objectId/topology'), async ({ request, params }) => {
    // Topology is an object, so the shared array-based `empty` scenario does not apply.
    const state = new URL(request.url).searchParams.get('scenario');
    await delay(state === 'slow' ? 2500 : 250);
    if (state === 'error')
      return HttpResponse.json({ message: 'Сервис временно недоступен.' }, { status: 503 });
    const detail = objectDetailFixtures.find((item) => String(item.object_id) === params.objectId);
    if (!detail) return objectMissing();
    const topology = objectTopologyFixture(detail.object_id, detail.object_name);
    return HttpResponse.json(
      state === 'empty' ? { ...topology, piket_min: null, piket_max: null, segments: [] } : topology,
    );
  }),
  http.get(endpoint('/objects/:id'), async ({ params }) => {
    await delay(250);
    const detail = objectDetailFixtures.find((item) => String(item.object_id) === params.id);
    return detail ? HttpResponse.json(detail) : objectMissing();
  }),
  http.get(
    endpoint('/tickets'),
    async ({ request }) => (await scenario(request)) ?? HttpResponse.json(ticketFixtures),
  ),
];
