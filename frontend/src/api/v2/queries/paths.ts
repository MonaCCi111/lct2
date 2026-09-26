import type { V2DraftListParams, V2EvidenceParams, V2ObjectListParams, V2WorkOrderListParams } from './keys';

function withQuery(path: string, values: Record<string, string | number | undefined>) {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) if (value !== undefined) query.set(key, String(value));
  return `${path}${query.size ? `?${query}` : ''}`;
}

export const v2ObjectsPath = (params: V2ObjectListParams = {}) =>
  withQuery('/objects', {
    kind: params.kind,
    name: params.name,
    limit: params.limit,
    cursor: params.cursor,
  });

export const v2ObjectPath = (id: number) => `/objects/${encodeURIComponent(String(id))}`;

export const v2DraftsPath = (params: V2DraftListParams = {}) =>
  withQuery('/drafts', {
    group_id: params.groupId,
    object_id: params.objectId,
    basis_kind: params.basisKind,
    review_state: params.reviewState,
    from: params.from,
    to: params.to,
    at: params.at,
    limit: params.limit,
    cursor: params.cursor,
  });

export const v2DraftPath = (id: string, at?: string) =>
  withQuery(`/drafts/${encodeURIComponent(id)}`, { at });

export const v2DraftDecisionsPath = (id: string) => `/drafts/${encodeURIComponent(id)}/decisions`;

export const v2DraftEvidencePath = (id: string, params: V2EvidenceParams = {}) =>
  withQuery(`/drafts/${encodeURIComponent(id)}/evidence`, {
    at: params.at,
    limit: params.limit,
    cursor: params.cursor,
  });

export const v2WorkOrdersPath = (params: V2WorkOrderListParams = {}) =>
  withQuery('/work-orders', {
    draft_id: params.draftId,
    object_id: params.objectId,
    status: params.status,
    limit: params.limit,
    cursor: params.cursor,
  });

export const v2WorkOrderPath = (id: string) => `/work-orders/${encodeURIComponent(id)}`;
