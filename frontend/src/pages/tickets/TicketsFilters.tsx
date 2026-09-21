import { SearchInput, Select } from '../../components/ui/Fields';
import { Button } from '../../components/ui/Button';
import {
  statusFilterOptions,
  type TicketFilterState,
  type TicketStatusFilter,
} from './ticket-registry-model';

export function TicketsFilters({
  filters,
  onChange,
  onReset,
  filtered,
}: {
  filters: TicketFilterState;
  onChange: (filters: TicketFilterState) => void;
  onReset: () => void;
  filtered: boolean;
}) {
  return (
    <div className="tickets-filters">
      <SearchInput
        label="Поиск по наряду, названию, объекту, прогнозу или исполнителю"
        placeholder="Наряд, название, объект, прогноз"
        value={filters.search}
        onChange={(event) => onChange({ ...filters, search: event.target.value })}
      />
      <div className="tickets-status-filter">
        <Select
          label="Статус наряда"
          value={filters.status}
          onChange={(event) => onChange({ ...filters, status: event.target.value as TicketStatusFilter })}
          options={statusFilterOptions}
        />
      </div>
      {filtered && (
        <Button variant="ghost" onClick={onReset}>
          Сбросить фильтры
        </Button>
      )}
    </div>
  );
}
