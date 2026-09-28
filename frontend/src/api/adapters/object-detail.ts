import type { ObjectDetailDto } from '../dto/object-detail';
import type { ObjectDetail } from '../../domain/object/detail';

// Backend owns risk level and prediction counts; the adapter only renames fields.
export function toObjectDetail(dto: ObjectDetailDto): ObjectDetail {
  return {
    objectId: dto.object_id,
    objectName: dto.object_name,
    parentObjectId: dto.parent_object_id,
    objectType: dto.object_type,
    channelsTotal: dto.channels_total,
    mlSupportedChannels: dto.ml_supported_channels,
    riskLevel: dto.risk_level,
    activePredictions: dto.active_predictions,
    criticalPredictions: dto.critical_predictions,
    highPredictions: dto.high_predictions,
    updatedAt: dto.updated_at,
  };
}
