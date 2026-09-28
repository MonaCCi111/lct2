# DOLOS FRONTEND FINAL HANDOFF REPORT

This report records the repository state after the complete frontend gate and the first push of
`frontend-dolos`. The audited implementation baseline is
`ff357bc3494840a1a6cc5c78e25bc59e86690829`; the documentation commit containing this file follows
that implementation commit.

## 1. Git state

- Repository: `C:\Users\Pc\Desktop\лцт`
- Remote: `origin = https://github.com/MonaCCi111/lct2.git`
- Working branch: `frontend-dolos`
- Audited implementation HEAD: `ff357bc3494840a1a6cc5c78e25bc59e86690829`
- Initial remote verification: local HEAD and `origin/frontend-dolos` both pointed to `ff357bc`.
- Working tree was clean before this document was created.
- `main` was not checked out, merged, rebased, reset, or otherwise changed.

## 2. Frontend stack

Versions below come from `frontend/package.json`:

| Area                 | Technology                                                                                                                                                                  |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Framework            | React `^19.3.0`, React DOM `^19.3.0`                                                                                                                                        |
| Language             | TypeScript `^7.0.2`, strict project build through `tsc -b`                                                                                                                  |
| Build/dev server     | Vite `^8.3.0`, `@vitejs/plugin-react ^6.1.1`                                                                                                                                |
| Routing              | React Router DOM `^7.18.4`                                                                                                                                                  |
| Server state         | TanStack React Query `^5.103.1`                                                                                                                                             |
| Mocking              | MSW `^2.15.0` in browser and Node tests                                                                                                                                     |
| Charts               | Recharts `^3.10.1`                                                                                                                                                          |
| UI primitives        | Radix Dialog, Dropdown Menu, Tabs, Tooltip; Lucide React icons                                                                                                              |
| Unit/component tests | Vitest `^5.0.1`, jsdom `^30.1.0`, Testing Library React `^16.3.3`, jest-dom `^7.0.1`                                                                                        |
| Browser tests        | Playwright `^1.63.0`, using installed Edge by default                                                                                                                       |
| Formatting           | Prettier `^3.9.8`                                                                                                                                                           |
| Styling              | Tailwind CSS `^4.3.3` is imported through Vite, with the product UI primarily expressed through custom CSS, design tokens, component classes, and page-specific stylesheets |

The package requires Node.js 24 or newer.

## 3. How to run locally

Windows PowerShell:

```powershell
cd "C:\Users\Pc\Desktop\лцт\frontend"
npm.cmd ci
npm.cmd run dev
```

The default development URL is `http://127.0.0.1:5173`. Use `npm.cmd` when PowerShell execution
policy blocks the `npm.ps1` shim.

Mock development needs `VITE_ENABLE_MOCKS=true`; `.env.example` supplies this local example. For a
production build and local preview:

```powershell
npm.cmd run build
npm.cmd run preview
```

Vite preview normally listens on `http://127.0.0.1:4173`. Environment values are read at Vite
startup/build time, so restart the dev server or rebuild after changing them.

## 4. Environment variables

The committed `.env.example` and client config define:

| Variable               | Purpose                            | Runtime fallback                          | Behavior                                                                                                 |
| ---------------------- | ---------------------------------- | ----------------------------------------- | -------------------------------------------------------------------------------------------------------- |
| `VITE_API_BASE_URL`    | v1 operational API base            | `/api/v1`                                 | All legacy HTTP requests are relative to this value. `.env.example` uses `http://localhost:8000/api/v1`. |
| `VITE_API_V2_BASE_URL` | v2 historical review API base      | `http://localhost:8000/api/v2`            | All `src/api/v2` requests are relative to this value.                                                    |
| `VITE_ENABLE_MOCKS`    | Starts the shared v1/v2 MSW worker | disabled unless the exact value is `true` | `true` enables fixtures and `/foundation`; any other value uses HTTP and hides `/foundation`.            |

All `VITE_*` values are public browser configuration. Never store secrets in them. No auth/session
environment variable exists yet.

Browser scripts additionally accept `TEST_BASE_URL` and `BROWSER_CHANNEL`; these are test process
settings rather than product Vite variables.

## 5. Current routes

