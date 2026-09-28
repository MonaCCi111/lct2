import type { RiskLevel } from '../../domain/prediction/types';
export interface ObjectStatusSummaryDto {
  object_id: number;
  object_name: string;
  risk_level: RiskLevel | null;
  active_predictions: number;
  critical_predictions: number;
  high_predictions: number;
  ml_supported_channels: number;
  channels_total: number;
  updated_at: string;
}
