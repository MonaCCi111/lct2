import type { RiskLevel } from '../../domain/prediction/types';
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
export const ticketKeys = { all: ['tickets'] as const };
export const systemKeys = { all: ['system'] as const };
export const dashboardKeys = {
  all: ['dashboard'] as const,
  summary: () => [...dashboardKeys.all, 'summary'] as const,
};