| Route                              | Purpose                                                                         |
| ---------------------------------- | ------------------------------------------------------------------------------- |
| `/`                                | Redirects to `/overview`.                                                       |
| `/overview`                        | Operational Center.                                                             |
| `/objects`                         | Operational object registry.                                                    |
| `/objects/:objectId`               | Object workspace.                                                               |
| `/predictions`                     | Operational prediction registry.                                                |
| `/predictions/:predictionId`       | Prediction investigation.                                                       |
| `/tickets`                         | Legacy v1 work-ticket registry and drawers.                                     |
| `/analytics`                       | Operational aggregate analytics.                                                |
| `/review`                          | Historical v2 dispatcher queue.                                                 |
| `/review/:draftId`                 | Historical draft/evidence/decision/work-order workspace.                        |
| `/review/work-orders`              | v2 work-order registry.                                                         |
| `/review/work-orders/:workOrderId` | v2 work-order detail.                                                           |
| `/foundation`                      | Component/foundation test bench, registered only when `VITE_ENABLE_MOCKS=true`. |

Unknown URLs render “Страница не найдена”. Production hosting must provide SPA fallback to
`index.html` for direct detail-route reloads while keeping `/api/*` routed to the backend.

## 6. Legacy `/api/v1` architecture

The operational/demo contour is:

```text
HTTP or MSW → wire DTO → adapter → domain model → TanStack Query → page model → React UI
```

The base URL comes from `VITE_API_BASE_URL`, with `/api/v1` as the code fallback. DTOs and adapters
live under `src/api`; domain types live under `src/domain`; query keys and hooks are centralized in
`src/api/queries`.

Main entities:

- `Prediction`: backend-owned probability, risk, urgency, ITS, factors and support state.
- `Object`: catalogue, status aggregates, detail, topology and related predictions.
- `Ticket`: legacy operational work item with create and status workflow.
- `Analytics`: ready-made aggregates for charts and ranked objects.
- `Telemetry`: numeric/state samples, events and range metadata.

The current v1 surface contains 14 method/path pairs documented in
`docs/BACKEND_API_CONTRACT_V1.md`, including system, dashboard, catalogue/status/detail/topology,
prediction list/detail, telemetry, ticket list/detail/create/status, and analytics summary.

## 7. `/api/v1` pages

### `/overview`

Shows a separate dashboard summary aggregate, operational prediction queue, object-status panel,
ticket counts, ML coverage and freshness. The queue supports text/object/risk/urgency filters,
keyboard row navigation and per-block refresh/error/stale behavior. Its fixed-height desktop
workspace uses internal scrolling. Data comes from `/dashboard/summary`, operational predictions,
object status, and system queries. Demo aggregates are separate fixture snapshots and are not fully
reconciled with every mock list.

### `/objects`

Shows the available object-status registry ordered by criticality, with search, risk filter,
coverage, counts and update time. Rows open `/objects/:objectId` by click or Enter. The scope is the
loaded active-object sample rather than a guaranteed complete production catalogue.

### `/objects/:objectId`

Combines object detail, summary, proportional topology, segment selection and object predictions.
Prediction filters and numeric piket filtering can be combined with topology selection. Detail,
topology and prediction data have independent states. The richer fixture exists mainly for object
203; the demo catalogue does not contain every referenced object consistently.

### `/predictions`

Shows the operational prediction registry with search, object/domain/risk/urgency/support filters,
sorting, reset, result count and keyboard navigation. It uses the operational sample, which filters
unsupported/low rows and is not a server-paginated complete registry.

### `/predictions/:predictionId`

Shows prediction context, ready risk/urgency/ITS values, factors, recommendation, technical data,
numeric or state telemetry, event markers, 6/24/48-hour ranges, and ticket handoff. Prediction and
telemetry fail independently. Telemetry fixtures are deterministic and do not define production
retention, downsampling, or unknown-channel policy.

### `/tickets`

Shows searchable/filterable legacy tickets, URL-driven detail/create drawers, manual creation,
creation from a prediction and transitions `draft → approved/rejected`, `approved → completed`.
The MSW store is mutable but resets on reload. It has known validation, manual-object naming,
aggregate invalidation and replacement-policy gaps described below.

### `/analytics`

Shows 24h/7d/30d aggregates: summary, risk timeline, urgency distribution, ticket status,
top-risk objects and ML-domain coverage. Range changes retain the previous result while loading and
support empty/error/stale states. Values are deterministic mock aggregates, not reconstructed in
React, but their snapshot is not fully coherent with every v1 fixture.

## 8. UI/UX state

- The visual system targets a compact industrial/enterprise control interface.
- Theme preference is `system`, `light`, or `dark`; it follows OS changes in system mode and is
  persisted when localStorage is available.
