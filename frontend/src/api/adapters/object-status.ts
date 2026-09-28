import type { ObjectStatusSummaryDto } from '../dto/object-status';
import type { ObjectStatusSummary } from '../../domain/object/status';
import type { RiskLevel } from '../../domain/prediction/types';
const priority: Record<RiskLevel, number> = { critical: 0, high: 1, medium: 2, low: 3 };
export function toObjectStatusSummary(dto: ObjectStatusSummaryDto): ObjectStatusSummary {
  return {
    objectId: dto.object_id,
    objectName: dto.object_name,
    riskLevel: dto.risk_level,
    activePredictions: dto.active_predictions,
    criticalPredictions: dto.critical_predictions,
    highPredictions: dto.high_predictions,
    mlSupportedChannels: dto.ml_supported_channels,
    channelsTotal: dto.channels_total,
    updatedAt: dto.updated_at,
  };
}
export function toObjectStatusList(dtos: readonly ObjectStatusSummaryDto[]): ObjectStatusSummary[] {
  return dtos
    .map(toObjectStatusSummary)
    .filter((item) => item.activePredictions > 0)
    .sort(
      (a, b) =>
        (a.riskLevel ? priority[a.riskLevel] : 3) - (b.riskLevel ? priority[b.riskLevel] : 3) ||
        b.criticalPredictions - a.criticalPredictions ||
        a.objectId - b.objectId,
    );
}
