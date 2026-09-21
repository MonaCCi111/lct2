import type { Ticket, TicketStatus } from '../../domain/ticket/types';

export type TicketStatusFilter = TicketStatus | 'all';
export interface TicketFilterState {
  search: string;
  status: TicketStatusFilter;
}
export const initialTicketFilters: TicketFilterState = { search: '', status: 'all' };
export const hasTicketFilters = (filters: TicketFilterState) =>
  filters.search.trim() !== '' || filters.status !== 'all';

export const statusFilterOptions: { value: TicketStatusFilter; label: string }[] = [
  { value: 'all', label: 'Все статусы' },
  { value: 'draft', label: 'Черновики' },
  { value: 'approved', label: 'Согласованные' },
  { value: 'rejected', label: 'Отклонённые' },
  { value: 'completed', label: 'Выполненные' },
];

// Work that still needs a decision comes first; finished records sink to the bottom.
const statusOrder: Record<TicketStatus, number> = {
  draft: 0,
  approved: 1,
  rejected: 2,
  completed: 3,
};

export function selectTickets(rows: readonly Ticket[], filters: TicketFilterState) {
  const term = filters.search.trim().toLocaleLowerCase('ru');
  return rows
    .filter(
      (row) =>
        (filters.status === 'all' || row.status === filters.status) &&
        (term === '' ||
          `${row.id} ${row.title} ${row.objectName} ${row.predictionId ?? ''} ${row.assignee ?? ''}`
            .toLocaleLowerCase('ru')
            .includes(term)),
    )
    .sort(
      (a, b) =>
        statusOrder[a.status] - statusOrder[b.status] ||
        Date.parse(b.updatedAt) - Date.parse(a.updatedAt) ||
        a.id.localeCompare(b.id, 'ru'),
    );
}

export const ticketSourceLabel = (ticket: Ticket) => ticket.predictionId ?? 'Ручной';

const ticketForms = ['наряд', 'наряда', 'нарядов'] as const;
export function formatTicketCount(count: number) {
  const tens = count % 100;
  const ones = count % 10;
  const form = tens > 10 && tens < 20 ? 2 : ones === 1 ? 0 : ones >= 2 && ones <= 4 ? 1 : 2;
  return `${count} ${ticketForms[form]}`;
}

export const transitionLabels: Record<TicketStatus, string> = {
  draft: 'Вернуть в черновик',
  approved: 'Согласовать',
  rejected: 'Отклонить',
  completed: 'Отметить выполненным',
};
export const transitionConfirmations: Record<TicketStatus, { title: string; description: string }> = {
  draft: { title: 'Вернуть наряд в черновик?', description: '' },
  approved: {
    title: 'Согласовать наряд?',
    description: 'Наряд будет передан в работу и станет доступен для завершения.',
  },
  rejected: {
    title: 'Отклонить наряд?',
    description: 'Отклонённый наряд нельзя согласовать позднее — потребуется создать новый.',
  },
  completed: {
    title: 'Отметить наряд выполненным?',
    description: 'После завершения статус нельзя изменить в интерфейсе.',
  },
};