- Risk and urgency are independent backend semantics. They must never be derived from one another.
- Semantic color occupies small dots, markers, bars or restrained text rather than large filled
  pills. Critical/high/medium remain distinguishable through text plus shape/color.
- `/overview` is a fixed-height desktop operational workspace with internal panel/table scrolling.
- Urgency uses compact vertical markers, an increasing urgency scale, and tabular numeric values.
- Operational v1 timestamps require an explicit offset and render in `Europe/Moscow`, with `МСК`
  where full time is shown.
- Historical v2 source timestamps are a separate literal-time rule described below.
- Legacy names such as `объект Фита` are displayed as `объект θ`; the original Russian name remains
  searchable and available in titles/accessibility context. Do not apply this legacy mapping to
  arbitrary v2 catalogue names.
- Focus-visible, skip link, keyboard table navigation, accessible names, text labels alongside
  semantic colors, reduced motion and dialog focus handling are implemented.
- Desktop QA covers 1920×1080 and 1366×768 in both themes. Avoid changing column geometry,
  overview height, internal overflow, semantic indicators or focus behavior without rerunning the
  full browser suite.

## 9. `/api/v2` architecture

The parallel namespace is isolated in `frontend/src/api/v2`:

- `client`: base URL and HTTP/error normalization.
- `dto`: snake_case wire contracts.
- `domain`: UI-facing v2 models.
- `adapters`: lossless wire-to-domain mapping.
- `queries`: paths, query keys, hooks and mutations.
- `mocks`: fixtures, handlers, mutable decision and work-order stores.
- `utils`: literal historical timestamp presentation.

`/api/v1` and `/api/v2` intentionally coexist. V2 Draft is not a legacy Prediction and v2 WorkOrder
is not a v1 Ticket.

## 10. `/api/v2` semantics

- `score` is model-specific and displayed as a raw decimal. It is not failure probability, risk,
  urgency, or ITS.
- Historical source time is timezone-naive. It is displayed literally with no UTC, МСК, or browser
  `Date` conversion.
- Null ITS remains null and is displayed as unavailable; it never becomes zero.
- Approval is a human review decision. It does not confirm a physical incident, failure, or model
  ground truth.
- `source_alarm`/fixture `is_alarm` is source evidence, not a confirmed incident.
- `observed_status` is described as an observed event rather than a prediction.
- Server action timestamps such as decision/work-order creation must include an offset and use the
  operational Moscow formatter.

## 11. `/api/v2` endpoints implemented in frontend

| Endpoint                      | Client and models                     | Hook                       | MSW | UI usage                                         | Tests                                       |
| ----------------------------- | ------------------------------------- | -------------------------- | --- | ------------------------------------------------ | ------------------------------------------- |
| `GET /meta`                   | Meta DTO/domain/adapter               | `useV2Meta`                | yes | Historical data notice                           | adapter, hook, browser                      |
| `GET /objects`                | paged Object DTO/domain/adapter       | `useV2Objects`             | yes | filters and object names                         | adapter, hook, browser                      |
| `GET /objects/{id}`           | Object DTO/domain/adapter             | `useV2Object`              | yes | API foundation; no direct screen consumer yet    | hook 200/404                                |
| `GET /drafts`                 | paged Draft DTO/domain/adapter        | `useV2Drafts`              | yes | review queue                                     | adapter, filters/path, browser              |
| `GET /drafts/{id}`            | Draft DTO/domain/adapter              | `useV2Draft`               | yes | draft and linked work-order context              | encoded ID, browser                         |
| `GET /drafts/{id}/evidence`   | paged Evidence DTO/domain/adapter     | `useV2DraftEvidence`       | yes | draft evidence table                             | adapter, encoded ID, browser                |
| `GET /drafts/{id}/decisions`  | Decision DTO/domain/adapter           | `useV2DraftDecisions`      | yes | history and authoritative work-order eligibility | hook/store/browser                          |
| `POST /drafts/{id}/decisions` | DecisionRequest and Decision mappings | `useCreateV2DraftDecision` | yes | approve/reject form                              | validation, idempotency, 409, browser       |
| `GET /work-orders`            | paged WorkOrder DTO/domain/adapter    | `useV2WorkOrders`          | yes | v2 work-order registry                           | hook/store/browser                          |
| `POST /work-orders`           | WorkOrderRequest/WorkOrder mappings   | `useCreateV2WorkOrder`     | yes | explicit create form                             | guards, idempotency, duplicate 409, browser |
| `GET /work-orders/{id}`       | WorkOrder DTO/domain/adapter          | `useV2WorkOrder`           | yes | v2 work-order detail                             | hook/store/browser                          |

