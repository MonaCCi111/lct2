import { Archive } from 'lucide-react';
import type { V2Meta } from '../../api/v2/domain/types';
import { formatV2HistoricalTimestamp } from '../../api/v2/utils/historical-time';
import { Button } from '../../components/ui/Button';

export function HistoricalNotice({
  meta,
  loading,
  error,
  retry,
}: {
  meta?: V2Meta;
  loading: boolean;
  error?: string;
  retry: () => void;
}) {
  return (
    <aside className="review-history-notice" aria-label="Режим данных">
      <Archive size={16} aria-hidden="true" />
      <div>
        <strong>Исторические данные</strong>
        {loading && <span>Загрузка сведений о срезе…</span>}
        {meta && (
          <span>
            Срез данных:{' '}
            <time dateTime={meta.dataCutoff}>{formatV2HistoricalTimestamp(meta.dataCutoff)}</time>
            {!meta.sourceTimezoneKnown && ' · зона времени источника не указана'}
          </span>
        )}
        {error && <span>Сведения о срезе недоступны: {error}</span>}
      </div>
      {error && (
        <Button variant="ghost" onClick={retry}>
          Повторить
        </Button>
      )}
    </aside>
  );
}
