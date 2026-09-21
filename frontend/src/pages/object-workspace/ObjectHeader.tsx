import { RefreshCw } from 'lucide-react';
import type { UseQueryResult } from '@tanstack/react-query';
import type { ObjectDetail } from '../../domain/object/detail';
import { PageHeader } from '../../components/feedback/PageShell';
import { Button } from '../../components/ui/Button';
import { formatCount, formatDateTime } from '../../utils/formatters';
import { mlCoveragePercent } from './object-workspace-model';

export function ObjectHeader({ query, objectId }: { query: UseQueryResult<ObjectDetail>; objectId: number }) {
  const detail = query.data;
  const description = detail
    ? `${detail.objectType} · ${formatCount(detail.channelsTotal)} каналов · ML-покрытие ${mlCoveragePercent(detail.mlSupportedChannels, detail.channelsTotal)}%`
    : query.isPending
      ? 'Загрузка данных объекта…'
      : 'Данные объекта недоступны';
  return (
    <PageHeader
      title={detail ? detail.objectName : `Объект ${objectId}`}
      description={description}
      action={
        <div className="object-header-meta">
          <span>
            {detail ? `Обновлено ${formatDateTime(detail.updatedAt)}` : 'Время обновления неизвестно'}
          </span>
          <Button
            variant="ghost"
            aria-label="Обновить данные объекта"
            disabled={query.isFetching}
            onClick={() => void query.refetch()}
          >
            <RefreshCw size={14} />
            <span>Обновить</span>
          </Button>
        </div>
      }
    />
  );
}
