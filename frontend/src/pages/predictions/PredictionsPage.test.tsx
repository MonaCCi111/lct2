import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Routes, Route, useParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterAll, afterEach, beforeAll, beforeEach, describe, expect, it } from 'vitest';
import { delay, http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../api/mocks/handlers';
import { operationalPredictions } from '../../api/mocks/operational';
import { predictionFixtures } from '../../api/mocks/fixtures';
import { toPrediction } from '../../api/adapters/prediction';
import { apiConfig } from '../../api/client/config';
import { TooltipProvider } from '../../components/ui/Tooltip';
import { PredictionsRegistryTable } from './PredictionsRegistryTable';
import { initialFilters, selectPredictions } from './predictions-registry-model';
import PredictionsPage from './PredictionsPage';

const server = setupServer(...handlers);
const endpoint = `${apiConfig.baseUrl}/predictions`;
let client: QueryClient;
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
beforeEach(() => {
  client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
});
afterEach(() => {
  client.clear();
  server.resetHandlers();
  delete document.documentElement.dataset.theme;
});
afterAll(() => server.close());
function Target() {
  return <h1>Прогноз {useParams().predictionId}</h1>;
}
function mount() {
  return render(
    <QueryClientProvider client={client}>
      <TooltipProvider>
        <MemoryRouter initialEntries={['/predictions']}>
          <Routes>
            <Route path="/predictions" element={<PredictionsPage />} />
            <Route path="/predictions/:predictionId" element={<Target />} />
          </Routes>
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}
const ready = () => screen.findByText('Показано 24 из 24 загруженных прогнозов');
const rows = () => screen.getAllByRole('row', { name: /^Открыть прогноз:/ });
const temperature = () => screen.getByRole('row', { name: /Температура ВШ-3/ });

describe('Predictions registry', () => {
  it('renders the available dataset with honest count and retains 46% critical', async () => {
    mount();
    await ready();
    expect(rows()).toHaveLength(24);
    expect(screen.getByText('Показана текущая доступная выборка прогнозов')).toBeVisible();
    expect(within(temperature()).getByText(/46\s*%/)).toBeVisible();
    expect(within(temperature()).getByText('Критический')).toBeVisible();
    expect(within(temperature()).getByText('1–6 ч')).toBeVisible();
    expect(within(temperature()).getByLabelText('20.09.2026, 18:40 МСК')).toBeVisible();
  });
  it('defaults to urgency then probability descending', async () => {
    mount();
    await ready();
    expect(
      rows()
        .slice(0, 4)
        .map((row) => within(row).getAllByRole('cell')[6]!.textContent?.replace(/\s/g, '')),
    ).toEqual(['82%', '79%', '73%', '46%']);
    expect(
      rows()
        .slice(0, 4)
        .every((row) => row.textContent?.includes('1–6 ч')),
    ).toBe(true);
    expect(rows()[4]).toHaveTextContent('6–24 ч');
    expect(rows()[12]).toHaveTextContent('24–48 ч');
  });
  it.each([
    ['critical', 5],
    ['high', 7],
    ['medium', 12],
    ['low', 0],
  ] as const)('filters risk %s', async (risk, count) => {
    mount();
    await ready();
    await userEvent.selectOptions(screen.getByLabelText('Риск'), risk);
    expect(screen.getByText(`Показано ${count} из 24 загруженных прогнозов`)).toBeVisible();
  });
  it.each([
    ['FLASH_1_6H', 4],
    ['URGENT_6_24H', 8],
    ['PLANNED_24_48H', 12],
    ['NORMAL', 0],
  ] as const)('filters urgency %s', async (urgency, count) => {
    mount();
    await ready();
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Срочность' }), urgency);
    expect(screen.getByText(`Показано ${count} из 24 загруженных прогнозов`)).toBeVisible();
  });
  it('builds unique object choices and filters by object ID', async () => {
    mount();
    await ready();
    expect(within(screen.getByLabelText('Объект')).getAllByRole('option')).toHaveLength(9);
    await userEvent.selectOptions(screen.getByLabelText('Объект'), '203');
    expect(rows()).toHaveLength(3);
    expect(rows().every((row) => row.textContent?.includes('объект Фита'))).toBe(true);
  });
  it.each(['  тЕмПеРаТуРа ВШ-3  ', 'Фита', 'ПК 88+50'])(
    'searches sensor/type/object/piket: %s',
    async (term) => {
      mount();
      await ready();
      await userEvent.type(screen.getByRole('searchbox'), term);
      expect(rows().length).toBeGreaterThan(0);
      expect(
        rows().every((row) =>
          row.textContent?.toLocaleLowerCase('ru').includes(term.trim().toLocaleLowerCase('ru')),
        ),
      ).toBe(true);
    },
  );
  it('searches the full sensor type while the column shows its short label', async () => {
    mount();
    await ready();
    await userEvent.type(screen.getByRole('searchbox'), 'Состояние фазы');
    expect(rows().length).toBeGreaterThan(0);
    // Matching still runs against the domain value; the cell renders the compact label and keeps
    // the original wording in its title.
    for (const row of rows()) {
      expect(row.textContent).toContain('Фаза');
      expect(row.textContent).not.toContain('Состояние фазы');
      expect(within(row).getByTitle('Состояние фазы')).toBeInTheDocument();
    }
  });
  it('intersects all filters and resets them', async () => {
    mount();
    await ready();
    await userEvent.selectOptions(screen.getByLabelText('Риск'), 'critical');
    await userEvent.selectOptions(screen.getByRole('combobox', { name: 'Срочность' }), 'FLASH_1_6H');
    await userEvent.selectOptions(screen.getByLabelText('Объект'), '203');
    await userEvent.type(screen.getByRole('searchbox'), 'темп');
    expect(rows()).toHaveLength(1);
    expect(temperature()).toBeVisible();
    expect(screen.getByText('Показано 1 из 24 загруженных прогнозов')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Сбросить фильтры' }));
    await ready();
    expect(screen.getByRole('searchbox')).toHaveValue('');
    expect(screen.getByLabelText('Риск')).toHaveValue('all');
    expect(screen.getByRole('combobox', { name: 'Срочность' })).toHaveValue('all');
    expect(screen.getByLabelText('Объект')).toHaveValue('all');
  });
  it.each(['click', 'Enter'])('opens the correct prediction with %s', async (method) => {
    mount();
    await ready();
    if (method === 'click') await userEvent.click(temperature());
    else {
      temperature().focus();
      await userEvent.keyboard('{Enter}');
    }
    expect(screen.getByRole('heading', { name: 'Прогноз OP-001' })).toBeVisible();
  });
  it('keeps header/filters and table skeleton while pending', () => {
    server.use(
      http.get(endpoint, async () => {
        await delay('infinite');
        return HttpResponse.json([]);
      }),
    );
    const view = mount();
    expect(screen.getByRole('heading', { name: 'Прогнозы' })).toBeVisible();
    expect(screen.getByRole('searchbox')).toBeVisible();
    expect(screen.getByRole('status')).toHaveTextContent('Загрузка данных');
    expect(view.container.querySelectorAll('.skeleton')).toHaveLength(150);
  });
  it('shows initial errors and retries using refetch', async () => {
    server.use(http.get(endpoint, () => HttpResponse.json({ message: 'Ошибка реестра' }, { status: 503 })));
    mount();
    expect(await screen.findByRole('alert')).toHaveTextContent('Ошибка реестра');
    server.resetHandlers();
    await userEvent.click(screen.getByRole('button', { name: 'Повторить' }));
    await ready();
  });
  it('distinguishes an empty API response', async () => {
    server.use(http.get(endpoint, () => HttpResponse.json([])));
    mount();
    expect(await screen.findByText('Прогнозы отсутствуют')).toBeVisible();
  });
  it('distinguishes filtered empty and clears it', async () => {
    mount();
    await ready();
    await userEvent.type(screen.getByRole('searchbox'), 'несуществующий датчик');
    expect(screen.getByText('По заданным условиям прогнозы не найдены')).toBeVisible();
    expect(screen.queryByText('Прогнозы отсутствуют')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Очистить условия' }));
    await ready();
  });
  it('retains cached rows after refresh fails and recovers', async () => {
    mount();
    await ready();
    server.use(http.get(endpoint, () => HttpResponse.json({}, { status: 503 })));
    await userEvent.click(screen.getByRole('button', { name: 'Обновить прогнозы' }));
    expect(await screen.findByText('Показаны сохранённые данные. Требуется обновление.')).toBeVisible();
    expect(rows()).toHaveLength(24);
    server.resetHandlers();
    await userEvent.click(screen.getByRole('button', { name: 'Обновить' }));
    await waitFor(() =>
      expect(
        screen.queryByText('Показаны сохранённые данные. Требуется обновление.'),
      ).not.toBeInTheDocument(),
    );
  });
  it.each(['Вероятность', 'Обновлено', 'Объект'])(
    'supports controlled ascending/descending sorting: %s',
    async (column) => {
      mount();
      await ready();
      await userEvent.click(screen.getByRole('button', { name: column }));
      expect(screen.getByRole('columnheader', { name: column })).toHaveAttribute('aria-sort', 'ascending');
      const asc = rows().map((row) => row.getAttribute('aria-label'));
      await userEvent.click(screen.getByRole('button', { name: column }));
      expect(screen.getByRole('columnheader', { name: column })).toHaveAttribute('aria-sort', 'descending');
      expect(rows().map((row) => row.getAttribute('aria-label'))).not.toEqual(asc);
      await userEvent.click(screen.getByRole('button', { name: 'Вернуть порядок по срочности' }));
      expect(rows()[0]).toHaveTextContent(/82\s*%/);
    },
  );
  it('renders all supplied review statuses as neutral human-readable text', async () => {
    const statuses = ['pending_review', 'acknowledged', 'rejected', 'ticket_created'] as const;
    server.use(
      http.get(endpoint, () =>
        HttpResponse.json(
          operationalPredictions.map((row, index) => ({ ...row, review_status: statuses[index % 4] })),
        ),
      ),
    );
    mount();
    await ready();
    // The column shows a compact label; the full domain wording stays in the cell title.
    const compact: Record<string, string> = {
      'Ожидает рассмотрения': 'Ожидает',
      Подтверждён: 'Подтверждён',
      Отклонён: 'Отклонён',
      'Создан наряд': 'Наряд создан',
    };
    for (const [full, short] of Object.entries(compact)) {
      expect(screen.getAllByText(short).length).toBeGreaterThan(0);
      expect(screen.getAllByTitle(full).length).toBeGreaterThan(0);
    }
  });
  it.each(['light', 'dark'])('keeps textual semantic indicators in %s', async (theme) => {
    document.documentElement.dataset.theme = theme;
    const view = mount();
    await ready();
    expect(view.container.querySelectorAll('.risk-indicator')).toHaveLength(24);
    expect(view.container.querySelectorAll('.urgency-indicator')).toHaveLength(24);
    expect(view.container.querySelectorAll('.badge')).toHaveLength(0);
    expect(document.documentElement.dataset.theme).toBe(theme);
  });
  it('never displays fabricated ML numbers for an unsupported row', () => {
    const row = toPrediction(predictionFixtures.find((item) => !item.prediction_supported)!);
    render(
      // The column hint uses the shared Tooltip, which the app always provides via AppProviders.
      <TooltipProvider>
        <MemoryRouter>
          <PredictionsRegistryTable
            rows={[row]}
            onRetry={() => {}}
            onReset={() => {}}
            filtered={false}
            onSort={() => {}}
          />
        </MemoryRouter>
      </TooltipProvider>,
    );
    expect(screen.getByText('ML-анализ недоступен')).toBeVisible();
    expect(screen.queryByText('Низкий')).not.toBeInTheDocument();
    expect(screen.queryByText(/1\s*%/)).not.toBeInTheDocument();
    expect(screen.queryByText('99')).not.toBeInTheDocument();
  });
  it('keeps missing values last in both directions without mutating input', () => {
    const original = operationalPredictions.slice(0, 3).map(toPrediction);
    original[0] = { ...original[0]!, failureProbability: null, generatedAt: 'invalid' };
    const ids = original.map((row) => row.id);
    for (const column of ['probability', 'updated'])
      for (const direction of ['asc', 'desc'] as const) {
        expect(selectPredictions(original, initialFilters, { column, direction }).at(-1)?.id).toBe(
          original[0]?.id,
        );
      }
    expect(original.map((row) => row.id)).toEqual(ids);
  });
});
