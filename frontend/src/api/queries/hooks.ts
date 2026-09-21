import { useQuery } from '@tanstack/react-query';
import { apiGet } from '../client/http';
import type { PredictionDto } from '../dto/prediction';
import type { DashboardSummaryDto } from '../dto/dashboard';
import type { ObjectDto, SystemDto, TicketDto } from '../dto/resources';
import { toPrediction } from '../adapters/prediction';
import { toDashboardSummary } from '../adapters/dashboard';
import type { ObjectStatusSummaryDto } from '../dto/object-status';
import type { ObjectDetailDto } from '../dto/object-detail';
import type { ObjectTopologyDto } from '../dto/object-topology';
import { toObjectStatusList } from '../adapters/object-status';
import { toObjectDetail } from '../adapters/object-detail';
import { toObjectTopology } from '../adapters/object-topology';
import type { TelemetryResponseDto } from '../dto/telemetry';
import type { TelemetryRange } from '../../domain/telemetry/types';
import { toTelemetrySeries } from '../adapters/telemetry';
import { toOperationalQueue } from '../adapters/operational-queue';
import { toObject, toTicket } from '../adapters/resources';
import {
  dashboardKeys,
  objectKeys,
  predictionKeys,
  systemKeys,
  telemetryKeys,
  ticketKeys,
  type PredictionFilters,
  type TelemetryParams,
} from './keys';

export const useDashboardSummary = () =>
  useQuery({
    queryKey: dashboardKeys.summary(),
    queryFn: async ({ signal }) =>
      toDashboardSummary(await apiGet<DashboardSummaryDto>('/dashboard/summary', signal)),
  });

export function usePredictions(filters: PredictionFilters = {}) {
  const params = new URLSearchParams();
  if (filters.objectId !== undefined) params.set('object_id', String(filters.objectId));
  if (filters.riskLevel) params.set('risk_level', filters.riskLevel);
  if (filters.view) params.set('view', filters.view);
  return useQuery({
    queryKey: predictionKeys.list(filters),
    queryFn: async ({ signal }) => {
      const predictions = (
        await apiGet<PredictionDto[]>(`/predictions${params.size ? `?${params}` : ''}`, signal)
      ).map(toPrediction);
      return filters.view === 'operational' ? toOperationalQueue(predictions) : predictions;
    },
  });
}
export const usePrediction = (id: string) =>
  useQuery({
    queryKey: predictionKeys.detail(id),
    queryFn: async ({ signal }) =>
      toPrediction(await apiGet<PredictionDto>(`/predictions/${encodeURIComponent(id)}`, signal)),
  });
export const useObjects = () =>
  useQuery({
    queryKey: objectKeys.list(),
    queryFn: async ({ signal }) => (await apiGet<ObjectDto[]>('/objects', signal)).map(toObject),
  });
export const useObjectStatusSummary = () =>
  useQuery({
    queryKey: objectKeys.statusSummary(),
    queryFn: async ({ signal }) =>
      toObjectStatusList(await apiGet<ObjectStatusSummaryDto[]>('/objects/status-summary', signal)),
  });
export const useObjectDetail = (id: number) =>
  useQuery({
    queryKey: objectKeys.detail(id),
    queryFn: async ({ signal }) => toObjectDetail(await apiGet<ObjectDetailDto>(`/objects/${id}`, signal)),
    enabled: Number.isFinite(id),
  });
export const useObjectTopology = (id: number) =>
  useQuery({
    queryKey: objectKeys.topology(id),
    queryFn: async ({ signal }) =>
      toObjectTopology(await apiGet<ObjectTopologyDto>(`/objects/${id}/topology`, signal)),
    enabled: Number.isFinite(id),
  });
// Range tokens live in the UI; the query layer converts them into absolute UTC instants.
const rangeHours: Record<TelemetryRange, number> = { '6h': 6, '24h': 24, '48h': 48 };
const rangePoints: Record<TelemetryRange, number> = { '6h': 96, '24h': 144, '48h': 192 };
export const TELEMETRY_MAX_POINTS = 1000;
export function telemetryWindow(range: TelemetryRange, now = Date.now()) {
  const limit = Math.min(rangePoints[range], TELEMETRY_MAX_POINTS);
  return {
    dateFrom: new Date(now - rangeHours[range] * 3_600_000).toISOString(),
    dateTo: new Date(now).toISOString(),
    limit,
  };
}
export function useSensorTelemetry(channelId: number, params: TelemetryParams) {
  return useQuery({
    queryKey: telemetryKeys.sensor(channelId, params),
    queryFn: async ({ signal }) => {
      const { dateFrom, dateTo, limit } = telemetryWindow(params.range);
      const search = new URLSearchParams({
        date_from: dateFrom,
        date_to: dateTo,
        limit: String(limit),
      });
      return toTelemetrySeries(
        await apiGet<TelemetryResponseDto>(`/sensors/${channelId}/telemetry?${search}`, signal),
      );
    },
    enabled: Number.isFinite(channelId),
  });
}
export const useTickets = () =>
  useQuery({
    queryKey: ticketKeys.all,
    queryFn: async ({ signal }) => (await apiGet<TicketDto[]>('/tickets', signal)).map(toTicket),
  });
export const useSystem = () =>
  useQuery({
    queryKey: systemKeys.all,
    queryFn: async ({ signal }) => {
      const dto = await apiGet<SystemDto>('/system', signal);
      return { status: dto.status, updatedAt: dto.updated_at };
    },
    refetchInterval: 60_000,
  });
