import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { useV2Draft, useV2DraftEvidence, useV2Meta, useV2Objects } from '../../api/v2/queries/hooks';
import {
  formatV2HistoricalTimestamp,
  V2_AVAILABLE_AT_LABEL,
  V2_SOURCE_TIME_LABEL,
} from '../../api/v2/utils/historical-time';
import { DataTable, TruncatedText, type Column } from '../../components/data-display/DataTable';
import { ErrorState, LoadingState, StaleState } from '../../components/feedback/States';
import { PageHeader } from '../../components/feedback/PageShell';
import { Button } from '../../components/ui/Button';
import { HistoricalNotice } from './HistoricalNotice';
import { BasisLabel, ReviewState } from './ReviewSemantics';
import { DecisionPanel } from './DecisionPanel';
import { WorkOrderPanel } from './WorkOrderPanel';
import { formatForecastHorizon, formatIts, formatModelScore, parseLimitations } from './review-model';
import type { V2Evidence } from '../../api/v2/domain/types';
import './review-page.css';

const evidenceColumns: readonly Column<V2Evidence>[] = [
  {
    id: 'time',
    header: 'Время',
    className: 'cell-tertiary review-evidence-time',
    cell: (row) => formatV2HistoricalTimestamp(row.sourceTime ?? row.eventTime),
  },
  {
    id: 'observed',
    header: 'Наблюдаемое значение',
    cell: (row) => <TruncatedText text={row.observedValue} />,
  },
  {
    id: 'numeric',
    header: 'Числовое значение',
    className: 'cell-numeric cell-secondary',
    align: 'right',
    cell: (row) =>
      row.numericValue === null ? '—' : `${row.numericValue}${row.numericUnit ? ` ${row.numericUnit}` : ''}`,
  },
  {
    id: 'alarm',
    header: 'Признак alarm',
    cell: (row) => {
      const alarm = row.sourceAlarm ?? row.recordedAlarm;
      return alarm === null ? '—' : alarm ? 'Да' : 'Нет';
    },
  },
  {
    id: 'source',
    header: 'Source ref',
    className: 'cell-tertiary review-source-ref',
    cell: (row) => <TruncatedText text={row.sourceRef} />,
  },
];

export default function ReviewDetailPage() {
  const draftId = useParams().draftId ?? '';
  const meta = useV2Meta();
  const draft = useV2Draft(draftId);
  const evidence = useV2DraftEvidence(draftId, { limit: 100 });
  const objects = useV2Objects({ limit: 200 });

  if (draft.isPending) return <LoadingState />;
  if (draft.isError && !draft.data)
    return <ErrorState message={draft.error.message} onRetry={() => void draft.refetch()} />;
  if (!draft.data) return null;

  const item = draft.data;
  const objectName = objects.data?.items.find((object) => object.objectId === item.objectId)?.objectName;
  const limitations = parseLimitations(item.limitations);
  const refresh = () =>
    void Promise.all([draft.refetch(), evidence.refetch(), objects.refetch(), meta.refetch()]);

  return (
    <div className="review-page review-detail-page">
      <Link className="review-back" to="/review">
        <ArrowLeft size={14} aria-hidden="true" />К очереди проверки
      </Link>
      <PageHeader
        title="Черновик проверки"
        description={item.draftId}
        action={
          <Button variant="ghost" disabled={draft.isFetching || evidence.isFetching} onClick={refresh}>
            <RefreshCw size={14} aria-hidden="true" />
            Обновить данные
          </Button>
        }
      />
      <HistoricalNotice
        meta={meta.data}
        loading={meta.isPending}
        error={meta.isError ? meta.error.message : undefined}
        retry={() => void meta.refetch()}
      />
      {draft.isError && draft.data && (
        <StaleState onRefresh={() => void draft.refetch()} refreshing={draft.isFetching} />
      )}
      <section className="review-detail-panel" aria-labelledby="review-detail-heading">
        <header>
          <div>
            <p className="section-eyebrow">Контекст черновика</p>
            <h2 id="review-detail-heading">{objectName ?? `Объект ${item.objectId}`}</h2>
            <p className="review-detail-object-id">Object ID {item.objectId}</p>
          </div>
          <ReviewState value={item.reviewState} />
        </header>
        <dl className="review-detail-grid">
          <div>
            <dt>Канал</dt>
            <dd className="numeric">{item.channelId}</dd>
          </div>
          <div>
            <dt>Основание</dt>
            <dd>
              <BasisLabel value={item.basisKind} />
            </dd>
          </div>
          <div>
            <dt>Модель</dt>
            <dd>{item.modelVersion ?? '—'}</dd>
          </div>
          <div>
            <dt>Target kind</dt>
            <dd>{item.targetKind}</dd>
          </div>
          <div>
            <dt>Балл модели</dt>
            <dd className="numeric">{formatModelScore(item.score)}</dd>
          </div>
          <div>
            <dt>Горизонт</dt>
            <dd className="numeric">{formatForecastHorizon(item.forecastHorizonHours)}</dd>
          </div>
          <div>
            <dt>{V2_SOURCE_TIME_LABEL}</dt>
            <dd className="numeric">
              <time dateTime={item.sourceObservationTime ?? undefined}>
                {formatV2HistoricalTimestamp(item.sourceObservationTime)}
              </time>
            </dd>
          </div>
          <div>
            <dt>{V2_AVAILABLE_AT_LABEL}</dt>
            <dd className="numeric">
              <time dateTime={item.availableAt}>{formatV2HistoricalTimestamp(item.availableAt)}</time>
            </dd>
          </div>
          <div>
            <dt>ИТС</dt>
            <dd>{formatIts(item.itsValue)}</dd>
          </div>
          <div>
            <dt>Причина статуса ИТС</dt>
            <dd>{item.itsStatus ?? '—'}</dd>
          </div>
        </dl>
        <div className="review-detail-text-block">
          <h3>Ограничения данных</h3>
          {limitations.length ? (
            <ul>
              {limitations.map((value) => (
                <li key={value}>{value}</li>
              ))}
            </ul>
          ) : (
            <p>—</p>
          )}
        </div>
        <div className="review-detail-text-block">
          <h3>Source ref</h3>
          <p className="review-raw-value">{item.sourceRef ?? '—'}</p>
        </div>
      </section>
      <DecisionPanel draft={item} />
      <WorkOrderPanel draft={item} />
      <section className="review-evidence-panel" aria-labelledby="review-evidence-heading">
        <header>
          <div>
            <h2 id="review-evidence-heading">Свидетельства</h2>
            <p>Исходные исторические наблюдения без интерпретации как подтверждённой аварии.</p>
          </div>
        </header>
        {evidence.data && evidence.isError && (
          <StaleState onRefresh={() => void evidence.refetch()} refreshing={evidence.isFetching} />
        )}
        <DataTable
          columns={evidenceColumns}
          rows={evidence.data?.items ?? []}
          rowKey={(row) => `${row.sourceRef}:${row.eventId ?? row.eventTime ?? row.availableAt}`}
          caption="Свидетельства черновика"
          loading={evidence.isPending}
          error={!evidence.data && evidence.isError ? evidence.error.message : undefined}
          onRetry={() => void evidence.refetch()}
          emptyTitle="Свидетельства для черновика не найдены."
        />
      </section>
    </div>
  );
}
