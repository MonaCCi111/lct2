import type { ReactNode } from 'react';
import { render, screen, within, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useSearchParams } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterAll, afterEach, beforeAll, describe, expect, it } from 'vitest';
import { delay, http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import { handlers } from '../../api/mocks/handlers';
import { apiConfig } from '../../api/client/config';
import { resetTicketStore } from '../../api/mocks/tickets';
import { TooltipProvider } from '../../components/ui/Tooltip';
import TicketsPage from './TicketsPage';

const server = setupServer(...handlers);
const client = new QueryClient({ defaultOptions: { queries: { retry: false, staleTime: Infinity } } });
const endpoint = (path: string) => `${apiConfig.baseUrl}${path}`;
beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => {
  server.resetHandlers();
  client.clear();
  // Mock mutations change module state; every test starts from the same dataset.
  resetTicketStore();
});
afterAll(() => server.close());

function LocationProbe() {
  const [params] = useSearchParams();
  return <span data-testid="query">{params.toString()}</span>;
}
function wrapper({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <TooltipProvider>{children}</TooltipProvider>
    </QueryClientProvider>
  );
}
function mount(search = '') {
  return render(
    <MemoryRouter initialEntries={[`/tickets${search}`]}>
      <LocationProbe />
      <Routes>
        <Route path="/tickets" element={<TicketsPage />} />
        <Route path="/objects/:objectId" element={<h1>Рабочее пространство объекта</h1>} />
        <Route path="/predictions/:predictionId" element={<h1>Расследование прогноза</h1>} />
      </Routes>
    </MemoryRouter>,
    { wrapper },
  );
}
const registry = () => within(screen.getByRole('region', { name: 'Реестр нарядов' }));
const drawer = () => within(screen.getByRole('dialog'));
const query = () => screen.getByTestId('query').textContent ?? '';
const ready = () => screen.findByText('15 нарядов');

describe('Tickets registry', () => {
  it('renders the work order log with restrained statuses and Moscow timestamps', async () => {
    mount();
    await ready();
    expect(registry().getAllByRole('row')).toHaveLength(16); // header + 15 tickets
    expect(registry().getByText('Проверка дренажного насоса № 2')).toBeVisible();
    expect(registry().getAllByText('Черновик').length).toBeGreaterThan(0);
    expect(registry().getAllByText(/20\.09\.2026, \d{2}:\d{2} МСК/).length).toBeGreaterThan(0);
    // Restrained workflow badges, never filled risk capsules.
    expect(document.querySelectorAll('.badge.tone-critical')).toHaveLength(0);
  });
  it('sorts pending work first and newest updates on top inside a status', async () => {
    mount();
    await ready();
    const statuses = registry()
      .getAllByRole('row')
      .slice(1)
      .map((row) => row.textContent ?? '');
    const order = ['Черновик', 'Согласован', 'Отклонён', 'Выполнен'];
    const positions = statuses.map((text) => order.findIndex((label) => text.includes(label)));
    expect(positions).toEqual([...positions].sort((a, b) => a - b));
    expect(statuses[0]).toContain('WO-2026-0922');
  });
  it('filters by status, searches and reports the result count', async () => {
    mount();
    await ready();
    await userEvent.selectOptions(screen.getByLabelText('Статус наряда'), 'completed');
    expect(registry().getByText('4 из 15 нарядов')).toBeVisible();
    await userEvent.selectOptions(screen.getByLabelText('Статус наряда'), 'all');
    await userEvent.type(screen.getByRole('searchbox'), 'насос');
    expect(registry().getByText('3 из 15 нарядов')).toBeVisible();
    // Combined status + search narrows further.
    await userEvent.selectOptions(screen.getByLabelText('Статус наряда'), 'completed');
    expect(registry().getByText('2 из 15 нарядов')).toBeVisible();
    await userEvent.clear(screen.getByRole('searchbox'));
    await userEvent.type(screen.getByRole('searchbox'), 'такого наряда нет');
    expect(registry().getByText('По заданным условиям наряды не найдены')).toBeVisible();
    // Both the filter bar and the empty state offer a reset; use the one in the filter bar.
    await userEvent.click(
      within(document.querySelector('.tickets-filters') as HTMLElement).getByRole('button', {
        name: 'Сбросить фильтры',
      }),
    );
    expect(await ready()).toBeVisible();
  });
  it('searches by prediction id and assignee', async () => {
    mount();
    await ready();
    await userEvent.type(screen.getByRole('searchbox'), 'HYDRO-003');
    expect(registry().getByText('1 из 15 нарядов')).toBeVisible();
    await userEvent.clear(screen.getByRole('searchbox'));
    await userEvent.type(screen.getByRole('searchbox'), 'Инженер КИП');
    expect(registry().getByText('1 из 15 нарядов')).toBeVisible();
  });
});

