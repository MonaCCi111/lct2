import type { ReactNode } from 'react';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { delay, http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../api/mocks/handlers';
import { apiConfig } from '../../api/client/config';
import { dashboardSummaryFixture } from '../../api/mocks/dashboard';
import { TooltipProvider } from '../../components/ui/Tooltip';
import OverviewPage from './OverviewPage';

const server = setupServer(...handlers);
const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
const endpoint = (path: string) => `${apiConfig.baseUrl}${path}`;
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  client.clear();
});
afterAll(() => server.close());
function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter>{children}</MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>
  );
}
function mount() {
  return render(
    <Routes>
      <Route path="/" element={<OverviewPage />} />
      <Route path="/predictions/:id" element={<h1>Расследование shell</h1>} />
      <Route path="/objects/:id" element={<h1>Объект shell</h1>} />
    </Routes>,
    { wrapper },
  );
}
const queue = () => within(screen.getByRole('region', { name: 'Очередь рисков' }));
const summary = () => within(screen.getByRole('region', { name: 'Сводка инфраструктуры' }));
async function ready() {
  await screen.findByText('Показано 24 из 24 загруженных');
}

describe('Operational Center', () => {
  it('renders independent aggregate counts, Moscow timestamp, coverage and ticket summary', async () => {
    mount();
    await ready();
    expect(summary().getByText('137')).toBeVisible();
    expect(summary().getByText('8')).toBeVisible();
    expect(summary().getByText('32')).toBeVisible();
    expect(summary().getByText('42')).toBeVisible();
    // Freshness reads as a relative age; the exact Moscow timestamp stays in the title.
    expect(screen.getByTitle('20.09.2026, 18:42 МСК')).toHaveTextContent(/^Обновлено /);
    expect(screen.getByText('80%')).toBeVisible();
    expect(screen.queryByText('8000%')).not.toBeInTheDocument();
    expect(within(screen.getByRole('region', { name: 'Сводка нарядов' })).getByText('19')).toBeVisible();
  });
  it('retains 46% critical and opens a focused queue row with Enter', async () => {
    mount();
    await ready();
    const row = queue().getByRole('row', { name: 'Открыть прогноз: Температура ВШ-3, объект Фита' });
    expect(within(row).getByText('Критический')).toBeVisible();
    expect(within(row).getByText(/46\s*%/)).toBeVisible();
    expect(within(row).getByText('1–6 ч')).toBeVisible();
    row.focus();
    await userEvent.keyboard('{Enter}');
    expect(screen.getByRole('heading', { name: 'Расследование shell' })).toBeVisible();
  });
  it('navigates from a row click and from object status links', async () => {
    const first = mount();
    await ready();
    await userEvent.click(queue().getByRole('row', { name: /Температура ВШ-3/ }));
    expect(screen.getByText('Расследование shell')).toBeVisible();
    first.unmount();
    mount();
    await ready();
    await userEvent.click(
      within(screen.getByRole('region', { name: 'Состояние объектов' })).getByRole('link', {
        name: /объект Фита/,
      }),
    );
    expect(screen.getByText('Объект shell')).toBeVisible();
  });
  it('loads blocks independently with local skeletons', async () => {
    server.use(
      http.get(endpoint('/dashboard/summary'), async () => {
        await delay(800);
        return HttpResponse.json(dashboardSummaryFixture);
      }),
    );
    mount();
    expect(summary().getByRole('status', { name: 'Загрузка сводки' })).toBeInTheDocument();
    expect(queue().getByRole('status')).toHaveTextContent('Загрузка');
    expect(screen.getByRole('status', { name: 'Загрузка объектов' })).toBeInTheDocument();
    await ready();
    expect(summary().getByRole('status')).toBeInTheDocument();
    await waitFor(() => expect(summary().getByText('137')).toBeVisible());
  });
  it('keeps queue and objects working when summary fails', async () => {
    server.use(
      http.get(endpoint('/dashboard/summary'), () =>
        HttpResponse.json({ message: 'Ошибка сводки' }, { status: 503 }),
      ),
    );
    mount();
    await ready();
    expect(summary().getByRole('alert')).toHaveTextContent('Ошибка сводки');
    expect(screen.getByText('Показано объектов: 8')).toBeVisible();
  });
  it('keeps summary and objects working when predictions fail', async () => {
    server.use(
      http.get(endpoint('/predictions'), () =>
        HttpResponse.json({ message: 'Ошибка очереди' }, { status: 503 }),
      ),
    );
    mount();
    await waitFor(() => expect(summary().getByText('137')).toBeVisible());
    expect(queue().getByRole('alert')).toHaveTextContent('Ошибка очереди');
    expect(await screen.findByText('Показано объектов: 8')).toBeVisible();
  });
  it('keeps summary and queue working when object aggregates fail', async () => {
    server.use(
      http.get(endpoint('/objects/status-summary'), () =>
        HttpResponse.json({ message: 'Ошибка объектов' }, { status: 503 }),
      ),
    );
    mount();
    await ready();
    expect(summary().getByText('137')).toBeVisible();
    expect(
      within(screen.getByRole('region', { name: 'Состояние объектов' })).getByRole('alert'),
    ).toHaveTextContent('Ошибка объектов');
  });
  it('shows an empty queue without hiding objects or inventing zero summary counts', async () => {
    server.use(http.get(endpoint('/predictions'), () => HttpResponse.json([])));
    mount();
    await screen.findByText('Активных рисков нет');
    expect(screen.getByText('Система не обнаружила прогнозов, требующих внимания диспетчера.')).toBeVisible();
    expect(await screen.findByText('Показано объектов: 8')).toBeVisible();
    expect(summary().getByText('137')).toBeVisible();
  });
  it('filters the loaded queue by urgency, object and search without changing summary', async () => {
    mount();
    await ready();
    await userEvent.click(screen.getByRole('button', { name: '1–6 ч' }));
    expect(queue().getByText('Показано 4 из 24 загруженных')).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText('Объект в очереди'), '203');
    expect(queue().getByText('Показано 1 из 24 загруженных')).toBeVisible();
    await userEvent.type(screen.getByRole('searchbox'), 'нет такого датчика');
    expect(queue().getByText('Прогнозы не найдены')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Сбросить фильтры' }));
    expect(queue().getByText('Показано 24 из 24 загруженных')).toBeVisible();
    expect(summary().getByText('137')).toBeVisible();
  });
  it.each([
    ['/dashboard/summary', 'Обновить сводку', 'Сводка инфраструктуры', '137'],
    ['/predictions', 'Обновить очередь рисков', 'Очередь рисков', 'Температура ВШ-3'],
    ['/objects/status-summary', 'Обновить состояние объектов', 'Состояние объектов', 'объект Фита'],
  ])('retains cached data after failed refresh of %s', async (path, button, region, text) => {
    mount();
    await ready();
    await screen.findByText('Показано объектов: 8');
    server.use(
      http.get(endpoint(path), () => HttpResponse.json({ message: 'Ошибка обновления' }, { status: 503 })),
    );
    await userEvent.click(screen.getByRole('button', { name: button }));
    const block = within(screen.getByRole('region', { name: region }));
    await waitFor(() =>
      expect(block.getByText('Показаны сохранённые данные. Требуется обновление.')).toBeVisible(),
    );
    expect(block.getByText(text)).toBeVisible();
  });
  it('reads risk as coloured text in the queue while the object panel keeps its dots', async () => {
    mount();
    await ready();
    const riskCells = queue().getAllByRole('cell', { name: /Критический|Высокий|Умеренный/ });
    expect(riskCells.length).toBeGreaterThan(0);
    // The urgency squares already mark the row, so the queue drops the duplicate risk dot.
    for (const cell of riskCells) expect(cell.querySelector('.semantic-marker')).toBeNull();
    expect(riskCells[0]?.querySelector('.risk-indicator-text')).not.toBeNull();
    // Scoped change: the object panel still shows a dot next to each risk label.
    const panel = within(screen.getByRole('region', { name: 'Состояние объектов' }));
    expect(panel.getAllByText('Критический')[0]?.closest('.semantic-indicator')).toHaveClass(
      'risk-indicator',
    );
    expect(
      screen.getByRole('region', { name: 'Состояние объектов' }).querySelectorAll('.semantic-marker').length,
    ).toBeGreaterThan(0);
  });
  it('opens the object workspace from the object cell without opening the prediction', async () => {
    mount();
    await ready();
    await userEvent.click(queue().getAllByRole('link', { name: 'объект Фита' })[0]!);
    expect(screen.getByRole('heading', { name: 'Объект shell' })).toBeVisible();
    expect(screen.queryByText('Расследование shell')).not.toBeInTheDocument();
  });
  it('explains the urgency squares from a keyboard-reachable header hint', async () => {
    mount();
    await ready();
    const hint = queue().getByRole('button', { name: 'Как читать индикатор срочности' });
    hint.focus();
    expect(hint).toHaveFocus();
    const tooltip = await screen.findByRole('tooltip');
    // Squares never replace the label: every step is spelled out.
    for (const label of ['1–6 ч', '6–24 ч', '24–48 ч'])
      expect(within(tooltip).getByText(label)).toBeInTheDocument();
  });
});
