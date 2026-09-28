import type { AnalyticsSummaryDto } from '../dto/analytics';
import type { AnalyticsSummary } from '../../domain/analytics/types';
export function toAnalyticsSummary(dto: AnalyticsSummaryDto): AnalyticsSummary {
  return {
    generatedAt: dto.generated_at,
    range: dto.range,
    totals: {
      activePredictions: dto.totals.active_predictions,
      criticalPredictions: dto.totals.critical_predictions,
      highPredictions: dto.totals.high_predictions,
      openTickets: dto.totals.open_tickets,
      completedTickets: dto.totals.completed_tickets,
      mlCoveragePercent: dto.totals.ml_coverage_percent,
    },
    riskTimeline: dto.risk_timeline.map((point) => ({ ...point })),
    urgencyDistribution: dto.urgency_distribution.map((item) => ({ ...item })),
    topObjects: dto.top_objects.map((item) => ({
      objectId: item.object_id,
      objectName: item.object_name,
      riskLevel: item.risk_level,
      activePredictions: item.active_predictions,
      criticalPredictions: item.critical_predictions,
      highPredictions: item.high_predictions,
      openTickets: item.open_tickets,
    })),
    ticketStatusDistribution: dto.ticket_status_distribution.map((item) => ({ ...item })),
    mlDomainCoverage: dto.ml_domain_coverage.map((item) => ({
      domain: item.domain,
      channelsTotal: item.channels_total,
      channelsSupported: item.channels_supported,
      coveragePercent: item.coverage_percent,
    })),
  };
}
