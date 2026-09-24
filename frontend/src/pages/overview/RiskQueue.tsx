import { useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { ArrowDownWideNarrow, ArrowUpRight, RefreshCw } from 'lucide-react';
import { usePredictions } from '../../api/queries/hooks';
import { DataTable, type Column } from '../../components/data-display/DataTable';
import { MetricValue } from '../../components/data-display/MetricValue';
import { SensorTypeCell } from '../../components/data-display/SensorTypeCell';
import { UrgencyColumnHint } from '../../components/data-display/UrgencyColumnHint';
import { RiskBadge, UrgencyBadge } from '../../components/ui/Badge';
import { Button, IconButton } from '../../components/ui/Button';
import { StaleState } from '../../components/feedback/States';
import { Tooltip } from '../../components/ui/Tooltip';
import { QueueFilters } from './QueueFilters';
import {
  filterQueue,
  initialQueueFilters,
  queueObjectOptions,
  toRiskQueueRow,
  type RiskQueueRow,
} from './queue-model';

const columns: Column<RiskQueueRow>[] = [
  {
    id: 'urgency',
    header: 'Срочность',
    headerHint: <UrgencyColumnHint />,
    className: 'queue-urgency',
    cell: (row) => <UrgencyBadge value={row.urgency} />,
  },
  {
    id: 'risk',
    header: 'Риск',
    className: 'queue-risk',
    // The urgency squares already mark this row, so risk reads as coloured text without a dot.
    cell: (row) => <RiskBadge value={row.risk} showMarker={false} />,
  },
  {
    id: 'object',
    header: 'Объект',
    className: 'queue-object',
    cell: (row) => (
      // The letter is the display form; the full Russian name stays one hover away.
      <Link className="table-entity-link" to={`/objects/${row.objectId}`} title={row.objectFullName}>
        {row.objectName}
      </Link>
    ),
  },
  {
    id: 'piket',
    header: 'Пикет',
    className: 'queue-piket cell-secondary',
    cell: (row) => <span className="nowrap">{row.piket}</span>,
  },
  {
    id: 'sensor',
    header: 'Датчик',
    className: 'queue-sensor',
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
    className: 'queue-type cell-secondary',
    cell: (row) => <SensorTypeCell sensorType={row.sensorType} />,
  },
  {
    id: 'probability',
    header: 'Вероятность',
    className: 'queue-probability cell-secondary',
    align: 'right',
    // Colour follows the value's own scale, so a column of numbers can be scanned; the risk
    // column keeps the backend verdict.
    cell: (row) => <MetricValue value={row.probability} tone={row.probabilityTone} />,
  },
  {
    id: 'health',
    header: 'ИТС',
    className: 'queue-health cell-secondary',
    align: 'right',
    cell: (row) => <MetricValue value={row.health} tone={row.healthTone} />,
  },
  {
    id: 'updated',
    header: 'МСК',
    className: 'queue-updated cell-tertiary',
    align: 'right',
    cell: (row) => (
      <span title={row.fullUpdated} aria-label={`Обновлено ${row.fullUpdated}`}>
        {row.updated}
      </span>
    ),
  },
];

export function RiskQueue() {
  const query = usePredictions({ view: 'operational' });
  const [filters, setFilters] = useState(initialQueueFilters);
  const navigate = useNavigate();
  const rows = useMemo(
    () => filterQueue(query.data ?? [], filters).map(toRiskQueueRow),
    [query.data, filters],
  );
  const objects = useMemo(() => queueObjectOptions(query.data ?? []), [query.data]);
  const filtered = filters.urgency !== 'all' || filters.objectId !== 'all' || filters.search.trim() !== '';
  return (
    <section className="risk-queue" aria-labelledby="risk-queue-title">
      <header className="operational-heading">
        <div>
          <h2 id="risk-queue-title">
            Очередь рисков{' '}
            <span className="heading-count" aria-hidden="true">
              {query.data ? query.data.length : '—'}
            </span>
          </h2>
          <p>Прогнозы, требующие внимания диспетчера</p>
        </div>
        <IconButton
          label="Обновить очередь рисков"
          variant="ghost"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          <RefreshCw size={14} />
        </IconButton>
      </header>
      <QueueFilters filters={filters} onChange={setFilters} objects={objects} />
      <div className="queue-context">
        <span>Показаны приоритетные прогнозы</span>
        <Tooltip content="Сначала срочность, затем вероятность по убыванию">
          <span className="queue-sort-hint">
            <ArrowDownWideNarrow size={13} />
            По срочности
          </span>
        </Tooltip>
      </div>
      {query.data && query.isError && (
        <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
      )}
      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        caption="Очередь рисков"
        loading={query.isPending}
        skeletonRows={10}
        error={!query.data ? query.error?.message : undefined}
        onRetry={() => void query.refetch()}
        emptyTitle={filtered ? 'Прогнозы не найдены' : 'Активных рисков нет'}
        emptyDescription={
          filtered
            ? 'Измените условия поиска или сбросьте фильтры.'
            : 'Система не обнаружила прогнозов, требующих внимания диспетчера.'
        }
        emptyAction={
          filtered ? (
            <Button onClick={() => setFilters(initialQueueFilters)}>Сбросить фильтры</Button>
          ) : undefined
        }
        rowProps={(row) => ({
          tabIndex: 0,
          className: `queue-row ${row.risk ? `queue-row-${row.risk}` : ''}`,
          'aria-label': `Открыть прогноз: ${row.sensorName}, ${row.objectFullName}`,
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
              : 'Данные очереди недоступны'}
        </span>
        <Link to="/predictions">
          Все прогнозы
          <ArrowUpRight size={13} />
        </Link>
      </footer>
    </section>
  );
}
