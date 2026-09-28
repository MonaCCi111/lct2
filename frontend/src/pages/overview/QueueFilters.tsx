import { SearchInput, Select } from '../../components/ui/Fields';
import { getUrgencyLabel } from '../../utils/formatters';
import type { QueueFilters as Filters } from './queue-model';
const urgencies = ['all', 'FLASH_1_6H', 'URGENT_6_24H', 'PLANNED_24_48H'] as const;
export function QueueFilters({
  filters,
  onChange,
  objects,
}: {
  filters: Filters;
  onChange: (filters: Filters) => void;
  objects: { value: string; label: string }[];
}) {
  return (
    <div className="queue-filters">
      <div className="urgency-filter" role="group" aria-label="Срочность прогнозов">
        {urgencies.map((value) => (
          <button
            key={value}
            type="button"
            aria-pressed={filters.urgency === value}
            onClick={() => onChange({ ...filters, urgency: value })}
          >
            {value === 'all' ? 'Все' : getUrgencyLabel(value)}
          </button>
        ))}
      </div>
      <div className="queue-object-filter">
        <Select
          label="Объект в очереди"
          value={filters.objectId}
          onChange={(event) => onChange({ ...filters, objectId: event.target.value })}
          options={objects}
        />
      </div>
      <SearchInput
        label="Поиск по датчику, объекту или пикету"
        placeholder="Датчик, объект, пикет"
        value={filters.search}
        onChange={(event) => onChange({ ...filters, search: event.target.value })}
      />
    </div>
  );
}
