import { useState } from 'react';
import { RefreshCw } from 'lucide-react';
import { useObjectStatusSummary } from '../../api/queries/hooks';
import { PageHeader } from '../../components/feedback/PageShell';
import { StaleState } from '../../components/feedback/States';
import { Button } from '../../components/ui/Button';
import { ObjectsFilters } from './ObjectsFilters';
import { ObjectsRegistryTable } from './ObjectsRegistryTable';
import { selectObjects, type RegistryRiskFilter } from './registry-model';
import './objects-page.css';

export default function ObjectsPage() {
  const query = useObjectStatusSummary();
  const [search, setSearch] = useState('');
  const [risk, setRisk] = useState<RegistryRiskFilter>('all');
  const filtered = search.trim() !== '' || risk !== 'all';
  const rows = selectObjects(query.data ?? [], search, risk);
  const reset = () => {
    setSearch('');
    setRisk('all');
  };
  return (
    <div className="objects-registry">
      <PageHeader
        title="Объекты"
        description="Состояние инженерной инфраструктуры"
        action={
          <Button variant="ghost" disabled={query.isFetching} onClick={() => void query.refetch()}>
            <RefreshCw size={14} aria-hidden="true" />
            Обновить реестр
          </Button>
        }
      />
      <section className="objects-registry-panel" aria-label="Реестр объектов">
        <ObjectsFilters
          search={search}
          risk={risk}
          onSearch={setSearch}
          onRisk={setRisk}
          onReset={reset}
          filtered={filtered}
        />
        <p className="objects-registry-scope">Доступная выборка объектов с активными прогнозами</p>
        {query.data && query.isError && (
          <StaleState onRefresh={() => void query.refetch()} refreshing={query.isFetching} />
        )}
        <ObjectsRegistryTable
          rows={rows}
          loading={query.isPending}
          error={!query.data && query.isError ? query.error.message : undefined}
          onRetry={() => void query.refetch()}
          filtered={filtered && Boolean(query.data?.length)}
          onReset={reset}
        />
        <footer className="objects-registry-footer">
          <span aria-live="polite">
            {query.data
              ? `Показано ${rows.length} из ${query.data.length} загруженных объектов`
              : query.isPending
                ? 'Загрузка объектов…'
                : 'Выборка недоступна'}
          </span>
          <span>Сначала критические · время МСК</span>
        </footer>
      </section>
    </div>
  );
}
