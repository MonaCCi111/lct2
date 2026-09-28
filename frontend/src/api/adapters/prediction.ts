import type { PredictionDto } from '../dto/prediction';
import type { Prediction } from '../../domain/prediction/types';

// Backend is authoritative: probability never determines risk, urgency, or health.
export function toPrediction(dto: PredictionDto): Prediction {
  const supported = dto.prediction_supported;
  return {
    id: dto.prediction_id,
    channelId: dto.channel_id,
    sensorName: dto.sensor_name,
    sensorType: dto.sensor_type,
    subsystem: dto.subsystem,
    tag: dto.tag,
    objectId: dto.object_id,
    objectName: dto.object_name,
    parentObjectId: dto.parent_object_id ?? null,
    piket: dto.piket,
    // Physical location, not an ML output: kept even when prediction support is false.
    piketValue: Number.isFinite(dto.piket_value) ? dto.piket_value : null,
    predictionSupported: supported,
    modelDomain: supported ? dto.model_domain : null,
    modelVersion: dto.model_version,
    failureProbability: supported ? dto.failure_probability : null,
    riskLevel: supported ? dto.risk_level : null,
    maintenanceUrgency: supported ? dto.maintenance_urgency : null,
    leadTimeHours: supported ? dto.lead_time_hours : null,
    healthIndex: supported ? dto.health_index_its : null,
    topRiskFactors: supported ? [...dto.top_risk_factors] : [],
    recommendation: supported ? dto.recommendation : null,
    generatedAt: dto.generated_at,
    reviewStatus: dto.review_status,
    ticketId: dto.ticket_id,
  };
}
