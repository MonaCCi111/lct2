import { CircleHelp } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { formatV2HistoricalTimestamp, V2_SOURCE_TIME_LABEL } from '../../api/v2/utils/historical-time';
import { DataTable, TruncatedText, type Column } from '../../components/data-display/DataTable';
import { Button } from '../../components/ui/Button';
import { Tooltip } from '../../components/ui/Tooltip';
import { BasisLabel, ReviewState } from './ReviewSemantics';
import { formatForecastHorizon, formatModelScore, type ReviewQueueRow } from './review-model';

const scoreHelp = 'Баллы сравнимы только внутри одной модели и не являются вероятностью отказа.';

const columns: readonly Column<ReviewQueueRow>[] = [
  {
    id: 'object',
    header: 'Объект',
    className: 'review-object',
    cell: (row) => (
      <span className="review-object-name" title={row.objectName}>
        <strong>{row.objectName}</strong>
        <small>ID {row.objectId}</small>
      </span>
    ),
  },
  { id: 'channel', header: 'Канал', className: 'cell-numeric', cell: (row) => row.channelId },
  { id: 'basis', header: 'Основание', cell: (row) => <BasisLabel value={row.basisKind} /> },
  {
    id: 'model',
    header: 'Модель',
    className: 'cell-secondary review-model',
    cell: (row) => (row.modelVersion ? <TruncatedText text={row.modelVersion} /> : '—'),
  },
  {
    id: 'score',
    header: 'Балл модели',
    className: 'cell-numeric',
    align: 'right',
    headerHint: (
      <Tooltip content={scoreHelp}>
        <button className="review-column-help" aria-label={scoreHelp}>
          <CircleHelp size={13} aria-hidden="true" />
        </button>
      </Tooltip>
    ),
    cell: (row) => formatModelScore(row.score),
  },
  {
    id: 'horizon',
    header: 'Горизонт',
    className: 'cell-numeric cell-secondary',
    align: 'right',
    cell: (row) => formatForecastHorizon(row.forecastHorizonHours),
  },
  {
    id: 'source-time',
    header: 'Время источника',
    className: 'review-source-time cell-tertiary',
    cell: (row) => (
      <Tooltip content={V2_SOURCE_TIME_LABEL}>
        <time tabIndex={0} dateTime={row.sourceObservationTime ?? undefined}>
          {formatV2HistoricalTimestamp(row.sourceObservationTime)}
        </time>
      </Tooltip>
    ),
  },
  { id: 'state', header: 'Состояние проверки', cell: (row) => <ReviewState value={row.reviewState} /> },
];

export function ReviewQueueTable({
  rows,
  loading,
  error,
  retry,
  filtered,
  reset,
}: {
  rows: readonly ReviewQueueRow[];
  loading: boolean;
  error?: string;
  retry: () => void;
  filtered: boolean;
  reset: () => void;
}) {
  const navigate = useNavigate();
  const open = (row: ReviewQueueRow) => navigate(`/review/${encodeURIComponent(row.draftId)}`);
  return (
    <DataTable
      columns={columns}
      rows={rows}
      rowKey={(row) => row.draftId}
      caption="Исторические черновики для проверки"
      loading={loading}
      error={error}
      onRetry={retry}
      skeletonRows={8}
      emptyTitle={
        filtered ? 'Черновики по заданным условиям не найдены.' : 'Черновики для проверки не найдены.'
      }
      emptyDescription={filtered ? 'Измените условия или сбросьте фильтры.' : undefined}
      emptyAction={filtered ? <Button onClick={reset}>Сбросить фильтры</Button> : undefined}
      rowProps={(row) => ({
        tabIndex: 0,
        className: 'review-queue-row',
        'aria-label': `Открыть черновик: ${row.objectName}, канал ${row.channelId}`,
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
