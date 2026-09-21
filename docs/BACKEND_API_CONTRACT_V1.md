# Dolos — Backend API Contract V1

## Readiness summary

| Area                                      | Status | Backend can implement now?                             |
| ----------------------------------------- | ------ | ------------------------------------------------------ |
| System                                    | STABLE | yes                                                    |
| Dashboard summary                         | STABLE | yes; agree shared snapshot scope                       |
| Object catalogue and detail               | STABLE | yes                                                    |
| Object status registry                    | DRAFT  | partial; all/active scope unresolved                   |
| Object topology                           | STABLE | yes                                                    |
| Prediction detail                         | STABLE | yes; ML wrapper required                               |
| Prediction registry                       | DRAFT  | partial; full dataset and server paging unresolved     |
| Telemetry                                 | DRAFT  | shape yes; storage/sampling semantics unresolved       |
| Tickets: list, detail, create, transition | STABLE | yes; reproduce validated lifecycle, not mock defects   |
| Analytics                                 | DRAFT  | yes, aggregate shape stable; source/history unresolved |
| Pagination extension                      | FUTURE | proposal only; coordinated frontend migration required |
| Authentication                            | FUTURE | not defined                                            |
| Realtime updates                          | FUTURE | not defined                                            |

**Inventory: 14 currently implemented method/path pairs: 10 STABLE, 4 DRAFT, 0 FUTURE endpoints.** Three FUTURE areas above have no agreed new endpoint. Proposed pagination extends an existing endpoint and is not counted as a fifteenth API.

Audit baseline: branch `main`, commit `1ecdfa943e6e7772a7652338fb6a082669448f1e` (`feat(frontend): implement analytics workspace`), 21 September 2026. This document records actual frontend consumption, DTOs, adapters, hooks, HTTP client, MSW handlers/fixtures and [FRONTEND_CONTRACT_V2.md](FRONTEND_CONTRACT_V2.md). It is a backend handoff, not a backend implementation or a replacement for UI/UX requirements.

- **STABLE**: frontend depends on this wire shape and backend may implement it now. It does not certify the mock as a production business engine.
- **DRAFT**: wire shape is consumed today, but dataset/storage/aggregation decisions remain open. Implement the shape without silently choosing unresolved semantics.
- **FUTURE / PROPOSED**: not consumed by current frontend; do not substitute it for CURRENT.
- **CURRENT** below means observed behavior. Recommendations and proposed validation are explicitly identified. Significant discrepancies are indexed in §12; no runtime fixes are made by this handoff.

## 1. Transport, identifiers and global rules

### Base URL and deployment

`frontend/src/api/client/config.ts` uses `VITE_API_BASE_URL`, default `/api/v1`, and removes one trailing slash. Every path below is relative to that base.

Examples:

- Same-origin: `GET /api/v1/dashboard/summary`.
- With `VITE_API_BASE_URL=https://api.example.org/api/v1`: `GET https://api.example.org/api/v1/predictions/OW-004`.
- With `VITE_ENABLE_MOCKS=true` (exact string), MSW intercepts requests before React renders. Disable mocks with `false` for backend integration. Vite env is build-time configuration; restart/rebuild after changes. Never put secrets in `VITE_*`.

GET requests send `Accept: application/json`; no request body and no Content-Type header. POST/PATCH send both `Accept: application/json` and `Content-Type: application/json`, with JSON body. Successful responses must contain JSON with `Content-Type: application/json`: bare arrays for lists, bare objects for details/aggregates/writes. No `data` envelope, no pagination envelope, no 204 response: the client always parses a success body as JSON.

Cross-origin deployments must allow the configured frontend origin and GET/POST/PATCH/OPTIONS with Accept/Content-Type as applicable. Origins are deployment configuration, not a hardcoded localhost contract. No bearer token is sent; no explicit `credentials: include` is configured (fetch uses its default same-origin credentials behavior). Authentication, roles, session/JWT and CSRF conventions are FUTURE, not implied by this document. SPA hosting must route browser paths to the frontend entry point.

### IDs and scalar types

| Identifier            | JSON type      | Meaning                                                                                       |
| --------------------- | -------------- | --------------------------------------------------------------------------------------------- |
| object_id, channel_id | number         | Stable entity identifiers; backend should use integer IDs representable exactly in JavaScript |
| parent_object_id      | number or null | Parent object; only PredictionDto additionally permits omission                               |
| prediction_id         | string         | Opaque stable prediction ID, not necessarily UUID; e.g. OW-004                                |
| ticket_id             | string         | Opaque stable ticket ID; e.g. WO-2026-0931; mock numbering is not a production requirement    |
| segment_id            | string         | Stable segment identity within an object's topology                                           |

Numeric IDs are sent as decimal path/query strings; JSON responses keep them numeric, not quoted. Prediction/ticket detail IDs are URL-encoded by the hook. No API for creating catalogue IDs is currently required. Counts are nonnegative integers; probability is a finite fraction 0..1; coverage is a finite percentage 0..100; ИТС is finite 0..100. TypeScript declares most numbers simply `number`; server validation must enforce these domain constraints.

### Timestamp contract — global

Every operational timestamp in response DTOs and telemetry request bounds must be an absolute ISO 8601 instant with UTC or explicit offset:

- Valid: `2026-09-20T15:42:00Z`.
- Equivalent: `2026-09-20T18:42:00+03:00`.
- Invalid: `2026-09-20T18:42:00` without offset.

Backend should return UTC. UI displays all operational time in **Europe/Moscow**, regardless of browser timezone, with full-time label `20.09.2026, 18:42 МСК`. Do not pre-shift UTC values or send display strings. Numeric epoch support in a formatter does not change the DTO's string contract. Null timestamps are allowed only where explicitly nullable, e.g. `completed_at`. Invalid/offsetless values can render as a dash; this is defensive behavior, not permission to send them.

`dashboard.tickets.completed_today` uses the Moscow calendar day containing `generated_at`. Analytics periods are rolling elapsed-hour windows ending at `generated_at`, not browser-local calendar days.

### Null, missing, zero and empty values

All response fields in §10 are required unless marked `?`. Only `PredictionDto.parent_object_id` is optional; its adapter maps missing to null. Request fields, including nullable fields, are required. No runtime schema validation exists beyond HTTP/JSON parsing; missing keys can break UI.

| Value               | Contract meaning                                                                               |
| ------------------- | ---------------------------------------------------------------------------------------------- |
| null                | Explicit absence/unknown/not applicable for a nullable field                                   |
| missing field       | Not equivalent to null; invalid except optional prediction parent                              |
| 0                   | Known zero count, probability, index or numeric measurement; not missing data                  |
| ""                  | Actual empty text, not a substitute for null or an ID; title/description validation rejects it |
| []                  | Known empty collection; not an error and not a null aggregate                                  |
| {} / null aggregate | Not a valid replacement for a required object DTO                                              |

Nullable ML outputs: `model_domain`, `failure_probability`, `risk_level`, `maintenance_urgency`, `lead_time_hours`, `health_index_its`, `recommendation`. Supported records can still contain unknown nullable values; UI shows missing data rather than deriving replacements. `top_risk_factors` is always a string array, never null. `model_version` remains a required string, including unsupported records; no optional version convention exists.

`ticket_id: null` means no linked ticket. `prediction_id: null` on a ticket means manual work. `assignee: null` means unassigned; create UI converts its empty select value to null. `completed_at: null` means not completed; completed records should carry the completion instant. `numeric_value: null` means no numeric measurement (including state samples); zero is valid data. `unit: null` means no unit, not an empty string. `piket` and `piket_value` can be independently nullable but should describe the same location when both exist.

## 2. Canonical enums and ML semantics

| Type                      | Exact wire values                                                  |
| ------------------------- | ------------------------------------------------------------------ |
| RiskLevel                 | low, medium, high, critical                                        |
| MaintenanceUrgency        | FLASH_1_6H, URGENT_6_24H, PLANNED_24_48H, NORMAL                   |
| ModelDomain               | POWER_PHASE, ANALOG_TEMP, ANALOG_GAS, FIRE_SAFETY, HYDRO_MECHANICS |
| TicketStatus              | draft, approved, rejected, completed                               |
| ReviewStatus (prediction) | pending_review, acknowledged, rejected, ticket_created             |
| TelemetryValueType        | numeric, state                                                     |
| TelemetryStatusCode       | normal, failure, alarm, unknown                                    |
| System status             | operational, degraded                                              |
| AnalyticsRange            | 24h, 7d, 30d                                                       |

