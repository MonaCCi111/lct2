import type { RiskLevel } from '../prediction/types';
export interface ObjectStatusSummary {
  objectId: number;
  objectName: string;
  riskLevel: RiskLevel | null;
  activePredictions: number;
  criticalPredictions: number;
  highPredictions: number;
  mlSupportedChannels: number;
  channelsTotal: number;
  updatedAt: string;
}
