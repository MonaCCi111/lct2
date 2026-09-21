import { SearchInput, Select } from '../../components/ui/Fields';
import { getRiskLabel, getUrgencyLabel } from '../../utils/formatters';
import type { RiskLevel } from '../../domain/prediction/types';
import type { ObjectPredictionFilterState } from './object-workspace-model';

const urgencies = ['all', 'FLASH_1_6H', 'URGENT_6_24H', 'PLANNED_24_48H', 'NORMAL'] as const;
const risks: (RiskLevel | 'all')[] = ['all', 'critical', 'high', 'medium', 'low'];
const riskOptions = risks.map((value) => ({
  value,
  label: value === 'all' ? 'Любой риск' : getRiskLabel(value),
}));

export function ObjectPredictionFilters({
  filters,
  onChange,
}: {
  filters: ObjectPredictionFilterState;
  onChange: (filters: ObjectPredictionFilterState) => void;
}) {
  return (
    <div className="object-prediction-filters">
      <div className="urgency-filter" role="group" aria-label="Срочность прогнозов объекта">
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
      <div className="object-risk-filter">
        <Select
          label="Риск прогноза"
          value={filters.risk}
          onChange={(event) => onChange({ ...filters, risk: event.target.value as RiskLevel | 'all' })}
          options={riskOptions}
        />
      </div>
      <SearchInput
        label="Поиск по датчику, типу или пикету"
        placeholder="Датчик, тип, пикет"
        value={filters.search}
        onChange={(event) => onChange({ ...filters, search: event.target.value })}
      />
    </div>
  );
}