Exact fields, parameters, errors and parity notes are in `docs/API_V2_BACKEND_HANDOFF.md`.

## 12. Review workflow

`/review` is a historical queue with filters for review state, basis and object plus cursor-based
previous/next paging. It shows forecast and observed bases distinctly, raw model score, forecast
horizon when supplied, literal source time and current review state.

`/review/:draftId` shows contract context, nullable ITS, limitations, feature/source details,
independently loaded paged evidence, dispatcher action and append-only decision history. Queue rows
and deep links URL-encode colon-rich IDs.

## 13. Decision workflow

- Draft state is `pending`, `approved`, or `rejected`.
- Only pending drafts show the regular approve/reject controls.
- A non-empty reason is required on both paths.
- One stable `idempotency_key` is kept for retries of the same user attempt.
- Replaying the same key returns the same decision.
- Another regular decision after an existing decision returns 409; the frontend refreshes draft and
  history and shows a dedicated already-saved state.
- There is no silent overwrite.
- Decision history is append-only from the frontend perspective.
- Correction UI is not implemented because auth/elevated-role semantics remain upstream work.

## 14. Work-order workflow

The v2 flow is:

```text
Draft → approved Decision → explicit WorkOrder creation
```

Approval never creates a work order automatically. Creation requires the latest authoritative
approved Decision and no existing linked work order. The user supplies work type and description;
the request keeps a stable idempotency key. Pending/rejected drafts and duplicate work orders yield 409. Registry/detail routes are `/review/work-orders` and
`/review/work-orders/:workOrderId`.

V2 work orders and legacy `/tickets` remain separate stores and query namespaces. The v2 contract
does not yet define a work-order status enum, lifecycle transitions, or status mutation.

## 15. V1 versus V2 separation

| Layer     | Purpose                      | Data semantics                                                                            | UI                                                                                  |
| --------- | ---------------------------- | ----------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `/api/v1` | Operational/demo monitoring  | Legacy Prediction risk/probability/urgency/ITS, objects, telemetry, Tickets and analytics | `/overview`, `/objects`, `/predictions`, `/tickets`, `/analytics` and detail routes |
| `/api/v2` | Historical dispatcher review | Drafts, evidence, human decisions and explicit WorkOrders                                 | `/review` and its detail/work-order routes                                          |

Never adapt a Draft into legacy Prediction by inventing risk, urgency, probability or ITS. Never
cross-invalidate v1 Tickets and v2 WorkOrders.

## 16. Mock architecture

- One browser MSW worker combines v1 and v2 handler arrays.
- V1 uses deterministic fixtures plus a mutable in-memory Ticket store.
- V2 uses historical fixtures plus mutable Decision and WorkOrder stores.
- Stores reset on reload/test reset and are not persistence models.
- Mock-only `scenario=empty|error|slow` controls and browser override modules are test tools, not
  backend API requirements.
- V2 mocks do not fully implement all contract filters, historical `at` semantics, authorization,
  correction, validation, or pagination edge cases.
- The worker starts with `onUnhandledRequest: 'bypass'`; an unhandled request can reach the network
  in mock mode, so a missing handler is not a fixture fallback guarantee.
- In real mode the worker is not started and this app's previous worker registration is removed.

## 17. Real-mode behavior

With `VITE_ENABLE_MOCKS=false`:

- MSW does not start.
- V1 requests use `VITE_API_BASE_URL`.
- V2 requests use `VITE_API_V2_BASE_URL`.
- No fixture fallback occurs.
- Backend error envelopes and network failures produce visible UI error states.
- `/foundation` is not registered.

`npm.cmd run test:real` verifies both namespaces against a local HTTP stub, confirms the lack of
mock data/service-worker registration and checks visible v2 backend/network errors.

## 18. Testing baseline

The final pre-push run on `ff357bc` produced:

- `npm.cmd test`: 32 test files, 348 tests passed.
- `npm.cmd run typecheck`: passed.
- `npm.cmd run build`: passed; Vite production bundle completed.
- `npm.cmd run format:check`: passed.
- `npm.cmd run test:browser`: all ten browser scripts passed.
- `npm.cmd run test:real`: passed for v1 and v2 real HTTP behavior.

## 19. Browser coverage

