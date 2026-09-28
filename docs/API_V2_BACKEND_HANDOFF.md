# Dolos — API v2 Backend Handoff

Audit baseline: frontend branch `frontend-dolos`, commit `25ef1329f05593569e62ef99ac13dde935f66aee`,
contract branch `origin/feature/ml-research`, `integration/frontend_roma/api_contract_v1.json`.

The source contract identifies itself as:

- `contract_version`: `dispatcher_api_v1`
- `base_path`: `/api/v2`
- `data_version`: `ml_handoff_v1`

`/api/v1` and `/api/v2` remain separate. Existing operational screens continue to use v1. The v2
routes are the historical dispatcher review flow under `/review`. A v2 Draft must never be adapted
into the legacy Prediction domain.

## 1. Endpoint coverage matrix

Legend: `IMPLEMENTED` means the layer exists and is exercised; `PARTIAL` means only part of the
contract surface exists; `NOT STARTED` means no frontend implementation; `NOT NEEDED YET` means the
current UI intentionally has no consumer.

|   # | Method | Path                                      | Client      | DTO         | Adapter     | Hook        | MSW         | UI             | Mutation       | Tests       | Overall        |
| --: | ------ | ----------------------------------------- | ----------- | ----------- | ----------- | ----------- | ----------- | -------------- | -------------- | ----------- | -------------- |
|   1 | GET    | `/meta`                                   | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | NOT NEEDED YET | IMPLEMENTED | IMPLEMENTED    |
|   2 | GET    | `/model-types`                            | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|   3 | GET    | `/objects`                                | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | NOT NEEDED YET | IMPLEMENTED | IMPLEMENTED    |
|   4 | GET    | `/objects/{object_id}`                    | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | NOT NEEDED YET | NOT NEEDED YET | IMPLEMENTED | IMPLEMENTED    |
|   5 | GET    | `/overview`                               | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|   6 | GET    | `/channels`                               | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|   7 | GET    | `/channels/{channel_id}`                  | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|   8 | GET    | `/situations`                             | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|   9 | GET    | `/situations/{situation_id}`              | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|  10 | GET    | `/situations/{situation_id}/evidence`     | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|  11 | GET    | `/groups`                                 | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|  12 | GET    | `/groups/{group_id}`                      | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|  13 | GET    | `/drafts`                                 | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | NOT NEEDED YET | IMPLEMENTED | IMPLEMENTED    |
|  14 | GET    | `/drafts/{draft_id}`                      | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | NOT NEEDED YET | IMPLEMENTED | IMPLEMENTED    |
|  15 | GET    | `/drafts/{draft_id}/evidence`             | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | NOT NEEDED YET | IMPLEMENTED | IMPLEMENTED    |
|  16 | POST   | `/drafts/{draft_id}/decisions`            | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | IMPLEMENTED    | IMPLEMENTED | IMPLEMENTED    |
|  17 | GET    | `/drafts/{draft_id}/decisions`            | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | NOT NEEDED YET | IMPLEMENTED | IMPLEMENTED    |
|  18 | POST   | `/drafts/{draft_id}/decision-corrections` | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT STARTED    | NOT STARTED | NOT NEEDED YET |
|  19 | GET    | `/work-orders`                            | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | NOT NEEDED YET | IMPLEMENTED | IMPLEMENTED    |
|  20 | POST   | `/work-orders`                            | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | IMPLEMENTED    | IMPLEMENTED | IMPLEMENTED    |
|  21 | GET    | `/work-orders/{work_order_id}`            | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED | IMPLEMENTED    | NOT NEEDED YET | IMPLEMENTED | IMPLEMENTED    |
|  22 | GET    | `/charts/cases`                           | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|  23 | GET    | `/fire-history`                           | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|  24 | GET    | `/replays`                                | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |
|  25 | GET    | `/replays/{scenario_id}/events`           | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT STARTED | NOT NEEDED YET | NOT NEEDED YET | NOT STARTED | NOT NEEDED YET |

The current product UI uses ten method/path pairs directly. `GET /objects/{object_id}` is already
implemented and tested in the API layer but has no direct screen consumer. It is included in the
minimum backend handoff because the agreed current foundation exposes it and detail navigation may
use it without a contract change.

## 2. Transport and configuration

- v2 base URL: `VITE_API_V2_BASE_URL`, default `http://localhost:8000/api/v2`; one trailing slash is
  removed.
