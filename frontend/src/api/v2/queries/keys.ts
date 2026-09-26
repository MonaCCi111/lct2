import type { V2BasisKind, V2ReviewState } from '../dto/types';

export interface V2PageParams {
  limit?: number;
  cursor?: string;
}

export interface V2ObjectListParams extends V2PageParams {
  kind?: string;
  name?: string;
}

export interface V2DraftListParams extends V2PageParams {
  groupId?: string;
  objectId?: number;
  basisKind?: V2BasisKind;
  reviewState?: V2ReviewState;
  from?: string;
  to?: string;
  at?: string;
}

export interface V2EvidenceParams extends V2PageParams {
  at?: string;
}

export const v2MetaKeys = { all: ['v2', 'meta'] as const };
export const v2ObjectKeys = {
  all: ['v2', 'objects'] as const,
  lists: () => [...v2ObjectKeys.all, 'list'] as const,
  list: (params: V2ObjectListParams = {}) => [...v2ObjectKeys.lists(), params] as const,
  details: () => [...v2ObjectKeys.all, 'detail'] as const,
  detail: (id: number) => [...v2ObjectKeys.details(), id] as const,
};
export const v2DraftKeys = {
  all: ['v2', 'drafts'] as const,
  lists: () => [...v2DraftKeys.all, 'list'] as const,
  list: (params: V2DraftListParams = {}) => [...v2DraftKeys.lists(), params] as const,
  details: () => [...v2DraftKeys.all, 'detail'] as const,
  detail: (id: string, at?: string) => [...v2DraftKeys.details(), id, { at }] as const,
  decisions: (id: string) => [...v2DraftKeys.details(), id, 'decisions'] as const,
  evidence: (id: string, params: V2EvidenceParams = {}) =>
    [...v2DraftKeys.detail(id), 'evidence', params] as const,
};
