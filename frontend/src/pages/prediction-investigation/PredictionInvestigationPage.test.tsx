import type { ReactNode } from 'react';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterAll, afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { delay, http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../api/mocks/handlers';
import { apiConfig } from '../../api/client/config';
import { TooltipProvider } from '../../components/ui/Tooltip';
import PredictionInvestigationPage from './PredictionInvestigationPage';

const server = setupServer(...handlers);
const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
const endpoint = (path: string) => `${apiConfig.baseUrl}${path}`;
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  client.clear();
});
afterAll(() => server.close());

function TicketsStub() {
  const [params] = useSearchParams();
  return (
    <h1>{`Наряды shell predictionId=${params.get('predictionId') ?? '-'} ticketId=${params.get('ticketId') ?? '-'}`}</h1>
  );
}
function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
}
function mount(predictionId: string) {
  return render(
    <MemoryRouter initialEntries={[`/predictions/${predictionId}`]}>
      <Routes>
        <Route path="/predictions/:predictionId" element={<PredictionInvestigationPage />} />
        <Route path="/predictions" element={<h1>Журнал прогнозов</h1>} />
        <Route path="/objects/:objectId" element={<h1>Рабочее пространство объекта</h1>} />
        <Route path="/tickets" element={<TicketsStub />} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  );
}
const telemetry = () => within(screen.getByRole('region', { name: 'Телеметрия канала' }));
const context = () => within(screen.getByRole('complementary', { name: 'Оценка прогноза' }));
const summary = () => screen.getByTestId('telemetry-summary').textContent ?? '';
async function ready(name = 'Температура ВШ-3') {
  await screen.findByRole('heading', { level: 1, name });
  await waitFor(() => expect(screen.getByTestId('telemetry-summary')).toBeInTheDocument());
}

