import { useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { usePredictions } from '../../api/queries/hooks';
import { PageHeader } from '../../components/feedback/PageShell';
import { StaleState } from '../../components/feedback/States';
import { Button } from '../../components/ui/Button';
import type { SortState } from '../../components/data-display/DataTable';
import { PredictionsFilters } from './PredictionsFilters';
import { PredictionsRegistryTable } from './PredictionsRegistryTable';
import { initialFilters, hasFilters, objectOptions, selectPredictions } from './predictions-registry-model';
import './predictions-page.css';
export default function PredictionsPage() {
  const query = usePredictions({ view: 'operational' });
  const [filters, setFilters] = useState(initialFilters);
  const [sort, setSort] = useState<SortState>();
  const rows = useMemo(() => selectPredictions(query.data ?? [], filters, sort), [query.data, filters, sort]);
  const objects = useMemo(() => objectOptions(query.data ?? []), [query.data]);
  const reset = () => setFilters(initialFilters);
  return (
    <div className="predictions-registry">
      <PageHeader
        title="Прогнозы"
        description="Журнал предиктивной диагностики"
        action={
          <Button variant="ghost" disabled={query.isFetching} onClick={() => void query.refetch()}>
            <RefreshCw size={14} aria-hidden="true" />
            Обновить прогнозы
          </Button>
        }
      />
      <section className="predictions-registry-panel" aria-label="Реестр прогнозов">
        <PredictionsFilters filters={filters} onChange={setFilters} onReset={reset} objects={objects} />
        <div className="predictions-registry-context">
          <span>Показана текущая доступная выборка прогнозов</span>
          {sort ? (
            <Button variant="ghost" onClick={() => setSort(undefined)}>
              Вернуть порядок по срочности
            </Button>
          ) : (
            <span>Сначала срочность, затем вероятность</span>
          )}
        </div>
        {query.data && query.isError && (
          <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
        )}
        <PredictionsRegistryTable
          rows={rows}
          loading={query.isPending}
          error={!query.data ? query.error?.message : undefined}
          onRetry={() => void query.refetch()}
          filtered={hasFilters(filters) && Boolean(query.data?.length)}
          onReset={reset}
          sort={sort}
          onSort={setSort}
        />
        <footer className="predictions-registry-footer" aria-live="polite">
          {query.data
            ? `Показано ${rows.length} из ${query.data.length} загруженных прогнозов`
            : query.isPending
              ? 'Загрузка прогнозов…'
              : 'Выборка недоступна'}
        </footer>
      </section>
    </div>
  );
}
