import { Link, useParams } from 'react-router-dom';
import { ArrowLeft, RefreshCw } from 'lucide-react';
import { useV2Draft, useV2DraftDecisions, useV2Objects, useV2WorkOrder } from '../../api/v2/queries/hooks';
import { formatV2HistoricalTimestamp } from '../../api/v2/utils/historical-time';
import { ErrorState, LoadingState, StaleState } from '../../components/feedback/States';
import { PageHeader } from '../../components/feedback/PageShell';
import { Button } from '../../components/ui/Button';
import { formatDateTime } from '../../utils/formatters';
import { reviewStateLabels } from './review-model';
import { v2ObjectDisplayName } from './work-order-model';
import './review-page.css';

export default function WorkOrderDetailPage() {
  const workOrderId = useParams().workOrderId ?? '';
  const workOrder = useV2WorkOrder(workOrderId);
  const draftId = workOrder.data?.draftId ?? '';
  const draft = useV2Draft(draftId);
  const history = useV2DraftDecisions(draftId);
  const objects = useV2Objects({ limit: 200 });

  if (workOrder.isPending) return <LoadingState />;
  if (workOrder.isError && !workOrder.data)
    return <ErrorState message={workOrder.error.message} onRetry={() => void workOrder.refetch()} />;
  if (!workOrder.data) return null;
  const item = workOrder.data;
  const decision =
    history.data?.find((entry) => entry.workOrderId === item.workOrderId) ?? draft.data?.decision;
  const objectName = v2ObjectDisplayName(item.objectId, objects.data?.items ?? []);
  const refresh = () =>
    void Promise.all([workOrder.refetch(), draft.refetch(), history.refetch(), objects.refetch()]);

  return (
    <div className="review-page review-work-order-detail">
      <Link className="review-back" to="/review/work-orders">
        <ArrowLeft size={14} aria-hidden="true" />К нарядам v2
      </Link>
      <PageHeader
        title={item.workOrderId}
        description="Наряд из одобренного исторического черновика"
        action={
          <Button variant="ghost" onClick={refresh} disabled={workOrder.isFetching}>
            <RefreshCw size={14} />
            Обновить
          </Button>
        }
      />
      {workOrder.data && workOrder.isError && (
        <StaleState onRefresh={() => void workOrder.refetch()} refreshing={workOrder.isFetching} />
      )}
      <section className="review-work-order-detail-panel" aria-labelledby="work-order-detail-heading">
        <header>
          <div>
            <p className="section-eyebrow">Наряд v2</p>
            <h2 id="work-order-detail-heading">{item.workType}</h2>
          </div>
          <span className="review-work-order-api-status">{item.status}</span>
        </header>
        <dl className="review-detail-grid">
          <div>
            <dt>Work order ID</dt>
            <dd>{item.workOrderId}</dd>
          </div>
          <div>
            <dt>Объект</dt>
            <dd>
              {objectName}
              <small className="review-detail-secondary">ID {item.objectId}</small>
            </dd>
          </div>
          <div>
            <dt>Создан</dt>
            <dd>
              <time dateTime={item.createdAt}>{formatDateTime(item.createdAt)}</time>
            </dd>
          </div>
          <div>
            <dt>Создал</dt>
            <dd>{item.createdBy}</dd>
          </div>
          <div>
            <dt>Решение</dt>
            <dd>
              {decision ? reviewStateLabels[decision.decision] : '—'}
              {decision && <small className="review-detail-secondary">{decision.decisionId}</small>}
            </dd>
          </div>
          <div>
            <dt>Внешний ID</dt>
            <dd>{item.externalWorkOrderId ?? '—'}</dd>
          </div>
          <div>
            <dt>Исполнитель</dt>
            <dd>{item.assigneeId ?? '—'}</dd>
          </div>
          <div>
            <dt>Срок</dt>
            <dd>{item.dueAt ? formatDateTime(item.dueAt) : '—'}</dd>
          </div>
        </dl>
        <div className="review-detail-text-block">
          <h3>Описание работ</h3>
          <p>{item.description}</p>
        </div>
        <div className="review-work-order-source">
          <h3>Источник</h3>
          <Link to={`/review/${encodeURIComponent(item.draftId)}`}>{item.draftId}</Link>
          <dl>
            <div>
              <dt>Время источника, зона неизвестна</dt>
              <dd>{formatV2HistoricalTimestamp(draft.data?.sourceObservationTime)}</dd>
            </div>
            <div>
              <dt>Доступно в реконструкции</dt>
              <dd>{formatV2HistoricalTimestamp(draft.data?.availableAt)}</dd>
            </div>
          </dl>
        </div>
      </section>
    </div>
  );
}
