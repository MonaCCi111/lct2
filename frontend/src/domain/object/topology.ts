import type { RiskLevel } from '../prediction/types';
export interface TopologySegment {
  segmentId: string;
  label: string;
  piketFrom: number;
  piketTo: number;
  riskLevel: RiskLevel | null;
  activePredictions: number;
  criticalPredictions: number;
  highPredictions: number;
  maxFailureProbability: number | null;
}
export interface ObjectTopology {
  objectId: number;
  objectName: string;
  piketMin: number | null;
  piketMax: number | null;
  updatedAt: string;
  segments: readonly TopologySegment[];
}
