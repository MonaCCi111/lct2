export type V2BasisKind = 'forecast' | 'observed_status';
export type V2ReviewState = 'pending' | 'approved' | 'rejected';
export type V2DecisionValue = 'approved' | 'rejected';

export interface V2PageDto<T> {
  items: T[];
  next_cursor: string | null;
}

export interface V2MetaDto {
  contract_version: string;
  data_version: string;
  data_cutoff: string;
  source_timezone_known: boolean;
  real_feedback_available: boolean;
  live_ingestion_available: boolean;
}

export interface V2ObjectDto {
  object_id: number;
  object_name: string;
  kind: string;
  parent_id: number | null;
  channel_count: number;
}

/** Persisted decision event, used by the current draft snapshot and append-only history. */
export interface V2DecisionDto {
  decision_id: string;
  draft_id: string;
  decision: V2DecisionValue;
  reason: string;
  author_id: string;
  decided_at: string;
  idempotency_key: string;
  supersedes_decision_id: string | null;
  work_order_id: string | null;
}

export interface V2DecisionRequestDto {
  decision: V2DecisionValue;
  reason: string;
  idempotency_key: string;
}

export interface V2WorkOrderRequestDto {
  draft_id: string;
  work_type: string;
  description: string;
  idempotency_key: string;
  assignee_id?: string | null;
  due_at?: string | null;
}

export interface V2WorkOrderDto {
  work_order_id: string;
  draft_id: string;
  object_id: number;
  status: string;
  work_type: string;
  description: string;
  created_at: string;
  created_by: string;
  external_work_order_id: string | null;
  assignee_id: string | null;
  due_at: string | null;
}

export interface V2DraftDto {
  schema_version?: string;
  draft_id: string;
  group_id: string;
  object_id: number;
  channel_id: number;
  basis_kind: V2BasisKind;
  model_version: string | null;
  score: number | null;
  /**
   * Present in fixtures_v1.json and required by the integration guide, but omitted from the
   * api_contract_v1.json Draft schema. Keep optional until the upstream schema is corrected.
   */
  forecast_horizon_hours?: number | null;
  target_kind: string;
  source_obs_time?: string | null;
  available_at: string;
  review_status?: string;
  review_state: V2ReviewState;
  situation_id: string | null;
  location_key?: string | null;
  limitations: string;
  affected_channels?: number | null;
  channel_observation_state?: string | null;
  fault_reports_72h?: number | null;
  service_reports_72h?: number | null;
  mixed_alarm_timestamps_72h?: number | null;
  last_source_ref?: string | null;
  its_value: number | null;
  its_status?: string | null;
  calculation_version?: string | null;
  source_ref?: string | null;
  feature_snapshot?: Record<string, string | number | boolean | null> | null;
  decision: V2DecisionDto | null;
}

export interface V2EvidenceDto {
  schema_version?: string;
  draft_id?: string | null;
  group_id?: string | null;
  situation_id?: string | null;
  object_id?: number | null;
  channel_id: number;
  sensor_type?: string | null;
  evidence_kind?: string | null;
  source_time?: string | null;
  event_time?: string | null;
  available_at: string;
  event_id?: number | null;
  observed_value: string;
  numeric_value?: number | null;
  numeric_unit?: string | null;
  source_alarm?: boolean | null;
  /** Forecast evidence currently uses is_alarm while the generic Evidence schema says source_alarm. */
  is_alarm?: boolean | null;
  source_ref: string;
  channel_name?: string | null;
  piket?: string | null;
  dictionary_state?: string | null;
}
