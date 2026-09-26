import type {
  V2DecisionDto,
  V2DecisionRequestDto,
  V2DraftDto,
  V2EvidenceDto,
  V2MetaDto,
  V2ObjectDto,
  V2PageDto,
} from '../dto/types';
import type {
  V2Decision,
  V2DecisionRequest,
  V2Draft,
  V2Evidence,
  V2Meta,
  V2Object,
  V2Page,
} from '../domain/types';

export const toV2Meta = (dto: V2MetaDto): V2Meta => ({
  contractVersion: dto.contract_version,
  dataVersion: dto.data_version,
  dataCutoff: dto.data_cutoff,
  sourceTimezoneKnown: dto.source_timezone_known,
  realFeedbackAvailable: dto.real_feedback_available,
  liveIngestionAvailable: dto.live_ingestion_available,
});

export const toV2Object = (dto: V2ObjectDto): V2Object => ({
  objectId: dto.object_id,
  objectName: dto.object_name,
  kind: dto.kind,
  parentId: dto.parent_id,
  channelCount: dto.channel_count,
});

export const toV2Decision = (dto: V2DecisionDto): V2Decision => ({
  decisionId: dto.decision_id,
  draftId: dto.draft_id,
  decision: dto.decision,
  reason: dto.reason,
  authorId: dto.author_id,
  decidedAt: dto.decided_at,
  idempotencyKey: dto.idempotency_key,
  supersedesDecisionId: dto.supersedes_decision_id,
  workOrderId: dto.work_order_id,
});

export const toV2DecisionHistory = (dtos: readonly V2DecisionDto[]): V2Decision[] => dtos.map(toV2Decision);

export const toV2DecisionRequest = (request: V2DecisionRequest): V2DecisionRequestDto => ({
  decision: request.decision,
  reason: request.reason,
  idempotency_key: request.idempotencyKey,
});

export const toV2Draft = (dto: V2DraftDto): V2Draft => ({
  schemaVersion: dto.schema_version ?? null,
  draftId: dto.draft_id,
  groupId: dto.group_id,
  objectId: dto.object_id,
  channelId: dto.channel_id,
  basisKind: dto.basis_kind,
  modelVersion: dto.model_version,
  // A model-specific score is copied verbatim. No threshold or percentage conversion belongs here.
  score: dto.score,
  forecastHorizonHours: dto.forecast_horizon_hours ?? null,
  targetKind: dto.target_kind,
  sourceObservationTime: dto.source_obs_time ?? null,
  availableAt: dto.available_at,
  sourceReviewStatus: dto.review_status ?? null,
  reviewState: dto.review_state,
  situationId: dto.situation_id,
  locationKey: dto.location_key ?? null,
  limitations: dto.limitations,
  affectedChannels: dto.affected_channels ?? null,
  channelObservationState: dto.channel_observation_state ?? null,
  faultReports72h: dto.fault_reports_72h ?? null,
  serviceReports72h: dto.service_reports_72h ?? null,
  mixedAlarmTimestamps72h: dto.mixed_alarm_timestamps_72h ?? null,
  lastSourceRef: dto.last_source_ref ?? null,
  itsValue: dto.its_value,
  itsStatus: dto.its_status ?? null,
  calculationVersion: dto.calculation_version ?? null,
  sourceRef: dto.source_ref ?? null,
  featureSnapshot: dto.feature_snapshot ? { ...dto.feature_snapshot } : null,
  decision: dto.decision ? toV2Decision(dto.decision) : null,
});

export const toV2Evidence = (dto: V2EvidenceDto): V2Evidence => ({
  schemaVersion: dto.schema_version ?? null,
  draftId: dto.draft_id ?? null,
  groupId: dto.group_id ?? null,
  situationId: dto.situation_id ?? null,
  objectId: dto.object_id ?? null,
  channelId: dto.channel_id,
  sensorType: dto.sensor_type ?? null,
  evidenceKind: dto.evidence_kind ?? null,
  sourceTime: dto.source_time ?? null,
  eventTime: dto.event_time ?? null,
  availableAt: dto.available_at,
  eventId: dto.event_id ?? null,
  observedValue: dto.observed_value,
  numericValue: dto.numeric_value ?? null,
  numericUnit: dto.numeric_unit ?? null,
  sourceAlarm: dto.source_alarm ?? null,
  recordedAlarm: dto.is_alarm ?? null,
  sourceRef: dto.source_ref,
  channelName: dto.channel_name ?? null,
  piket: dto.piket ?? null,
  dictionaryState: dto.dictionary_state ?? null,
});

export function toV2Page<TDto, TDomain>(
  dto: V2PageDto<TDto>,
  mapItem: (item: TDto) => TDomain,
): V2Page<TDomain> {
  return { items: dto.items.map(mapItem), nextCursor: dto.next_cursor };
}
