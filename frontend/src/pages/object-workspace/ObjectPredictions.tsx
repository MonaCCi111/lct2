import { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowDownWideNarrow, RefreshCw } from 'lucide-react';
import type { UseQueryResult } from '@tanstack/react-query';
import type { Prediction } from '../../domain/prediction/types';
import type { TopologySegment } from '../../domain/object/topology';
import { DataTable, type Column } from '../../components/data-display/DataTable';
import { RiskBadge, UrgencyBadge } from '../../components/ui/Badge';
import { Button, IconButton } from '../../components/ui/Button';
import { StaleState, UnsupportedMlState } from '../../components/feedback/States';
import { Tooltip } from '../../components/ui/Tooltip';
import { ObjectPredictionFilters } from './ObjectPredictionFilters';
import {
  hasActiveFilters,
  initialObjectPredictionFilters,
  toObjectPredictionRow,
  type ObjectPredictionFilterState,
  type ObjectPredictionRow,
} from './object-workspace-model';

const columns: Column<ObjectPredictionRow>[] = [
  {
    id: 'urgency',
    header: 'Срочность',
    className: 'object-col-urgency',
    cell: (row) => <UrgencyBadge value={row.urgency} />,
  },
  {
    id: 'risk',
    header: 'Риск',
    className: 'object-col-risk',
    cell: (row) => <RiskBadge value={row.risk} />,
  },
  {
    id: 'piket',
    header: 'Пикет',
    className: 'object-col-piket',
    cell: (row) => <span className="muted nowrap">{row.piket}</span>,
  },
  {
    id: 'sensor',
    header: 'Датчик',
    className: 'object-col-sensor',
    cell: (row) => (
      <Link
        className="queue-sensor-link truncate"
        to={`/predictions/${row.id}`}
        tabIndex={-1}
        title={row.sensorName}
      >
        {row.sensorName}
      </Link>
    ),
  },
  {
    id: 'type',
    header: 'Тип',
    className: 'object-col-type',
    cell: (row) => (
      <span className="truncate muted" title={row.sensorType}>
        {row.sensorType}
      </span>
    ),
  },
  {
    id: 'probability',
    header: 'Вероятность',
    className: 'object-col-probability',
    align: 'right',
    cell: (row) => (row.risk === null ? <UnsupportedMlState /> : row.probability),
  },
  { id: 'health', header: 'ИТС', className: 'object-col-health', align: 'right', cell: (row) => row.health },
  {
    id: 'updated',
    header: 'Обновлено',
    className: 'object-col-updated',
    align: 'right',
    cell: (row) => (
      <span title={row.fullUpdated} aria-label={`Обновлено ${row.fullUpdated}`} className="muted">
        {row.updated}
      </span>
    ),
  },
];

export function ObjectPredictions({
  query,
  filters,
  onFiltersChange,
  selected,
  onResetSegment,
  predictions,
}: {
  query: UseQueryResult<Prediction[]>;
  filters: ObjectPredictionFilterState;
  onFiltersChange: (filters: ObjectPredictionFilterState) => void;
  selected: TopologySegment | null;
  onResetSegment: () => void;
  predictions: readonly Prediction[];
}) {
  const navigate = useNavigate();
  const rows = useMemo(() => predictions.map(toObjectPredictionRow), [predictions]);
  const narrowed = hasActiveFilters(filters) || selected !== null;
  const reset = () => {
    onFiltersChange(initialObjectPredictionFilters);
    onResetSegment();
  };
  return (
    <section className="object-predictions" aria-labelledby="object-predictions-title">
      <header className="workspace-block-heading">
        <div>
          <h2 id="object-predictions-title">
            Прогнозы объекта{' '}
            <span className="heading-count" aria-hidden="true">
              {query.data ? query.data.length : '—'}
            </span>
          </h2>
          <p>Активные прогнозы по каналам объекта</p>
        </div>
        <div className="object-predictions-tools">
          <Tooltip content="Сначала срочность, затем вероятность по убыванию">
            <span className="queue-sort-hint">
              <ArrowDownWideNarrow size={13} />
              По срочности
            </span>
          </Tooltip>
          <IconButton
            variant="ghost"
            label="Обновить прогнозы объекта"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            <RefreshCw size={14} />
          </IconButton>
        </div>
      </header>
      <ObjectPredictionFilters filters={filters} onChange={onFiltersChange} />
      {query.data && query.isError && (
        <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
      )}
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption="Прогнозы объекта"
        loading={query.isPending}
        skeletonRows={8}
        error={!query.data ? query.error?.message : undefined}
        onRetry={() => void query.refetch()}
        emptyTitle={narrowed ? 'Прогнозы не найдены' : 'Активных прогнозов для объекта нет'}
        emptyDescription={
          narrowed
            ? 'Измените условия поиска, выберите другой участок или сбросьте фильтры.'
            : 'Система не обнаружила активных прогнозов по каналам этого объекта.'
        }
        emptyAction={narrowed ? <Button onClick={reset}>Сбросить фильтры</Button> : undefined}
        rowProps={(row) => ({
          tabIndex: 0,
          className: `queue-row ${row.risk === 'critical' ? 'queue-row-critical' : ''}`,
          'aria-label': `Открыть прогноз: ${row.sensorName}, ${row.piket}`,
          onClick: (event) => {
            if (!(event.target instanceof Element && event.target.closest('a,button')))
              void navigate(`/predictions/${row.id}`);
          },
          onKeyDown: (event) => {
            if (event.key === 'Enter' && event.target === event.currentTarget) {
              event.preventDefault();
              void navigate(`/predictions/${row.id}`);
            }
          },
        })}
      />
      <footer className="queue-footer">
        <span aria-live="polite">
          {query.data
            ? `Показано ${rows.length} из ${query.data.length} загруженных`
            : query.isPending
              ? 'Загрузка прогнозов…'
              : 'Прогнозы объекта недоступны'}
        </span>
        <Link to="/predictions">Все прогнозы системы</Link>
      </footer>
    </section>
  );
}
