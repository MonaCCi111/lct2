# Dolos — API v2 Frontend Foundation

`/api/v1` and `/api/v2` intentionally coexist.

- `/api/v1` is the existing demo operational layer used by the current routes and UI.
- `/api/v2` is the historical dispatcher/review contract (`dispatcher_api_v1`). Its read-only
  foundation lives in `frontend/src/api/v2`. No existing route consumes it yet.

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

Decisions, decision corrections, work-order mutations, replay UI and v2 analytics remain outside
this foundation. The handlers added for Task 10B.1 expose only Meta, Objects, Drafts and Draft
Evidence reads.