ReviewStatus is independent of TicketStatus: a rejected ticket does not change prediction review status to rejected. There is currently no endpoint to acknowledge/reject a prediction directly.

Urgency labels: FLASH_1_6H → 1–6 ч; URGENT_6_24H → 6–24 ч; PLANNED_24_48H → 24–48 ч; NORMAL → Штатный режим. These are maintenance action windows, not guaranteed failure times.

Domain display labels are centralized in `utils/model-domain.ts`: Электропитание, Температура, Газ, Пожарная безопасность, Гидромеханика respectively. Sensor type/name are free text, not enums used by UI to infer a model domain.

### Backend-provided risk and urgency

Backend returns ready `risk_level` and `maintenance_urgency`. Frontend never derives them from probability, ИТС, telemetry or each other. Domain thresholds differ. This regression fragment is **valid** (not a complete PredictionDto):

```json
{
  "sensor_type": "Датчик температуры",
  "model_domain": "ANALOG_TEMP",
  "failure_probability": 0.46,
  "risk_level": "critical"
}
```

There is no global frontend threshold of 70%. The ML module reads per-domain operational thresholds from metadata; fallback thresholds in Python are not a universal API rule.

### Health index and lead time

The checked-in `backend_app_ml_predictor.py`, `predict_channel()`, computes supported-channel ИТС as:

```text
max(0, min(100, int(round(100.0 * (1.0 - probability)))))
```

Thus 0.46 gives 54 under that ML implementation. Backend returns the completed `health_index_its`; frontend displays it without calculating/checking the formula. Some fixtures carry other values (TEMP-001: 0.46 and 28). **CONTRACT ISSUE CI-04:** agree ML/source semantics; do not teach backend that all fixtures implement the formula. The wire field is `number | null`, although Python emits integers.

`lead_time_hours` is an indicative planning horizon, not a precise failure ETA. It may be null even for supported records. UI displays it only as approximate technical data and gets operational guidance from maintenance_urgency. No “failure in 4 hours” claim is warranted.

### Unsupported ML

The following fragment is mandatory for unsupported output; retain identification/location/version/generated_at/review/ticket fields from the full DTO:

```json
{
  "prediction_supported": false,
  "model_domain": null,
  "failure_probability": null,
  "risk_level": null,
  "maintenance_urgency": null,
  "lead_time_hours": null,
  "health_index_its": null,
  "top_risk_factors": [],
  "recommendation": null
}
```

Do not send fallback 1%, low, ИТС 99. The checked-in Python module currently does exactly that for unmapped/unloaded domains and lacks the full frontend envelope: a backend wrapper must expose support explicitly and enrich the prediction. `toPrediction` defensively clears ML fields when support is false; this is not a substitute for correct server output. Location and telemetry remain usable, and unsupported ML does not automatically prohibit creating a ticket.

## 3. Complete CURRENT endpoint inventory

All paths below are prefixed by `/api/v1` by default. Methods distinguish endpoints.

| #   | Method and path                   | Status | Success response             | Actual consumer                                                           |
| --- | --------------------------------- | ------ | ---------------------------- | ------------------------------------------------------------------------- |
| 1   | GET /system                       | STABLE | 200 SystemDto                | Shell / system drawer                                                     |
| 2   | GET /dashboard/summary            | STABLE | 200 DashboardSummaryDto      | Overview                                                                  |
| 3   | GET /objects                      | STABLE | 200 ObjectDto[]              | Ticket create object options                                              |
| 4   | GET /objects/status-summary       | DRAFT  | 200 ObjectStatusSummaryDto[] | Objects Registry and Overview                                             |
| 5   | GET /objects/:id                  | STABLE | 200 ObjectDetailDto          | Object Workspace                                                          |
| 6   | GET /objects/:objectId/topology   | STABLE | 200 ObjectTopologyDto        | Object Workspace                                                          |
| 7   | GET /predictions                  | DRAFT  | 200 PredictionDto[]          | Overview, Predictions Registry, Object Workspace; foundation in mock mode |
| 8   | GET /predictions/:predictionId    | STABLE | 200 PredictionDto            | Investigation and ticket source                                           |
| 9   | GET /sensors/:channelId/telemetry | DRAFT  | 200 TelemetryResponseDto     | Investigation                                                             |
| 10  | GET /tickets                      | STABLE | 200 TicketDto[]              | Tickets Registry                                                          |
| 11  | GET /tickets/:ticketId            | STABLE | 200 TicketDto                | Ticket drawer                                                             |
| 12  | POST /tickets                     | STABLE | 201 TicketDto                | Create drawer                                                             |
| 13  | PATCH /tickets/:ticketId/status   | STABLE | 200 TicketDto                | Ticket status actions                                                     |
| 14  | GET /analytics/summary            | DRAFT  | 200 AnalyticsSummaryDto      | Analytics                                                                 |

MSW uses `:id` for prediction detail; the frontend-facing name `:predictionId` describes the same URL, not another route. Likewise object parameter names do not create multiple endpoints. No additional runtime fetch endpoints were found outside the shared HTTP client. Old `TelemetrySample` and old object-detail-as-`ObjectDto` are superseded shapes, not extra endpoints. `/foundation` is a browser-only mock route, not an API.

### CURRENT query parameters, filtering and ordering

All parameters are optional at the wire level in the mock. “Always” below describes the current hook, not a server-side validation already implemented.

| Endpoint                          | Parameter     | Type                         | Required    | Current status      | Meaning                                                                                |
| --------------------------------- | ------------- | ---------------------------- | ----------- | ------------------- | -------------------------------------------------------------------------------------- |
| GET /objects                      | —             | —                            | no          | CURRENT             | No business query parameters; full catalogue array                                     |
| GET /objects/status-summary       | —             | —                            | no          | CURRENT             | No scope/search/paging params; adapter removes active_predictions = 0                  |
| GET /predictions                  | view          | literal operational          | no          | CURRENT hook + mock | Priority selection; current Overview and Registry always request it                    |
| GET /predictions                  | object_id     | numeric ID encoded as string | no          | CURRENT hook + mock | Exact object filter; Object Workspace uses it                                          |
| GET /predictions                  | risk_level    | RiskLevel                    | no          | CURRENT hook + mock | Exact risk filter; current pages primarily filter locally                              |
| GET /tickets                      | status        | TicketStatus                 | no          | CURRENT hook + mock | Exact status filter                                                                    |
| GET /tickets                      | search        | string                       | no          | CURRENT hook + mock | Trim + case-insensitive substring over ID, title, object name, prediction ID, assignee |
| GET /tickets                      | prediction_id | string                       | no          | CURRENT hook + mock | Exact linked prediction filter                                                         |
| GET /tickets                      | object_id     | numeric ID encoded as string | no          | CURRENT hook + mock | Exact object filter                                                                    |
| GET /sensors/:channelId/telemetry | date_from     | ISO timestamp                | hook always | CURRENT hook + mock | Window start                                                                           |
| GET /sensors/:channelId/telemetry | date_to       | ISO timestamp                | hook always | CURRENT hook + mock | Window end                                                                             |
| GET /sensors/:channelId/telemetry | limit         | number encoded as string     | hook always | CURRENT hook + mock | Requested sample cap; hook uses 96 / 144 / 192                                         |
| GET /analytics/summary            | range         | AnalyticsRange               | hook always | CURRENT hook + mock | Default 7d if omitted; unknown value gives 400                                         |

System, dashboard and detail/mutation endpoints have no business query parameters. Prediction `maintenance_urgency`, `search`, pagination and sorting are **not** current request parameters. Ticket registry calls `useTickets()` without filters and applies its UI filters locally, even though the hook/mock support the optional server filters.

Current mock prediction selection order: operational view picks the 24 OP-* records; otherwise a supplied object with workspace records picks those; otherwise six foundation records. Then object/risk filters are applied. Unknown filter values generally match nothing rather than trigger validation; production invalid-param validation is a recommendation (§11), not observed mock behavior.

Local ordering/filters (not server parameters):

