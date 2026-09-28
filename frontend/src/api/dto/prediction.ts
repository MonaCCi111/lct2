import type { MaintenanceUrgency, ModelDomain, ReviewStatus, RiskLevel } from '../../domain/prediction/types';

export interface PredictionDto {
  prediction_id: string;
  channel_id: number;
  sensor_name: string;
  sensor_type: string;
  subsystem: string;
  tag: string;
  object_id: number;
  object_name: string;
  parent_object_id?: number | null;
  piket: string | null;
  piket_value: number | null;
  prediction_supported: boolean;
  model_domain: ModelDomain | null;
  model_version: string;
  failure_probability: number | null;
  risk_level: RiskLevel | null;
  maintenance_urgency: MaintenanceUrgency | null;
  lead_time_hours: number | null;
  health_index_its: number | null;
  top_risk_factors: string[];
  recommendation: string | null;
  generated_at: string;
  review_status: ReviewStatus;
  ticket_id: string | null;
}
