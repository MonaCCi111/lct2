import { describe, expect, it } from 'vitest';
import type { TelemetryPoint, TelemetrySeries } from '../../domain/telemetry/types';
import { telemetryWindow } from '../../api/queries/hooks';
import {
  buildTelemetryChart,
  getUrgencyGuidance,
  telemetryEvents,
  telemetrySummary,
} from './prediction-investigation-model';

const point = (
  minutes: number,
  raw: string,
  numeric: number | null,
  extra: Partial<TelemetryPoint> = {},
): TelemetryPoint => ({
  timestamp: new Date(Date.UTC(2026, 8, 20, 12, minutes)).toISOString(),
  rawValue: raw,
  numericValue: numeric,
  statusCode: 'normal',
  isAlarm: false,
  isChatter: false,
  ...extra,
});
const series = (overrides: Partial<TelemetrySeries>): TelemetrySeries => ({
  channelId: 30004,
  sensorName: 'Температура ВШ-3',
  sensorType: 'Температура',
  valueType: 'numeric',
  unit: '°C',
  pointsCount: 0,
  points: [],
  ...overrides,
});

describe('telemetry chart model', () => {
  const numeric = series({
    points: [point(0, '21.4 °C', 21.4), point(10, '24.7 °C', 24.7), point(20, '28.7 °C', 28.7)],
  });
  it('maps numeric samples and reports min, max and last value', () => {
    const chart = buildTelemetryChart(numeric);
    expect(chart.kind).toBe('numeric');
    if (chart.kind !== 'numeric') throw new Error('expected numeric chart');
    expect({ min: chart.min, max: chart.max, last: chart.last }).toEqual({
      min: 21.4,
      max: 28.7,
      last: 28.7,
    });
  });
  it('never extends the series beyond the last measured sample', () => {
    const chart = buildTelemetryChart(numeric);
    expect(chart.data).toHaveLength(numeric.points.length);
    expect(chart.data.at(-1)?.time).toBe(Date.parse(numeric.points.at(-1)!.timestamp));
    // A forecast would need points after the last timestamp; there are none.
    const last = Date.parse(numeric.points.at(-1)!.timestamp);
    expect(chart.data.every((item) => item.time <= last)).toBe(true);
  });
  it('keeps data gaps as gaps instead of inventing values', () => {
    const chart = buildTelemetryChart(series({ points: [point(0, '—', null), point(10, '24.7 °C', 24.7)] }));
    if (chart.kind !== 'numeric') throw new Error('expected numeric chart');
    expect(chart.data[0]?.value).toBeNull();
    expect(chart.min).toBe(24.7);
  });
  it('positions discrete states on a stable index while keeping real labels', () => {
    const chart = buildTelemetryChart(
      series({
        valueType: 'state',
        unit: null,
        points: [point(0, 'Норма', null), point(10, 'Просадка', null), point(20, 'Норма', null)],
      }),
    );
    expect(chart.kind).toBe('state');
    if (chart.kind !== 'state') throw new Error('expected state chart');
    expect(chart.states).toEqual(['Норма', 'Просадка']);
    expect(chart.data.map((item) => item.stateIndex)).toEqual([0, 1, 0]);
    expect(chart.data.map((item) => item.raw)).toEqual(['Норма', 'Просадка', 'Норма']);
    expect(chart.last).toBe('Норма');
  });
});

describe('telemetry events', () => {
  it('lists alarms and collapses a chatter burst into a single entry', () => {
    const events = telemetryEvents(
      series({
        valueType: 'state',
        points: [
          point(0, 'Норма', null),
          point(5, 'Просадка', null, { isAlarm: true, statusCode: 'alarm' }),
          point(10, 'Норма', null, { isChatter: true }),
          point(11, 'Просадка', null, { isChatter: true, isAlarm: true }),
          point(12, 'Норма', null, { isChatter: true }),
          point(30, 'Отказ', null, { isAlarm: true, statusCode: 'failure' }),
        ],
      }),
    );
    expect(events.map((item) => item.kind)).toEqual(['alarm', 'chatter', 'alarm']);
    expect(events[2]?.raw).toBe('Отказ');
  });
  it('reports a sustained alarm once instead of one entry per sample', () => {
    const events = telemetryEvents(
      series({
        valueType: 'state',
        points: [
          point(0, 'Норма', null),
          ...[5, 6, 7, 8].map((minute) =>
            point(minute, 'Просадка', null, { isAlarm: true, statusCode: 'alarm' }),
          ),
          point(20, 'Норма', null),
          point(25, 'Просадка', null, { isAlarm: true, statusCode: 'alarm' }),
        ],
      }),
    );
    expect(events).toHaveLength(2);
    expect(events[0]?.timestamp).toBe(new Date(Date.UTC(2026, 8, 20, 12, 5)).toISOString());
    expect(events[1]?.timestamp).toBe(new Date(Date.UTC(2026, 8, 20, 12, 25)).toISOString());
  });
});

describe('telemetry summary', () => {
  it('describes a numeric series with its own statistics', () => {
    const summary = telemetrySummary(
      series({ points: [point(0, '21.4 °C', 21.4), point(10, '28.7 °C', 28.7)] }),
      '24h',
    );
    expect(summary).toContain('24 часа');
    expect(summary).toContain('2 точек');
    expect(summary).toContain('Минимум 21,4 °C');
    expect(summary).toContain('максимум 28,7 °C');
  });
  it('describes a state series by its states', () => {
    const summary = telemetrySummary(
      series({
        valueType: 'state',
        unit: null,
        points: [point(0, 'Норма', null), point(10, 'Отказ', null)],
      }),
      '6h',
    );
    expect(summary).toContain('Состояния: Норма, Отказ');
    expect(summary).toContain('Последнее: Отказ');
  });
  it('reports an empty series without inventing values', () => {
    expect(telemetrySummary(series({}), '48h')).toContain('Телеметрия отсутствует');
  });
});

describe('urgency guidance', () => {
  it.each([
    ['FLASH_1_6H', 'Требуется проверка в течение 1–6 часов'],
    ['URGENT_6_24H', 'Требуется проверка в течение 6–24 часов'],
    ['PLANNED_24_48H', 'Плановая проверка в течение 24–48 часов'],
    ['NORMAL', 'Штатный режим наблюдения'],
  ] as const)('maps %s to ready maintenance wording', (urgency, expected) => {
    expect(getUrgencyGuidance(urgency)).toBe(expected);
  });
  it('never claims a failure moment when urgency is missing', () => {
    expect(getUrgencyGuidance(null)).toBe('Срочность обслуживания не определена');
  });
});

describe('telemetry window', () => {
  const now = Date.UTC(2026, 8, 20, 15, 42);
  it.each([
    ['6h', 6, 96],
    ['24h', 24, 144],
    ['48h', 48, 192],
  ] as const)('turns range %s into absolute UTC bounds', (range, hours, limit) => {
    const window = telemetryWindow(range, now);
    expect(window.limit).toBe(limit);
    expect(Date.parse(window.dateTo)).toBe(now);
    expect(Date.parse(window.dateTo) - Date.parse(window.dateFrom)).toBe(hours * 3_600_000);
    // Absolute instants, never a manual timezone shift.
    expect(window.dateTo).toBe('2026-09-20T15:42:00.000Z');
  });
  it('stays within the documented API limit', () => {
    expect(telemetryWindow('48h', now).limit).toBeLessThanOrEqual(1000);
  });
});
