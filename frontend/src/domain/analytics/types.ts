import type { MaintenanceUrgency, ModelDomain, RiskLevel } from '../prediction/types';
import type { TicketStatus } from '../ticket/types';
export type AnalyticsRange = '24h' | '7d' | '30d';
export interface AnalyticsRiskTimelinePoint {
  timestamp: string;
  critical: number;
  high: number;
  medium: number;
}
export interface AnalyticsUrgencyDistribution {
  urgency: MaintenanceUrgency;
  count: number;
}
export interface AnalyticsObjectRisk {
  objectId: number;
  objectName: string;
  riskLevel: RiskLevel;
  activePredictions: number;
  criticalPredictions: number;
  highPredictions: number;
  openTickets: number;
}
export interface AnalyticsTicketStatus {
  status: TicketStatus;
  count: number;
}
export interface AnalyticsMlDomainCoverage {
  domain: ModelDomain;
  channelsTotal: number;
  channelsSupported: number;
  coveragePercent: number;
}
export interface AnalyticsSummary {
  generatedAt: string;
  range: AnalyticsRange;
  totals: {
    activePredictions: number;
    criticalPredictions: number;
    highPredictions: number;
    openTickets: number;
    completedTickets: number;
    mlCoveragePercent: number;
  };
  riskTimeline: AnalyticsRiskTimelinePoint[];
  urgencyDistribution: AnalyticsUrgencyDistribution[];
  topObjects: AnalyticsObjectRisk[];
  ticketStatusDistribution: AnalyticsTicketStatus[];
  mlDomainCoverage: AnalyticsMlDomainCoverage[];
}
