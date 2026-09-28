import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, useParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { delay, http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { apiConfig } from '../../api/client/config';
import type { ObjectStatusSummaryDto } from '../../api/dto/object-status';
import { TooltipProvider } from '../../components/ui/Tooltip';
import ObjectsPage from './ObjectsPage';

const item = (
  id: number,
  name: string,
  risk: ObjectStatusSummaryDto['risk_level'],
  critical: number,
  active: number,
): ObjectStatusSummaryDto => ({
  object_id: id,
  object_name: name,
  risk_level: risk,
  active_predictions: active,
  critical_predictions: critical,
  high_predictions: 7,
  ml_supported_channels: 722,
  channels_total: 860,
  updated_at: '2026-09-20T15:42:00Z',
});
const fixtures = [
  { ...item(8, 'объект Без оценки', null, 0, 1), ml_supported_channels: 0, channels_total: 0 },
  item(7, 'объект Низкий', 'low', 0, 1),
  item(6, 'объект Умеренный', 'medium', 0, 2),
  item(5, 'объект Высокий', 'high', 1, 3),
  item(2, 'объект Бета', 'critical', 2, 12),
  item(3, 'объект Альфа', 'critical', 2, 12),
  item(4, 'объект Дельта', 'critical', 2, 14),
  item(1, 'объект Фита', 'critical', 3, 18),
];
const endpoint = `${apiConfig.baseUrl}/objects/status-summary`;
const success = () => HttpResponse.json(fixtures);
const server = setupServer(http.get(endpoint, success));
let client: QueryClient;
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
});
afterEach(() => {
  server.resetHandlers();
  client.clear();
  delete document.documentElement.dataset.theme;
});
afterAll(() => server.close());
function DetailTarget() {
  return <h1>Объект {useParams().objectId}</h1>;
}
function mount() {
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter initialEntries={['/objects']}>
          <Routes>
            <Route path="/objects" element={<ObjectsPage />} />
            <Route path="/objects/:objectId" element={<DetailTarget />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}
const ready = () => screen.findByText('Показано 8 из 8 загруженных объектов');
const row = (name: string) => screen.getByRole('row', { name: `Открыть объект: объект ${name}` });

describe('Objects registry', () => {
  it('renders backend aggregates without deriving risk from their counts', async () => {
    mount();
    await ready();
    expect(within(row('Фита')).getByText('Критический')).toBeVisible();
    expect(within(row('Высокий')).getByText('Высокий')).toBeVisible();
    expect(within(row('Высокий')).getByText('1', { exact: true })).toBeVisible();
    expect(within(row('Умеренный')).getByText('Умеренный')).toBeVisible();
    expect(within(row('Низкий')).getByText('Низкий')).toBeVisible();
    expect(within(row('Без оценки')).getByText('Нет данных')).toBeVisible();
    expect(screen.getByText('Доступная выборка объектов с активными прогнозами')).toBeVisible();
  });
  it('orders by risk, critical count, active count and Russian object name, null last', async () => {
    mount();
    await ready();
    const names = screen
      .getAllByRole('row', { name: /^Открыть объект:/ })
      .map((element) => element.getAttribute('aria-label'));
    expect(names).toEqual(
      ['Фита', 'Дельта', 'Альфа', 'Бета', 'Высокий', 'Умеренный', 'Низкий', 'Без оценки'].map(
        (name) => `Открыть объект: объект ${name}`,
      ),
    );
  });
  it('searches names ignoring case and surrounding whitespace', async () => {
    mount();
    await ready();
    await userEvent.type(screen.getByRole('searchbox'), '  фИТА  ');
    expect(row('Фита')).toBeVisible();
    expect(screen.getByText('Показано 1 из 8 загруженных объектов')).toBeVisible();
  });
  it.each([
    ['critical', 4],
    ['high', 1],
    ['medium', 1],
    ['low', 1],
  ] as const)('filters %s risk', async (risk, count) => {
    mount();
    await ready();
    await userEvent.selectOptions(screen.getByLabelText('Состояние'), risk);
    expect(screen.getAllByRole('row', { name: /^Открыть объект:/ })).toHaveLength(count);
  });
  it('combines and resets filters with distinct filtered-empty feedback', async () => {
    mount();
    await ready();
    await userEvent.type(screen.getByRole('searchbox'), 'Фита');
    await userEvent.selectOptions(screen.getByLabelText('Состояние'), 'high');
    expect(screen.getByText('Объекты не найдены')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Сбросить фильтры' }));
    await ready();
    expect(screen.getByRole('searchbox')).toHaveValue('');
    expect(screen.getByLabelText('Состояние')).toHaveValue('all');
    expect(screen.getByRole('button', { name: 'Сбросить фильтры' })).toBeDisabled();
  });
  it.each(['click', 'Enter'])('navigates by %s to the correct object ID', async (method) => {
    mount();
    await ready();
    if (method === 'click') await userEvent.click(row('Фита'));
    else {
      row('Фита').focus();
      await userEvent.keyboard('{Enter}');
    }
    expect(screen.getByRole('heading', { name: 'Объект 1' })).toBeVisible();
  });
  it('uses table skeleton rows while the query is pending', async () => {
    server.use(
      http.get(endpoint, async () => {
        await delay('infinite');
        return success();
      }),
    );
    const view = mount();
    expect(screen.getByRole('status')).toHaveTextContent('Загрузка данных');
    expect(view.container.querySelectorAll('tbody tr')).toHaveLength(8);
    expect(view.container.querySelectorAll('.skeleton')).toHaveLength(56);
  });
  it('renders an initial error and retries through the existing query', async () => {
    server.use(
      http.get(endpoint, () => HttpResponse.json({ message: 'Реестр недоступен' }, { status: 503 })),
    );
    mount();
    expect(await screen.findByRole('alert')).toHaveTextContent('Реестр недоступен');
    server.use(http.get(endpoint, success));
    await userEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    await ready();
  });
  it('distinguishes a genuinely empty response from filtered-empty', async () => {
    server.use(http.get(endpoint, () => HttpResponse.json([])));
    mount();
    expect(await screen.findByText('Нет доступных объектов')).toBeVisible();
    expect(screen.queryByText('Объекты не найдены')).not.toBeInTheDocument();
  });
  it('keeps cached rows on refresh failure and can recover', async () => {
    mount();
    await ready();
    server.use(
      http.get(endpoint, () => HttpResponse.json({ message: 'Ошибка обновления' }, { status: 503 })),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Обновить реестр' }));
    expect(await screen.findByText('Показаны сохранённые данные. Требуется обновление.')).toBeVisible();
    expect(row('Фита')).toBeVisible();
    server.use(http.get(endpoint, success));
    await userEvent.click(screen.getByRole('button', { name: 'Обновить' }));
    await waitFor(() =>
      expect(
        screen.queryByText('Показаны сохранённые данные. Требуется обновление.'),
      ).not.toBeInTheDocument(),
    );
  });
  it('formats channel coverage and zero denominator without inventing data', async () => {
    mount();
    await ready();
    expect(within(row('Фита')).getByText('84%')).toBeVisible();
    expect(within(row('Фита')).getByText('722 / 860')).toBeVisible();
    expect(within(row('Без оценки')).getByText('—')).toBeVisible();
    expect(within(row('Фита')).getByText('20.09.2026, 18:42 МСК')).toBeVisible();
  });
  it.each(['light', 'dark'])('preserves labeled dot indicators in %s theme', async (theme) => {
    document.documentElement.dataset.theme = theme;
    const view = mount();
    await ready();
    expect(document.documentElement.dataset.theme).toBe(theme);
    expect(view.container.querySelectorAll('.risk-indicator')).toHaveLength(8);
    expect(view.container.querySelectorAll('.risk-marker[aria-hidden="true"]')).toHaveLength(8);
    expect(view.container.querySelectorAll('.badge')).toHaveLength(0);
  });
});
