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
import { objectTopologyFixture } from '../../api/mocks/object-workspace';
import { TooltipProvider } from '../../components/ui/Tooltip';
import ObjectWorkspacePage from './ObjectWorkspacePage';

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
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
}
function mount(objectId = '203') {
  return render(
    <MemoryRouter initialEntries={[`/objects/${objectId}`]}>
      <Routes>
        <Route path="/objects/:objectId" element={<ObjectWorkspacePage />} />
        <Route path="/objects" element={<h1>Реестр объектов</h1>} />
        <Route path="/predictions/:id" element={<h1>Расследование shell</h1>} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  );
}
const topology = () => within(screen.getByRole('region', { name: 'Топология объекта' }));
const predictions = () => within(screen.getByRole('region', { name: 'Прогнозы объекта' }));
const summary = () => within(screen.getByRole('region', { name: 'Состояние объекта' }));
const criticalSegment = () => topology().getByRole('button', { name: /Участок ПК 88\+50 — ПК 112/ });
async function ready() {
  await screen.findByText('Показано 24 из 24 загруженных');
  await topology().findByRole('button', { name: /Участок ПК 88\+50/ });
}

describe('Object Workspace', () => {
  it('renders object detail, Moscow timestamp and backend aggregates without KPI cards', async () => {
    mount();
    await ready();
    expect(screen.getByRole('heading', { name: 'объект Фита' })).toBeVisible();
    expect(screen.getByText('Инженерный объект · 860 каналов · ML-покрытие 84%')).toBeVisible();
    expect(screen.getByText('Обновлено 20.09.2026, 18:42 МСК')).toBeVisible();
    expect(summary().getByText('Критический')).toBeVisible();
    expect(summary().getByText('4')).toBeVisible();
    expect(summary().getByText('8')).toBeVisible();
    expect(summary().getByText('24')).toBeVisible();
    expect(summary().getByText('722 / 860 каналов')).toBeVisible();
    expect(summary().getByRole('img', { name: 'ML-покрытие 84% каналов объекта' })).toBeVisible();
  });
  it('draws every segment with a length proportional to its piket range', async () => {
    const view = mount();
    await ready();
    const fixture = objectTopologyFixture(203, 'объект Фита');
    const lines = view.container.querySelectorAll('.topology-segment-line');
    expect(lines).toHaveLength(fixture.segments.length);
    const widths = [...lines].map((line) => Number(line.getAttribute('width')));
    const ranges = fixture.segments.map((segment) => segment.piket_to - segment.piket_from);
    const unit = widths[0]! / ranges[0]!;
    widths.forEach((width, index) => expect(width / ranges[index]!).toBeCloseTo(unit, 6));
    // ПК0–ПК14,5 against ПК48–ПК80: geometry follows the piket range, not a fixed slot.
    expect(widths[3]! / widths[0]!).toBeCloseTo(32 / 14.5, 6);
  });
  it('exposes segment risk and counts to assistive technology, not colour alone', async () => {
    mount();
    await ready();
    expect(criticalSegment()).toHaveAccessibleName(
      'Участок ПК 88+50 — ПК 112, Вентшахта ВШ-3, критический риск, 4 прогноза',
    );
    expect(topology().getByRole('button', { name: /Участок ПК 0 — ПК 14\+50/ })).toHaveAccessibleName(
      /низкий риск, 0 прогнозов/,
    );
  });
  it('filters predictions by the selected segment and resets the selection', async () => {
    mount();
    await ready();
    await userEvent.click(criticalSegment());
    expect(criticalSegment()).toHaveAttribute('aria-pressed', 'true');
    expect(
      topology().getByText('Выбран участок: ПК 88+50 — ПК 112 · Вентшахта ВШ-3 · 4 прогноза'),
    ).toBeVisible();
    expect(predictions().getByText('Показано 4 из 24 загруженных')).toBeVisible();
    expect(predictions().getByText('Температура ВШ-3')).toBeVisible();
    expect(predictions().queryByText('Пожарный извещатель ИП-14')).not.toBeInTheDocument();
    await userEvent.click(topology().getByRole('button', { name: 'Сбросить' }));
    expect(predictions().getByText('Показано 24 из 24 загруженных')).toBeVisible();
    expect(criticalSegment()).toHaveAttribute('aria-pressed', 'false');
  });
  it('selects a segment from the keyboard with Enter and Space', async () => {
    mount();
    await ready();
    criticalSegment().focus();
    expect(criticalSegment()).toHaveFocus();
    await userEvent.keyboard('{Enter}');
    expect(predictions().getByText('Показано 4 из 24 загруженных')).toBeVisible();
    await userEvent.keyboard(' ');
    expect(predictions().getByText('Показано 24 из 24 загруженных')).toBeVisible();
  });
  it('keeps predictions without a piket value out of numeric segment ranges', async () => {
    mount();
    await ready();
    expect(predictions().getByText('Шкаф телемеханики ТМ-1')).toBeVisible();
    await userEvent.click(criticalSegment());
    expect(predictions().queryByText('Шкаф телемеханики ТМ-1')).not.toBeInTheDocument();
    await userEvent.click(topology().getByRole('button', { name: 'Сбросить' }));
    expect(predictions().getByText('Шкаф телемеханики ТМ-1')).toBeVisible();
  });
  it('keeps 46% temperature critical and orders rows by ready urgency values', async () => {
    mount();
    await ready();
    const row = predictions().getByRole('row', {
      name: 'Открыть прогноз: Температура ВШ-3, ПК 89+40',
    });
    expect(within(row).getByText('Критический')).toBeVisible();
    expect(within(row).getByText(/46\s*%/)).toBeVisible();
    expect(within(row).getByText('1–6 ч')).toBeVisible();
    const urgencies = predictions()
      .getAllByRole('row')
      .slice(1)
      .map((item) => item.textContent ?? '');
    const order = ['1–6 ч', '6–24 ч', '24–48 ч', 'Штатный режим'];
    const positions = urgencies.map((text) => order.findIndex((label) => text.startsWith(label)));
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
    // Highest probability leads inside the most urgent group.
    expect(urgencies[0]).toMatch(/82\s*%/);
  });
  it('filters the loaded predictions by urgency, risk and sensor search', async () => {
    mount();
    await ready();
    await userEvent.click(screen.getByRole('button', { name: '1–6 ч' }));
    expect(predictions().getByText('Показано 4 из 24 загруженных')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Все' }));
    await userEvent.selectOptions(screen.getByLabelText('Риск прогноза'), 'high');
    expect(predictions().getByText('Показано 8 из 24 загруженных')).toBeVisible();
    await userEvent.type(screen.getByRole('searchbox'), 'насос');
    expect(predictions().getByText('Показано 3 из 24 загруженных')).toBeVisible();
    await userEvent.clear(screen.getByRole('searchbox'));
    await userEvent.type(screen.getByRole('searchbox'), 'нет такого датчика');
    expect(predictions().getByText('Прогнозы не найдены')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Сбросить фильтры' }));
    expect(predictions().getByText('Показано 24 из 24 загруженных')).toBeVisible();
  });
  it('opens a prediction from a row click and from a focused row with Enter', async () => {
    const first = mount();
    await ready();
    await userEvent.click(predictions().getByRole('row', { name: /Температура ВШ-3/ }));
    expect(screen.getByRole('heading', { name: 'Расследование shell' })).toBeVisible();
    first.unmount();
    mount();
    await ready();
    const row = predictions().getByRole('row', { name: /Фаза B · тяговый ввод/ });
    row.focus();
    await userEvent.keyboard('{Enter}');
    expect(screen.getByRole('heading', { name: 'Расследование shell' })).toBeVisible();
  });
  it('loads detail, topology and predictions independently with local skeletons', async () => {
    server.use(
      http.get(endpoint('/objects/:objectId/topology'), async () => {
        await delay(900);
        return HttpResponse.json(objectTopologyFixture(203, 'объект Фита'));
      }),
    );
    mount();
    expect(topology().getByRole('status', { name: 'Загрузка топологии' })).toBeInTheDocument();
    await screen.findByText('Показано 24 из 24 загруженных');
    expect(summary().getByText('Критический')).toBeVisible();
    await waitFor(() => expect(criticalSegment()).toBeVisible());
  });
  it('keeps predictions visible when the topology endpoint fails', async () => {
    server.use(
      http.get(endpoint('/objects/:objectId/topology'), () =>
        HttpResponse.json({ message: 'Ошибка топологии' }, { status: 503 }),
      ),
    );
    mount();
    await screen.findByText('Показано 24 из 24 загруженных');
    expect(topology().getByRole('alert')).toHaveTextContent('Ошибка топологии');
    expect(predictions().getByText('Температура ВШ-3')).toBeVisible();
    expect(summary().getByText('Критический')).toBeVisible();
  });
  it('keeps the topology visible when the predictions endpoint fails', async () => {
    server.use(
      http.get(endpoint('/predictions'), () =>
        HttpResponse.json({ message: 'Ошибка прогнозов' }, { status: 503 }),
      ),
    );
    mount();
    await topology().findByRole('button', { name: /Участок ПК 88\+50/ });
    expect(predictions().getByRole('alert')).toHaveTextContent('Ошибка прогнозов');
    expect(summary().getByText('Критический')).toBeVisible();
  });
  it('shows an empty topology without hiding predictions', async () => {
    server.use(
      http.get(endpoint('/objects/:objectId/topology'), () =>
        HttpResponse.json({
          ...objectTopologyFixture(203, 'объект Фита'),
          piket_min: null,
          piket_max: null,
          segments: [],
        }),
      ),
    );
    mount();
    await screen.findByText('Показано 24 из 24 загруженных');
    expect(topology().getByText('Топология объекта недоступна')).toBeVisible();
    expect(
      topology().getByText('Для объекта пока не сформирована структура участков по пикетам.'),
    ).toBeVisible();
    expect(predictions().getByText('Температура ВШ-3')).toBeVisible();
  });
  it('shows empty predictions without hiding the topology', async () => {
    server.use(http.get(endpoint('/predictions'), () => HttpResponse.json([])));
    mount();
    await predictions().findByText('Активных прогнозов для объекта нет');
    expect(await topology().findByRole('button', { name: /Участок ПК 88\+50/ })).toBeVisible();
  });
  it('keeps cached predictions after a failed refresh', async () => {
    mount();
    await ready();
    server.use(
      http.get(endpoint('/predictions'), () =>
        HttpResponse.json({ message: 'Ошибка обновления' }, { status: 503 }),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Обновить прогнозы объекта' }));
    await waitFor(() =>
      expect(predictions().getByText('Показаны сохранённые данные. Требуется обновление.')).toBeVisible(),
    );
    expect(predictions().getByText('Температура ВШ-3')).toBeVisible();
  });
  it('reports a missing object and links back to the object list', async () => {
    mount('999');
    expect(await screen.findByRole('heading', { name: 'Объект не найден' })).toBeVisible();
    expect(screen.getByText('Объект с указанным идентификатором отсутствует или недоступен.')).toBeVisible();
    await userEvent.click(screen.getByRole('link', { name: 'К списку объектов' }));
    expect(screen.getByRole('heading', { name: 'Реестр объектов' })).toBeVisible();
  });
});
