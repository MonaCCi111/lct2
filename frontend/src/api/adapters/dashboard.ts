import type { DashboardSummaryDto } from '../dto/dashboard';
import type { DashboardSummary } from '../../domain/dashboard/types';

// Summary is an independent backend aggregate, never reconstructed from list endpoints.
export function toDashboardSummary(dto: DashboardSummaryDto): DashboardSummary {
  return {
    generatedAt: dto.generated_at,
    modelVersion: dto.model_version,
    channels: {
      total: dto.channels.total,
      mlSupported: dto.channels.ml_supported,
      mlUnsupported: dto.channels.ml_unsupported,
      coveragePercent: dto.channels.coverage_percent,
    },
    predictions: {
      active: dto.predictions.active,
      critical: dto.predictions.critical,
      high: dto.predictions.high,
      medium: dto.predictions.medium,
      flash1To6h: dto.predictions.flash_1_6h,
      urgent6To24h: dto.predictions.urgent_6_24h,
      planned24To48h: dto.predictions.planned_24_48h,
    },
    objects: {
      total: dto.objects.total,
      affected: dto.objects.affected,
      critical: dto.objects.critical,
    },
    tickets: {
      draft: dto.tickets.draft,
      approved: dto.tickets.approved,
      completedToday: dto.tickets.completed_today,
    },
  };
}