The browser chain covers navigation, MSW, themes, tables, drawers and charts across the product.
Major page suites run dark/light at 1920×1080 and 1366×768. Coverage includes mouse and keyboard
navigation, focus/dialog behavior, responsive overflow, loading, error, empty, populated and stale
states, Moscow time under non-Moscow browser zones, the 46%-critical invariant, unsupported ML,
review semantics, decision/idempotency conflicts, explicit work-order creation, duplicate
protection and the absence of v1 ticket mutation from v2 flows.

Generated screenshots are local test artifacts under `frontend/test-results` and are ignored by
Git.

## 20. Backend handoff

`docs/API_V2_BACKEND_HANDOFF.md` is the current v2 implementation handoff. It contains:

- the 25-endpoint contract coverage matrix;
- the 11 frontend-ready endpoints and actual query parameters;
- required/nullable response expectations;
- error/status handling;
- cursor pagination;
- idempotency and mutation invariants;
- timestamp and score semantics;
- mock-versus-real differences;
- dependency-based backend implementation order and acceptance checklist.

## 21. Known upstream/integration gaps

- `forecast_horizon_hours` is present in forecast fixtures/integration guidance but absent from the
  formal Draft schema.
- `review_status` exists in fixtures while `review_state` is the canonical workflow field.
- Evidence fixtures use `is_alarm` while the formal field is `source_alarm`.
- WorkOrder status enum, lifecycle and mutation endpoints are not defined.
- Authentication/session transport and identity are not defined.
- Elevated role/permission behavior is not defined beyond expected 403 semantics.
- Decision correction exists in the contract but lacks frontend UI and complete auth policy.
- Live ingestion remains unavailable in the historical handoff data.
- A genuinely running `/api/v2` backend has not been confirmed; the last localhost probe refused
  connections and real-mode automation uses its own HTTP stub.

## 22. Open frontend technical debt

The CI-01…CI-14 inventory in `docs/BACKEND_API_CONTRACT_V1.md` was checked against the current
source. None was fully closed by the later v2 work, so all remain relevant to v1 integration:

| ID    | Current state                                                                                                                         |
| ----- | ------------------------------------------------------------------------------------------------------------------------------------- |
| CI-01 | `FRONTEND_CONTRACT_V2.md` has stale early inventory/query-key/browser-script counts even though later analytics sections exist.       |
| CI-02 | Older contract/README sections still describe missing workflows or detail shells that are now implemented.                            |
| CI-03 | Object and prediction registries still use active/operational subsets; full catalogue/list scope and server paging remain unresolved. |
| CI-04 | Legacy ML formula/module and v1 fixture ITS values remain inconsistent; frontend correctly does not derive ITS.                       |
| CI-05 | V1 object catalogue still omits IDs referenced by status/detail/workspace fixtures.                                                   |
| CI-06 | Manual mock Ticket creation still hardcodes `объект Фита` instead of resolving the submitted object ID.                               |
| CI-07 | V1 mock Ticket validation remains incomplete for object/reference/types and full schema validation.                                   |
| CI-08 | Telemetry unknown numeric channel versus known-empty behavior and range validation remain ambiguous/permissive.                       |
| CI-09 | The old frontend contract contains the completed-ticket count typo; actual seeds contain four completed timestamps.                   |
| CI-10 | Dashboard, analytics, ticket and object-status fixtures remain separate, numerically inconsistent snapshots.                          |
| CI-11 | Ticket mutations still do not immediately invalidate dashboard/analytics aggregates.                                                  |
| CI-12 | Mock scenario helpers can return shapes that are unsuitable as production wire examples.                                              |
| CI-13 | Rejected/completed legacy Tickets still block a replacement for the same prediction despite stale copy suggesting otherwise.          |
| CI-14 | `CreateTicketDrawer` still calls `usePrediction(predictionId ?? '')`; the v1 hook has no empty-ID `enabled` guard.                    |

Additional debt:

- `frontend/README.md`, early portions of `FRONTEND_CONTRACT_V2.md`, and historical task reports are
  useful records but are stale regarding v2, current route maturity and test counts. This report
  and the two API handoff documents should be used for current integration.
- Full runtime DTO schema validation is absent. The client validates HTTP success and JSON syntax,
  then TypeScript adapters assume the declared shape.
- Large registries are not virtualized and v1 list paging is unresolved.
- V2 work-order list fetches linked Draft details per visible row to display decision information.

## 23. Git history summary

Significant frontend commits on `frontend-dolos`:

