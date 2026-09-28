import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import { Link, useNavigate } from 'react-router-dom';
import type { V2WorkOrder } from '../../api/v2/domain/types';
import { useV2Draft, useV2Objects, useV2WorkOrders } from '../../api/v2/queries/hooks';
import { DataTable, TruncatedText, type Column } from '../../components/data-display/DataTable';
import { StaleState } from '../../components/feedback/States';
import { PageHeader } from '../../components/feedback/PageShell';
import { Button } from '../../components/ui/Button';
import { formatDateTime } from '../../utils/formatters';
import { reviewStateLabels } from './review-model';
import { toWorkOrderRows, type WorkOrderRow } from './work-order-model';
import './review-page.css';

function WorkOrderDecisionCell({ draftId }: { draftId: string }) {
  const draft = useV2Draft(draftId);
  if (draft.isPending) return <span className="cell-tertiary">Загрузка…</span>;
  if (!draft.data?.decision) return <span>—</span>;
  return (
    <span className="review-work-order-decision">
      <strong>{reviewStateLabels[draft.data.decision.decision]}</strong>
      <small title={draft.data.decision.decisionId}>{draft.data.decision.decisionId}</small>
    </span>
  );
}

const columns: readonly Column<WorkOrderRow>[] = [
  {
    id: 'id',
    header: 'Наряд',
    cell: (row) => <strong className="review-work-order-id">{row.workOrderId}</strong>,
  },
  {
    id: 'object',
    header: 'Объект',
    cell: (row) => (
      <span className="review-object-name">
        <strong>{row.objectName}</strong>
        <small>ID {row.objectId}</small>
      </span>
    ),
  },
  {
    id: 'draft',
    header: 'Исходный черновик',
    className: 'cell-tertiary review-work-order-draft',
    cell: (row) => <TruncatedText text={row.draftId} />,
  },
  {
    id: 'decision',
    header: 'Решение',
    cell: (row) => <WorkOrderDecisionCell draftId={row.draftId} />,
  },
  { id: 'type', header: 'Тип работ', cell: (row) => <TruncatedText text={row.workType} /> },
  { id: 'status', header: 'Статус API', className: 'cell-secondary', cell: (row) => row.status },
  {
    id: 'created',
    header: 'Создан',
    className: 'cell-tertiary review-decision-time',
    cell: (row) => <time dateTime={row.createdAt}>{formatDateTime(row.createdAt)}</time>,
  },
];

export default function WorkOrdersPage() {
  const [cursors, setCursors] = useState<(string | undefined)[]>([undefined]);
  const query = useV2WorkOrders({ limit: 50, cursor: cursors.at(-1) });
  const objects = useV2Objects({ limit: 200 });
  const navigate = useNavigate();
  const rows = useMemo(
    () => toWorkOrderRows(query.data?.items ?? [], objects.data?.items ?? []),
    [query.data?.items, objects.data?.items],
  );
  const open = (row: V2WorkOrder) => navigate(`/review/work-orders/${encodeURIComponent(row.workOrderId)}`);

  return (
    <div className="review-page review-work-orders-page">
      <Link className="review-back" to="/review">
        К очереди проверки
      </Link>
      <PageHeader
        title="Наряды v2"
        description="Наряды, явно созданные из одобренных исторических черновиков."
        action={
          <Button variant="ghost" disabled={query.isFetching} onClick={() => void query.refetch()}>
            <RefreshCw size={14} aria-hidden="true" />
            Обновить список
          </Button>
        }
      />
      <section className="review-work-orders-list" aria-label="Реестр нарядов v2">
        {query.data && query.isError && (
          <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
        )}
        <DataTable
          columns={columns}
          rows={rows}
          rowKey={(row) => row.workOrderId}
          caption="Наряды v2"
          loading={query.isPending}
          error={!query.data && query.isError ? query.error.message : undefined}
          onRetry={() => void query.refetch()}
          emptyTitle="Наряды v2 ещё не созданы."
          rowProps={(row) => ({
            tabIndex: 0,
            className: 'review-work-order-row',
            'aria-label': `Открыть наряд ${row.workOrderId}`,
            onClick: () => open(row),
            onKeyDown: (event) => {
              if (event.key === 'Enter' && event.target === event.currentTarget) {
                event.preventDefault();
                open(row);
              }
            },
          })}
        />
        <footer className="review-queue-footer">
          <span>{query.data ? `В текущей выборке: ${rows.length}` : 'Загрузка нарядов…'}</span>
          <div className="review-pagination">
            {cursors.length > 1 && (
              <Button variant="ghost" onClick={() => setCursors((items) => items.slice(0, -1))}>
                <ChevronLeft size={14} />
                Назад
              </Button>
            )}
            {query.data?.nextCursor && (
              <Button onClick={() => setCursors((items) => [...items, query.data?.nextCursor ?? undefined])}>
                Следующая выборка
                <ChevronRight size={14} />
              </Button>
            )}
          </div>
        </footer>
      </section>
    </div>
  );
}
