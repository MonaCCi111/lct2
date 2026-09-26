import { useMutation, useQuery, useQueryClient, type QueryClient } from '@tanstack/react-query';
import {
  toV2Decision,
  toV2DecisionHistory,
  toV2DecisionRequest,
  toV2Draft,
  toV2Evidence,
  toV2Meta,
  toV2Object,
  toV2Page,
  toV2WorkOrder,
  toV2WorkOrderRequest,
} from '../adapters';
import { v2ApiGet, v2ApiSend } from '../client/http';
import type {
  V2DecisionDto,
  V2DraftDto,
  V2EvidenceDto,
  V2MetaDto,
  V2ObjectDto,
  V2PageDto,
  V2WorkOrderDto,
} from '../dto/types';
import type { V2DecisionRequest, V2WorkOrderRequest } from '../domain/types';
import { ApiError } from '../../client/http';
import type { V2DraftListParams, V2EvidenceParams, V2ObjectListParams, V2WorkOrderListParams } from './keys';
import { v2DraftKeys, v2MetaKeys, v2ObjectKeys, v2WorkOrderKeys } from './keys';
import {
  v2DraftDecisionsPath,
  v2DraftEvidencePath,
  v2DraftPath,
  v2DraftsPath,
  v2ObjectPath,
  v2ObjectsPath,
  v2WorkOrderPath,
  v2WorkOrdersPath,
} from './paths';

export const useV2Meta = () =>
  useQuery({
    queryKey: v2MetaKeys.all,
    queryFn: async ({ signal }) => toV2Meta(await v2ApiGet<V2MetaDto>('/meta', signal)),
  });

export const useV2Objects = (params: V2ObjectListParams = {}) =>
  useQuery({
    queryKey: v2ObjectKeys.list(params),
    queryFn: async ({ signal }) =>
      toV2Page(await v2ApiGet<V2PageDto<V2ObjectDto>>(v2ObjectsPath(params), signal), toV2Object),
  });

export const useV2Object = (id: number) =>
  useQuery({
    queryKey: v2ObjectKeys.detail(id),
    queryFn: async ({ signal }) => toV2Object(await v2ApiGet<V2ObjectDto>(v2ObjectPath(id), signal)),
    enabled: Number.isFinite(id),
  });

export const useV2Drafts = (params: V2DraftListParams = {}) =>
  useQuery({
    queryKey: v2DraftKeys.list(params),
    queryFn: async ({ signal }) =>
      toV2Page(await v2ApiGet<V2PageDto<V2DraftDto>>(v2DraftsPath(params), signal), toV2Draft),
  });

export const useV2Draft = (id: string, at?: string) =>
  useQuery({
    queryKey: v2DraftKeys.detail(id, at),
    queryFn: async ({ signal }) => toV2Draft(await v2ApiGet<V2DraftDto>(v2DraftPath(id, at), signal)),
    enabled: id !== '',
  });

export const useV2DraftEvidence = (id: string, params: V2EvidenceParams = {}) =>
  useQuery({
    queryKey: v2DraftKeys.evidence(id, params),
    queryFn: async ({ signal }) =>
      toV2Page(
        await v2ApiGet<V2PageDto<V2EvidenceDto>>(v2DraftEvidencePath(id, params), signal),
        toV2Evidence,
      ),
    enabled: id !== '',
  });

export const useV2DraftDecisions = (id: string) =>
  useQuery({
    queryKey: v2DraftKeys.decisions(id),
    queryFn: async ({ signal }) =>
      toV2DecisionHistory(await v2ApiGet<V2DecisionDto[]>(v2DraftDecisionsPath(id), signal)),
    enabled: id !== '',
  });

export function invalidateV2DecisionQueries(queryClient: QueryClient, draftId: string) {
  void queryClient.invalidateQueries({ queryKey: v2DraftKeys.lists() });
  void queryClient.invalidateQueries({ queryKey: v2DraftKeys.detail(draftId) });
  void queryClient.invalidateQueries({ queryKey: v2DraftKeys.decisions(draftId) });
}

export function useCreateV2DraftDecision() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async ({ draftId, request }: { draftId: string; request: V2DecisionRequest }) =>
      toV2Decision(
        await v2ApiSend<V2DecisionDto>(v2DraftDecisionsPath(draftId), toV2DecisionRequest(request)),
      ),
    onSuccess: (_decision, variables) => {
      invalidateV2DecisionQueries(queryClient, variables.draftId);
    },
    onError: (error, variables) => {
      if (error instanceof ApiError && error.status === 409)
        invalidateV2DecisionQueries(queryClient, variables.draftId);
    },
  });
}

export const useV2WorkOrders = (params: V2WorkOrderListParams = {}) =>
  useQuery({
    queryKey: v2WorkOrderKeys.list(params),
    queryFn: async ({ signal }) =>
      toV2Page(await v2ApiGet<V2PageDto<V2WorkOrderDto>>(v2WorkOrdersPath(params), signal), toV2WorkOrder),
  });

export const useV2WorkOrder = (id: string) =>
  useQuery({
    queryKey: v2WorkOrderKeys.detail(id),
    queryFn: async ({ signal }) => toV2WorkOrder(await v2ApiGet<V2WorkOrderDto>(v2WorkOrderPath(id), signal)),
    enabled: id !== '',
  });

export function invalidateV2WorkOrderQueries(queryClient: QueryClient, draftId: string) {
  void queryClient.invalidateQueries({ queryKey: v2WorkOrderKeys.all });
  void queryClient.invalidateQueries({ queryKey: v2DraftKeys.detail(draftId) });
  void queryClient.invalidateQueries({ queryKey: v2DraftKeys.decisions(draftId) });
}

export function useCreateV2WorkOrder() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (request: V2WorkOrderRequest) =>
      toV2WorkOrder(await v2ApiSend<V2WorkOrderDto>('/work-orders', toV2WorkOrderRequest(request))),
    onSuccess: (workOrder, request) => {
      queryClient.setQueryData(v2WorkOrderKeys.detail(workOrder.workOrderId), workOrder);
      invalidateV2WorkOrderQueries(queryClient, request.draftId);
    },
    onError: (error, request) => {
      if (error instanceof ApiError && error.status === 409)
        invalidateV2WorkOrderQueries(queryClient, request.draftId);
    },
  });
}
