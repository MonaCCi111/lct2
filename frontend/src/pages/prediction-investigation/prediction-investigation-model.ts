import type { MaintenanceUrgency } from '../../domain/prediction/types';
import type { TelemetryPoint, TelemetryRange, TelemetrySeries } from '../../domain/telemetry/types';
import { formatTelemetryValue } from '../../utils/formatters';

export const telemetryRanges: { value: TelemetryRange; label: string }[] = [
  { value: '6h', label: '6 ч' },
  { value: '24h', label: '24 ч' },
  { value: '48h', label: '48 ч' },
];
export const defaultTelemetryRange: TelemetryRange = '24h';
export const rangeLabels: Record<TelemetryRange, string> = {
  '6h': '6 часов',
  '24h': '24 часа',
  '48h': '48 часов',
};

// Urgency text comes from the ready maintenance_urgency value, never from lead time or probability.
export const urgencyGuidance: Record<MaintenanceUrgency, string> = {
  FLASH_1_6H: 'Требуется проверка в течение 1–6 часов',
  URGENT_6_24H: 'Требуется проверка в течение 6–24 часов',
  PLANNED_24_48H: 'Плановая проверка в течение 24–48 часов',
  NORMAL: 'Штатный режим наблюдения',
};
export const getUrgencyGuidance = (urgency: MaintenanceUrgency | null) =>
  urgency === null ? 'Срочность обслуживания не определена' : urgencyGuidance[urgency];

export interface TelemetryChartPoint {
  time: number;
  value: number | null;
  stateIndex: number | null;
  raw: string;
  isAlarm: boolean;
  isChatter: boolean;
}
export interface NumericChartModel {
  kind: 'numeric';
  data: readonly TelemetryChartPoint[];
  min: number | null;
  max: number | null;
  last: number | null;
  unit: string | null;
}
export interface StateChartModel {
  kind: 'state';
  data: readonly TelemetryChartPoint[];
  states: readonly string[];
  last: string | null;
}
export type TelemetryChartModel = NumericChartModel | StateChartModel;

const toTime = (point: TelemetryPoint) => Date.parse(point.timestamp);

/**
 * Builds chart data strictly from the received samples. No point is ever appended beyond the last
 * measured timestamp: the ML contract returns a risk probability, not a future telemetry series.
 */
export function buildTelemetryChart(series: TelemetrySeries): TelemetryChartModel {
  if (series.valueType === 'state') {
    // Distinct states get a stable vertical position; labels always show the real raw value.
    const states = [...new Set(series.points.map((point) => point.rawValue))];
    const data = series.points.map((point) => ({
      time: toTime(point),
      value: null,
      stateIndex: states.indexOf(point.rawValue),
      raw: point.rawValue,
      isAlarm: point.isAlarm,
      isChatter: point.isChatter,
    }));
    return { kind: 'state', data, states, last: series.points.at(-1)?.rawValue ?? null };
  }
  const data = series.points.map((point) => ({
    time: toTime(point),
    value: point.numericValue,
    stateIndex: null,
    raw: point.rawValue,
    isAlarm: point.isAlarm,
    isChatter: point.isChatter,
  }));
  const values = data.map((point) => point.value).filter((value): value is number => value !== null);
  return {
    kind: 'numeric',
    data,
    min: values.length > 0 ? Math.min(...values) : null,
    max: values.length > 0 ? Math.max(...values) : null,
    last: data.at(-1)?.value ?? null,
    unit: series.unit,
  };
}

export interface TelemetryEvent {
  timestamp: string;
  raw: string;
  kind: 'alarm' | 'chatter';
}
/**
 * Collapses consecutive samples of the same kind into a single entry: a sag that lasts eight
 * samples is one event for the dispatcher, not eight identical lines.
 */
export function telemetryEvents(series: TelemetrySeries): TelemetryEvent[] {
  const events: TelemetryEvent[] = [];
  let open: TelemetryEvent['kind'] | null = null;
  for (const point of series.points) {
    const kind = point.isChatter ? 'chatter' : point.isAlarm ? 'alarm' : null;
    if (kind !== null && kind !== open)
      events.push({ timestamp: point.timestamp, raw: point.rawValue, kind });
    open = kind;
  }
  return events;
}

/**
 * Screen-reader summary of the loaded series. These are plain statistics of the samples that were
 * received — they are not an ML judgement and never feed risk, urgency or health.
 */
export function telemetrySummary(series: TelemetrySeries, range: TelemetryRange) {
  const window = `${series.sensorName}, ${rangeLabels[range]}.`;
  if (series.points.length === 0) return `Телеметрия отсутствует. ${window}`;
  const count = `${series.points.length} точек.`;
  if (series.valueType === 'state') {
    const states = [...new Set(series.points.map((point) => point.rawValue))];
    return `Телеметрия состояний: ${window} ${count} Состояния: ${states.join(', ')}. Последнее: ${series.points.at(-1)?.rawValue ?? '—'}.`;
  }
  const chart = buildTelemetryChart(series) as NumericChartModel;
  if (chart.min === null || chart.max === null) return `Телеметрия: ${window} ${count}`;
  return `Телеметрия: ${window} ${count} Минимум ${formatTelemetryValue(chart.min, series.unit)}, максимум ${formatTelemetryValue(chart.max, series.unit)}, последнее значение ${formatTelemetryValue(chart.last, series.unit)}.`;
}

export const statusLabels: Record<TelemetryPoint['statusCode'], string> = {
  normal: 'Норма',
  alarm: 'Авария',
  failure: 'Неисправен',
  unknown: 'Нет данных',
};