describe('Ticket detail', () => {
  it('opens from a row click and keeps the ticket in the URL', async () => {
    mount();
    await ready();
    await userEvent.click(registry().getByRole('row', { name: /WO-2026-0917/ }));
    expect(await screen.findByRole('dialog')).toBeVisible();
    expect(await drawer().findByText('Проверка дренажного насоса № 2')).toBeVisible();
    expect(query()).toBe('ticketId=WO-2026-0917');
  });
  it('opens from a focused row with Enter', async () => {
    mount();
    await ready();
    const row = registry().getByRole('row', { name: /WO-2026-0912/ });
    row.focus();
    await userEvent.keyboard('{Enter}');
    expect(await screen.findByRole('dialog')).toBeVisible();
    expect(query()).toBe('ticketId=WO-2026-0912');
  });
  it('opens straight from a ticketId deep link with full context', async () => {
    mount('?ticketId=WO-2026-0918');
    expect(await screen.findByRole('dialog')).toBeVisible();
    await waitFor(() => expect(drawer().getByText('Согласован')).toBeVisible());
    expect(drawer().getByText('Служба вентиляции')).toBeVisible();
    expect(drawer().getByText(/19\.09\.2026, \d{2}:\d{2} МСК/)).toBeVisible();
    expect(drawer().getByRole('link', { name: /OW-016/ })).toBeVisible();
  });
  it('reports a missing ticket and clears the query on close', async () => {
    mount('?ticketId=WO-NOPE');
    expect(await screen.findByTestId('ticket-missing')).toHaveTextContent('Наряд не найден');
    await userEvent.click(screen.getByRole('button', { name: 'Закрыть панель' }));
    await waitFor(() => expect(query()).toBe(''));
  });
  it('navigates to the object and to the source prediction', async () => {
    const first = mount('?ticketId=WO-2026-0917');
    await screen.findByRole('dialog');
    await userEvent.click(await screen.findByRole('link', { name: 'Насосная станция' }));
    expect(screen.getByRole('heading', { name: 'Рабочее пространство объекта' })).toBeVisible();
    first.unmount();
    client.clear();
    mount('?ticketId=WO-2026-0917');
    await screen.findByRole('dialog');
    await userEvent.click(await screen.findByRole('link', { name: 'Открыть прогноз' }));
    expect(screen.getByRole('heading', { name: 'Расследование прогноза' })).toBeVisible();
  });
});