- v1 base URL remains independently controlled by `VITE_API_BASE_URL`.
- `VITE_ENABLE_MOCKS=true` starts one MSW worker containing v1 and v2 handlers.
- Any other value, including `false`, does not start MSW and unregisters this app's existing MSW
  service worker before React renders.
- GET sends `Accept: application/json`. POST also sends `Content-Type: application/json`.
- Every successful response must contain JSON. The client does not accept `204 No Content` for the
  implemented calls.
- No Authorization header or cross-origin credentials policy is implemented. CORS and future auth
  must be coordinated before protected production deployment.

## 3. Response fields currently required by the frontend

The adapter reads the following wire fields. Fields described as nullable must be present as JSON
`null` when unknown unless the item is explicitly marked as a fixture compatibility extension.

### Meta

Required: `contract_version`, `data_version`, `data_cutoff`, `source_timezone_known`,
`real_feedback_available`, `live_ingestion_available`.

### Object

Required: `object_id`, `object_name`, `kind`, `channel_count`. Nullable: `parent_id`.
`object_name` must come from the dispatcher catalogue; the frontend does not derive a name from
sensor data.

### Draft

Contract required: `draft_id`, `group_id`, `object_id`, `channel_id`, `basis_kind`, `target_kind`,
`available_at`, `review_state`, `limitations`.

Contract nullable: `model_version`, `score`, `situation_id`, `its_value`, `decision`.
`decision`, when non-null, has the Decision shape below.

Current fixture compatibility fields are accepted but are not contract requirements:
`schema_version`, `forecast_horizon_hours`, `source_obs_time`, `review_status`, `location_key`,
`affected_channels`, `channel_observation_state`, `fault_reports_72h`, `service_reports_72h`,
`mixed_alarm_timestamps_72h`, `last_source_ref`, `its_status`, `calculation_version`, `source_ref`,
and `feature_snapshot`.

Enums used by current UI: `basis_kind` is `forecast | observed_status`; `review_state` is
`pending | approved | rejected`.

### Evidence

Contract required: `channel_id`, `available_at`, `source_ref`, `observed_value`.
Contract nullable: `event_id`, `numeric_value`, `numeric_unit`, `source_alarm`, `dictionary_state`.

The fixture also supplies optional context including `draft_id`, `group_id`, `situation_id`,
`object_id`, `sensor_type`, `evidence_kind`, `source_time`, `event_time`, `channel_name`, `piket`, and
`is_alarm`. `is_alarm` is preserved separately from the contract field `source_alarm`; it is not a
replacement for that field.

### Decision

Required: `decision_id`, `draft_id`, `decision`, `reason`, `author_id`, `decided_at`,
`idempotency_key`. Nullable: `supersedes_decision_id`, `work_order_id`.
`decision` is `approved | rejected`.

### WorkOrder

Required: `work_order_id`, `draft_id`, `object_id`, `status`, `work_type`, `description`,
`created_at`, `created_by`. Nullable: `external_work_order_id`, `assignee_id`, `due_at`.
The frontend renders `status` literally because the current contract defines no status enum.

## 4. Implemented endpoint obligations

