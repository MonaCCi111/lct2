import type { UseQueryResult } from '@tanstack/react-query';
import type { ObjectDetail } from '../../domain/object/detail';
import { ErrorState, Skeleton, StaleState } from '../../components/feedback/States';
import { RiskBadge } from '../../components/ui/Badge';
import { formatCount } from '../../utils/formatters';
import { mlCoveragePercent } from './object-workspace-model';

export function ObjectSummary({ query }: { query: UseQueryResult<ObjectDetail> }) {
  const detail = query.data;
  const coverage = detail ? mlCoveragePercent(detail.mlSupportedChannels, detail.channelsTotal) : 0;
  return (
    <section className="object-summary" aria-label="Состояние объекта" aria-busy={query.isPending}>
      {detail && query.isError && (
        <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
      )}
      {detail ? (
        <dl className="object-summary-metrics">
          <div>
            <dt>Состояние</dt>
            <dd className="object-summary-risk">
              <RiskBadge value={detail.riskLevel} />
            </dd>
          </div>
          <div>
            <dt>Критические</dt>
            <dd className={detail.criticalPredictions > 0 ? 'tone-critical' : undefined}>
              {formatCount(detail.criticalPredictions)}
            </dd>
          </div>
          <div>
            <dt>Высокие</dt>
            <dd>{formatCount(detail.highPredictions)}</dd>
          </div>
          <div>
            <dt>Активные риски</dt>
            <dd>{formatCount(detail.activePredictions)}</dd>
          </div>
          <div className="object-summary-coverage">
            <dt>ML-покрытие</dt>
            <dd>
              {coverage}%
              <span>
                {formatCount(detail.mlSupportedChannels)} / {formatCount(detail.channelsTotal)} каналов
              </span>
            </dd>
            <div className="coverage-bar" role="img" aria-label={`ML-покрытие ${coverage}% каналов объекта`}>
              <span style={{ width: `${coverage}%` }} />
            </div>
          </div>
        </dl>
      ) : query.isPending ? (
        <div className="object-summary-metrics" role="status" aria-label="Загрузка состояния объекта">
          {Array.from({ length: 5 }, (_, index) => (
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
