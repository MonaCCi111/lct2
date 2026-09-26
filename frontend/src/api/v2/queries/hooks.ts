import { useQuery } from '@tanstack/react-query';
import { toV2Draft, toV2Evidence, toV2Meta, toV2Object, toV2Page } from '../adapters';
import { v2ApiGet } from '../client/http';
import type { V2DraftDto, V2EvidenceDto, V2MetaDto, V2ObjectDto, V2PageDto } from '../dto/types';
import type { V2DraftListParams, V2EvidenceParams, V2ObjectListParams } from './keys';
import { v2DraftKeys, v2MetaKeys, v2ObjectKeys } from './keys';
import { v2DraftEvidencePath, v2DraftPath, v2DraftsPath, v2ObjectPath, v2ObjectsPath } from './paths';

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
