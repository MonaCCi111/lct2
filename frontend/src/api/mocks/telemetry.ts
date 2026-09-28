import type {
  TelemetryPointDto,
  TelemetryResponseDto,
  TelemetryStatusCode,
  TelemetryValueType,
} from '../dto/telemetry';

// Deterministic pseudo-noise: the same index always yields the same value, so demo series and
// tests are reproducible while still looking like a real measurement channel.
function wobble(seed: number, index: number) {
  const value = Math.sin((index + 1) * 12.9898 + seed * 78.233) * 43758.5453;
  return value - Math.floor(value); // 0..1
}

interface BuiltPoint {
  raw: string;
  numeric: number | null;
  status: TelemetryStatusCode;
  alarm?: boolean;
  chatter?: boolean;
}
interface TelemetryFixture {
  channelId: number;
  sensorName: string;
  sensorType: string;
  valueType: TelemetryValueType;
  unit: string | null;
  // `position` is 0 at the oldest point and 1 at the newest one.
  build: (position: number, index: number) => BuiltPoint;
}

const celsius = (value: number): BuiltPoint => ({
  raw: `${value.toFixed(1)} °C`,
  numeric: Number(value.toFixed(1)),
  status: 'normal',
});

const fixtures: TelemetryFixture[] = [
  {
    // Scenario A — critical ANALOG_TEMP channel behind prediction OW-004 (46%, critical).
    // Calm start, a noisy middle, then a constant plateau: the stuck-ADC-bit signature.
    channelId: 30004,
    sensorName: 'Температура ВШ-3',
    sensorType: 'Температура',
    valueType: 'numeric',
    unit: '°C',
    build: (position, index) => {
      const drift = 22.4 + position * 3.6;
      if (position >= 0.72) {
        // Plateau: the low bit stopped changing, the value freezes.
        const frozen = celsius(27.3);
        return { ...frozen, status: 'unknown', raw: '27.3 °C' };
      }
      const noise = position >= 0.42 ? (wobble(1, index) - 0.5) * 5.2 : (wobble(1, index) - 0.5) * 1.1;
      const value = drift + noise;
      const alarm = value >= 26.4;
      return { ...celsius(value), status: alarm ? 'alarm' : 'normal', alarm };
    },
  },
  {
    // Scenario B + C — POWER_PHASE state channel behind prediction OW-005 (82%, critical):
    // steady supply, a sag, a chatter burst, then a failure.
    channelId: 30005,
    sensorName: 'Фаза B · тяговый ввод',
    sensorType: 'Состояние фазы',
    valueType: 'state',
    unit: null,
    build: (position, index) => {
      if (position >= 0.93) return { raw: 'Отказ', numeric: null, status: 'failure', alarm: true };
      if (position >= 0.62 && position < 0.72) {
        // Chatter: the input flaps between states several times in a row.
        const sagging = index % 2 === 0;
        return {
          raw: sagging ? 'Просадка' : 'Норма',
          numeric: null,
          status: sagging ? 'alarm' : 'normal',
          alarm: sagging,
          chatter: true,
        };
      }
      if (position >= 0.34 && position < 0.4)
        return { raw: 'Просадка', numeric: null, status: 'alarm', alarm: true };
      return { raw: 'Норма', numeric: null, status: 'normal' };
    },
  },
  {
    // Numeric gas channel behind prediction OW-016 (77%, critical): smooth concentration growth.
    channelId: 30016,
    sensorName: 'Газ CO · венткамера ВК-6',
    sensorType: 'Газ',
    valueType: 'numeric',
    unit: 'ppm',
    build: (position, index) => {
      const value = 6.2 + position * 11.4 + (wobble(3, index) - 0.5) * 1.3;
      const alarm = value >= 16.5;
      return {
        raw: `${value.toFixed(2)} ppm`,
        numeric: Number(value.toFixed(2)),
        status: alarm ? 'alarm' : 'normal',
        alarm,
      };
    },
  },
  {
    // Scenario F — access-control door: ML is unsupported for this channel, telemetry still works.
    channelId: 1006,
    sensorName: 'Дверь технического помещения',
    sensorType: 'КД Дверь',
    valueType: 'state',
    unit: null,
    build: (position, index) => {
      if (position >= 0.55 && position < 0.61) {
        const open = index % 2 === 0;
        return {
          raw: open ? 'Открыта' : 'Закрыта',
          numeric: null,
          status: 'normal',
          chatter: true,
        };
      }
      const open = (position >= 0.24 && position < 0.29) || (position >= 0.78 && position < 0.82);
      return { raw: open ? 'Открыта' : 'Закрыта', numeric: null, status: 'normal' };
    },
  },
  {
    // Scenario G — pump behind prediction HYDRO-003, which already has a work order.
    channelId: 1003,
    sensorName: 'Дренажный насос № 2',
    sensorType: 'Насос',
    valueType: 'state',
    unit: null,
    build: (position, index) => {
      // Frequent starts: the risk factor reported for this channel.
      const running = wobble(5, index) > 0.55;
      if (position >= 0.88 && position < 0.92)
        return { raw: 'Перегрев', numeric: null, status: 'alarm', alarm: true };
      return { raw: running ? 'Работа' : 'Остановлен', numeric: null, status: 'normal' };
    },
  },
];

export const telemetryChannels = fixtures.map((item) => item.channelId);

export function telemetryFixture(
  channelId: number,
  dateFrom: number,
  dateTo: number,
  limit: number,
): TelemetryResponseDto | null {
  const fixture = fixtures.find((item) => item.channelId === channelId);
  if (!fixture) return null;
  const count = Math.max(Math.min(limit, 1000), 1);
  const span = Math.max(dateTo - dateFrom, 1);
  const step = span / Math.max(count - 1, 1);
  const telemetry: TelemetryPointDto[] = Array.from({ length: count }, (_, index) => {
    const position = count === 1 ? 1 : index / (count - 1);
    const built = fixture.build(position, index);
    return {
      timestamp: new Date(dateFrom + index * step).toISOString(),
      raw_value: built.raw,
      numeric_value: built.numeric,
      status_code: built.status,
      is_alarm: built.alarm === true,
      is_chatter: built.chatter === true,
    };
  });
  return {
    channel_id: fixture.channelId,
    sensor_name: fixture.sensorName,
    sensor_type: fixture.sensorType,
    value_type: fixture.valueType,
    unit: fixture.unit,
    points_count: telemetry.length,
    telemetry,
  };
}

// Scenario D — a known channel that simply has no stored telemetry for the window.
export function emptyTelemetry(channelId: number): TelemetryResponseDto {
  return {
    channel_id: channelId,
    sensor_name: 'Канал без телеметрии',
    sensor_type: 'Неизвестно',
    value_type: 'numeric',
    unit: null,
    points_count: 0,
    telemetry: [],
  };
}