describe('Ticket lifecycle', () => {
  const openTicket = async (id: string) => {
    mount(`?ticketId=${id}`);
    expect(await screen.findByRole('dialog')).toBeVisible();
  };
  it('moves a draft to approved through a confirmation', async () => {
    await openTicket('WO-2026-0917');
    await userEvent.click(await screen.findByRole('button', { name: 'Согласовать' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Согласовать наряд?' }));
    await userEvent.click(dialog.getByRole('button', { name: 'Согласовать' }));
    await waitFor(() => expect(drawer().getByText('Согласован')).toBeVisible());
    expect(drawer().getByRole('button', { name: 'Отметить выполненным' })).toBeVisible();
  });
  it('moves a draft to rejected through a confirmation', async () => {
    await openTicket('WO-2026-0917');
    await userEvent.click(await screen.findByRole('button', { name: 'Отклонить' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Отклонить наряд?' }));
    await userEvent.click(dialog.getByRole('button', { name: 'Отклонить' }));
    await waitFor(() => expect(drawer().getByText('Отклонён')).toBeVisible());
    expect(drawer().getByText('Наряд отклонён. Дальнейшие действия недоступны.')).toBeVisible();
  });
  it('completes an approved ticket and records the completion time', async () => {
    await openTicket('WO-2026-0918');
    await userEvent.click(await screen.findByRole('button', { name: 'Отметить выполненным' }));
    const dialog = within(screen.getByRole('dialog', { name: 'Отметить наряд выполненным?' }));
    expect(dialog.getByText('После завершения статус нельзя изменить в интерфейсе.')).toBeVisible();
    await userEvent.click(dialog.getByRole('button', { name: 'Отметить выполненным' }));
    await waitFor(() => expect(drawer().getByText('Выполнен')).toBeVisible());
    expect(drawer().getByText('Завершён')).toBeVisible();
    expect(drawer().getByText('Наряд выполнен. Дальнейшие действия недоступны.')).toBeVisible();
  });
  it.each([
    ['WO-2026-0910', 'Наряд отклонён. Дальнейшие действия недоступны.'],
    ['WO-2026-0901', 'Наряд выполнен. Дальнейшие действия недоступны.'],
  ])('offers no lifecycle actions for %s', async (id, note) => {
    await openTicket(id);
    expect(await screen.findByText(note)).toBeVisible();
    expect(drawer().queryByRole('button', { name: 'Согласовать' })).not.toBeInTheDocument();
    expect(drawer().queryByRole('button', { name: 'Отметить выполненным' })).not.toBeInTheDocument();
  });
  it('surfaces a rejected transition from the API without closing the drawer', async () => {
    server.use(
      http.patch(endpoint('/tickets/:ticketId/status'), () =>
        HttpResponse.json({ message: 'Переход «draft» → «completed» недопустим.' }, { status: 409 }),
      ),
    );
    await openTicket('WO-2026-0917');
    await userEvent.click(await screen.findByRole('button', { name: 'Согласовать' }));
    await userEvent.click(
      within(screen.getByRole('dialog', { name: 'Согласовать наряд?' })).getByRole('button', {
        name: 'Согласовать',
      }),
    );
    const confirm = within(screen.getByRole('dialog', { name: 'Согласовать наряд?' }));
    expect(await confirm.findByRole('alert')).toHaveTextContent('недопустим');
    // Neither the confirmation nor the ticket drawer is closed, so a retry stays possible.
    expect(confirm.getByRole('button', { name: 'Согласовать' })).toBeEnabled();
    expect(query()).toBe('ticketId=WO-2026-0917');
  });
  it('lets the confirmation be dismissed with Escape', async () => {
    await openTicket('WO-2026-0917');
    await userEvent.click(await screen.findByRole('button', { name: 'Согласовать' }));
    expect(screen.getByRole('dialog', { name: 'Согласовать наряд?' })).toBeVisible();
    await userEvent.keyboard('{Escape}');
    await waitFor(() =>
      expect(screen.queryByRole('dialog', { name: 'Согласовать наряд?' })).not.toBeInTheDocument(),
    );
    expect(drawer().getByText('Черновик')).toBeVisible();
  });
});

describe('Ticket creation', () => {
  it('opens prefilled from a predictionId deep link', async () => {
    mount('?predictionId=OW-004');
    expect(await screen.findByRole('dialog')).toBeVisible();
    await waitFor(() => expect(screen.getByLabelText('Название')).toHaveValue('Проверка: Температура ВШ-3'));
    // The description reuses the recommendation the model already produced.
    expect((screen.getByLabelText('Описание') as HTMLTextAreaElement).value).toContain(
      'Калибровка измерительного тракта или замена термопары.',
    );
    // Source context uses the ready ML values of the prediction.
    const source = within(screen.getByRole('region', { name: 'Источник наряда' }));
    expect(source.getByText('OW-004')).toBeVisible();
    expect(source.getByText('Критический')).toBeVisible();
    expect(source.getByText('1–6 ч')).toBeVisible();
  });
  it('validates the form before sending anything', async () => {
    mount('?predictionId=OW-004');
    await waitFor(() => expect(screen.getByLabelText('Название')).toHaveValue('Проверка: Температура ВШ-3'));
    await userEvent.clear(screen.getByLabelText('Название'));
    await userEvent.clear(screen.getByLabelText('Описание'));
    await userEvent.click(screen.getByRole('button', { name: 'Создать черновик' }));
    expect(await screen.findByText('Укажите название наряда.')).toBeVisible();
    expect(screen.getByText('Опишите работы по наряду.')).toBeVisible();
    await userEvent.type(screen.getByLabelText('Название'), 'ab');
    await userEvent.type(screen.getByLabelText('Описание'), 'коротко');
    await userEvent.click(screen.getByRole('button', { name: 'Создать черновик' }));
    expect(await screen.findByText(/от 3 до 120 символов/)).toBeVisible();
    expect(screen.getByText(/от 10 до 2000 символов/)).toBeVisible();
  });
  it('creates a draft, opens it and links the prediction to it', async () => {
    mount('?predictionId=OW-004');
    await waitFor(() => expect(screen.getByLabelText('Название')).toHaveValue('Проверка: Температура ВШ-3'));
    await userEvent.selectOptions(screen.getByLabelText('Исполнитель'), 'Смена А');
    await userEvent.click(screen.getByRole('button', { name: 'Создать черновик' }));
    await waitFor(() => expect(query()).toMatch(/^ticketId=WO-2026-\d{4}$/));
    await waitFor(() => expect(drawer().getByText('Черновик')).toBeVisible());
    expect(drawer().getByText('Проверка: Температура ВШ-3')).toBeVisible();
    expect(drawer().getByText('Смена А')).toBeVisible();
    expect(drawer().getByRole('link', { name: /OW-004/ })).toBeVisible();
    // The registry picked the new ticket up.
    await waitFor(() => expect(registry().getByText('16 нарядов')).toBeVisible());
  });
  it('refuses a duplicate ticket for a prediction that already has one', async () => {
    mount('?predictionId=HYDRO-003');
    expect(await screen.findByTestId('duplicate-ticket')).toHaveTextContent('WO-2026-0917');
    expect(screen.queryByLabelText('Название')).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Открыть наряд' }));
    await waitFor(() => expect(query()).toBe('ticketId=WO-2026-0917'));
  });
  it('reports a missing prediction while the registry stays usable', async () => {
    mount('?predictionId=UNKNOWN-1');
    expect(await screen.findByTestId('prediction-missing')).toHaveTextContent('Прогноз не найден');
    expect(screen.getByText('Создание наряда из указанного прогноза невозможно.')).toBeVisible();
    expect(await ready()).toBeVisible();
  });
  it('keeps the entered data when the mutation fails', async () => {
    server.use(
      http.post(endpoint('/tickets'), () =>
        HttpResponse.json({ message: 'Сервис нарядов недоступен.' }, { status: 503 }),
      ),
    );
    mount('?predictionId=OW-004');
    await waitFor(() => expect(screen.getByLabelText('Название')).toHaveValue('Проверка: Температура ВШ-3'));
    await userEvent.clear(screen.getByLabelText('Название'));
    await userEvent.type(screen.getByLabelText('Название'), 'Ручная правка названия');
    await userEvent.click(screen.getByRole('button', { name: 'Создать черновик' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Сервис нарядов недоступен.');
    expect(screen.getByLabelText('Название')).toHaveValue('Ручная правка названия');
    expect(screen.getByRole('dialog')).toBeVisible();
  });
  it('creates a manual ticket with an object picked from the existing catalogue', async () => {
    mount();
    await ready();
    await userEvent.click(screen.getByRole('button', { name: /Новый наряд/ }));
    expect(await screen.findByRole('dialog')).toBeVisible();
    await userEvent.click(screen.getByRole('button', { name: 'Создать черновик' }));
    expect(await screen.findByText('Выберите объект.')).toBeVisible();
    await userEvent.selectOptions(await screen.findByLabelText('Объект'), '101');
    await userEvent.type(screen.getByLabelText('Название'), 'Плановый осмотр щитовой');
    await userEvent.type(screen.getByLabelText('Описание'), 'Контрольный осмотр по графику ТО.');
    await userEvent.click(screen.getByRole('button', { name: 'Создать черновик' }));
    await waitFor(() => expect(drawer().getByText('Плановый осмотр щитовой')).toBeVisible());
    expect(drawer().getByText('Ручной наряд')).toBeVisible();
  });
});

describe('Tickets registry states', () => {
  it('shows a loading skeleton before the log arrives', async () => {
    server.use(
      http.get(endpoint('/tickets'), async () => {
        await delay(700);
        return HttpResponse.json([]);
      }),
    );
    mount();
    expect(registry().getByRole('status')).toHaveTextContent('Загрузка');
    expect(registry().getByText('Загрузка нарядов…')).toBeVisible();
  });
  it('shows an error with retry and an empty API result', async () => {
    server.use(
      http.get(endpoint('/tickets'), () =>
        HttpResponse.json({ message: 'Сервис нарядов недоступен.' }, { status: 503 }),
      ),
    );
    const first = mount();
    expect(await registry().findByRole('alert')).toHaveTextContent('Сервис нарядов недоступен.');
    expect(registry().getByRole('button', { name: 'Повторить' })).toBeVisible();
    first.unmount();
    client.clear();
    server.use(http.get(endpoint('/tickets'), () => HttpResponse.json([])));
    mount();
    expect(await screen.findByText('Наряды отсутствуют')).toBeVisible();
    expect(screen.getByText('Рабочие задания пока не создавались.')).toBeVisible();
  });
  it('keeps cached rows after a failed refresh', async () => {
    mount();
    await ready();
    server.use(
      http.get(endpoint('/tickets'), () =>
        HttpResponse.json({ message: 'Ошибка обновления' }, { status: 503 }),
      ),
    );
    await userEvent.click(screen.getByRole('button', { name: 'Обновить' }));
    await waitFor(() =>
      expect(registry().getByText('Показаны сохранённые данные. Требуется обновление.')).toBeVisible(),
    );
    expect(registry().getByText('Проверка дренажного насоса № 2')).toBeVisible();
  });
  it('renders the same registry semantics in both themes', async () => {
    for (const theme of ['dark', 'light']) {
      document.documentElement.dataset.theme = theme;
      const view = mount();
      await ready();
      expect(registry().getAllByText('Черновик').length).toBeGreaterThan(0);
      expect(document.querySelectorAll('.badge.tone-critical')).toHaveLength(0);
      view.unmount();
      client.clear();
    }
    delete document.documentElement.dataset.theme;
  });
});
