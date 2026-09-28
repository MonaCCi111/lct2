import { SearchInput, Select } from '../../components/ui/Fields';
import { Button } from '../../components/ui/Button';
import type { RegistryRiskFilter } from './registry-model';

interface Props {
  search: string;
  risk: RegistryRiskFilter;
  onSearch: (value: string) => void;
  onRisk: (value: RegistryRiskFilter) => void;
  onReset: () => void;
  filtered: boolean;
}
export function ObjectsFilters({ search, risk, onSearch, onRisk, onReset, filtered }: Props) {
  return (
    <div className="objects-registry-filters" role="group" aria-label="Фильтры объектов">
      <div className="objects-registry-search">
        <label htmlFor="objects-search">Поиск</label>
        <SearchInput
          id="objects-search"
          label="Поиск объектов"
          placeholder="Название объекта"
          value={search}
          onChange={(event) => onSearch(event.target.value)}
        />
      </div>
      <Select
        label="Состояние"
        value={risk}
        onChange={(event) => onRisk(event.target.value as RegistryRiskFilter)}
        options={[
          { value: 'all', label: 'Все состояния' },
          { value: 'critical', label: 'Критические' },
          { value: 'high', label: 'Высокие' },
          { value: 'medium', label: 'Умеренные' },
          { value: 'low', label: 'Низкие' },
        ]}
      />
      <Button variant="ghost" disabled={!filtered} onClick={onReset}>
        Сбросить фильтры
      </Button>
    </div>
  );
}
