import type { AnalyticsRange } from '../../domain/analytics/types';
import { Select } from '../../components/ui/Fields';
import { analyticsRangeLabels } from './analytics-model';
export function AnalyticsRangeControl({
  value,
  onChange,
}: {
  value: AnalyticsRange;
  onChange: (value: AnalyticsRange) => void;
}) {
  return (
    <Select
      label="Период аналитики"
      value={value}
      onChange={(event) => onChange(event.target.value as AnalyticsRange)}
      options={Object.entries(analyticsRangeLabels).map(([value, label]) => ({ value, label }))}
    />
  );
}