| Endpoint                            | Query/body sent by frontend                                                                                                                    | Response                | Expected errors and behavior                                                                                                                                         |
| ----------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET /meta`                         | no query                                                                                                                                       | `Meta`                  | `404` unknown route; other contract errors shown in the historical notice                                                                                            |
| `GET /objects`                      | UI sends `limit=200`; client also supports `kind`, `name`, `cursor`                                                                            | `Page<Object>`          | invalid paging/filter `400`; page must contain `items`, `next_cursor`                                                                                                |
| `GET /objects/{object_id}`          | URL-encoded numeric ID                                                                                                                         | `Object`                | `404` for unknown object                                                                                                                                             |
| `GET /drafts`                       | UI sends `limit=50`, optional `cursor`, `basis_kind`, `review_state`, `object_id`; client also supports `group_id`, `from`, `to`, `at`         | `Page<Draft>`           | `400` invalid query; `422` unsupported historical time/schema                                                                                                        |
| `GET /drafts/{draft_id}`            | URL-encoded opaque ID; optional `at` supported                                                                                                 | `Draft`                 | `404` unknown draft; `422` unsupported historical time/schema                                                                                                        |
| `GET /drafts/{draft_id}/evidence`   | URL-encoded ID; UI sends `limit=50`; client supports `at`, `cursor`                                                                            | `Page<Evidence>`        | `404` unknown draft; `422` unsupported historical time/schema                                                                                                        |
| `GET /drafts/{draft_id}/decisions`  | URL-encoded ID                                                                                                                                 | `Decision[]` bare array | `404` unknown draft                                                                                                                                                  |
| `POST /drafts/{draft_id}/decisions` | `decision`, trimmed `reason`, stable `idempotency_key`                                                                                         | `Decision` JSON         | `400` missing/invalid fields; `404` unknown draft; `409` conflicting decision; same key returns the original result                                                  |
| `GET /work-orders`                  | UI sends `limit=50`, optional `cursor`; client supports `draft_id`, `object_id`, `status`                                                      | `Page<WorkOrder>`       | invalid paging/filter `400`                                                                                                                                          |
| `GET /work-orders/{work_order_id}`  | URL-encoded opaque ID                                                                                                                          | `WorkOrder`             | `404` unknown work order                                                                                                                                             |
| `POST /work-orders`                 | required `draft_id`, trimmed `work_type`, trimmed `description`, stable `idempotency_key`; optional `assignee_id`, `due_at` only when supplied | `WorkOrder` JSON        | `400` invalid fields; `404` unknown draft; `409` draft not approved, duplicate order, or stale state; same key returns the original result; `422` unsupported schema |

The client accepts any HTTP 2xx response with valid JSON. Current MSW writes return `201`; backend
should use `201 Created` for the two create operations for parity.

The work-order list currently fetches the linked draft for each visible row to display its latest
decision ID and value. The backend must therefore support concurrent `GET /drafts/{draft_id}` calls.
This is an explicit current dependency and a possible future list projection optimization, not a
reason to add undocumented fields to WorkOrder.

## 5. Pagination

Paginated resources use request `limit` and opaque `cursor`; response is exactly:

```json
{ "items": [], "next_cursor": null }
```

Contract default is 50 and maximum is 200. `next_cursor` is a string or null. Ordering must remain
stable by `available_at`, then immutable ID. The frontend stores returned cursors and never derives
offsets. It shows previous/next page controls; it does not request a total count.

`GET /drafts/{draft_id}/decisions` is a bare array, not a page.

## 6. Mutations and idempotency

A decision attempt generates one idempotency key and retains it for retries of that same form
attempt. The backend takes `author_id` from the authenticated session. Replaying the same key must
return the same decision. A different decision attempt on a decided draft returns `409`. Approval
does not create a work order.

Work-order creation is a separate explicit user action. It is allowed only when the latest
authoritative Decision is approved and has no `work_order_id`. The dispatcher supplies
`work_type` and `description`. Replaying its key returns the same WorkOrder; another order for the
same draft returns `409`. Pending and rejected drafts also return `409`. On success, subsequent
Draft and Decision reads must expose the linked `work_order_id`.

The frontend refreshes only v2 draft/decision/work-order caches. No v1 ticket is created or
invalidated.

## 7. Error contract and UI behavior

Contract error JSON is:

```json
{ "code": "string", "message": "string", "details": {} }
```

`details` may be null. The v2 client preserves all four values: HTTP status, backend `code`,
`message`, and `details`. If the body is absent or malformed it supplies a status-based message and
`HTTP_ERROR` code. A malformed successful JSON body becomes `INVALID_RESPONSE`; a failed fetch
becomes `NETWORK_ERROR` with status 0.

| Condition                   | UI behavior                                                                 |
| --------------------------- | --------------------------------------------------------------------------- |
| backend unavailable         | visible v2 connection message and retry action; no mock fallback            |
| `400`                       | backend message appears in the affected detail/form/list error state        |
| `403`                       | generic backend message is supported; correction UI is not implemented      |
| `404`                       | detail/list error state shows the backend message                           |
| `409` decision              | dedicated already-saved state; draft and history are refreshed              |
| `409` work order            | dedicated unavailable/duplicate state; linked draft and work orders refresh |
| `422`                       | backend message appears; code/details remain available to application code  |
| malformed 2xx JSON          | visible `API v2 вернул некорректный JSON.`                                  |
| empty page/history/evidence | explicit empty state; never replaced with demo data                         |
| nullable values             | rendered as unavailable/dash; null ITS is never zero                        |

The browser-level suite directly covers 409 flows, empty and populated states. Unit coverage covers
missing reason, unknown draft, rejected/pending work-order creation and idempotency. Dedicated
browser scenarios for every 400/403/404/422 variant are still unnecessary duplication; backend
messages share the same error components.

## 8. Mock versus real contract

Confirmed parity:

- Unknown object, draft and work order return 404.
- Decision missing reason returns 400; decision conflict returns 409.
- Same idempotency key replays the decision/work order.
- Work-order creation requires an approved draft and rejects pending/rejected or duplicate orders
  with 409.
- Decision and work-order POST return 201 JSON.
- Draft and work-order list mocks implement cursor slices.

Known differences that the backend must not copy blindly:

- `/objects` MSW returns its complete fixture and ignores `kind`, `name`, `limit`, and `cursor`.
- `/drafts` MSW applies `basis_kind`, `review_state`, `object_id`, `limit`, and `cursor`, but ignores
  `group_id`, `from`, `to`, and `at`.
- `/drafts/{draft_id}` MSW ignores `at`.
- Evidence MSW ignores `at`, `limit`, and `cursor`.
- MSW has no 403 path because correction/auth is not implemented.
- Mock identity is fixed (`dispatcher.mock`); production author comes from authentication.
- Mock validation is intentionally small and does not validate every enum/type or the max limit.
- Unknown object filters yield an empty page rather than a 404, which is appropriate for a list;
  unknown object detail yields 404.
- The mock work-order status `created` is fixture behavior, not an agreed status enum.
- Current fixtures contain fields missing from the schema, especially `forecast_horizon_hours` and
  evidence `is_alarm`.

## 9. Schema conformance issues

### CONFORMANCE ISSUE — preserved error metadata (fixed)

- Frontend path: `frontend/src/api/v2/client/http.ts`
- Contract field: error `code`, `details`
- Before: v2 replaced every backend code with `HTTP_ERROR` and discarded `details`.
- After: v2 preserves a string backend code and the details value; fallback behavior remains.
- Severity: medium. Message/status UI worked, but diagnostics and future typed handling did not
  conform.

### CONFORMANCE ISSUE — `forecast_horizon_hours`

- Frontend path: `frontend/src/api/v2/dto/types.ts` (`V2DraftDto`)
- Contract field: absent from `schemas.Draft`; present in `fixtures_v1.json` and required by the
  integration guide's forecast example.
- Difference: frontend accepts it as optional nullable compatibility data.
- Severity: medium, upstream blocker. Add it to the canonical Draft schema before treating it as
  required.

### CONFORMANCE ISSUE — `review_status` versus `review_state`

- Frontend path: `frontend/src/api/v2/dto/types.ts`
- Contract field: `review_state` is canonical and enum-constrained.
- Difference: fixture-only `review_status` is also accepted as optional source metadata; UI state
  uses only `review_state`.
- Severity: low. Backend should emit canonical `review_state`; decide whether to remove or formally
  document `review_status`.

### CONFORMANCE ISSUE — evidence alarm field

- Frontend path: `frontend/src/api/v2/dto/types.ts`, `frontend/src/api/v2/adapters/index.ts`
- Contract field: `source_alarm`; fixtures also use `is_alarm`.
- Difference: frontend preserves the two nullable fields separately and does not infer one from the
  other.
- Severity: medium, upstream fixture/schema alignment required.

### CONFORMANCE ISSUE — fixture extension fields

- Frontend path: `V2DraftDto` and `V2EvidenceDto`
- Contract field: multiple fixture context fields are absent from the schema inventory.
- Difference: extensions are optional and nullable in frontend; only contract fields are required.
- Severity: low for runtime compatibility, medium for generated schema/validation. Canonicalize the
  schema or publish an explicit additional-properties policy.

The declared enums, required core fields, nullable core fields, nested Decision, page shape, and
wire names otherwise conform to the current JSON contract.

## 10. Time and data semantics

- `score` is copied verbatim and displayed as a decimal model score. It is never converted to a
  probability, risk, urgency, or ITS.
- `observed_status` is labelled “Наблюдаемое событие”, never a prediction.
- `source_alarm`/`is_alarm` is shown only as an alarm marker. It does not confirm a physical
  incident.
- `approved` means the dispatcher approved a review draft. It does not confirm a failure or model
  ground truth.
- Null ITS is displayed as “ИТС не рассчитан”; it is never converted to zero.
- Historical source timestamps are timezone-naive. `source_obs_time`, evidence event/source time,
  historical `available_at`, and `data_cutoff` are rendered literally and receive no UTC, МСК, or
  browser timezone conversion.
- Server event timestamps such as `decided_at`, `created_at`, and non-null `due_at` must include an
  offset or `Z`; the operational UI formats them in `Europe/Moscow` and may append `МСК`.

## 11. Routing and identifiers

Frontend routes are `/review`, `/review/:draftId`, `/review/work-orders`, and
`/review/work-orders/:workOrderId`. Draft and work-order IDs are opaque strings and are URL-encoded
before request/navigation. Colon-rich fixture IDs are covered by hook and browser checks. Object
IDs remain JSON numbers and decimal path/query values.

Production SPA hosting must return the frontend entry point for direct reloads on both detail
routes. API routing must remain under `/api/v2` so SPA fallback cannot intercept it.

## 12. Known upstream gaps and blockers

| Topic                             | Status                   | Required resolution                                                            |
| --------------------------------- | ------------------------ | ------------------------------------------------------------------------------ |
| `forecast_horizon_hours`          | BLOCKED UPSTREAM         | add nullable field and type to canonical Draft schema                          |
| `review_status` vs `review_state` | PARTIAL                  | confirm `review_state` as sole workflow field and disposition of fixture field |
| WorkOrder status                  | BLOCKED UPSTREAM         | publish status enum and transition semantics before lifecycle controls         |
| authorization/elevated role       | BLOCKED UPSTREAM         | define auth transport, identity and permission/error behavior                  |
| decision correction               | NOT NEEDED YET / BLOCKED | endpoint exists in contract, but UI waits for elevated-role/auth policy        |
| timezone-naive historical data    | RESOLVED FOR UI          | preserve literal source values; backend must not add an invented offset        |
| error body metadata               | RESOLVED IN FRONTEND     | code/details are now preserved                                                 |
| live backend smoke                | UNVERIFIED               | `localhost:8000` refused connections during this audit                         |

## 13. Minimum backend implementation order

1. **Phase 1a — read backbone:** implement `/meta`, `/objects`, `/drafts`, draft detail and evidence
   together, including pagination, historical query validation, stable IDs, literal source times,
   CORS, and the error envelope. Object detail can ship in the same catalogue slice.
2. **Phase 1b — integration smoke:** run the frontend with `VITE_ENABLE_MOCKS=false` and the actual
   `VITE_API_V2_BASE_URL`; verify empty, populated, 404, 422, malformed-response and unavailable
   behavior before enabling writes.
3. **Phase 2 — decision store:** implement decision history and idempotent create atomically. Return
   current decision in Draft, derive author from session, and return 409 for a conflicting regular
   decision.
4. **Phase 3 — work orders:** implement idempotent explicit creation plus list/detail. Enforce the
   latest approved decision and single-order invariant transactionally, then expose
   `Decision.work_order_id` consistently.
5. **Phase 4 — corrections and auth:** define authentication and elevated permissions first, then
   implement append-only decision corrections and 403 behavior. Add UI only in a separately scoped
   task.

The remaining 14 contract endpoints can be implemented independently when a product UI needs
them. They are not required to connect the current review workflow.

## 14. Backend acceptance checklist

- [ ] All implemented endpoints use `/api/v2`, JSON bodies and exact snake_case fields.
- [ ] Required versus nullable fields match the contract; unknown numeric values remain null.
- [ ] Pages use `items` plus nullable opaque `next_cursor`, maximum limit 200 and stable ordering.
- [ ] Bare decision history is an array.
- [ ] Error responses preserve `code`, `message`, and nullable `details` with the documented status.
- [ ] Colon-rich draft IDs and opaque work-order IDs survive URL decoding unchanged.
- [ ] Historical timestamps stay literal; server action timestamps include an offset.
- [ ] Same idempotency key returns the same mutation result.
- [ ] Conflicting decisions and duplicate/non-approved work orders return 409 atomically.
- [ ] Approval does not create a work order.
- [ ] Work-order creation updates the linked decision relation consistently.
- [ ] Score, alarm, approval, observed status and null ITS retain the stated semantics.
- [ ] `VITE_ENABLE_MOCKS=false` reaches the real backend and never falls back to fixtures.
- [ ] SPA deep-link fallback works for review and work-order detail routes.
