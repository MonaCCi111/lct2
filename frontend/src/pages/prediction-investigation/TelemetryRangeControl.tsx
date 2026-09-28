import type { TelemetryRange } from '../../domain/telemetry/types';
import { telemetryRanges } from './prediction-investigation-model';

export function TelemetryRangeControl({
  value,
  onChange,
  disabled,
}: {
  value: TelemetryRange;
  onChange: (range: TelemetryRange) => void;
  disabled?: boolean;
}) {
  return (
    <div className="urgency-filter" role="group" aria-label="Период телеметрии">
      {telemetryRanges.map((range) => (
        <button
          key={range.value}
          type="button"
          aria-pressed={value === range.value}
          disabled={disabled}
          onClick={() => onChange(range.value)}
        >
          {range.label}
        </button>
      ))}
    </div>
  );
}
