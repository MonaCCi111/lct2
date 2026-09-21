import { formatDateTime, formatTelemetryValue } from '../../utils/formatters';
import type { TelemetryChartPoint } from './prediction-investigation-model';

export const chartGrid = {
  stroke: 'var(--border-subtle)',
  strokeDasharray: '2 4',
  vertical: false,
} as const;

export const chartAxis = {
  stroke: 'var(--border-default)',
  tick: { fill: 'var(--text-secondary)', fontSize: 11 },
  tickLine: false,
  axisLine: { stroke: 'var(--border-default)' },
  minTickGap: 28,
} as const;

interface MarkerProps {
  cx?: number;
  cy?: number;
  payload?: TelemetryChartPoint;
}
/**
 * Ordinary samples render no dot; only alarm and chatter samples get a restrained marker, so the
 * line stays calm instead of turning the whole chart into a warning surface.
 */
export function TelemetryPointMarker({ cx, cy, payload }: MarkerProps) {
  if (cx === undefined || cy === undefined || !payload) return null;
  if (payload.isChatter)
    return (
      <rect
        x={cx - 2}
        y={cy - 5}
        width={4}
        height={10}
        rx={1}
        className="telemetry-marker telemetry-marker-chatter"
      />
    );
  if (payload.isAlarm)
    return <circle cx={cx} cy={cy} r={3} className="telemetry-marker telemetry-marker-alarm" />;
  return null;
}

interface TooltipEntry {
  payload?: TelemetryChartPoint;
}
/** Timestamps are formatted here from the sample itself, always in the operational timezone. */
export function TelemetryTooltip({
  active,
  payload,
  unit,
}: {
  active?: boolean;
  payload?: readonly TooltipEntry[];
  unit: string | null;
}) {
  const point = payload?.[0]?.payload;
  if (!active || !point) return null;
  return (
    <div className="telemetry-tooltip">
      <span className="telemetry-tooltip-time">{formatDateTime(point.time)}</span>
      <span className="telemetry-tooltip-value">
        {point.value === null ? `Состояние: ${point.raw}` : formatTelemetryValue(point.value, unit)}
      </span>
      {point.isAlarm && <span className="telemetry-tooltip-flag">Аварийное значение</span>}
      {point.isChatter && <span className="telemetry-tooltip-flag">Дребезг сигнала</span>}
    </div>
  );
}
