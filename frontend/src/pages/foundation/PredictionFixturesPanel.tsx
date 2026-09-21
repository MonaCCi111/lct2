import { useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import { RefreshCw } from 'lucide-react';
import { usePredictions } from '../../api/queries/hooks';
import {
  DataTable,
  TruncatedText,
  type Column,
  type SortState,
} from '../../components/data-display/DataTable';
import { RiskBadge, UrgencyBadge } from '../../components/ui/Badge';
import { IconButton } from '../../components/ui/Button';
import { Panel } from '../../components/ui/Panel';
import { StaleState, UnsupportedMlState } from '../../components/feedback/States';
import { toPredictionRow, type PredictionRow } from './predictionRow';
const columns: Column<PredictionRow>[] = [
  {
    id: 'sensorName',
    header: 'Датчик',
    width: '26%',
    sortable: true,
    cell: (row) => (
      <Link to={`/predictions/${row.id}`} className="table-link">
        <TruncatedText text={row.sensorName} />
      </Link>
    ),
  },
  {
    id: 'modelDomain',
    header: 'ML-домен',
    width: '18%',
    cell: (row) => <span className="muted text-xs">{row.modelDomain}</span>,
  },
  { id: 'probability', header: 'Вероятность', width: '12%', align: 'right', cell: (row) => row.probability },
  {
    id: 'risk',
    header: 'Риск',
    width: '23%',
    cell: (row) => (row.supported ? <RiskBadge value={row.risk} /> : <UnsupportedMlState />),
  },
  {
    id: 'urgency',
    header: 'Срочность',
    width: '14%',
    cell: (row) => (row.supported ? <UrgencyBadge value={row.urgency} /> : '—'),
  },
  { id: 'healthIndex', header: 'ИТС', width: '7%', align: 'right', cell: (row) => row.healthIndex },
];
export function PredictionFixturesPanel() {
  const query = usePredictions();
  const [sort, setSort] = useState<SortState>({ column: 'sensorName', direction: 'asc' });
  const rows = useMemo(
    () =>
      (query.data ?? [])
        .map(toPredictionRow)
        .sort((a, b) => a.sensorName.localeCompare(b.sensorName, 'ru') * (sort.direction === 'asc' ? 1 : -1)),
    [query.data, sort],
  );
  return (
    <Panel
      title="Контракт прогнозов · 6 сценариев"
      className="table-panel"
      action={
        <IconButton
          label="Обновить тестовые данные"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          <RefreshCw size={14} />
        </IconButton>
      }
    >
      {query.data && (query.isStale || query.isError) && (
        <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
      )}
      <DataTable
        caption="Проверка контракта прогнозов"
        rows={rows}
        columns={columns}
        rowKey={(row) => row.id}
        loading={query.isPending}
        error={!query.data && query.error ? query.error.message : undefined}
        onRetry={() => void query.refetch()}
        sort={sort}
        onSort={setSort}
      />
    </Panel>
  );
}
