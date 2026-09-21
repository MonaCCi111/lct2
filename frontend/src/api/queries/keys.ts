import type { RiskLevel } from '../../domain/prediction/types';
import type { TelemetryRange } from '../../domain/telemetry/types';
import type { TicketStatus } from '../../domain/ticket/types';
export interface PredictionFilters {
  objectId?: number;
  riskLevel?: RiskLevel;
  view?: 'operational';
}
export const predictionKeys = {
  all: ['predictions'] as const,
  list: (filters: PredictionFilters = {}) => [...predictionKeys.all, 'list', filters] as const,
  detail: (id: string) => [...predictionKeys.all, 'detail', id] as const,
};
export const objectKeys = {
  all: ['objects'] as const,
  list: () => [...objectKeys.all, 'list'] as const,
  statusSummary: () => [...objectKeys.all, 'status-summary'] as const,
  detail: (id: number) => [...objectKeys.all, 'detail', id] as const,
  topology: (id: number) => [...objectKeys.all, 'topology', id] as const,
};
export interface TelemetryParams {
  range: TelemetryRange;
}
// The key holds the semantic range; absolute date_from/date_to are built at fetch time.
export const telemetryKeys = {
  all: ['telemetry'] as const,
  sensor: (channelId: number, params: TelemetryParams) =>
    [...telemetryKeys.all, 'sensor', channelId, params] as const,
};
export interface TicketFilters {
  status?: TicketStatus;
  search?: string;
  predictionId?: string;
  objectId?: number;
}
export const ticketKeys = {
  all: ['tickets'] as const,
  list: (filters: TicketFilters = {}) => [...ticketKeys.all, 'list', filters] as const,
  detail: (id: string) => [...ticketKeys.all, 'detail', id] as const,
};
export const systemKeys = { all: ['system'] as const };
export const dashboardKeys = {
  all: ['dashboard'] as const,
  summary: () => [...dashboardKeys.all, 'summary'] as const,
};
