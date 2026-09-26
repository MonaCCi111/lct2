import type {
  V2DecisionDto,
  V2DraftDto,
  V2EvidenceDto,
  V2MetaDto,
  V2ObjectDto,
  V2PageDto,
  V2WorkOrderDto,
} from '../dto/types';

export const v2MetaFixture: V2MetaDto = {
  contract_version: 'dispatcher_api_v1',
  data_version: 'ml_handoff_v1',
  data_cutoff: '2026-06-30T23:59:59',
  source_timezone_known: false,
  real_feedback_available: false,
  live_ingestion_available: false,
};

export const v2ObjectFixture: V2ObjectDto = {
  object_id: 5333,
  object_name: 'ДУ объект Кси',
  kind: 'controlHouse',
  parent_id: 5327,
  channel_count: 215,
};

export const v2ObjectsFixture: V2PageDto<V2ObjectDto> = {
  items: [v2ObjectFixture],
  next_cursor: null,
};

export const v2ObservedDraftFixture: V2DraftDto = {
  schema_version: 'ml_handoff_v1',
  draft_id: 'observed:OBSERVED_PUMP_FLOODED_STATUS:5333:20250202T030222',
  group_id: 'review_v2:5333:20250202T030222',
  object_id: 5333,
  channel_id: 229590,
  basis_kind: 'observed_status',
  model_version: null,
  score: null,
  forecast_horizon_hours: null,
  target_kind: 'OBSERVED_PUMP_FLOODED_STATUS',
  source_obs_time: '2025-02-02T03:02:22',
  available_at: '2025-02-02T04:03:57',
  review_status: 'draft',
  situation_id: 'OBSERVED_PUMP_FLOODED_STATUS:5333:20250202T030222',
  location_key: null,
  limitations: 'observed_text_status_not_confirmed_physical_incident;maintenance_context_unavailable',
  affected_channels: 2,
  channel_observation_state: 'ambiguous_simultaneous_statuses',
  fault_reports_72h: 1,
  service_reports_72h: 4,
  mixed_alarm_timestamps_72h: 1,
  last_source_ref: 'source_v2/journal_2025.parquet:channel_id+event_time+event_id+sensor_value+is_alarm',
  its_value: null,
  its_status: 'unavailable_no_confirmed_health_target',
  calculation_version: 'dispatch_review_v2',
  source_ref: 'dispatch_review_v2/diagnostic_2025_2026/members.parquet:draft_id',
  review_state: 'pending',
  decision: null,
};

export const v2ForecastDraftFixture: V2DraftDto = {
  schema_version: 'ml_handoff_v1',
  draft_id: 'power_phase_scada_v2:178259:20251210T090000',
  group_id: 'review_v2:5003:20251210T090000',
  object_id: 5003,
  channel_id: 178259,
  basis_kind: 'forecast',
  model_version: 'power_phase_scada_v2',
  score: 0.9848484848484849,
  forecast_horizon_hours: 48,
  target_kind: 'SCADA_STATUS_EPISODE',
  source_obs_time: '2025-12-10T09:00:00',
  available_at: '2025-12-10T09:00:00',
  review_status: 'draft',
  situation_id: null,
  location_key: null,
  limitations: 'model_score_is_not_physical_failure_probability;event_time_only;delivery_time_unavailable',
  affected_channels: null,
  channel_observation_state: 'recent_observation',
  fault_reports_72h: 0,
  service_reports_72h: 1,
  mixed_alarm_timestamps_72h: 0,
  last_source_ref: 'source_v2/journal_2025.parquet:channel_id+event_time+event_id+sensor_value+is_alarm',
  its_value: null,
  its_status: 'unavailable_no_confirmed_health_target',
  calculation_version: 'dispatch_review_v2',
  source_ref: 'dispatch_review_v2/diagnostic_2025_2026/members.parquet:draft_id',
  feature_snapshot: {
    channel_id: 178259,
    sensor_type: 'Состояние фазы',
    obs_time: '2025-12-10 09:00:00',
    event_count_1h: 1,
    event_count_24h: 1,
    status_changes_1h: 1,
    status_changes_24h: 1,
    status_changes_72h: 3,
    rapid_status_changes_24h: 0,
    fast_change_fraction_24h: 0,
    alarm_events_24h: 0,
    alarm_event_fraction_24h: 0,
    undefined_events_24h: 0,
    undefined_event_fraction_24h: 0,
    observed_hours_72h: 2,
  },
  review_state: 'pending',
  decision: null,
};

export const v2DraftsFixture: V2PageDto<V2DraftDto> = {
  items: [v2ForecastDraftFixture, v2ObservedDraftFixture],
  next_cursor: null,
};

export const v2DecisionFixture: V2DecisionDto = {
  decision_id: 'review-decision-fixture',
  draft_id: v2ForecastDraftFixture.draft_id,
  decision: 'approved',
  reason: 'Сигнал и контекст проверены диспетчером.',
  author_id: 'dispatcher.fixture',
  decided_at: '2026-09-26T12:30:00Z',
  idempotency_key: 'fixture-idempotency-key',
  supersedes_decision_id: null,
  work_order_id: null,
};

export const v2WorkOrderFixture: V2WorkOrderDto = {
  work_order_id: 'WO-V2-0001',
  draft_id: v2ForecastDraftFixture.draft_id,
  object_id: v2ForecastDraftFixture.object_id,
  status: 'created',
  work_type: 'Диагностика цепи питания',
  description: 'Проверить цепь питания и зарегистрировать результат осмотра.',
  created_at: '2026-09-26T13:00:00Z',
  created_by: 'dispatcher.fixture',
  external_work_order_id: null,
  assignee_id: null,
  due_at: null,
};

export const v2ForecastEvidenceFixture: V2EvidenceDto = {
  draft_id: v2ForecastDraftFixture.draft_id,
  group_id: v2ForecastDraftFixture.group_id,
  channel_id: 178259,
  event_time: '2025-12-10T08:16:53',
  available_at: '2025-12-10T08:16:53',
  event_id: 3262044394,
  observed_value: 'Есть питание',
  is_alarm: false,
  source_ref: 'source_v2/journal_2025.parquet:channel_id+event_time+event_id+sensor_value+is_alarm',
};

export const v2ForecastEvidencePageFixture: V2PageDto<V2EvidenceDto> = {
  items: [v2ForecastEvidenceFixture],
  next_cursor: null,
};
