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
    const basis = new URL(request.url).searchParams.get('basis_kind');
    const items = basis
      ? v2DraftsFixture.items.filter((item) => item.basis_kind === basis)
      : v2DraftsFixture.items;
    return HttpResponse.json({ items, next_cursor: null });
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
