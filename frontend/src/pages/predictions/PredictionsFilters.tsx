import { Button } from '../../components/ui/Button';
import { SearchInput, Select } from '../../components/ui/Fields';
import { getRiskLabel, getUrgencyLabel } from '../../utils/formatters';
import { hasFilters, type RegistryFilters } from './predictions-registry-model';

interface Props {
  filters: RegistryFilters;
  onChange: (filters: RegistryFilters) => void;
  onReset: () => void;
  objects: { value: string; label: string }[];
}
export function PredictionsFilters({ filters, onChange, onReset, objects }: Props) {
  return (
    <div className="predictions-registry-filters" role="group" aria-label="Фильтры прогнозов">
      <div className="predictions-registry-search">
        <label htmlFor="predictions-search">Поиск</label>
        <SearchInput
          id="predictions-search"
          label="Поиск прогнозов"
          placeholder="Поиск по датчику, объекту или пикету"
          value={filters.search}
          onChange={(event) => onChange({ ...filters, search: event.target.value })}
        />
      </div>
      <Select
        label="Срочность"
        value={filters.urgency}
        onChange={(event) =>
          onChange({ ...filters, urgency: event.target.value as RegistryFilters['urgency'] })
        }
        options={[
          { value: 'all', label: 'Все сроки' },
          ...(['FLASH_1_6H', 'URGENT_6_24H', 'PLANNED_24_48H', 'NORMAL'] as const).map((value) => ({
            value,
            label: getUrgencyLabel(value),
          })),
        ]}
      />
      <Select
        label="Риск"
        value={filters.risk}
        onChange={(event) => onChange({ ...filters, risk: event.target.value as RegistryFilters['risk'] })}
        options={[
          { value: 'all', label: 'Все риски' },
          ...(['critical', 'high', 'medium', 'low'] as const).map((value) => ({
            value,
            label: getRiskLabel(value),
          })),
        ]}
      />
      <Select
        label="Объект"
        value={filters.objectId}
        onChange={(event) => onChange({ ...filters, objectId: event.target.value })}
        options={objects}
      />
      {hasFilters(filters) && (
        <Button variant="ghost" onClick={onReset}>
          Сбросить фильтры
        </Button>
      )}
    </div>
  );
}
