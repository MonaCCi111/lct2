import { useNavigate } from 'react-router-dom';
import { DataTable, type Column } from '../../components/data-display/DataTable';
import { RiskBadge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import type { ObjectStatusSummary } from '../../domain/object/status';
import { formatCount, formatDateTime } from '../../utils/formatters';
import { registryCoverage } from './registry-model';

const columns: readonly Column<ObjectStatusSummary>[] = [
  {
    id: 'object',
    header: 'Объект',
    width: '24%',
    cell: (row) => (
      <span className="objects-registry-name" title={row.objectName}>
        {row.objectName}
      </span>
    ),
  },
  { id: 'risk', header: 'Состояние', width: '14%', cell: (row) => <RiskBadge value={row.riskLevel} /> },
  {
    id: 'active',
    header: 'Активные прогнозы',
    width: '13%',
    align: 'right',
    cell: (row) => formatCount(row.activePredictions),
  },
  {
    id: 'critical',
    header: 'Критические',
    width: '10%',
    align: 'right',
    cell: (row) => formatCount(row.criticalPredictions),
  },
  {
    id: 'high',
    header: 'Высокие',
    width: '8%',
    align: 'right',
    cell: (row) => formatCount(row.highPredictions),
  },
  {
    id: 'coverage',
    header: 'ML-покрытие',
    width: '12%',
    align: 'right',
    cell: (row) => (
      <span className="objects-registry-coverage">
        <span>{registryCoverage(row)}</span>
        <span className="objects-registry-channels">
          {formatCount(row.mlSupportedChannels)} / {formatCount(row.channelsTotal)}
        </span>
      </span>
    ),
  },
  {
    id: 'updated',
    header: 'Обновлено',
    width: '19%',
    cell: (row) => (
      <time className="objects-registry-time" dateTime={row.updatedAt}>
        {formatDateTime(row.updatedAt)}
      </time>
    ),
  },
];
interface Props {
  rows: readonly ObjectStatusSummary[];
  loading: boolean;
  error?: string;
  onRetry: () => void;
  filtered: boolean;
  onReset: () => void;
}
export function ObjectsRegistryTable({ rows, loading, error, onRetry, filtered, onReset }: Props) {
  const navigate = useNavigate();
  const open = (row: ObjectStatusSummary) => navigate(`/objects/${row.objectId}`);
  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(row) => String(row.objectId)}
      caption="Реестр инженерных объектов"
      loading={loading}
      error={error}
      onRetry={onRetry}
      skeletonRows={8}
      emptyTitle={filtered ? 'Объекты не найдены' : 'Нет доступных объектов'}
      emptyDescription={
        filtered ? 'Измените параметры поиска или фильтрации.' : 'В доступной выборке объектов пока нет.'
      }
      emptyAction={filtered ? <Button onClick={onReset}>Очистить поиск и фильтры</Button> : undefined}
      rowProps={(row) => ({
        className: 'objects-registry-row',
        tabIndex: 0,
        'aria-label': `Открыть объект: ${row.objectName}`,
        onClick: () => open(row),
        onKeyDown: (event) => {
          if (event.key === 'Enter') {
            event.preventDefault();
            open(row);
          }
        },
      })}
    />
  );
}
