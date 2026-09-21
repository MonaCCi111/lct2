import type { RiskLevel } from '../../domain/prediction/types';
export interface TopologySegmentDto {
  segment_id: string;
  label: string;
  piket_from: number;
  piket_to: number;
  risk_level: RiskLevel | null;
  active_predictions: number;
  critical_predictions: number;
  high_predictions: number;
  max_failure_probability: number | null;
}
export interface ObjectTopologyDto {
  object_id: number;
  object_name: string;
  piket_min: number | null;
  piket_max: number | null;
  updated_at: string;
  segments: TopologySegmentDto[];
}
