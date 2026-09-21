import type { ObjectTopologyDto, TopologySegmentDto } from '../dto/object-topology';
import type { ObjectTopology, TopologySegment } from '../../domain/object/topology';

// Segment risk is a backend aggregate; it is never derived from predictions here.
export function toTopologySegment(dto: TopologySegmentDto): TopologySegment {
  return {
    segmentId: dto.segment_id,
    label: dto.label,
    piketFrom: dto.piket_from,
    piketTo: dto.piket_to,
    riskLevel: dto.risk_level,
    activePredictions: dto.active_predictions,
    criticalPredictions: dto.critical_predictions,
    highPredictions: dto.high_predictions,
    maxFailureProbability: dto.max_failure_probability,
  };
}
export function toObjectTopology(dto: ObjectTopologyDto): ObjectTopology {
  return {
    objectId: dto.object_id,
    objectName: dto.object_name,
    piketMin: dto.piket_min,
    piketMax: dto.piket_max,
    updatedAt: dto.updated_at,
    segments: dto.segments.map(toTopologySegment).sort((a, b) => a.piketFrom - b.piketFrom),
  };
}
