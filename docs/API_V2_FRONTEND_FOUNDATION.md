# Dolos — API v2 Frontend Foundation

`/api/v1` and `/api/v2` intentionally coexist.

- `/api/v1` is the existing demo operational layer used by the current routes and UI.
- `/api/v2` is the historical dispatcher/review contract (`dispatcher_api_v1`). Its isolated
  transport, DTO, adapter and query layer lives in `frontend/src/api/v2`. The `/review` routes
  consume this layer without adapting drafts into the legacy Prediction domain.

The v2 client has a separate `VITE_API_V2_BASE_URL`, DTOs, domain models, adapters, query keys,
hooks and MSW handlers. It must not adapt a v2 Draft into the legacy Prediction domain.

## Semantic boundaries

`score` is a model-specific value in the 0..1 range. It is not physical failure probability,
universal risk, maintenance urgency or ITS. Frontend code preserves it verbatim and may label it
only as a model score. Observed drafts have a null score.

Historical source timestamps have no known timezone. `source_obs_time`, source event time and
historical `available_at` values are rendered literally. They must not pass through `Date`, the
browser timezone or the v1 Moscow formatter. The corresponding labels are “Время источника, зона
неизвестна” and “Доступно в реконструкции”.

Null ITS remains null and means that a physical health target was not confirmed. It must not be
converted to zero or derived from score.

## Known upstream contract gap

The current `fixtures_v1.json` and integration guide contain `forecast_horizon_hours`, including a
48-hour forecast example, but `api_contract_v1.json.schemas.Draft` omits the field. The v2 DTO keeps
it optional and nullable, while a conformance test records its presence in the current fixture. It
must not become required until the upstream schema declares it.

The review detail supports `GET /drafts/{draft_id}/decisions` and
`POST /drafts/{draft_id}/decisions`. A decision requires `decision`, `reason` and one stable
`idempotency_key` per user attempt. Successful decisions invalidate only v2 draft list/detail and
history keys. A 409 triggers the same refresh and is presented as an already-saved decision.
Decision timestamps are timezone-aware server events and use the operational datetime formatter;
historical draft/evidence timestamps remain literal.

The separate v2 work-order flow supports `GET /work-orders`, `GET /work-orders/{work_order_id}`
and `POST /work-orders`. Creation is available only when the latest authoritative Decision is
approved and has no `work_order_id`. The user explicitly supplies the required `work_type` and
`description`; one stable `idempotency_key` belongs to that create attempt. Approval never creates
a work order implicitly. After creation, the Decision relation is refreshed and the resource is
available under `/review/work-orders` and `/review/work-orders/:workOrderId`.

V2 work orders are isolated from legacy `/api/v1/tickets`; neither stores nor query invalidation
cross that boundary. The current contract does not enumerate work-order status values and exposes
no status mutation, so the frontend displays the returned status literally and implements no
lifecycle controls. Decision corrections, assignment workflow, auth, replay UI and v2 analytics
remain outside the current frontend.
