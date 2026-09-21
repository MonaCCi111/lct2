import type { MaintenanceUrgency, ModelDomain, RiskLevel } from '../../domain/prediction/types';
import type { TicketStatus } from '../../domain/ticket/types';
import type { AnalyticsRange } from '../../domain/analytics/types';
export type { AnalyticsRange } from '../../domain/analytics/types';
export interface AnalyticsRiskTimelinePointDto {
  timestamp: string;
  critical: number;
  high: number;
  medium: number;
}
export interface AnalyticsUrgencyDistributionDto {
  urgency: MaintenanceUrgency;
  count: number;
}
export interface AnalyticsObjectRiskDto {
  object_id: number;
  object_name: string;
  risk_level: RiskLevel;
  active_predictions: number;
  critical_predictions: number;
  high_predictions: number;
  open_tickets: number;
}
export interface AnalyticsTicketStatusDto {
  status: TicketStatus;
  count: number;
}
export interface AnalyticsMlDomainCoverageDto {
  domain: ModelDomain;
  channels_total: number;
  channels_supported: number;
  coverage_percent: number;
}
export interface AnalyticsSummaryDto {
  generated_at: string;
  range: AnalyticsRange;
  totals: {
    active_predictions: number;
    critical_predictions: number;
    high_predictions: number;
    open_tickets: number;
    completed_tickets: number;
    ml_coverage_percent: number;
  };
  risk_timeline: AnalyticsRiskTimelinePointDto[];
  urgency_distribution: AnalyticsUrgencyDistributionDto[];
  top_objects: AnalyticsObjectRiskDto[];
  ticket_status_distribution: AnalyticsTicketStatusDto[];
  ml_domain_coverage: AnalyticsMlDomainCoverageDto[];
}
