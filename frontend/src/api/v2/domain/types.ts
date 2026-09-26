import type { V2BasisKind, V2DecisionValue, V2ReviewState } from '../dto/types';

export interface V2Page<T> {
  items: T[];
  nextCursor: string | null;
}

export interface V2Meta {
  contractVersion: string;
  dataVersion: string;
  dataCutoff: string;
  sourceTimezoneKnown: boolean;
  realFeedbackAvailable: boolean;
  liveIngestionAvailable: boolean;
}

export interface V2Object {
  objectId: number;
  objectName: string;
  kind: string;
  parentId: number | null;
  channelCount: number;
}

export interface V2Decision {
  decisionId: string;
  draftId: string;
  decision: V2DecisionValue;
  reason: string;
  authorId: string;
  decidedAt: string;
  idempotencyKey: string;
  supersedesDecisionId: string | null;
  workOrderId: string | null;
}

export interface V2DecisionRequest {
  decision: V2DecisionValue;
  reason: string;
  idempotencyKey: string;
}

/**
 * A dispatcher draft is its own domain. In particular it has no legacy risk, urgency,
 * failure-probability or health-index interpretation.
 */
export interface V2Draft {
  schemaVersion: string | null;
  draftId: string;
  groupId: string;
  objectId: number;
  channelId: number;
  basisKind: V2BasisKind;
  modelVersion: string | null;
  score: number | null;
  forecastHorizonHours: number | null;
  targetKind: string;
  sourceObservationTime: string | null;
  availableAt: string;
  sourceReviewStatus: string | null;
  reviewState: V2ReviewState;
  situationId: string | null;
  locationKey: string | null;
  limitations: string;
  affectedChannels: number | null;
  channelObservationState: string | null;
  faultReports72h: number | null;
  serviceReports72h: number | null;
  mixedAlarmTimestamps72h: number | null;
  lastSourceRef: string | null;
  itsValue: number | null;
  itsStatus: string | null;
  calculationVersion: string | null;
  sourceRef: string | null;
  featureSnapshot: Readonly<Record<string, string | number | boolean | null>> | null;
  decision: V2Decision | null;
}

export interface V2Evidence {
  schemaVersion: string | null;
  draftId: string | null;
  groupId: string | null;
  situationId: string | null;
  objectId: number | null;
  channelId: number;
  sensorType: string | null;
  evidenceKind: string | null;
  sourceTime: string | null;
  eventTime: string | null;
  availableAt: string;
  eventId: number | null;
  observedValue: string;
  numericValue: number | null;
  numericUnit: string | null;
  sourceAlarm: boolean | null;
  recordedAlarm: boolean | null;
  sourceRef: string;
  channelName: string | null;
  piket: string | null;
  dictionaryState: string | null;
}