describe('Prediction Investigation', () => {
  it('renders the prediction, its context and Moscow timestamps', async () => {
    mount('OW-004');
    await ready();
    expect(screen.getByText('Температура')).toBeVisible();
    expect(screen.getByRole('link', { name: 'объект θ' })).toHaveAttribute('title', 'объект Фита');
    expect(screen.getByText('ПК 89+40')).toBeVisible();
    // Freshness reads as a relative age; the exact Moscow timestamp stays in the title.
    expect(screen.getByTitle('20.09.2026, 18:38 МСК')).toHaveTextContent(/^Обновлено /);
    expect(screen.getByText('Ожидает рассмотрения')).toBeVisible();
  });
  it('keeps 46% ANALOG_TEMP critical and shows ready urgency wording', async () => {
    mount('OW-004');
    await ready();
    expect(context().getByText('Критический')).toBeVisible();
    expect(context().getByText(/46\s*%/)).toBeVisible();
    expect(context().getByText('Требуется проверка в течение 1–6 часов')).toBeVisible();
    expect(context().getByText('1–6 ч')).toBeVisible();
    // Lead time must never be presented as a moment of failure.
    expect(screen.queryByText(/Отказ произойдёт/)).not.toBeInTheDocument();
  });
  it('shows the health index compactly with a scale instead of a gauge', async () => {
    mount('OW-004');
    await ready();
    expect(context().getByText('54')).toBeVisible();
    expect(context().getByText('/ 100')).toBeVisible();
    expect(
      context().getByRole('img', { name: 'Индекс технического состояния 54 из 100' }),
    ).toBeInTheDocument();
  });
  it('renders numbered risk factors and the backend recommendation verbatim', async () => {
    mount('OW-004');
    await ready();
    const factors = context().getAllByRole('listitem');
    expect(factors[0]).toHaveTextContent('Зависание младшего бита АЦП (16 ч постоянного значения)');
    expect(factors[1]).toHaveTextContent('Высокий шум термопары (СКО = 2,84 °C)');
    expect(context().getByText('Калибровка измерительного тракта или замена термопары.')).toBeVisible();
  });
  it('renders a numeric telemetry series with its own statistics', async () => {
    mount('OW-004');
    await ready();
    expect(summary()).toContain('Телеметрия:');
    expect(summary()).toContain('144 точек');
    expect(summary()).toMatch(/Минимум .+ °C/);
    expect(telemetry().getByText('Точек')).toBeVisible();
    expect(telemetry().getByText('144')).toBeVisible();
  });
  it('renders a state telemetry series with real state labels', async () => {
    mount('OW-005');
    await ready('Фаза B · тяговый ввод');
    expect(summary()).toContain('Телеметрия состояний');
    expect(summary()).toContain('Норма');
    expect(summary()).toContain('Отказ');
    expect(telemetry().getByText('Последнее состояние')).toBeVisible();
  });
  it('marks chatter and alarm events without painting the whole chart', async () => {
    mount('OW-005');
    await ready('Фаза B · тяговый ввод');
    const events = within(telemetry().getByRole('list'));
    expect(events.getAllByText('Дребезг сигнала').length).toBeGreaterThan(0);
    expect(events.getAllByText('Аварийное значение').length).toBeGreaterThan(0);
    expect(events.getAllByText(/\d{2}\.\d{2}\.\d{4}, \d{2}:\d{2} МСК/).length).toBeGreaterThan(0);
  });
  it('switches the telemetry range and requests a new absolute window', async () => {
    const requests: string[] = [];
    server.events.on('request:start', ({ request }) => {
      if (request.url.includes('/telemetry')) requests.push(request.url);
    });
    mount('OW-004');
    await ready();
    expect(telemetry().getByText('144')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: '6 ч' }));
    await waitFor(() => expect(telemetry().getByText('96')).toBeVisible());
    expect(screen.getByRole('button', { name: '6 ч' })).toHaveAttribute('aria-pressed', 'true');
    const last = new URL(requests.at(-1) ?? '');
    expect(last.searchParams.get('limit')).toBe('96');
    const from = Date.parse(last.searchParams.get('date_from') ?? '');
    const to = Date.parse(last.searchParams.get('date_to') ?? '');
    expect(to - from).toBe(6 * 3_600_000);
  });
  it('shows a telemetry skeleton while the prediction context is already available', async () => {
    server.use(
      http.get(endpoint('/sensors/:channelId/telemetry'), async () => {
        await delay(900);
        return HttpResponse.json({ telemetry: [], points_count: 0, channel_id: 30004 });
      }),
    );
    mount('OW-004');
    await screen.findByRole('heading', { level: 1, name: 'Температура ВШ-3' });
    expect(telemetry().getByRole('status', { name: 'Загрузка телеметрии' })).toBeInTheDocument();
    expect(context().getByText('Критический')).toBeVisible();
  });
  it('keeps the prediction usable when telemetry fails', async () => {
    server.use(
      http.get(endpoint('/sensors/:channelId/telemetry'), () =>
        HttpResponse.json({ message: 'Сервис телеметрии временно недоступен.' }, { status: 503 }),
      ),
    );
    mount('OW-004');
    await screen.findByRole('heading', { level: 1, name: 'Температура ВШ-3' });
    expect(
      await telemetry().findByText('Не удалось загрузить телеметрию. Данные прогноза остаются доступны.'),
    ).toBeVisible();
    expect(telemetry().getByRole('button', { name: 'Повторить' })).toBeVisible();
    expect(context().getByText('Критический')).toBeVisible();
    expect(context().getByText(/46\s*%/)).toBeVisible();
  });
  it('shows an empty telemetry state without hiding the prediction', async () => {
    mount('OW-001');
    await screen.findByRole('heading', { level: 1, name: 'Температура кабельного лотка КЛ-3' });
    expect(await telemetry().findByText('Телеметрия отсутствует')).toBeVisible();
    expect(telemetry().getByText('За выбранный период данные не получены.')).toBeVisible();
    expect(context().getByText('Низкий')).toBeVisible();
  });
  it('keeps cached telemetry after a failed refresh', async () => {
    mount('OW-004');
    await ready();
    server.use(
      http.get(endpoint('/sensors/:channelId/telemetry'), () =>
        HttpResponse.json({ message: 'Ошибка обновления' }, { status: 503 }),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Обновить телеметрию' }));
    await waitFor(() =>
      expect(telemetry().getByText('Показаны сохранённые данные. Требуется обновление.')).toBeVisible(),
    );
    expect(telemetry().getByText('144')).toBeVisible();
  });
  it('reports unsupported ML without inventing low risk values', async () => {
    mount('DOOR-006');
    await ready('Дверь технического помещения');
    expect(screen.getByTestId('ml-unsupported')).toHaveTextContent('ML-анализ недоступен');
    expect(
      screen.getByText('Тип датчика пока не входит в область активного предиктивного мониторинга.'),
    ).toBeVisible();
    expect(context().queryByText('Низкий')).not.toBeInTheDocument();
    expect(context().queryByText(/1\s*%/)).not.toBeInTheDocument();
    expect(context().queryByText('99')).not.toBeInTheDocument();
    // Telemetry stays available for an unsupported channel.
    expect(summary()).toContain('Телеметрия состояний');
    expect(summary()).toContain('Закрыта');
  });
  it('reports a missing prediction and links back to the registry', async () => {
    mount('NOPE-404');
    expect(await screen.findByRole('heading', { name: 'Прогноз не найден' })).toBeVisible();
    expect(
      screen.getByText('Прогноз с указанным идентификатором отсутствует или больше недоступен.'),
    ).toBeVisible();
    await userEvent.click(screen.getByRole('link', { name: 'К журналу прогнозов' }));
    expect(screen.getByRole('heading', { name: 'Журнал прогнозов' })).toBeVisible();
  });
  it('navigates to the object workspace from the prediction context', async () => {
    mount('OW-004');
    await ready();
    await userEvent.click(screen.getByRole('link', { name: 'объект θ' }));
    expect(screen.getByRole('heading', { name: 'Рабочее пространство объекта' })).toBeVisible();
  });
  it('hands the prediction over to the tickets flow without creating anything', async () => {
    mount('OW-004');
    await ready();
    await userEvent.click(screen.getByRole('link', { name: /Создать наряд/ }));
    expect(
      screen.getByRole('heading', { name: 'Наряды shell predictionId=OW-004 ticketId=-' }),
    ).toBeVisible();
  });
  it('replaces the action with the existing work order when one is already created', async () => {
    mount('HYDRO-003');
    await ready('Дренажный насос № 2');
    expect(screen.queryByRole('link', { name: /Создать наряд/ })).not.toBeInTheDocument();
    expect(screen.getByTestId('existing-ticket')).toHaveTextContent('WO-2026-0917');
    expect(screen.getByText('Создан наряд')).toBeVisible();
    await userEvent.click(screen.getByRole('link', { name: /Открыть наряд/ }));
    expect(
      screen.getByRole('heading', { name: 'Наряды shell predictionId=- ticketId=WO-2026-0917' }),
    ).toBeVisible();
  });
  it('exposes technical details as a collapsed disclosure reachable by keyboard', async () => {
    mount('OW-004');
    await ready();
    const disclosure = screen.getByText('Технические данные');
    const details = disclosure.closest('details');
    // Collapsed by default so technical context never competes with operational information.
    expect(details).not.toHaveAttribute('open');
    // Native summary keyboard activation is a browser behaviour; jsdom only covers focus + toggle.
    disclosure.focus();
    expect(disclosure).toHaveFocus();
    await userEvent.click(disclosure);
    expect(details).toHaveAttribute('open');
    expect(screen.getByText('#30004')).toBeVisible();
    expect(screen.getByText('ANALOG_TEMP')).toBeVisible();
    expect(screen.getByText('4 ч (ориентировочно)')).toBeVisible();
  });
  it('keeps range controls and the action reachable from the keyboard', async () => {
    mount('OW-004');
    await ready();
    const range = screen.getByRole('button', { name: '48 ч' });
    range.focus();
    expect(range).toHaveFocus();
    await userEvent.keyboard('{Enter}');
    await waitFor(() => expect(telemetry().getByText('192')).toBeVisible());
    const cta = screen.getByRole('link', { name: /Создать наряд/ });
    cta.focus();
    expect(cta).toHaveFocus();
  });
  it('renders identical prediction semantics in both themes', async () => {
    for (const theme of ['dark', 'light']) {
      document.documentElement.dataset.theme = theme;
      const view = mount('OW-004');
      await ready();
      expect(context().getByText('Критический')).toBeVisible();
      expect(context().getByText(/46\s*%/)).toBeVisible();
      expect(summary()).toContain('144 точек');
      view.unmount();
      client.clear();
    }
    delete document.documentElement.dataset.theme;
  });
  it('requests telemetry only for the channel of the loaded prediction', async () => {
    const paths: string[] = [];
    server.events.on('request:start', ({ request }) => {
      const url = new URL(request.url);
      if (url.pathname.includes('/telemetry')) paths.push(url.pathname);
    });
    vi.useFakeTimers({ shouldAdvanceTime: true });
    vi.setSystemTime(new Date('2026-09-20T15:42:00Z'));
    mount('OW-016');
    await ready('Газ CO · венткамера ВК-6');
    vi.useRealTimers();
    expect(paths.every((path) => path.endsWith('/sensors/30016/telemetry'))).toBe(true);
    expect(summary()).toContain('ppm');
  });
});