| Hash      | Message                                                              |
| --------- | -------------------------------------------------------------------- |
| `ff357bc` | `chore(frontend): stabilize api v2 integration contract`             |
| `25ef132` | `feat(frontend): add v2 work order workflow`                         |
| `fa47213` | `feat(frontend): add dispatcher draft decisions`                     |
| `ddb946b` | `feat(frontend): add historical review queue`                        |
| `44e5132` | `feat(frontend): add api v2 read-only foundation`                    |
| `3af5869` | `ux(frontend): make the urgency scale rise and show its unlit steps` |
| `ea74a28` | `ux(frontend): sharpen severity colors and urgency markers`          |
| `491ecc1` | `ux(frontend): refine theme palette and operational indicators`      |
| `4ca1ef5` | `ux(frontend): refine operational clarity and navigation`            |
| `5ae7fa0` | `polish(frontend): sharpen operational reading across registries`    |
| `6604bbe` | `feat(frontend): implement analytics workspace`                      |
| `6b2f4f5` | `feat(frontend): implement ticket workflow`                          |
| `b206571` | `feat(frontend): implement prediction investigation`                 |
| `ce2dfa1` | `chore(frontend): integrate registry features`                       |
| `b7466ee` | `feat(frontend): implement predictions registry`                     |
| `0a821e5` | `feat(frontend): implement objects registry`                         |
| `ba2f5a4` | `feat(frontend): implement object workspace`                         |

## 24. Branch strategy

`frontend-dolos` is the current frontend working branch. Local `main` has a separate unrelated Git
history: `git merge-base frontend-dolos main` returns no merge base. Do not automatically merge the
branches or use `--allow-unrelated-histories`. The team must decide the canonical branch and the
intended import/integration method explicitly.

## 25. What not to do

- Do not merge `main` automatically or use unrelated-history merge as a convenience.
- Do not force-push or rewrite `frontend-dolos` history.
- Do not derive risk, urgency, probability or ITS from v2 score.
- Do not timezone-convert historical source timestamps.
- Do not replace v1 `/tickets` with v2 WorkOrders without a product/API decision.
- Do not mix v1 and v2 DTOs, query keys, stores or invalidation.
- Do not remove the mock contour until the real backend and integration environment are available.
- Do not copy known MSW permissiveness or fixture inconsistencies into production backend rules.

## 26. Recommended next frontend tasks

### HIGH

- Connect `VITE_API_V2_BASE_URL` to a genuinely running backend and run a live read/write smoke in
  an authorized integration environment.
- Validate real responses against the handoff, including pagination, 400/404/409/422, idempotency,
  colon-rich IDs, CORS and SPA deep links.
- Fix only confirmed contract mismatches, beginning with schema alignment for forecast horizon and
  alarm/review fields.

### MEDIUM

- Add decision-correction UI after auth/session and elevated-role contracts are final.
- Add work-order lifecycle UI only after status enum and mutation endpoints are published.
- Address the v2 work-order list's per-row Draft fetch if backend latency makes it material.

### LOW

- Add replay UI when its product workflow is defined.
- Add v2 analytics when backend aggregates and semantics are agreed.
- Reconcile or archive stale README/contract/task-report sections and resolve the v1 CI inventory.

## 27. Final runbook

### Mock development

```powershell
cd "C:\Users\Pc\Desktop\лцт\frontend"
$env:VITE_ENABLE_MOCKS = "true"
npm.cmd run dev
```

### Production build

```powershell
cd "C:\Users\Pc\Desktop\лцт\frontend"
npm.cmd ci
$env:VITE_ENABLE_MOCKS = "false"
npm.cmd run build
npm.cmd run preview
```

### Real backend mode

```powershell
cd "C:\Users\Pc\Desktop\лцт\frontend"
$env:VITE_ENABLE_MOCKS = "false"
$env:VITE_API_BASE_URL = "http://localhost:8000/api/v1"
$env:VITE_API_V2_BASE_URL = "http://localhost:8000/api/v2"
npm.cmd run dev
```

Replace the two URLs with the integration deployment when available. CORS must allow the frontend
origin. Do not put tokens or credentials in `VITE_*` variables.

### Tests

```powershell
cd "C:\Users\Pc\Desktop\лцт\frontend"
npm.cmd test
npm.cmd run typecheck
npm.cmd run build
npm.cmd run format:check

# Start mock dev server on 127.0.0.1:5173 in another terminal first:
npm.cmd run test:browser

# Starts its own Vite instance and local HTTP stub:
npm.cmd run test:real
```