- Operational predictions: supported, non-null risk, non-low only; urgency FLASH → URGENT → PLANNED → NORMAL → null, probability descending (null last), ID tie-break.
- Predictions Registry: same priority source, local risk/urgency/object/search; optional probability/time/object sort, shared urgency tie-break. Returning low/unsupported under operational view alone will not make them visible.
- Object Workspace: `object_id` request, then local urgency/risk/search/numeric segment range; low/unsupported are retained.
- Object status adapter: active > 0; risk critical/high/medium/low-or-null, critical count descending, ID. Registry additionally sorts ready values by risk (null last), critical count, active count, Russian name, ID.
- Tickets: draft/approved/rejected/completed; updated_at descending, ID tie-break; local status/search.

`scenario=empty|error|slow` is a **mock-only test control**, not a backend query contract. It is handled for predictions lists, object lists/status, tickets lists, topology and telemetry; browser-only override modules also simulate states. Never implement these as production switches. Some override helpers can return intentionally unsuitable shapes; see CI-12.

## 4. System and Dashboard — STABLE

### GET /system

Returns SystemDto (§10). `operational` and `degraded` describe service state, not HTTP status; a degraded service can respond 200. `updated_at` is the status observation time. Current mock always returns operational with current timestamp. Hook polls every 60 seconds.

```json
{ "status": "operational", "updated_at": "2026-09-20T15:42:00Z" }
```

### GET /dashboard/summary

Independent network snapshot: never built by the frontend from loaded registry rows. All fields in DashboardSummaryDto are required. `generated_at` identifies the snapshot, `model_version` its reported model version.

- channels: total, supported, unsupported, ready coverage percentage; supported + unsupported should equal total.
- predictions: active total, three risk counts and three urgency counts. Active may include low, and urgency may include NORMAL; neither omitted group has its own field. Critical does not imply FLASH.
- objects: total catalogue size, affected population, critical subset. Do not infer these from the eight displayed objects.
- tickets: current draft and approved counts, completed_today in the Moscow day of the snapshot.
- Frontend only sums two supplied counters for “Срочные ≤24 ч”: flash_1_6h + urgent_6_24h. It never recalculates risk or summary from predictions.

```json
{
  "generated_at": "2026-09-20T15:42:00Z",
  "model_version": "7.2",
  "channels": {
    "total": 12480,
    "ml_supported": 9984,
    "ml_unsupported": 2496,
    "coverage_percent": 80
  },
  "predictions": {
    "active": 137,
    "critical": 8,
    "high": 24,
    "medium": 61,
    "flash_1_6h": 6,
    "urgent_6_24h": 26,
    "planned_24_48h": 61
  },
  "objects": { "total": 186, "affected": 42, "critical": 5 },
  "tickets": { "draft": 12, "approved": 19, "completed_today": 7 }
}
```

This is the actual static demo fixture, not acceptance data for production totals. Backend must define the active population, shared snapshot scope and refresh policy consistently; counts must not be inferred from client review labels.

## 5. Objects and topology

### GET /objects — STABLE

Bare ObjectDto[] catalogue for ticket creation; it is **not** the data source for the current Objects Registry. `subsystem` is a catalogue string; `parent_object_id` is required nullable. Empty catalogue is `[]`.

```json
[
  {
    "object_id": 101,
    "object_name": "Технический блок № 1",
    "parent_object_id": null,
    "subsystem": "Инженерные системы"
  }
]
```

Example is a compact valid response, not the complete mock list (101 and 102). Production catalogue must include objects referenced by predictions, details and tickets; mock only includes two (CI-05).

### GET /objects/status-summary — DRAFT

ObjectStatusSummaryDto[] supplies risk, counts, channel totals and updated_at per object. Counts and risk are backend aggregates, not derived in React. Object coverage display divides the two channel counts; there is no coverage_percent field in this DTO.

```json
[
  {
    "object_id": 203,
    "object_name": "объект Фита",
    "risk_level": "critical",
    "active_predictions": 24,
    "critical_predictions": 4,
    "high_predictions": 8,
    "ml_supported_channels": 722,
    "channels_total": 860,
    "updated_at": "2026-09-20T15:42:00Z"
  }
]
```

**DRAFT decision:** full production registry should include zero-active objects. Agree either all objects in this response or a proposed `scope=all|active` parameter. Neither is sufficient without changing the current `toObjectStatusList` active-only filter; coordinate that frontend migration. Current eight rows are a priority mock subset, not a production row limit.

### GET /objects/:id — STABLE

ObjectDetailDto (§10), not ObjectDto. `object_type` is free text; ready risk/counts/channel totals and timestamp are independent of the loaded prediction list. Null risk means unknown/unavailable, not low. A known object without predictions is still a 200 detail, not 404.

```json
{
  "object_id": 203,
  "object_name": "объект Фита",
  "parent_object_id": null,
  "object_type": "Инженерный объект",
  "channels_total": 860,
  "ml_supported_channels": 722,
  "risk_level": "critical",
  "active_predictions": 24,
  "critical_predictions": 4,
  "high_predictions": 8,
  "updated_at": "2026-09-20T15:42:00Z"
}
```

Unknown object gives 404. For one object and matching snapshot, detail and status-summary should agree. Coverage display differs in precision: workspace rounds to an integer; registry uses up to one decimal. Do not interpret that formatting difference as different backend populations.

### GET /objects/:objectId/topology — STABLE

ObjectTopologyDto and TopologySegmentDto (§10). Segment `risk_level`, counts and `max_failure_probability` are **backend aggregates**. The frontend only renames and sorts segments by piket_from; it never derives segment risk from predictions or maximum probability.

- Numeric range is in pikets, matching prediction.piket_value.
- Nonempty segments have unique IDs, ascending contiguous ranges and positive lengths: next piket_from equals preceding piket_to.
- Supplied piket_min/max should bound all segments. Both can be null for absent topology.
- Frontend segment selection includes both boundaries. A prediction exactly at a shared boundary is visible for either adjacent segment; agree aggregate boundary semantics accordingly. Do not assume sums of segment counts always equal an object total (shared boundaries and unlocated channels).
- `max_failure_probability` is fraction 0..1 or null if no probability is known; no fake 0 for missing values.
- Known object with no topology: 200 object with `segments: []`, typically null bounds. Unknown object: 404.

Compact valid standalone example (not a subset pretending to cover the full 0..400 mock topology):

```json
{
  "object_id": 203,
  "object_name": "объект Фита",
  "piket_min": 0,
  "piket_max": 20,
  "updated_at": "2026-09-20T15:42:00Z",
  "segments": [
    {
      "segment_id": "SEG-203-01",
      "label": "Входной участок",
      "piket_from": 0,
      "piket_to": 20,
      "risk_level": "low",
      "active_predictions": 0,
      "critical_predictions": 0,
      "high_predictions": 0,
      "max_failure_probability": null
    }
  ]
}
```

Register static `/objects/status-summary` and nested topology routes so they are not accidentally interpreted as an object ID.

### Piket contract

