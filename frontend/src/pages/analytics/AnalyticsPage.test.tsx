import type { ReactNode } from 'react';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { beforeAll, afterAll, afterEach, describe, it, expect, vi } from 'vitest';
import { http, HttpResponse, delay } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../api/mocks/handlers';
import { analyticsFixtures, emptyAnalytics } from '../../api/mocks/analytics';
import { apiConfig } from '../../api/client/config';
import { analyticsKeys } from '../../api/queries/keys';
import AnalyticsPage from './AnalyticsPage';
import { RiskTimelineTooltip } from './RiskTimelineChart';
// jsdom has no layout; only container measurement is replaced, real Recharts is retained.
vi.mock('recharts', async (importOriginal) => {
  const actual = await importOriginal<typeof import('recharts')>();
  return {
    ...actual,
    ResponsiveContainer: ({ children }: { children: ReactNode }) => (
      <actual.ResponsiveContainer width={800} height={214}>
        {children}
      </actual.ResponsiveContainer>
    ),
  };
});
const server = setupServer(...handlers);
const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
const endpoint = `${apiConfig.baseUrl}/analytics/summary`;
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  client.clear();
  document.documentElement.removeAttribute('data-theme');
});
afterAll(() => server.close());
function mount() {
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={['/analytics']}>
        <Routes>
          <Route path="/analytics" element={<AnalyticsPage />} />
          <Route path="/objects/:id" element={<h1>Рабочее пространство объекта</h1>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}
const ready = () => screen.findByText('Активные риски');
describe('Analytics workspace', () => {
  it('renders default 7d summary, independent aggregate and Moscow timestamp', async () => {
    const requests: string[] = [];
    server.use(
      http.get(endpoint, ({ request }) => {
        requests.push(new URL(request.url).searchParams.get('range')!);
        return HttpResponse.json({
          ...analyticsFixtures['7d'],
          totals: { ...analyticsFixtures['7d'].totals, open_tickets: 42 },
        });
      }),
    );
    mount();
    await ready();
    expect(screen.getByRole('heading', { level: 1, name: 'Аналитика' })).toBeVisible();
    expect(screen.getByLabelText('Период аналитики')).toHaveValue('7d');
    expect(requests).toEqual(['7d']);
    expect(screen.getByText('42')).toBeVisible();
    expect(screen.getByText('Обновлено 20.09.2026, 18:42 МСК')).toBeVisible();
    expect(screen.getByText('137')).toBeVisible();
    expect(screen.getAllByText('80%').length).toBeGreaterThan(0);
    expect(client.getQueryData(analyticsKeys.summary('7d'))).toHaveProperty('totals.openTickets', 42);
  });
  it.each(['24h', '30d'] as const)('switches 7d to %s and isolates query caches', async (range) => {
    mount();
    await ready();
    await userEvent.selectOptions(screen.getByLabelText('Период аналитики'), range);
    await waitFor(() => expect(screen.getByTestId('risk-timeline')).toHaveAttribute('data-range', range));
    expect(screen.getByTestId('risk-timeline')).toHaveAttribute(
      'data-points',
      String(analyticsFixtures[range].risk_timeline.length),
    );
    expect(client.getQueryData(analyticsKeys.summary(range))).toHaveProperty('range', range);
    expect(client.getQueryData(analyticsKeys.summary('7d'))).toBeDefined();
  });
  it('renders three line series, textual summary and keyboard-readable data table without pie', async () => {
    const { container } = mount();
    await ready();
    expect(container.querySelectorAll('.recharts-line-curve')).toHaveLength(3);
    expect(container.querySelector('.recharts-pie')).toBeNull();
    expect(screen.getByRole('img', { name: /8 критических, 24 высоких, 61 умеренных/ })).toBeInTheDocument();
    await userEvent.click(screen.getByText('Таблица динамики · МСК'));
    expect(screen.getByRole('table', { name: 'Значения динамики рисков' })).toBeVisible();
  });
  it('renders a Moscow tooltip with all three counts', () => {
    render(
      <RiskTimelineTooltip active payload={[{ payload: analyticsFixtures['7d'].risk_timeline.at(-1) }]} />,
    );
    expect(screen.getByText('20.09.2026, 18:42 МСК')).toBeVisible();
    for (const text of ['Критические', 'Высокие', 'Умеренные', '8', '24', '61'])
      expect(screen.getByText(text)).toBeVisible();
  });
  it('renders urgency and canonical ticket distributions with textual alternatives', async () => {
    mount();
    await ready();
    const urgency = screen.getByRole('figure', { name: 'Распределение активных рисков по срочности' });
    expect(within(urgency).getAllByRole('listitem')).toHaveLength(4);
    expect(within(urgency).getByText('Штатный режим')).toBeVisible();
    const tickets = screen.getByRole('figure', { name: 'Распределение нарядов по текущему статусу' });
    expect(
      within(tickets)
        .getAllByRole('listitem')
        .map((x) => x.textContent),
    ).toEqual(['Черновик5', 'Согласован4', 'Отклонён2', 'Выполнен4']);
  });
  it('renders backend ranking without sorting or scoring', async () => {
    mount();
    await ready();
    const rows = within(screen.getByRole('table', { name: 'Объекты с наибольшим риском' })).getAllByRole(
      'row',
    );
    expect(rows.slice(1).map((x) => x.getAttribute('aria-label'))).toEqual(
      analyticsFixtures['7d'].top_objects.map((x) => `${x.object_name}: открыть объект`),
    );
  });
  it.each(['mouse', 'Enter'])('navigates from object row with %s', async (method) => {
    mount();
    await ready();
    const row = screen.getByRole('row', { name: 'объект Фита: открыть объект' });
    if (method === 'mouse') await userEvent.click(row);
    else {
      row.focus();
      await userEvent.keyboard('{Enter}');
    }
    expect(screen.getByRole('heading', { name: 'Рабочее пространство объекта' })).toBeVisible();
  });
  it('renders coverage as neutral data with human labels and domain codes', async () => {
    const { container } = mount();
    await ready();
    const table = screen.getByRole('table', { name: 'ML-покрытие по доменам' });
    for (const text of [
      'Электропитание',
      'Температура',
      'Газ',
      'Пожарная безопасность',
      'Гидромеханика',
      'ANALOG_TEMP',
      '84%',
    ])
      expect(within(table).getByText(text)).toBeVisible();
    expect(container.querySelectorAll('.analytics-coverage')).toHaveLength(5);
    expect(table.querySelector('.tone-critical')).toBeNull();
  });
  it('shows structured initial loading', () => {
    server.use(
      http.get(endpoint, async () => {
        await delay(1000);
        return HttpResponse.json(analyticsFixtures['7d']);
      }),
    );
    mount();
    expect(screen.getByRole('status', { name: 'Загрузка аналитики' })).toBeVisible();
  });
  it('shows initial error and retries successfully', async () => {
    server.use(http.get(endpoint, () => HttpResponse.json({}, { status: 503 })));
    mount();
    await screen.findByRole('alert');
    server.resetHandlers();
    await userEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    await ready();
  });
  it('shows empty aggregate without misleading charts', async () => {
    server.use(http.get(endpoint, () => HttpResponse.json(emptyAnalytics('7d'))));
    mount();
    expect(await screen.findByText('Аналитические данные отсутствуют')).toBeVisible();
    expect(screen.getByText('За выбранный период агрегаты пока не сформированы.')).toBeVisible();
    expect(screen.queryByTestId('risk-timeline')).toBeNull();
  });
  it('retains charts after failed refresh', async () => {
    mount();
    await ready();
    server.use(http.get(endpoint, () => HttpResponse.json({}, { status: 503 })));
    await userEvent.click(screen.getByRole('button', { name: 'Обновить аналитику' }));
    expect(await screen.findByText('Показаны сохранённые данные. Требуется обновление.')).toBeVisible();
    expect(screen.getByTestId('risk-timeline')).toHaveAttribute('data-range', '7d');
  });
  it('labels retained range while loading and after a failed range switch', async () => {
    mount();
    await ready();
    server.use(
      http.get(endpoint, async () => {
        await delay(150);
        return HttpResponse.json({}, { status: 503 });
      }),
    );
    await userEvent.selectOptions(screen.getByLabelText('Период аналитики'), '24h');
    expect(screen.getByText(/Показаны данные за 7 дней. Загружается период 24 ч/)).toBeVisible();
    expect(screen.queryByRole('status', { name: 'Загрузка аналитики' })).toBeNull();
    expect(
      await screen.findByText(/Показаны данные за 7 дней. Не удалось загрузить период 24 ч/),
    ).toBeVisible();
    expect(screen.getByTestId('risk-timeline')).toHaveAttribute('data-range', '7d');
  });
  it.each(['dark', 'light'])('keeps semantic content in %s theme', async (theme) => {
    document.documentElement.dataset.theme = theme;
    mount();
    await ready();
    expect(document.documentElement).toHaveAttribute('data-theme', theme);
    expect(screen.getByRole('img', { name: /Динамика активных рисков/ })).toBeInTheDocument();
  });
  it('range control is keyboard reachable and labelled', async () => {
    mount();
    await ready();
    const control = screen.getByRole('combobox', { name: 'Период аналитики' });
    // The header refresh control now precedes it, so walk the tab order instead of assuming it
    // is the very first stop.
    for (let stop = 0; stop < 5 && document.activeElement !== control; stop++) await userEvent.tab();
    expect(control).toHaveFocus();
  });
  it('contains no fabricated performance metrics or future failures', async () => {
    const { container } = mount();
    await ready();
    expect(container.textContent).not.toMatch(
      /MTTR|SLA|accuracy|precision|recall|ROC-AUC|F1|будущих аварий|ожидается.*отказов/i,
    );
  });
});
