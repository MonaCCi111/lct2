import { http, HttpResponse } from 'msw';
import { v2ApiConfig } from '../client/config';
import type { V2DecisionRequestDto } from '../dto/types';
import {
  v2DraftsFixture,
  v2ForecastDraftFixture,
  v2ForecastEvidencePageFixture,
  v2MetaFixture,
  v2ObjectsFixture,
  v2ObjectFixture,
  v2ObservedDraftFixture,
} from './fixtures';
import { applyV2DecisionState, createV2Decision, listV2Decisions, V2DecisionMockError } from './decisions';

const endpoint = (path: string) => `${v2ApiConfig.baseUrl}${path}`;
const missing = () => HttpResponse.json({ message: 'Ресурс API v2 не найден.' }, { status: 404 });

export const v2Handlers = [
  http.get(endpoint('/meta'), () => HttpResponse.json(v2MetaFixture)),
  http.get(endpoint('/objects'), () => HttpResponse.json(v2ObjectsFixture)),
  http.get(endpoint('/objects/:objectId'), ({ params }) =>
    String(params.objectId) === String(v2ObjectFixture.object_id)
      ? HttpResponse.json(v2ObjectFixture)
      : missing(),
  ),
  http.get(endpoint('/drafts'), ({ request }) => {
    const query = new URL(request.url).searchParams;
    const basis = query.get('basis_kind');
    const reviewState = query.get('review_state');
    const objectId = query.get('object_id');
    const offset = Math.max(0, Number(query.get('cursor') ?? 0) || 0);
    const limit = Math.max(1, Number(query.get('limit') ?? 50) || 50);
    const matching = v2DraftsFixture.items
      .map(applyV2DecisionState)
      .filter(
        (item) =>
          (!basis || item.basis_kind === basis) &&
          (!reviewState || item.review_state === reviewState) &&
          (!objectId || item.object_id === Number(objectId)),
      );
    const items = matching.slice(offset, offset + limit);
    const nextCursor = offset + limit < matching.length ? String(offset + limit) : null;
    return HttpResponse.json({ items, next_cursor: nextCursor });
  }),
  http.get(endpoint('/drafts/:draftId'), ({ params }) => {
    const id = String(params.draftId);
    const draft = v2DraftsFixture.items.find((item) => item.draft_id === id);
    return draft ? HttpResponse.json(applyV2DecisionState(draft)) : missing();
  }),
  http.get(endpoint('/drafts/:draftId/evidence'), ({ params }) => {
    const id = String(params.draftId);
    if (id === v2ForecastDraftFixture.draft_id) return HttpResponse.json(v2ForecastEvidencePageFixture);
    if (id === v2ObservedDraftFixture.draft_id) return HttpResponse.json({ items: [], next_cursor: null });
    return missing();
  }),
  http.get(endpoint('/drafts/:draftId/decisions'), ({ params }) => {
    const id = String(params.draftId);
    return v2DraftsFixture.items.some((item) => item.draft_id === id)
      ? HttpResponse.json(listV2Decisions(id))
      : missing();
  }),
  http.post(endpoint('/drafts/:draftId/decisions'), async ({ params, request }) => {
    const id = String(params.draftId);
    if (!v2DraftsFixture.items.some((item) => item.draft_id === id)) return missing();
    try {
      const body = (await request.json()) as V2DecisionRequestDto;
      return HttpResponse.json(createV2Decision(id, body, new Date().toISOString()), { status: 201 });
    } catch (error) {
      if (error instanceof V2DecisionMockError)
        return HttpResponse.json(
          { code: 'decision_error', message: error.message, details: null },
          { status: error.status },
        );
      return HttpResponse.json(
        { code: 'invalid_request', message: 'Некорректный запрос решения.', details: null },
        { status: 400 },
      );
    }
  }),
];
