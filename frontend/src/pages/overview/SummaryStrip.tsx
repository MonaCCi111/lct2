import type { useDashboardSummary } from '../../api/queries/hooks';
import { ErrorState, Skeleton, StaleState } from '../../components/feedback/States';
import { formatCount } from '../../utils/formatters';
export function SummaryStrip({ query }: { query: ReturnType<typeof useDashboardSummary> }) {
  const summary = query.data;
  return (
    <section className="summary-strip" aria-label="Сводка инфраструктуры" aria-busy={query.isPending}>
      {summary && query.isError && (
        <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
      )}
      {summary ? (
        <dl className="summary-metrics">
          <div>
            <dt>Активные риски</dt>
            <dd>{formatCount(summary.predictions.active)}</dd>
          </div>
          <div>
            <dt>
              <span className="status-dot tone-critical" />
              Критические
            </dt>
            <dd className="tone-critical">
              {formatCount(summary.predictions.critical)}
              <span>требуют внимания</span>
            </dd>
          </div>
          <div>
            <dt>Срочные ≤24 ч</dt>
            <dd>
              {formatCount(summary.predictions.flash1To6h + summary.predictions.urgent6To24h)}
              <span>приоритет обслуживания</span>
            </dd>
          </div>
          <div>
            <dt>Затронутые объекты</dt>
            <dd>
              {formatCount(summary.objects.affected)}
              <span className="summary-total">/ {formatCount(summary.objects.total)}</span>
              <span>{summary.objects.critical} критических</span>
            </dd>
          </div>
        </dl>
      ) : query.isPending ? (
        <div className="summary-metrics" role="status" aria-label="Загрузка сводки">
          {Array.from({ length: 4 }, (_, index) => (
            <div key={index}>
              <Skeleton />
              <Skeleton />
            </div>
          ))}
        </div>
      ) : (
        <ErrorState message={query.error?.message} onRetry={() => void query.refetch()} />
      )}
    </section>
  );
}
