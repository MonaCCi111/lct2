import { Link } from 'react-router-dom';
import { ArrowUpRight, RefreshCw } from 'lucide-react';
import { useObjectStatusSummary } from '../../api/queries/hooks';
import { EmptyState, ErrorState, Skeleton, StaleState } from '../../components/feedback/States';
import { RiskBadge } from '../../components/ui/Badge';
import { IconButton } from '../../components/ui/Button';
import { formatDateTime } from '../../utils/formatters';
export function ObjectStatusPanel() {
  const query = useObjectStatusSummary();
  return (
    <section className="object-status" aria-labelledby="object-status-title">
      <header className="operational-heading">
        <div>
          <h2 id="object-status-title">Состояние объектов</h2>
          <p>Объекты с активными прогнозами</p>
        </div>
        <IconButton
          variant="ghost"
          label="Обновить состояние объектов"
          disabled={query.isFetching}
          onClick={() => void query.refetch()}
        >
          <RefreshCw size={14} />
        </IconButton>
      </header>
      {query.data && query.isError && (
        <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
      )}
      {query.isPending ? (
        <div className="object-loading" role="status" aria-label="Загрузка объектов">
          {Array.from({ length: 6 }, (_, index) => (
            <div key={index}>
              <Skeleton />
              <Skeleton />
            </div>
          ))}
        </div>
      ) : !query.data ? (
        <ErrorState message={query.error?.message} onRetry={() => void query.refetch()} />
      ) : query.data.length === 0 ? (
        <EmptyState title="Нет объектов с активными прогнозами" />
      ) : (
        <ul className="object-status-list">
          {query.data.map((item) => (
            <li key={item.objectId}>
              <Link
                to={`/objects/${item.objectId}`}
                title={`Обновлено ${formatDateTime(item.updatedAt)} · ML: ${item.mlSupportedChannels} / ${item.channelsTotal} каналов`}
              >
                <span className="object-status-main">
                  <span className="object-name">{item.objectName}</span>
                  <RiskBadge value={item.riskLevel} />
                </span>
                <span className="object-status-detail">
                  <span>
                    {item.criticalPredictions} крит. · {item.highPredictions} высок.
                  </span>
                  <span>{item.activePredictions} активных</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      )}
      <footer className="queue-footer">
        <span>{query.data ? `Показано объектов: ${query.data.length}` : 'Приоритетные объекты'}</span>
        <Link to="/objects">
          Все объекты
          <ArrowUpRight size={13} />
        </Link>
      </footer>
    </section>
  );
}
