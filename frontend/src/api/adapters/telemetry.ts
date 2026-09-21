import type { TelemetryPointDto, TelemetryResponseDto } from '../dto/telemetry';
import type { TelemetryPoint, TelemetrySeries } from '../../domain/telemetry/types';

// Transport values only: no risk, urgency or forecast is derived from telemetry.
export function toTelemetryPoint(dto: TelemetryPointDto): TelemetryPoint {
  return {
    timestamp: dto.timestamp,
    rawValue: dto.raw_value,
    numericValue: Number.isFinite(dto.numeric_value) ? dto.numeric_value : null,
    statusCode: dto.status_code,
    isAlarm: dto.is_alarm,
    isChatter: dto.is_chatter,
  };
}

export function toTelemetrySeries(dto: TelemetryResponseDto): TelemetrySeries {
  const points = dto.telemetry
    .map(toTelemetryPoint)
    .sort((a, b) => Date.parse(a.timestamp) - Date.parse(b.timestamp));
  return {
    channelId: dto.channel_id,
    sensorName: dto.sensor_name,
    sensorType: dto.sensor_type,
    valueType: dto.value_type,
    unit: dto.unit,
    // Backend reports how many points it produced; the array stays the source for rendering.
    pointsCount: dto.points_count,
    points,
  };
}
