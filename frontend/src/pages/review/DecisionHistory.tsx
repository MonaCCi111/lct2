import type { V2Decision } from '../../api/v2/domain/types';
import { DataTable, TruncatedText, type Column } from '../../components/data-display/DataTable';
import { formatDateTime } from '../../utils/formatters';
import { reviewStateLabels } from './review-model';

const columns: readonly Column<V2Decision>[] = [
  {
    id: 'decision',
    header: 'Решение',
    cell: (row) => reviewStateLabels[row.decision],
  },
  { id: 'author', header: 'Диспетчер', className: 'cell-secondary', cell: (row) => row.authorId },
  {
    id: 'time',
    header: 'Время решения',
    className: 'cell-tertiary review-decision-time',
    cell: (row) => <time dateTime={row.decidedAt}>{formatDateTime(row.decidedAt)}</time>,
  },
  { id: 'reason', header: 'Причина', cell: (row) => <TruncatedText text={row.reason} /> },
  {
    id: 'decision-id',
    header: 'Decision ID',
    className: 'cell-tertiary',
    cell: (row) => <TruncatedText text={row.decisionId} />,
  },
  {
    id: 'supersedes',
    header: 'Исправляет решение',
    className: 'cell-tertiary',
    cell: (row) => (row.supersedesDecisionId ? <TruncatedText text={row.supersedesDecisionId} /> : '—'),
  },
  {
    id: 'work-order',
    header: 'Наряд',
    className: 'cell-tertiary',
    cell: (row) => row.workOrderId ?? '—',
  },
];

export function DecisionHistory({
  rows,
  loading,
  error,
  retry,
}: {
  rows: readonly V2Decision[];
  loading: boolean;
  error?: string;
  retry: () => void;
}) {
  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(row) => row.decisionId}
      caption="История решений по черновику"
      loading={loading}
      error={error}
      onRetry={retry}
      skeletonRows={2}
      emptyTitle="Решений пока нет."
    />
  );
}
