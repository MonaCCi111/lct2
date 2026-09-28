import type { RiskLevel } from '../../domain/prediction/types';
export interface ObjectDetailDto {
  object_id: number;
  object_name: string;
  parent_object_id: number | null;
  object_type: string;
  channels_total: number;
  ml_supported_channels: number;
  risk_level: RiskLevel | null;
  active_predictions: number;
  critical_predictions: number;
  high_predictions: number;
  updated_at: string;
}
