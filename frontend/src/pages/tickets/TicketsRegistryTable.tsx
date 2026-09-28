import { DataTable, type Column } from '../../components/data-display/DataTable';
import { RiskBadge, StatusBadge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import type { Ticket } from '../../domain/ticket/types';
import { formatDateTime } from '../../utils/formatters';
import { formatObjectName } from '../../utils/object-name';
import { ticketSourceLabel } from './ticket-registry-model';

// Tickets span several days, so the registry shows the full Moscow date, not only the time.
const timeCell = (value: string | null) =>
  value === null ? (
    <span className="muted">—</span>
  ) : (
    <time className="nowrap" dateTime={value} title={formatDateTime(value)}>
      {formatDateTime(value)}
    </time>
  );

const columns: readonly Column<Ticket>[] = [
  { id: 'id', header: 'Наряд', className: 'tk-id', cell: (row) => <span className="nowrap">{row.id}</span> },
  {
    id: 'status',
    header: 'Статус',
    className: 'tk-status',
    cell: (row) => <StatusBadge value={row.status} />,
  },
  {
    id: 'title',
    header: 'Название',
    cell: (row) => (
      <span className="truncate" title={row.title}>
        {row.title}
      </span>
    ),
  },
  {
    id: 'object',
    header: 'Объект',
    className: 'tk-object',
    cell: (row) => (
      <span className="truncate" title={row.objectName}>
        {formatObjectName(row.objectName)}
      </span>
    ),
  },
  {
    id: 'source',
    header: 'Источник',
    className: 'tk-source cell-secondary',
    cell: (row) => <span className="nowrap">{ticketSourceLabel(row)}</span>,
  },
  {
    id: 'priority',
    header: 'Приоритет',
    className: 'tk-priority',
    cell: (row) =>
      row.priority === null ? <span className="muted">—</span> : <RiskBadge value={row.priority} />,
  },
  {
    id: 'assignee',
    header: 'Исполнитель',
    className: 'tk-assignee cell-secondary',
    cell: (row) =>
      row.assignee === null ? (
        <span className="muted">Не назначен</span>
      ) : (
        <span className="truncate" title={row.assignee}>
          {row.assignee}
        </span>
      ),
  },
  {
    id: 'created',
    header: 'Создан',
    className: 'tk-created cell-tertiary',
    cell: (row) => timeCell(row.createdAt),
  },
  {
    id: 'updated',
    header: 'Обновлён',
    className: 'tk-updated cell-tertiary',
    cell: (row) => timeCell(row.updatedAt),
  },
];

export function TicketsRegistryTable({
  rows,
  loading,
  error,
  onRetry,
  filtered,
  onReset,
  onOpen,
  activeTicketId,
}: {
  rows: readonly Ticket[];
  loading?: boolean;
  error?: string;
  onRetry: () => void;
  filtered: boolean;
  onReset: () => void;
  onOpen: (ticket: Ticket) => void;
  activeTicketId: string | null;
}) {
  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      caption="Журнал нарядов"
      loading={loading}
      skeletonRows={12}
      error={error}
      onRetry={onRetry}
      emptyTitle={filtered ? 'По заданным условиям наряды не найдены' : 'Наряды отсутствуют'}
      emptyDescription={
        filtered ? 'Измените условия поиска или сбросьте фильтры.' : 'Рабочие задания пока не создавались.'
      }
      emptyAction={filtered ? <Button onClick={onReset}>Сбросить фильтры</Button> : undefined}
      rowProps={(row) => ({
        tabIndex: 0,
        className: `queue-row ${row.id === activeTicketId ? 'tickets-row-active' : ''}`,
        'aria-label': `Открыть наряд ${row.id}: ${row.title}`,
        onClick: (event) => {
          if (!(event.target instanceof Element && event.target.closest('a,button'))) onOpen(row);
        },
        onKeyDown: (event) => {
          if (event.key === 'Enter' && event.target === event.currentTarget) {
            event.preventDefault();
            onOpen(row);
          }
        },
      })}
    />
  );
}
