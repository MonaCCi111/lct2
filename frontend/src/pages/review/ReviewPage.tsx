import { useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight, RefreshCw } from 'lucide-react';
import { useV2Drafts, useV2Meta, useV2Objects } from '../../api/v2/queries/hooks';
import { StaleState } from '../../components/feedback/States';
import { PageHeader } from '../../components/feedback/PageShell';
import { Button } from '../../components/ui/Button';
import { HistoricalNotice } from './HistoricalNotice';
import { initialReviewFilters, ReviewFilters, type ReviewFiltersValue } from './ReviewFilters';
import { ReviewQueueTable } from './ReviewQueueTable';
import { toReviewQueueRows } from './review-model';
import './review-page.css';

export default function ReviewPage() {
  const [filters, setFilters] = useState<ReviewFiltersValue>(initialReviewFilters);
  const [cursors, setCursors] = useState<(string | undefined)[]>([undefined]);
  const cursor = cursors.at(-1);
  const meta = useV2Meta();
  const objects = useV2Objects({ limit: 200 });
  const drafts = useV2Drafts({
    limit: 50,
    cursor,
    reviewState: filters.reviewState === 'all' ? undefined : filters.reviewState,
    basisKind: filters.basisKind === 'all' ? undefined : filters.basisKind,
    objectId: filters.objectId === 'all' ? undefined : filters.objectId,
  });
  const rows = useMemo(
    () => toReviewQueueRows(drafts.data?.items ?? [], objects.data?.items ?? []),
    [drafts.data?.items, objects.data?.items],
  );
  const filtered = filters.reviewState !== 'all' || filters.basisKind !== 'all' || filters.objectId !== 'all';
  const changeFilters = (next: ReviewFiltersValue) => {
    setFilters(next);
    setCursors([undefined]);
  };
  const refresh = () => void Promise.all([meta.refetch(), objects.refetch(), drafts.refetch()]);

  return (
    <div className="review-page">
      <PageHeader
        title="Очередь проверки"
        description="Исторические ML-черновики и наблюдаемые события для проверки диспетчером."
        action={
          <Button variant="ghost" disabled={drafts.isFetching} onClick={refresh}>
            <RefreshCw size={14} aria-hidden="true" />
            Обновить очередь
          </Button>
        }
      />
      <HistoricalNotice
        meta={meta.data}
        loading={meta.isPending}
        error={meta.isError ? meta.error.message : undefined}
        retry={() => void meta.refetch()}
      />
      <section className="review-queue-panel" aria-label="Очередь исторической проверки">
        <ReviewFilters value={filters} objects={objects.data?.items ?? []} onChange={changeFilters} />
        {objects.isError && !objects.data && (
          <p className="review-catalog-warning" role="status">
            Каталог объектов недоступен. Для объектов без имени показан идентификатор.
          </p>
        )}
        {drafts.data && drafts.isError && (
          <StaleState onRefresh={() => void drafts.refetch()} refreshing={drafts.isFetching} />
        )}
        <ReviewQueueTable
          rows={rows}
          loading={drafts.isPending}
          error={!drafts.data && drafts.isError ? drafts.error.message : undefined}
          retry={() => void drafts.refetch()}
          filtered={filtered}
          reset={() => changeFilters(initialReviewFilters)}
        />
        <footer className="review-queue-footer">
          <span aria-live="polite">
            {drafts.data
              ? `В текущей выборке: ${rows.length}`
              : drafts.isPending
                ? 'Загрузка черновиков…'
                : 'Выборка недоступна'}
          </span>
          <div className="review-pagination" aria-label="Навигация по выборкам">
            {cursors.length > 1 && (
              <Button
                variant="ghost"
                onClick={() => setCursors((items) => items.slice(0, -1))}
                disabled={drafts.isFetching}
              >
                <ChevronLeft size={14} aria-hidden="true" />
                Назад
              </Button>
            )}
            {drafts.data?.nextCursor && (
              <Button
                variant="secondary"
                onClick={() => setCursors((items) => [...items, drafts.data?.nextCursor ?? undefined])}
                disabled={drafts.isFetching}
              >
                Следующая выборка
                <ChevronRight size={14} aria-hidden="true" />
              </Button>
            )}
          </div>
        </footer>
      </section>
    </div>
  );
}
