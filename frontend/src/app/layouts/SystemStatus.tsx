import { RefreshCw } from 'lucide-react';
import { useSystem } from '../../api/queries/hooks';
import { apiConfig } from '../../api/client/config';
import { formatDateTime } from '../../utils/formatters';
import { Badge } from '../../components/ui/Badge';
import { Button } from '../../components/ui/Button';
import { ErrorState, LoadingState, StaleState } from '../../components/feedback/States';
import { useV2Meta } from '../../api/v2/queries/hooks';
export function SystemIndicator() {
  return apiConfig.enableMocks ? <LegacySystemIndicator /> : <HistoricalSystemIndicator />;
}
function HistoricalSystemIndicator() {
  const query = useV2Meta();
  return <span className="system-indicator" role="status"><span className={`status-dot tone-${query.isError ? 'error' : query.isPending ? 'neutral' : 'success'}`} />{query.isError ? 'API v2 недоступен' : query.isPending ? 'Подключение…' : 'Исторический API доступен'}</span>;
}
function LegacySystemIndicator() {
  const query = useSystem();
  const unavailable = query.isError;
  const tone = unavailable
    ? 'error'
    : query.isPending
      ? 'neutral'
      : query.data.status === 'degraded'
        ? 'warning'
        : 'success';
  return (
    <span className="system-indicator" role="status">
      <span className={`status-dot tone-${tone}`} />
      {unavailable
        ? 'API недоступен'
        : query.isPending
          ? 'Подключение…'
          : query.data.status === 'degraded'
            ? 'API: сбой сервиса'
            : apiConfig.enableMocks
              ? 'Демо API доступен'
              : 'API доступен'}
    </span>
  );
}
export function SystemStatus() {
  return apiConfig.enableMocks ? <LegacySystemStatus /> : <HistoricalSystemStatus />;
}
function HistoricalSystemStatus() {
  const query = useV2Meta();
  if (query.isPending) return <LoadingState />;
  if (query.isError) return <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />;
  return <div className="sample-stack"><Badge tone="info">Исторический API v2</Badge><dl className="definition-list"><dt>Срез данных</dt><dd>{query.data.dataCutoff}</dd><dt>Живой поток</dt><dd>{query.data.liveIngestionAvailable ? 'Доступен' : 'Не подключён'}</dd><dt>Реальные решения в источнике</dt><dd>{query.data.realFeedbackAvailable ? 'Есть' : 'Нет'}</dd><dt>Время источника</dt><dd>{query.data.sourceTimezoneKnown ? 'Зона известна' : 'Зона не подтверждена'}</dd></dl><Button onClick={() => void query.refetch()}>Обновить статус</Button></div>;
}
function LegacySystemStatus() {
  const query = useSystem();
  return (
    <div className="sample-stack">
      <Badge tone={apiConfig.enableMocks ? 'warning' : 'info'}>
        {apiConfig.enableMocks ? 'Демонстрационный режим' : 'Реальный API'}
      </Badge>
      {query.isPending ? (
        <LoadingState />
      ) : query.data ? (
        <>
          {query.isError && (
            <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
          )}
          <dl className="definition-list">
            <dt>Сервис</dt>
            <dd>{query.data.status === 'operational' ? 'Доступен' : 'Частично недоступен'}</dd>
            <dt>Последний ответ</dt>
            <dd>{formatDateTime(query.data.updatedAt)}</dd>
            <dt>Источник данных</dt>
            <dd>{apiConfig.enableMocks ? 'MSW · тестовые сценарии' : 'Backend API'}</dd>
          </dl>
        </>
      ) : (
        <ErrorState message={query.error.message} onRetry={() => void query.refetch()} />
      )}
      <Button disabled={query.isFetching} onClick={() => void query.refetch()}>
        <RefreshCw size={14} />
        {query.isFetching ? 'Проверка…' : 'Проверить соединение'}
      </Button>
    </div>
  );
}