`piket` is display text (e.g. `ПК88,5` or current formatter's `ПК 88+50`). `piket_value: 88.5` is numeric location. Backend sends both for predictions when known. UI never parses display text to filter a range. Null/nonfinite numeric location is excluded from selected numeric segments; it remains visible without selection, including unsupported channels.

## 6. Predictions

### GET /predictions/:predictionId — STABLE

Full PredictionDto (§10), shared with list items. Required context: channel, sensor/type, subsystem, tag, object/name, location, support flag/version, nullable ML outputs, ordered textual risk factors/recommendation, generated_at, review status, ticket link. Only parent_object_id may be omitted (mapped to null).

`top_risk_factors` is a string array with backend order preserved; no scores or factor weights are implied. Recommendation is plain text and is displayed verbatim. `generated_at` is prediction generation time, not necessarily latest telemetry sample or ticket update. IDs are stable across list/detail.

Complete compact example based on TEMP-001 (including its actual mock ИТС; CI-04):

```json
{
  "prediction_id": "TEMP-001",
  "channel_id": 1001,
  "sensor_name": "Температура шкафа управления",
  "sensor_type": "Температура",
  "subsystem": "Вентиляция",
  "tag": "TT-001",
  "object_id": 101,
  "object_name": "Технический блок № 1",
  "parent_object_id": null,
  "piket": "ПК 12+40",
  "piket_value": 12.4,
  "prediction_supported": true,
  "model_domain": "ANALOG_TEMP",
  "model_version": "7.2",
  "failure_probability": 0.46,
  "risk_level": "critical",
  "maintenance_urgency": "FLASH_1_6H",
  "lead_time_hours": 3,
  "health_index_its": 28,
  "top_risk_factors": ["Нестабильность показаний температуры"],
  "recommendation": "Проверить датчик и вентиляцию шкафа.",
  "generated_at": "2026-09-20T09:00:00Z",
  "review_status": "pending_review",
  "ticket_id": null
}
```

Unknown prediction returns 404, not a null DTO. Detail supports low and unsupported even though the current priority registry does not show them.

### GET /predictions — DRAFT

Returns a bare array of the **same complete DTO**. Query table is in §3. Empty selection is 200 `[]`; an object filter with no matching records does not itself return object 404 in the mock.

**DRAFT decision:** a full production registry must be able to retrieve low, medium, high, critical and unsupported entries, not just 24 priority rows. Agree whether the full dataset is latest prediction per channel or prediction history, active/inactive definition, support-state filtering, sorting and pagination. Current DTO has no active flag or historical cursor.

`view=operational` is a consumed priority-view contract, not a way to access the full registry. Current adapter always removes low/unsupported regardless of what the server sends. Current six-row no-view mock dataset is a test fixture, not the intended production full list.

## 7. Telemetry — DRAFT

### GET /sensors/:channelId/telemetry

Full TelemetryResponseDto and TelemetryPointDto are in §10. Example request:

```http
GET /api/v1/sensors/30004/telemetry?date_from=2026-09-19T15%3A42%3A00Z&date_to=2026-09-20T15%3A42%3A00Z&limit=144
Accept: application/json
```

CURRENT hook converts UI ranges into absolute UTC bounds at fetch time: 6h → 96 points, 24h → 144, 48h → 192; hard cap constant 1000. It enables fetching once channelId is finite. Range token is a cache key component, **not** a telemetry query parameter. Date window is recomputed on refetch, not frozen at prediction generated_at.

Response example demonstrating a measured numeric gap (two points, not a complete mock series):

```json
{
  "channel_id": 30004,
  "sensor_name": "Температура ВШ-3",
  "sensor_type": "Температура",
  "value_type": "numeric",
  "unit": "°C",
  "points_count": 2,
  "telemetry": [
    {
      "timestamp": "2026-09-20T15:40:00Z",
      "raw_value": "27.3 °C",
      "numeric_value": 27.3,
      "status_code": "normal",
      "is_alarm": false,
      "is_chatter": false
    },
    {
      "timestamp": "2026-09-20T15:42:00Z",
      "raw_value": "Нет измерения",
      "numeric_value": null,
      "status_code": "unknown",
      "is_alarm": false,
      "is_chatter": false
    }
  ]
}
```

State response example:

```json
{
  "channel_id": 30005,
  "sensor_name": "Фаза B · тяговый ввод",
  "sensor_type": "Состояние фазы",
  "value_type": "state",
  "unit": null,
  "points_count": 1,
  "telemetry": [
    {
      "timestamp": "2026-09-20T15:42:00Z",
      "raw_value": "Просадка",
      "numeric_value": null,
      "status_code": "alarm",
      "is_alarm": true,
      "is_chatter": true
    }
  ]
}
```

- Backend explicitly selects numeric/state; frontend never infers it from sensor name.
- Numeric null creates a break; chart uses connectNulls=false. An omitted timestamp/sample is not automatically inferred to be a gap—send an explicit null sample where a known outage must interrupt the line.
- State chart labels come from raw_value (e.g. Норма, Просадка, Отказ), rendered as steps. status_code is a separate normalized classification; is_alarm and is_chatter are explicit flags, not derived by UI from text or code.
- Adapter maps fields and sorts timestamps ascending. `points_count` is server reported, should equal telemetry.length; UI renders the actual array.
- Empty known channel/window: 200 with real channel metadata, points_count 0 and telemetry []; no null response. Unsupported ML does not imply unavailable telemetry.
- No future points, forecast line or prediction accuracy fields are required.

**CURRENT mock permissiveness:** omitted/invalid dates fall back to now and now−24h; zero/invalid limit defaults to 144; limit is capped at 1000 and the fixture enforces at least one sample. It does not validate inverted windows or integer limits strictly. Numeric unknown channel returns 200 synthetic empty metadata; only a nonnumeric channel produces 404. These are test conveniences/CI-08, not production validation guidance.

**DRAFT decisions:** retention, historical storage, raw sampling interval, inclusive/exclusive date bounds, maximum interval, production maximum points (1000 is today's client/mock ceiling, not an agreed storage capacity), downsampling/aggregation policy and treatment of alarm/chatter during downsampling. Recommended validation after agreement: valid absolute dates, start < end, positive integer limit within agreed cap. Do not interpolate fabricated measurements to satisfy limit; limit is an upper bound, not a required array length.

## 8. Tickets — STABLE

### GET /tickets

Bare TicketDto[] (§10). Current optional filters are listed in §3; registry applies its controls locally. Empty list is 200 []. All canonical statuses are returned when no filter is sent.

```json
[
  {
    "ticket_id": "WO-2026-0917",
    "prediction_id": "HYDRO-003",
    "object_id": 102,
    "object_name": "Насосная станция",
    "sensor_name": "Дренажный насос № 2",
    "piket": "ПК 12+40",
    "title": "Проверка дренажного насоса № 2",
    "description": "Проверить состояние подшипникового узла и режим работы насоса.",
    "status": "draft",
    "priority": "high",
    "assignee": "Инженер КИП",
    "created_at": "2026-09-20T09:10:00Z",
    "updated_at": "2026-09-20T09:10:00Z",
    "completed_at": null
  }
]
```

### GET /tickets/:ticketId

Returns one TicketDto or 404. Browser `/tickets?ticketId=...` opens a drawer, but it requests this API detail URL. Do not confuse camelCase browser route parameters with snake_case API filters.

```json
{
  "ticket_id": "WO-2026-0917",
  "prediction_id": "HYDRO-003",
  "object_id": 102,
  "object_name": "Насосная станция",
  "sensor_name": "Дренажный насос № 2",
  "piket": "ПК 12+40",
  "title": "Проверка дренажного насоса № 2",
  "description": "Проверить состояние подшипникового узла и режим работы насоса.",
  "status": "draft",
  "priority": "high",
  "assignee": "Инженер КИП",
  "created_at": "2026-09-20T09:10:00Z",
  "updated_at": "2026-09-20T09:10:00Z",
  "completed_at": null
}
```

### POST /tickets

Request is exactly CreateTicketRequestDto (§10), not TicketDto. Example:

```json
{
  "prediction_id": "OW-004",
  "object_id": 203,
  "title": "Проверка: Температура ВШ-3",
  "description": "Калибровка измерительного тракта или замена термопары.",
  "assignee": "Инженер КИП"
}
```

201 response:

```json
{
  "ticket_id": "WO-2026-0931",
  "prediction_id": "OW-004",
  "object_id": 203,
  "object_name": "объект Фита",
  "sensor_name": "Температура ВШ-3",
  "piket": "ПК 89+40",
  "title": "Проверка: Температура ВШ-3",
  "description": "Калибровка измерительного тракта или замена термопары.",
  "status": "draft",
  "priority": "critical",
  "assignee": "Инженер КИП",
  "created_at": "2026-09-20T15:43:00Z",
  "updated_at": "2026-09-20T15:43:00Z",
  "completed_at": null
}
```

Backend assigns ID, draft status, timestamps, object/sensor/piket context and priority. Priority is a snapshot of the supported source prediction's ready risk_level, not calculated from probability; unsupported/manual priority is null. For a linked prediction, mock copies its object_id/name and ignores a conflicting body.object_id. Production must agree strict mismatch validation; do not trust client-supplied context.

Manual request example:

```json
{
  "prediction_id": null,
  "object_id": 101,
  "title": "Осмотр технического блока",
  "description": "Провести контрольный осмотр после завершения ремонта.",
  "assignee": null
}
```

Manual response should preserve that object ID and resolve its actual catalogue name, with prediction_id/sensor_name/piket/priority null. Current mock hardcodes manual object_name to объект Фита even for 101 (CI-06); **do not reproduce that defect**.

Validation to duplicate server-side:

- Trim title and description before checking/persisting: title 3–120, description 10–2000. UI and mock use JavaScript string length (UTF-16 code units); cross-language length policy should match or be explicitly agreed.
- Valid body shape/types; prediction_id is a nonempty existing string or explicit null; object_id is a valid catalogue ID; assignee string or null.
- UI requires a selected object for manual creation; DTO always requires object_id, including prediction-driven creation.
- Current fixed assignee choices: Смена А, Смена Б, Инженер КИП, Электротехническая группа, Служба вентиляции. This is a UI reference list, not an authenticated staff identity contract. Mock accepts any assignee; no directory endpoint exists.
- Mock only validates title/description lengths and linked-prediction existence/uniqueness, not the entire body. Server validation of IDs, types and context remains necessary (CI-07).

CURRENT errors: malformed/unexpected request 400; title/description length 422; unknown prediction 404; existing ticket for this prediction 409. Additional object/type validation is recommended, not already demonstrated in MSW.

### PATCH /tickets/:ticketId/status

Dedicated status transition, not generic JSON Patch. Request:

```json
{ "status": "completed" }
```

For an approved ticket, 200 example:

```json
{
  "ticket_id": "WO-2026-0918",
  "prediction_id": "OW-016",
  "object_id": 203,
  "object_name": "объект Фита",
  "sensor_name": "Газ CO · венткамера ВК-6",
  "piket": "ПК 217",
  "title": "Проверка: Газ CO · венткамера ВК-6",
  "description": "Проверить работу приточной вентиляции и выполнить калибровку газоанализатора.",
  "status": "completed",
  "priority": "critical",
  "assignee": "Служба вентиляции",
  "created_at": "2026-09-19T14:20:00Z",
  "updated_at": "2026-09-20T15:43:00Z",
  "completed_at": "2026-09-20T15:43:00Z"
}
```

| Current status | Allowed next statuses |
| -------------- | --------------------- |
| draft          | approved, rejected    |
| approved       | completed             |
| rejected       | none                  |
| completed      | none                  |

Backend must validate the transition against persisted state atomically. Same-state requests and draft → completed are not allowed by the current map. Unknown ticket: 404. Disallowed transition: 409, including an unknown status value in the current mock. Malformed JSON/unexpected exception: 400. On success update updated_at; when completing, set completed_at to the same instant. No reopen, delete, generic edit, rejection reason, attachments or history endpoint exists.

### Duplicate rule and synchronization

**One prediction → at most one ticket, regardless of ticket status**, including rejected/completed. Manual tickets with prediction_id null are not subject to the prediction uniqueness rule. Enforce uniqueness transactionally (not only a pre-insert UI check); concurrent duplicate creation must return 409 for the loser. No idempotency-key protocol is defined yet.

Every subsequent list/detail prediction response with a ticket must include `ticket_id != null` and `review_status = ticket_created`. Current mock overlays this from the ticket store for all prediction endpoints. A terminal ticket does not clear the link, reset risk, remove the prediction or allow a replacement ticket automatically.

Creation refreshes ticket and prediction caches; status mutation refreshes ticket caches. Neither mutation invalidates dashboard/analytics caches today (CI-11). Return the complete committed TicketDto, not an acknowledgement only. In-memory mock reset-on-reload is not a production persistence requirement.

## 9. Analytics — DRAFT

### GET /analytics/summary?range=24h|7d|30d

AnalyticsSummaryDto and nested DTOs are in §10. Default is 7d; invalid range gives 400 in MSW. No arbitrary date range parameters. Shape is stable enough to implement, but history/population/ranking source requires backend agreement.

- generated_at is snapshot end. 24h/7d/30d mean 24/168/720 elapsed hours ending there.
- totals.active_predictions/critical_predictions/high_predictions/open_tickets/ml_coverage_percent, urgency_distribution, top_objects, ticket_status_distribution and ml_domain_coverage describe the current snapshot, not the sum of timeline points.
- totals.completed_tickets counts completions within the selected interval; it need not equal the current all-time completed-status count.
- risk_timeline represents historical active-risk counts for critical/high/medium, not new events, cumulative totals or predicted future failures. Last point aligns with current critical/high totals. Low is not a required series.
- urgency_distribution covers active predictions; count labels come directly from urgency enums. Include zero buckets when known; sum should equal the same active population.
- top_objects is backend-ranked, with stable unique object IDs/names. Frontend preserves supplied order, no weighted score. It is a subset, so its sums need not equal network totals.
- open_tickets is an authoritative aggregate; UI does not calculate draft + approved, although that is its intended lifecycle meaning.
- ticket_status_distribution is current status of all tickets, displayed draft/approved/rejected/completed, not a lifecycle transition history.
- coverage_percent is ready percent, accompanied by supported/total. Supported ≤ total. Overall ml_coverage_percent should reflect the channel-weighted ratio, not the unweighted mean of domains. Domain codes must be unique. Zero denominator convention in the frontend contract is 0.
- UI must not reconstruct any of these business aggregates from predictions/tickets/objects lists.

Current deterministic fixtures contain 13/8/16 points for 24h/7d/30d (rough target densities 12–24 / 7–14 / 15–30, not exact production cardinalities). No runtime random or reconstruction from current predictions. Snapshot totals: 137 active, 8 critical, 24 high, 9 open tickets, 80% coverage. Completed-in-period: 1/3/4. Historical overlaps and final points agree within Analytics fixtures, but other mock endpoints are separate snapshots/CI-10.

Absent aggregate uses a **200 full DTO** with correct range/generated_at, zero totals and all five arrays empty. This is distinct from a legitimate zero-risk snapshot with timeline or coverage records. No 204, null or [] aggregate. Range switching uses placeholder data with the old range clearly labelled; failed refresh preserves previous data and shows stale state.

**DRAFT decisions:** authoritative history store, snapshot cadence, window inclusion boundaries, consistency across endpoints, active-risk population (latest per channel vs multiple predictions), supported-channel counting across domains, object ranking rule/limit, freshness lag, completed-in-period timestamp definition. No MTTR, SLA, acknowledgement time, full ticket history, model accuracy, precision/recall/F1 or ROC-AUC is derivable from this DTO. Do not invent fields or claim a count of future accidents.

## 10. Exact wire schemas

The following declarations are copied from audited DTO files, with imports removed. Enum identifiers resolve to §2; nullable and optional markers are intentional. They are the complete HTTP shapes, not camelCase domain objects. Backend implementers need not inspect presentation components.

### SystemDto and ObjectDto — dto/resources.ts

```ts
interface ObjectDto {
  object_id: number;
  object_name: string;
  parent_object_id: number | null;
  subsystem: string;
}
interface SystemDto {
  status: "operational" | "degraded";
  updated_at: string;
}
```

### DashboardSummaryDto — dto/dashboard.ts

```ts
interface DashboardSummaryDto {
  generated_at: string;
  model_version: string;
  channels: {
    total: number;
    ml_supported: number;
    ml_unsupported: number;
    coverage_percent: number;
  };
  predictions: {
    active: number;
    critical: number;
    high: number;
    medium: number;
    flash_1_6h: number;
    urgent_6_24h: number;
    planned_24_48h: number;
  };
  objects: {
    total: number;
    affected: number;
    critical: number;
  };
  tickets: {
    draft: number;
    approved: number;
    completed_today: number;
  };
}
```

### ObjectStatusSummaryDto — dto/object-status.ts

```ts
interface ObjectStatusSummaryDto {
  object_id: number;
  object_name: string;
  risk_level: RiskLevel | null;
  active_predictions: number;
  critical_predictions: number;
  high_predictions: number;
  ml_supported_channels: number;
  channels_total: number;
  updated_at: string;
}
```

### ObjectDetailDto — dto/object-detail.ts

```ts
interface ObjectDetailDto {
  object_id: number;
  object_name: string;
  parent_object_id: number | null;
  object_type: string;
  channels_total: number;
  ml_supported_channels: number;
  risk_level: RiskLevel | null;
  active_predictions: number;
  critical_predictions: number;
  high_predictions: number;
  updated_at: string;
}
```

### ObjectTopologyDto and TopologySegmentDto — dto/object-topology.ts

```ts
interface TopologySegmentDto {
  segment_id: string;
  label: string;
  piket_from: number;
  piket_to: number;
  risk_level: RiskLevel | null;
  active_predictions: number;
  critical_predictions: number;
  high_predictions: number;
  max_failure_probability: number | null;
}
interface ObjectTopologyDto {
  object_id: number;
  object_name: string;
  piket_min: number | null;
  piket_max: number | null;
  updated_at: string;
  segments: TopologySegmentDto[];
}
```

### PredictionDto — dto/prediction.ts

```ts
interface PredictionDto {
  prediction_id: string;
  channel_id: number;
  sensor_name: string;
  sensor_type: string;
  subsystem: string;
  tag: string;
  object_id: number;
  object_name: string;
  parent_object_id?: number | null;
  piket: string | null;
  piket_value: number | null;
  prediction_supported: boolean;
  model_domain: ModelDomain | null;
  model_version: string;
  failure_probability: number | null;
  risk_level: RiskLevel | null;
  maintenance_urgency: MaintenanceUrgency | null;
  lead_time_hours: number | null;
  health_index_its: number | null;
  top_risk_factors: string[];
  recommendation: string | null;
  generated_at: string;
  review_status: ReviewStatus;
  ticket_id: string | null;
}
```

### Telemetry DTOs — dto/telemetry.ts

```ts
type TelemetryValueType = "numeric" | "state";
type TelemetryStatusCode = "normal" | "failure" | "alarm" | "unknown";

interface TelemetryPointDto {
  timestamp: string;
  raw_value: string;
  numeric_value: number | null;
  status_code: TelemetryStatusCode;
  is_alarm: boolean;
  is_chatter: boolean;
}

interface TelemetryResponseDto {
  channel_id: number;
  sensor_name: string;
  sensor_type: string;
  value_type: TelemetryValueType;
  unit: string | null;
  points_count: number;
  telemetry: TelemetryPointDto[];
}
```

### Ticket DTOs and mutation requests — dto/ticket.ts

```ts
interface TicketDto {
  ticket_id: string;
  prediction_id: string | null;
  object_id: number;
  object_name: string;
  sensor_name: string | null;
  piket: string | null;
  title: string;
  description: string;
  status: TicketStatus;
  priority: RiskLevel | null;
  assignee: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
}

// Backend assigns ticket_id, status, created_at and updated_at; the client never sends them.
interface CreateTicketRequestDto {
  prediction_id: string | null;
  object_id: number;
  title: string;
  description: string;
  assignee: string | null;
}

interface UpdateTicketStatusRequestDto {
  status: TicketStatus;
}
```

### Analytics DTOs — dto/analytics.ts

`AnalyticsRange = '24h' | '7d' | '30d'` is defined in domain/analytics/types.ts.

```ts
interface AnalyticsRiskTimelinePointDto {
  timestamp: string;
  critical: number;
  high: number;
  medium: number;
}
interface AnalyticsUrgencyDistributionDto {
  urgency: MaintenanceUrgency;
  count: number;
}
interface AnalyticsObjectRiskDto {
  object_id: number;
  object_name: string;
  risk_level: RiskLevel;
  active_predictions: number;
  critical_predictions: number;
  high_predictions: number;
  open_tickets: number;
}
interface AnalyticsTicketStatusDto {
  status: TicketStatus;
  count: number;
}
interface AnalyticsMlDomainCoverageDto {
  domain: ModelDomain;
  channels_total: number;
  channels_supported: number;
  coverage_percent: number;
}
interface AnalyticsSummaryDto {
  generated_at: string;
  range: AnalyticsRange;
  totals: {
    active_predictions: number;
    critical_predictions: number;
    high_predictions: number;
    open_tickets: number;
    completed_tickets: number;
    ml_coverage_percent: number;
  };
  risk_timeline: AnalyticsRiskTimelinePointDto[];
  urgency_distribution: AnalyticsUrgencyDistributionDto[];
  top_objects: AnalyticsObjectRiskDto[];
  ticket_status_distribution: AnalyticsTicketStatusDto[];
  ml_domain_coverage: AnalyticsMlDomainCoverageDto[];
}
```

### Adapter behavior relevant to backend

Most adapters only rename snake_case fields to camelCase. Exceptions matter:

| Wire type / transformation       | Actual behavior                                                                                                                        |
| -------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------- |
| PredictionDto → Prediction       | prediction_id → id; health_index_its → healthIndex; missing parent → null; nonfinite piket_value → null; unsupported ML fields cleared |
| ObjectDto → InfrastructureObject | object_id → id; object_name → name                                                                                                     |
| Object status list               | Active-only filtering and sorting described in §3                                                                                      |
| ObjectTopologyDto                | Segments sorted by piketFrom; aggregates untouched                                                                                     |
| TelemetryResponseDto             | telemetry → points; nonfinite numeric_value → null; timestamps sorted; points_count retained as pointsCount                            |
| TicketDto                        | ticket_id → id; priority preserved                                                                                                     |
| DashboardSummaryDto              | Ready nested aggregates preserved; only field renaming                                                                                 |
| AnalyticsSummaryDto              | Ready arrays/totals preserved, ranking preserved                                                                                       |
| SystemDto                        | Inline hook mapping updated_at → updatedAt, no separate adapter                                                                        |

No adapter implements full runtime schema validation. Do not rely on unknown enum fallback, omitted arrays, numeric strings or NaN (invalid JSON) being accepted.

## 11. Errors, HTTP status codes and query behavior

### Actual and recommended compatible error format

CURRENT client reads only a top-level string `message`; all normal MSW failures use it:

```json
{ "message": "Для прогноза уже создан наряд WO-2026-0931." }
```

**Recommended compatible extension**, not yet consumed structured metadata:

```json
{
  "message": "Для прогноза уже создан наряд WO-2026-0931.",
  "code": "TICKET_ALREADY_EXISTS",
  "details": { "ticket_id": "WO-2026-0931" }
}
```

Keep top-level message. An `{"error":{"code":"...","message":"..."}}`-only envelope is incompatible with meaningful current UI messages: frontend would show generic HTTP status. Machine code names above are proposed, not current ApiError codes. Current ApiError.code is locally assigned HTTP_ERROR / NETWORK_ERROR / INVALID_RESPONSE; backend code/details are ignored. Field-level server error mapping is not implemented; message is displayed as a general error.

No HTTP response/network failure → status 0 / NETWORK_ERROR locally (not a backend status). Successful non-JSON response → INVALID_RESPONSE. AbortSignal cancellation is rethrown, not translated into network failure. GET hooks forward signal; apiSend supports a signal, but current mutation hooks do not pass one. A cancelled client request does not prove a server mutation was rolled back.

### Status matrix

“Mock” lists actual normal handlers or explicit mock scenarios. 500 is a production server-error recommendation for every endpoint, not a currently synthesized happy-path fixture. 503 scenarios are test controls; real temporary unavailability may use 503 with the same message shape.

| Method/path                       | CURRENT success | CURRENT mock failure                                                          | Recommended production additions / unresolved                      |
| --------------------------------- | --------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------------ |
| GET /system                       | 200             | none                                                                          | 500/503 infrastructure failure                                     |
| GET /dashboard/summary            | 200             | 503 via browser override                                                      | 500/503; not 404 merely because counts are zero                    |
| GET /objects                      | 200 array       | 503 scenario                                                                  | 500/503                                                            |
| GET /objects/status-summary       | 200 array       | 503 scenario                                                                  | 500/503; scope validation only after agreement                     |
| GET /objects/:id                  | 200             | 404 unknown                                                                   | 400 malformed numeric ID; 500/503                                  |
| GET /objects/:objectId/topology   | 200             | 404 unknown object, 503 scenario                                              | 400 malformed ID; 500                                              |
| GET /predictions                  | 200 array       | 503 scenario                                                                  | 400 invalid known filters; 500; no-match remains []                |
| GET /predictions/:predictionId    | 200             | 404 unknown                                                                   | 500/503                                                            |
| GET /sensors/:channelId/telemetry | 200             | 404 nonnumeric channel, 503 scenario                                          | DRAFT: 404 unknown valid channel; 400 invalid window/limit; 500    |
| GET /tickets                      | 200 array       | 503 scenario                                                                  | 400 invalid known filters; 500                                     |
| GET /tickets/:ticketId            | 200             | 404 unknown                                                                   | 500/503                                                            |
| POST /tickets                     | 201             | 400 malformed/unexpected body; 422 text length; 404 prediction; 409 duplicate | 422 full schema/context validation; 404 unknown manual object; 500 |
| PATCH /tickets/:ticketId/status   | 200             | 400 malformed/unexpected body; 404 ticket; 409 forbidden/unknown transition   | Agree 422 for invalid enum/body versus current 409; 500            |
| GET /analytics/summary            | 200             | 400 invalid range; 503 via browser override                                   | 500/503                                                            |

No 401/403 auth policy is specified yet. No 404 for ordinary empty list, known object without topology, known channel with no measurements or analytics without formed aggregates. Unknown-channel 404 is still DRAFT: mock currently masks it as empty. Prediction/object/ticket detail 404 already has dedicated UI behavior; telemetry failure stays local to the telemetry section.

### Cache and refresh

QueryClient: staleTime 60s, gcTime 5min, refetch on window focus, one retry for network/server failures and none for 4xx. System has 60s polling; other queries use normal query/refetch behavior, not WebSocket/SSE. Mutation defaults do not introduce automatic retry. Analytics keys include range and retain old data while fetching; telemetry keys include channel and semantic range. Server must not use cached list pages as a substitute for an aggregate.

## 12. CONTRACT ISSUE register and required decisions

These findings are recorded without changing frontend behavior. “Mock defect” means do not reproduce it as production logic; it does not claim current frontend has already been fixed.

| ID    | Evidence and actual behavior                                                                                                                                                                                                                                  | Discrepancy / backend consequence                                                                                                                                          |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CI-01 | Frontend contract §10 inventory and query-key list omit Analytics; §18 and hooks/handlers implement it. §11 lists eight browser scripts while package.json has nine.                                                                                          | Use all 14 endpoints here; older inventory is incomplete.                                                                                                                  |
| CI-02 | Frontend contract §11 still says mutations/workflows absent and prediction detail shell; §§12/13/15 contain shell wording; §16 says Task 05 not started. Current pages and §§16–18 implement investigation, ticket mutations and analytics.                   | Historical limitations are stale; do not omit these APIs. Old TelemetrySample/ObjectDto detail were replaced.                                                              |
| CI-03 | toObjectStatusList filters active > 0; PredictionsPage requests operational and toOperationalQueue filters low/unsupported. Documented later limitations agree.                                                                                               | Full registries are DRAFT, not achieved merely by returning more rows. Requires frontend coordination, not just a backend scope flag.                                      |
| CI-04 | Python computes clamped rounded 100*(1-p); TEMP-001 mock uses p=.46, ИТС=28; OW-004 uses 54. Python unsupported fallback uses .01/low/99 and lacks prediction_supported/full DTO.                                                                             | Confirm ML model/version policy; wrapper must return nullable unsupported fields and ready outputs. Never infer risk or ИТС in frontend.                                   |
| CI-05 | /objects mock has 101/102; status/detail/workspace also reference 201–208. Detail and topologies exist for objects absent from catalogue.                                                                                                                     | Catalogue is demo-incomplete. Production must use consistent IDs/names and include selectable objects.                                                                     |
| CI-06 | createTicket manual branch takes body.object_id but always MANUAL_OBJECT_NAME = объект Фита. Form selects catalogue 101/102.                                                                                                                                  | Manual ticket ID/name mismatch is a mock defect; resolve name from the actual object.                                                                                      |
| CI-07 | Mock validates trimmed text lengths, prediction existence/duplicate and status transitions; not manual object existence, assignee type or full schema. Linked body.object_id mismatch is ignored.                                                             | Server must validate payload/references; agree mismatch and invalid-enum status policy. Do not treat mock permissiveness as authorization/security rules.                  |
| CI-08 | Unknown numeric telemetry channel yields 200 emptyTelemetry, nonnumeric yields 404; invalid windows/defaults are permissive.                                                                                                                                  | Cannot distinguish unknown from known-empty today. Agree 404 and request validation/storage semantics.                                                                     |
| CI-09 | Frontend contract §17 says four completed tickets but only three completed_at values. tickets.ts seeds provide all four.                                                                                                                                      | Actual complete records have four timestamps; frontend declaration is a documentation typo.                                                                                |
| CI-10 | Dashboard snapshot has 12 draft + 19 approved; ticket store and Analytics have 5 + 4. Analytics object 203 high=7 versus detail/status high=8; object 205 high versus detail critical. Dashboard critical total 8 versus nine critical across status objects. | Separate demo aggregates are not a coherent production dataset. Agree scope, snapshot timing and consistent aggregate sources; do not copy these numerical discrepancies.  |
| CI-11 | Create invalidates tickets + predictions; status change invalidates tickets only. Dashboard/Analytics static aggregates are not recomputed or immediately invalidated.                                                                                        | Production aggregate freshness can lag until refetch; server source consistency alone does not guarantee immediate UI refresh. Coordinate separately.                      |
| CI-12 | scenarios.ts can return [] for dashboard empty and topology-shaped data for a detail empty override; production handlers do not use these as valid detail/summary responses.                                                                                  | Test overrides are not wire-schema authority; follow DTO objects and documented valid empty forms.                                                                         |
| CI-13 | Rejection confirmation text says a new ticket will be needed; duplicate rule rejects all second tickets for the same prediction, including rejected/completed.                                                                                                | Current lifecycle wins: no replacement for that prediction. Agree new prediction/manual ticket policy or future lifecycle revision; do not silently relax uniqueness.      |
| CI-14 | CreateTicketDrawer calls usePrediction(predictionId ?? '') even with the drawer closed or in manual mode; usePrediction has no enabled guard. Resulting /predictions/ request may occur incidentally alongside /objects.                                      | Not a fifteenth endpoint or an empty-ID resource contract. Backend should handle it safely as list/trailing-slash normalization or 404; future frontend guard is separate. |

Other known differences are intentional: object coverage is formatted from supplied channel counts while dashboard/analytics return percentages; operational mock and workspace prediction IDs represent different datasets; list ordering may be changed locally. There is no discovered extra product endpoint outside the inventory, nor a documented endpoint that requires a removed runtime API (only superseded types/hooks and stale descriptions).

## 13. PROPOSED / FUTURE — do not implement as a replacement for CURRENT

### Full registries, pagination and sorting proposal

Future full predictions must include supported low/medium/high/critical and unsupported records. Suggested coordinated shape, **not compatible with today's array-consuming hook**:

```http
GET /api/v1/predictions?page=1&page_size=50&sort=generated_at&order=desc
```

```json
{ "items": [], "page": 1, "page_size": 50, "total": 0 }
```

This is a valid empty-page example. A populated page carries full PredictionDto items; total describes the complete filtered population.

| Endpoint/area                        | Parameter            | Type               | Required                      | Status           | Meaning                                           |
| ------------------------------------ | -------------------- | ------------------ | ----------------------------- | ---------------- | ------------------------------------------------- |
| Predictions / future paginated lists | page                 | integer >=1        | proposed default 1            | PROPOSED         | Page number                                       |
| Predictions / future paginated lists | page_size            | integer 1..200     | proposed default 50           | PROPOSED         | Bounded result size, limits to agree              |
| Predictions                          | sort                 | allowlisted field  | proposed default generated_at | PROPOSED         | Server ordering before paging                     |
| Predictions                          | order                | asc or desc        | proposed default desc         | PROPOSED         | Direction; stable prediction_id tie-break         |
| Predictions                          | maintenance_urgency  | MaintenanceUrgency | no                            | PROPOSED         | Filter not currently sent                         |
| Predictions                          | prediction_supported | boolean            | no                            | PROPOSED         | Include/exclude unsupported explicitly            |
| Predictions                          | search               | string             | no                            | PROPOSED         | Agree searched fields/collation                   |
| Objects status                       | scope                | all or active      | to agree                      | PROPOSED / DRAFT | Zero-active inclusion; adapter migration required |
| Objects status                       | risk_level, search   | RiskLevel, string  | no                            | PROPOSED         | Current registry controls are local               |

Define total after filters and before paging. Agree allowlisted sort fields, null ordering, Russian name collation, stable tie-breakers and snapshot consistency under concurrent updates; cursor paging may be preferable for evolving history. Never apply current local sorting/filtering only to one backend page and present it as a full-registry result. Existing keys, adapters, UI counts and tests need coordinated migration. Similar pagination for tickets/object catalogue is future, not an existing response wrapper. No exact new path or version is committed here.

### Other FUTURE areas

Authentication/authorization: not defined; no invented JWT, login or refresh-token endpoints. Realtime: no WebSocket/SSE endpoint or event schema; query/refetch remains current. Staff directory, ticket history/rejection reason/attachments and direct prediction review mutations are not required by this UI. They need separate scope and DTO decisions.

## 14. Traceability and endpoint-by-endpoint verification

Paths below are repository-relative links. Every CURRENT endpoint has a DTO, adapter (or inline mapping), hook and MSW handler. Shared [hooks](../frontend/src/api/queries/hooks.ts), [keys](../frontend/src/api/queries/keys.ts), [HTTP client](../frontend/src/api/client/http.ts) and [handlers](../frontend/src/api/mocks/handlers.ts) were audited together.

| Endpoint                          | DTO file                                                      | Adapter                                                                                                                             | Hook                   | Handler / fixture                                                                    |
| --------------------------------- | ------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------- | ---------------------- | ------------------------------------------------------------------------------------ |
| GET /system                       | [resources](../frontend/src/api/dto/resources.ts)             | Inline mapping in hook                                                                                                              | useSystem              | GET system / inline status fixture                                                   |
| GET /dashboard/summary            | [dashboard](../frontend/src/api/dto/dashboard.ts)             | [toDashboardSummary](../frontend/src/api/adapters/dashboard.ts)                                                                     | useDashboardSummary    | GET dashboard/summary / [dashboard fixture](../frontend/src/api/mocks/dashboard.ts)  |
| GET /objects                      | [resources](../frontend/src/api/dto/resources.ts)             | [toObject](../frontend/src/api/adapters/resources.ts)                                                                               | useObjects             | GET objects / [fixtures](../frontend/src/api/mocks/fixtures.ts)                      |
| GET /objects/status-summary       | [object-status](../frontend/src/api/dto/object-status.ts)     | [toObjectStatusList](../frontend/src/api/adapters/object-status.ts)                                                                 | useObjectStatusSummary | GET objects/status-summary / [operational](../frontend/src/api/mocks/operational.ts) |
| GET /objects/:id                  | [object-detail](../frontend/src/api/dto/object-detail.ts)     | [toObjectDetail](../frontend/src/api/adapters/object-detail.ts)                                                                     | useObjectDetail        | GET objects/:id / [object-workspace](../frontend/src/api/mocks/object-workspace.ts)  |
| GET /objects/:objectId/topology   | [object-topology](../frontend/src/api/dto/object-topology.ts) | [toObjectTopology](../frontend/src/api/adapters/object-topology.ts)                                                                 | useObjectTopology      | GET topology / objectTopologyFixture                                                 |
| GET /predictions                  | [prediction](../frontend/src/api/dto/prediction.ts)           | [toPrediction](../frontend/src/api/adapters/prediction.ts), [toOperationalQueue](../frontend/src/api/adapters/operational-queue.ts) | usePredictions         | GET predictions / fixtures + operational + object-workspace                          |
| GET /predictions/:predictionId    | [prediction](../frontend/src/api/dto/prediction.ts)           | toPrediction                                                                                                                        | usePrediction          | GET predictions/:id / same sources + applyTicketState                                |
| GET /sensors/:channelId/telemetry | [telemetry](../frontend/src/api/dto/telemetry.ts)             | [toTelemetrySeries](../frontend/src/api/adapters/telemetry.ts)                                                                      | useSensorTelemetry     | GET sensor telemetry / [telemetry fixture](../frontend/src/api/mocks/telemetry.ts)   |
| GET /tickets                      | [ticket](../frontend/src/api/dto/ticket.ts)                   | [toTicket](../frontend/src/api/adapters/ticket.ts)                                                                                  | useTickets             | GET tickets / [listTickets](../frontend/src/api/mocks/tickets.ts)                    |
| GET /tickets/:ticketId            | ticket                                                        | toTicket                                                                                                                            | useTicket              | GET ticket / findTicket                                                              |
| POST /tickets                     | ticket: CreateTicketRequestDto → TicketDto                    | toTicket                                                                                                                            | useCreateTicket        | POST tickets / createTicket                                                          |
| PATCH /tickets/:ticketId/status   | ticket: UpdateTicketStatusRequestDto → TicketDto              | toTicket                                                                                                                            | useUpdateTicketStatus  | PATCH status / updateTicketStatus                                                    |
| GET /analytics/summary            | [analytics](../frontend/src/api/dto/analytics.ts)             | [toAnalyticsSummary](../frontend/src/api/adapters/analytics.ts)                                                                     | useAnalyticsSummary    | GET analytics/summary / [analyticsFixtures](../frontend/src/api/mocks/analytics.ts)  |

Domain models are in [domain](../frontend/src/domain); time/labels in [formatters](../frontend/src/utils/formatters.ts). Further evidence: [ticket form validation](../frontend/src/pages/tickets/ticket-form-model.ts), [ticket transitions](../frontend/src/domain/ticket/types.ts), [ticket source/form](../frontend/src/pages/tickets/CreateTicketDrawer.tsx), [ML module](../backend_app_ml_predictor.py).

## 15. Backend acceptance checklist

- [ ] All 14 required routes use the exact wire shapes, bare arrays/objects and JSON responses.
- [ ] Timestamps include UTC/offset; completed_today uses Europe/Moscow.
- [ ] Numeric IDs, nullable fields and enums match DTOs; missing is not silently used for null.
- [ ] Unsupported ML returns the nullable ML block, never 1% / low / ИТС 99.
- [ ] Risk and urgency are backend-provided; 46% ANALOG_TEMP can be critical.
- [ ] ИТС follows the agreed ML version and is returned ready; frontend need not calculate it.
- [ ] Object and segment risk/counts are backend aggregates; numeric pikets match prediction locations.
- [ ] Catalogue IDs/names and prediction/ticket references are consistent.
- [ ] Dashboard is a separate aggregate; no client-list reconstruction.
- [ ] Duplicate ticket creation is atomically rejected with 409, including after terminal statuses.
- [ ] Ticket transitions and input validation are enforced server-side.
- [ ] Prediction list/detail reflect ticket_id and ticket_created consistently after creation.
- [ ] Manual ticket resolves the correct object name; no fixed demo name.
- [ ] Telemetry distinguishes numeric/state, preserves null gaps and explicit event flags.
- [ ] Unknown channel vs known-empty, retention, bounds and downsampling are agreed.
- [ ] Analytics returns ready history/distributions/ranking/coverage from an agreed source.
- [ ] Aggregates share documented scope/freshness; no fabricated MTTR/SLA/model-quality metrics.
- [ ] Full-registry scope and paging migration are agreed before changing list response shapes.
- [ ] Error message stays top-level; HTTP codes match the agreed matrix.
- [ ] CORS/base URL/mocks=false are configured for deployment; auth is not assumed to exist.

## Recommended Implementation Order

1. **Phase 1 — coherent catalogue and read backbone:** /system, /objects, /objects/:id, PredictionDto production wrapper with explicit support, /predictions and /predictions/:predictionId, /objects/status-summary and /dashboard/summary. Agree active population/full-registry scope first; a detail route is needed immediately for list navigation and ticket sources.
2. **Phase 2 — investigation:** object topology and telemetry. Implement real object/channel references, gaps and unknown/empty behavior; agree sampling, retention and bounds before storage work. Keep prediction detail functional from Phase 1.
3. **Phase 3 — persisted work orders:** ticket list/detail, create and status mutations together, with transactional duplicate/transition rules and synchronized prediction links. Resolve manual-object and rejection/replacement issues explicitly.
4. **Phase 4 — analytics:** agree history store, snapshot coherence and ranking, then serve the consumed aggregate DTO/ranges; no new quality/MTTR/SLA metrics.
5. **Phase 5 — separately scoped extensions:** coordinated pagination/filtering/sorting migration, auth/permissions and realtime. None is implied by the current frontend API.

Do not start backend implementation as part of this audit. FRONTEND_CONTRACT_V2.md remains the UI/UX source of truth; this document records backend obligations, actual consumption and the decisions that still require agreement.
