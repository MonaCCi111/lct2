import { delay, http, HttpResponse } from 'msw';
import { apiConfig } from '../client/config';
import { objectFixtures, predictionFixtures } from './fixtures';
import { dashboardSummaryFixture } from './dashboard';
import { operationalPredictions, objectStatusFixtures } from './operational';
import { objectDetailFixtures, objectTopologyFixture, objectWorkspacePredictions } from './object-workspace';
import { emptyTelemetry, telemetryFixture } from './telemetry';
import {
  TicketMockError,
  applyTicketState,
  applyTicketStateToAll,
  createTicket,
  findTicket,
  listTickets,
  updateTicketStatus,
} from './tickets';

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
      applyTicketStateToAll(
        predictionSource(params).filter(
          (item) =>
            (!params.has('object_id') || String(item.object_id) === params.get('object_id')) &&
            (!params.has('risk_level') || item.risk_level === params.get('risk_level')),
        ),
      ),
    );
  }),
  http.get(endpoint('/predictions/:id'), async ({ params }) => {
    await delay(250);
    const item = [...predictionFixtures, ...operationalPredictions, ...objectWorkspacePredictions].find(
      (item) => item.prediction_id === params.id,
    );
    return item ? HttpResponse.json(applyTicketState(item)) : missing();
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
  http.get(endpoint('/sensors/:channelId/telemetry'), async ({ request, params }) => {
    const url = new URL(request.url);
    const state = url.searchParams.get('scenario');
    await delay(state === 'slow' ? 2500 : 250);
    if (state === 'error')
      return HttpResponse.json({ message: 'Сервис телеметрии временно недоступен.' }, { status: 503 });
    const channelId = Number(params.channelId);
    if (!Number.isFinite(channelId)) return missing();
    const dateTo = Date.parse(url.searchParams.get('date_to') ?? '') || Date.now();
    const dateFrom = Date.parse(url.searchParams.get('date_from') ?? '') || dateTo - 24 * 3_600_000;
    const limit = Math.min(Number(url.searchParams.get('limit')) || 144, 1000);
    if (state === 'empty') return HttpResponse.json(emptyTelemetry(channelId));
    return HttpResponse.json(
      telemetryFixture(channelId, dateFrom, dateTo, limit) ?? emptyTelemetry(channelId),
    );
  }),
  http.get(endpoint('/tickets'), async ({ request }) => {
    const result = await scenario(request);
    if (result) return result;
    const params = new URL(request.url).searchParams;
    const search = (params.get('search') ?? '').trim().toLocaleLowerCase('ru');
    return HttpResponse.json(
      listTickets().filter(
        (item) =>
          (!params.has('status') || item.status === params.get('status')) &&
          (!params.has('prediction_id') || item.prediction_id === params.get('prediction_id')) &&
          (!params.has('object_id') || String(item.object_id) === params.get('object_id')) &&
          (search === '' ||
            `${item.ticket_id} ${item.title} ${item.object_name} ${item.prediction_id ?? ''} ${item.assignee ?? ''}`
              .toLocaleLowerCase('ru')
              .includes(search)),
      ),
    );
  }),
  http.get(endpoint('/tickets/:ticketId'), async ({ params }) => {
    await delay(200);
    const ticket = findTicket(String(params.ticketId));
    return ticket
      ? HttpResponse.json(ticket)
      : HttpResponse.json({ message: 'Указанный наряд отсутствует или больше недоступен.' }, { status: 404 });
  }),
  http.post(endpoint('/tickets'), async ({ request }) => {
    await delay(300);
    try {
      const body = (await request.json()) as Parameters<typeof createTicket>[0];
      return HttpResponse.json(createTicket(body, new Date().toISOString()), { status: 201 });
    } catch (error) {
      if (error instanceof TicketMockError)
        return HttpResponse.json({ message: error.message }, { status: error.status });
      return HttpResponse.json({ message: 'Некорректный запрос создания наряда.' }, { status: 400 });
    }
  }),
  http.patch(endpoint('/tickets/:ticketId/status'), async ({ request, params }) => {
    await delay(250);
    try {
      const body = (await request.json()) as { status: Parameters<typeof updateTicketStatus>[1] };
      return HttpResponse.json(
        updateTicketStatus(String(params.ticketId), body.status, new Date().toISOString()),
      );
    } catch (error) {
      if (error instanceof TicketMockError)
        return HttpResponse.json({ message: error.message }, { status: error.status });
      return HttpResponse.json({ message: 'Некорректный запрос смены статуса.' }, { status: 400 });
    }
  }),
];
