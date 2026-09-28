import type { TelemetryStatusCode, TelemetryValueType } from '../../api/dto/telemetry';
export type { TelemetryStatusCode, TelemetryValueType };

export interface TelemetryPoint {
  timestamp: string;
  rawValue: string;
  numericValue: number | null;
  statusCode: TelemetryStatusCode;
  isAlarm: boolean;
  isChatter: boolean;
}

export interface TelemetrySeries {
  channelId: number;
  sensorName: string;
  sensorType: string;
  valueType: TelemetryValueType;
  unit: string | null;
  pointsCount: number;
  points: readonly TelemetryPoint[];
}

export type TelemetryRange = '6h' | '24h' | '48h';
