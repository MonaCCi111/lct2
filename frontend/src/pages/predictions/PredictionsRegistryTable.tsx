import { useNavigate } from 'react-router-dom';
import { DataTable, type Column, type SortState } from '../../components/data-display/DataTable';
import { SensorTypeCell } from '../../components/data-display/SensorTypeCell';
import { RiskBadge, UrgencyBadge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { UnsupportedMlState } from '../../components/feedback/States';
import type { Prediction } from '../../domain/prediction/types';
import {
  formatDateTime,
  formatOperationalTime,
  formatProbability,
  formatHealthIndex,
} from '../../utils/formatters';
import { reviewLabels, reviewShortLabels } from './predictions-registry-model';

const columns: readonly Column<Prediction>[] = [
  {
    id: 'urgency',
    header: 'Срочность',
    className: 'pr-urgency',
    cell: (row) => <UrgencyBadge value={row.predictionSupported ? row.maintenanceUrgency : null} />,
  },
  {
    id: 'risk',
    header: 'Риск',
    className: 'pr-risk',
    cell: (row) => (row.predictionSupported ? <RiskBadge value={row.riskLevel} /> : <UnsupportedMlState />),
  },
  {
    id: 'object',
    header: 'Объект',
    className: 'pr-object',
    sortable: true,
    cell: (row) => (
      <span className="truncate" title={row.objectName}>
        {row.objectName}
      </span>
    ),
  },
  { id: 'piket', header: 'Пикет', className: 'pr-piket cell-secondary', cell: (row) => row.piket ?? '—' },
  {
    id: 'sensor',
    header: 'Датчик',
    cell: (row) => (
      <span className="truncate" title={row.sensorName}>
        {row.sensorName}
      </span>
    ),
  },
  {
    id: 'type',
    header: 'Тип',
    className: 'pr-type cell-secondary',
    cell: (row) => <SensorTypeCell sensorType={row.sensorType} />,
  },
  {
    id: 'probability',
    header: 'Вероятность',
    className: 'pr-probability cell-secondary',
    align: 'right',
    sortable: true,
    cell: (row) => formatProbability(row.predictionSupported ? row.failureProbability : null),
  },
  {
    id: 'health',
    header: 'ИТС',
    className: 'pr-health cell-secondary',
    align: 'right',
    cell: (row) => formatHealthIndex(row.predictionSupported ? row.healthIndex : null),
  },
  {
    id: 'status',
    header: 'Статус',
    className: 'pr-status',
    cell: (row) => (
      <span className="predictions-review-status" title={reviewLabels[row.reviewStatus]}>
        {reviewShortLabels[row.reviewStatus]}
      </span>
    ),
  },
  {
    id: 'updated',
    header: 'Обновлено',
    className: 'pr-updated cell-tertiary',
    sortable: true,
    cell: (row) => (
      <time
        dateTime={row.generatedAt}
        title={formatDateTime(row.generatedAt)}
        aria-label={formatDateTime(row.generatedAt)}
      >
        {formatOperationalTime(row.generatedAt)} МСК
      </time>
    ),
  },
];
interface Props {
  rows: readonly Prediction[];
  loading?: boolean;
  error?: string;
  onRetry: () => void;
  filtered: boolean;
  onReset: () => void;
  sort?: SortState;
  onSort: (sort: SortState) => void;
}
export function PredictionsRegistryTable({
  rows,
  loading,
  error,
  onRetry,
  filtered,
  onReset,
  sort,
  onSort,
}: Props) {
  const navigate = useNavigate();
  const open = (row: Prediction) => navigate(`/predictions/${encodeURIComponent(row.id)}`);
  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(row) => row.id}
      caption="Журнал ML-прогнозов"
      loading={loading}
      skeletonRows={15}
      error={error}
      onRetry={onRetry}
      sort={sort}
      onSort={onSort}
      emptyTitle={filtered ? 'По заданным условиям прогнозы не найдены' : 'Прогнозы отсутствуют'}
      emptyDescription={filtered ? 'Измените условия поиска или сбросьте фильтры.' : undefined}
      emptyAction={filtered ? <Button onClick={onReset}>Очистить условия</Button> : undefined}
      rowProps={(row) => ({
        tabIndex: 0,
        className: 'predictions-registry-row',
        'aria-label': `Открыть прогноз: ${row.sensorName}, ${row.objectName}`,
        onClick: () => open(row),
        onKeyDown: (event) => {
          if (event.key === 'Enter' && event.target === event.currentTarget) {
            event.preventDefault();
            open(row);
          }
        },
      })}
    />
  );
}
