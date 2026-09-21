export type RiskLevel = 'low' | 'medium' | 'high' | 'critical';
export type MaintenanceUrgency = 'NORMAL' | 'PLANNED_24_48H' | 'URGENT_6_24H' | 'FLASH_1_6H';
export type ModelDomain = 'POWER_PHASE' | 'ANALOG_TEMP' | 'ANALOG_GAS' | 'FIRE_SAFETY' | 'HYDRO_MECHANICS';
export type ReviewStatus = 'pending_review' | 'acknowledged' | 'rejected' | 'ticket_created';

export interface Prediction {
  id: string;
  channelId: number;
  sensorName: string;
  sensorType: string;
  subsystem: string;
  tag: string;
  objectId: number;
  objectName: string;
  parentObjectId: number | null;
  piket: string | null;
  piketValue: number | null;
  predictionSupported: boolean;
  modelDomain: ModelDomain | null;
  modelVersion: string;
  failureProbability: number | null;
  riskLevel: RiskLevel | null;
  maintenanceUrgency: MaintenanceUrgency | null;
  leadTimeHours: number | null;
  healthIndex: number | null;
  topRiskFactors: readonly string[];
  recommendation: string | null;
  generatedAt: string;
  reviewStatus: ReviewStatus;
  ticketId: string | null;
}
