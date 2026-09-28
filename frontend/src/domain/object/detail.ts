import type { RiskLevel } from '../prediction/types';
export interface ObjectDetail {
  objectId: number;
  objectName: string;
  parentObjectId: number | null;
  objectType: string;
  channelsTotal: number;
  mlSupportedChannels: number;
  riskLevel: RiskLevel | null;
  activePredictions: number;
  criticalPredictions: number;
  highPredictions: number;
  updatedAt: string;
}
