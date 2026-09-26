import { http, HttpResponse } from 'msw';
import { v2ApiConfig } from '../client/config';
import {
  v2DraftsFixture,
  v2ForecastDraftFixture,
  v2ForecastEvidencePageFixture,
  v2MetaFixture,
  v2ObjectsFixture,
  v2ObjectFixture,
  v2ObservedDraftFixture,
} from './fixtures';

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
    const matching = v2DraftsFixture.items.filter(
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
    return draft ? HttpResponse.json(draft) : missing();
  }),
  http.get(endpoint('/drafts/:draftId/evidence'), ({ params }) => {
    const id = String(params.draftId);
    if (id === v2ForecastDraftFixture.draft_id) return HttpResponse.json(v2ForecastEvidencePageFixture);
    if (id === v2ObservedDraftFixture.draft_id) return HttpResponse.json({ items: [], next_cursor: null });
    return missing();
  }),
];
