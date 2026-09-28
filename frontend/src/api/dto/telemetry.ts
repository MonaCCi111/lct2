export type TelemetryValueType = 'numeric' | 'state';
export type TelemetryStatusCode = 'normal' | 'failure' | 'alarm' | 'unknown';

export interface TelemetryPointDto {
  timestamp: string;
  raw_value: string;
  numeric_value: number | null;
  status_code: TelemetryStatusCode;
  is_alarm: boolean;
  is_chatter: boolean;
}

export interface TelemetryResponseDto {
  channel_id: number;
  sensor_name: string;
  sensor_type: string;
  value_type: TelemetryValueType;
  unit: string | null;
  points_count: number;
  telemetry: TelemetryPointDto[];
}
