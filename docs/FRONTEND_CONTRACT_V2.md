# Dolos — Frontend Contract V2

Актуальная frontend-спецификация. Этот файл — **source of truth для последующих задач**: архитектура, визуальные ограничения, доменная семантика, API-контракты и правила времени. README описывает запуск и проверку, но не переопределяет этот контракт. Изменения требований нужно отражать здесь вместе с кодом и тестами.

Состояние: реализованы Task 01 (Frontend Foundation), Task 02 (`/overview` — Operational Center), Task 03 (`/objects/:objectId` — Object Workspace), Objects Registry (`/objects`), Predictions Registry (`/predictions`), Task 04 (`/predictions/:predictionId` — Prediction Investigation), Task 05 (`/tickets` — наряды) и Task 06 (`/analytics` — Analytics). Основной рабочий цикл замкнут: риск → прогноз → расследование → создание наряда → обработка наряда. Реестры разрабатывались параллельно в отдельной ветке и внесены controlled integration поверх Task 03. Analytics использует отдельные mock-агрегаты; production/backend integration не начата.

## 1. Назначение и границы текущего этапа

Dolos — система предиктивного мониторинга инженерной инфраструктуры, рабочий инструмент диспетчера. На текущем этапе реализованы application shell, routing, design tokens, reusable primitives, domain types, API client, DTO adapters, TanStack Query и mock API.

Маршрут `/analytics` реализован как operational analytics workspace: отдельный агрегат, три периода, динамика рисков, распределения срочности и статусов нарядов, приоритетные объекты и ML-покрытие.

Task 02 разрешает подключить Dashboard Summary к `/overview` в рамках спецификации раздела 12. Task 03 добавляет Object Workspace в рамках раздела 13. Разделы 14 и 15 описывают Objects Registry и Predictions Registry, раздел 16 — Prediction Investigation, раздел 17 — наряды, раздел 18 — Analytics. Существующая архитектура сохраняется.

## 2. Стек и архитектура

- React, TypeScript strict, Vite, React Router, TanStack Query, Tailwind CSS, Lucide React, Recharts, MSW.
- Node.js 24+, версии зависимостей закреплены lockfile.
- Headless UI допустим для поведения сложных controls; текущая реализация использует Radix для tooltip, dropdown, tabs и drawer. Стили собственные, без default shadcn styling.
- `any` без крайне веской причины запрещён. DTO, domain model и UI model разделены.
- Поток данных: HTTP → DTO → adapter → domain → UI model → presentation component.
- Fetching находится в `api/queries`, URL задаётся в централизованном client. Компоненты не содержат API URLs и не получают DTO напрямую.
- Компоненты небольшие; mappings и formatters общие; без глубокого prop drilling и дублирования бизнес-логики.

```text
frontend/src/
├── app/              App.tsx, layouts, providers, router
├── api/              client, dto, adapters, queries, mocks
├── domain/           prediction, object, telemetry, ticket, dashboard
├── components/       ui, data-display, navigation, feedback
├── pages/            overview, objects, object-workspace, predictions,
│                     prediction-investigation, tickets, analytics, foundation
├── styles/           tokens.css, globals.css
└── utils/            formatters.ts
```

## 3. Routes и shell

| Route                        | Назначение                                                  |
| ---------------------------- | ----------------------------------------------------------- |
| `/`                          | Redirect на `/overview`                                     |
| `/overview`                  | Оперативный центр: summary, очередь рисков, объекты         |
| `/objects`                   | Objects Registry: реестр объектов с риском и ML-покрытием   |
| `/objects/:objectId`         | Object Workspace: состояние, топология по пикетам, прогнозы |
| `/predictions`               | Predictions Registry: операционный реестр прогнозов         |
| `/predictions/:predictionId` | Prediction Investigation: телеметрия, факторы, рекомендация |
| `/tickets`                   | Журнал нарядов; `?ticketId=` и `?predictionId=` открывают drawer |
| `/analytics`                 | Аналитика                                                   |
| `/foundation`                | Технический стенд компонентов и fixtures, только mock mode  |
| Неизвестный route            | Экран «Страница не найдена»                                 |

Sidebar: DOLOS, Оперативный центр, Объекты, Прогнозы, Наряды; отделённая Аналитика; внизу Состояние системы и Профиль. Topbar: breadcrumbs, состояние API, timestamp последнего ответа, profile control. Состояние системы и профиль открываются в drawer. Профиль пока локальный, авторизация не подключена.

## 4. Визуальная система

Modern Enterprise UI / Industrial Operations Workspace: строгий, утилитарный, корпоративный, минималистичный, информационно плотный desktop-интерфейс для многочасовой работы. Linear, Datadog, Sentry, Grafana и SCADA — ориентиры качества, не шаблоны для копирования.

Запрещены neon/cyberpunk, glow, glassmorphism, blur/translucent panels, любые декоративные gradients, glowing borders, гигантские KPI cards, радиусы 20 px+, floating objects, blobs, emoji, AI brain icons, sparkles, декоративные иллюстрации, excessive shadows, page entrance/flashy animations, marketing landing page styling и декоративные элементы без функции.

Базовые tokens:

```css
--bg-app: #18191d;
--bg-surface: #202226;
--bg-surface-elevated: #25282d;
--bg-hover: #2a2d32;
--border-subtle: #30333a;
--border-default: #383c43;
--text-primary: #e7e8ea;
--text-secondary: #a5a9b0;
--text-muted: #757a82;
```

Risk и status colors сдержанные, назначение цвета — передача состояния. Все tokens централизованы в `styles/tokens.css`.

- Typography: 12/13/14/16/20/24 px; основной UI 13–14 px; weights 400/500/600; без заголовков 32–48 px.
- Числа: `font-variant-numeric: tabular-nums`.
- Spacing: 4/8/12/16/20/24/32 px; radius 4–8 px; panels padding 12–16 px.
- Sidebar 216–232 px (реализовано 224), topbar 48–56 px (52), controls 32–36 px (32), table rows 36–42 px (40).
- Приоритет 1920×1080, корректная работа от 1366 px. На малой ширине sidebar сворачивается (сейчас менее 1100 px → 64 px).
- Только функциональные transitions 100–200 ms, поддержка reduced-motion.
- Semantic buttons, visible focus, keyboard navigation, aria-label для icon-only controls, достаточный contrast. Pointer cursor только у интерактивных элементов.
- Иконки — Lucide React, без смешения библиотек.

Обязательные primitives: Button (primary/secondary/ghost/danger), IconButton, Input, Select, SearchInput, Badge, RiskBadge, UrgencyBadge, StatusBadge, Tooltip, Dropdown, Tabs, table primitives, Skeleton, EmptyState, ErrorState, Drawer, Panel, Divider, Breadcrumbs. Дополнительно реализованы LoadingState, StaleState, UnsupportedMlState и ErrorBoundary.

DataTable: плотные строки, header, hover, controlled sortable column API, alignment/numeric alignment, ellipsis с tooltip, sticky header, empty/loading/error states. Без необоснованных zebra stripes. Sorting может быть серверным: порядок задаёт caller.

### Task 02.1 — Semantic UI Polish

Публичные имена и props `RiskBadge`, `UrgencyBadge`, `StatusBadge` сохранены. Их визуальная семантика реализуется в общих компонентах и общих стилях, а не локально на OverviewPage.

- Risk: нейтральный текст 12 px / 500 и dot 6 px; semantic color только у dot, без background и outline capsule.
- Urgency: нейтральный текст 12 px / 500, tabular numerals; слева marker 2×14 px с radius 1 px, окрашенный по urgency. Без filled pill.
- Dot/marker декоративны (`aria-hidden`); текст состояния всегда доступен независимо от цвета.
- Workflow status: нейтральный subtle background, border 1 px, radius 4 px, текст 12 px / 500. Без ярких capsules.
- Table body 13 px / 400–500; header 12 px / 500; summary labels 12 px / 500, числа 22 px / 500. Critical summary может сохранять красный marker/число; остальные значения нейтральны.
- Selected urgency filter: neutral elevated surface, border и primary text; без semantic color.
- Layout, геометрия колонок, API, DTO, adapters, sorting, filter logic, mocks, routes и бизнес-тесты в Task 02.1 не меняются. Task 03 не начинается.

## 5. Время: обязательно Europe/Moscow

**Все операционные timestamps в UI отображаются в timezone `Europe/Moscow`, независимо от timezone браузера или ОС.** Это относится к generated/updated/created timestamps прогнозов, сводки, нарядов, телеметрии и состояния API, включая topbar и drawers.

- API передаёт ISO 8601 timestamp с `Z` или явным offset `±HH:MM`. Рекомендуемый транспорт — UTC. Domain adapter сохраняет исходный момент времени и не сдвигает дату вручную.
- `formatDateTime()` использует `Intl.DateTimeFormat('ru-RU', { timeZone: 'Europe/Moscow', ... })` с четырёхзначным годом и 24-часовым временем. Текущий формат полного времени: `20.09.2026, 18:42 МСК`.
- Пример: `2026-09-20T15:42:00Z` → `20.09.2026, 18:42 МСК`; `2026-09-20T22:30:00Z` → `21.09.2026, 01:30 МСК`.
- `formatDateTime` также принимает epoch milliseconds. `null`, невалидные значения и строки без timezone → `—`; нельзя интерпретировать неоднозначные значения через timezone браузера.
- `formatRelativeTime` работает с абсолютными моментами времени и их разницей. Для строк действует то же требование явного offset. Относительные подписи не требуют суффикса `МСК`.
- Не использовать `toLocaleString()` или `Intl.DateTimeFormat()` без явной operational timezone для отображения операционных данных. Не прибавлять вручную три часа к timestamp.
- Дневной показатель `completed_today` рассчитывается backend по календарному дню в `Europe/Moscow`, к которому относится snapshot `generated_at`.

Общие formatters: `formatProbability`, `formatHealthIndex`, `formatDateTime`, `formatRelativeTime`, `getRiskLabel`, `getUrgencyLabel`.

## 6. Доменная семантика ML

```ts
export type RiskLevel = "low" | "medium" | "high" | "critical";
export type MaintenanceUrgency =
  "NORMAL" | "PLANNED_24_48H" | "URGENT_6_24H" | "FLASH_1_6H";
export type ModelDomain =
  | "POWER_PHASE"
  | "ANALOG_TEMP"
  | "ANALOG_GAS"
  | "FIRE_SAFETY"
  | "HYDRO_MECHANICS";
export type TicketStatus = "draft" | "approved" | "rejected" | "completed";
export type ReviewStatus =
  "pending_review" | "acknowledged" | "rejected" | "ticket_created";
```

| Urgency        | UI label      |
| -------------- | ------------- |
| NORMAL         | Штатный режим |
| PLANNED_24_48H | 24–48 ч       |
| URGENT_6_24H   | 6–24 ч        |
| FLASH_1_6H     | 1–6 ч         |

Risk labels: low → Низкий; medium → Умеренный; high → Высокий; critical → Критический.

**Frontend никогда не вычисляет RiskLevel, MaintenanceUrgency или healthIndex из failureProbability.** У ML-доменов разные thresholds. Все три значения приходят готовыми с backend; UI не использует общий порог 70% и не выводит срочность из уровня риска.

`failure_probability` — доля 0..1, `health_index_its` — 0..100 или null. Unsupported sensor: `prediction_supported=false`, nullable ML-поля, UI «ML-анализ недоступен». Запрещено подменять unsupported значениями low / 1% / ИТС 99. Адаптер очищает ML-поля, факторы и рекомендацию даже при ошибочно присланных числах, если поддержка явно false.

## 7. Prediction DTO → domain

```ts
export interface PredictionDto {
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

`toPrediction()` переводит поля в camelCase; `prediction_id` → `id`, `health_index_its` → `healthIndex`, `piket_value` → `piketValue`; отсутствующий `parent_object_id` → null. Domain types находятся в `domain/prediction/types.ts`, UI model для стенда — отдельно в `pages/foundation/predictionRow.ts`.

`piket` — строка только для отображения (`ПК 88+50`, `ПК 96`). `piket_value` — число в пикетах (`88.5`, `96`), единственный источник для фильтрации, сортировки и сопоставления с участками топологии. Компоненты не парсят строку `piket`; для обратного преобразования числа в подпись используется общий `formatPiket()`. `null` и нечисловые значения приводятся к `null`; такой прогноз никогда не попадает в числовой диапазон участка. `piket_value` — физическое расположение канала, а не ML-выход: адаптер сохраняет его и при `prediction_supported=false`.

Обязательные mock fixtures:

| ID        | Model domain / sensor | Probability | Risk     | Urgency        |
| --------- | --------------------- | ----------- | -------- | -------------- |
| TEMP-001  | ANALOG_TEMP           | 0.46        | critical | FLASH_1_6H     |
| POWER-002 | POWER_PHASE           | 0.82        | critical | FLASH_1_6H     |
| HYDRO-003 | HYDRO_MECHANICS       | 0.63        | high     | URGENT_6_24H   |
| GAS-004   | ANALOG_GAS            | 0.41        | medium   | PLANNED_24_48H |
| FIRE-005  | FIRE_SAFETY           | 0.08        | low      | NORMAL         |
| DOOR-006  | КД Дверь; unsupported | null        | null     | null           |

У DOOR-006 `model_domain`, `health_index_its` и `lead_time_hours` также null. Шесть fixtures проверяют граничные сценарии; они не являются полной сетью мониторинга.

## 8. Dashboard Summary — отдельный backend aggregate

Endpoint: **`GET /dashboard/summary`**. Ответ — один объект, без дополнительного envelope. В текущем контракте filters/pagination не определены.

```ts
export interface DashboardSummaryDto {
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

- `generated_at` — момент формирования snapshot; `model_version` — версия модели, указанная backend.
- Все счётчики — неотрицательные целые числа. `coverage_percent` — готовый процент 0..100, **не доля 0..1**; нельзя умножать его на 100 через `formatProbability`.
- Backend определяет совокупность активных прогнозов и затронутых объектов. Frontend не реконструирует эти показатели по review status, локальным фильтрам или загруженным страницам списка.
- Risk counts и urgency counts — независимые backend-показатели. Не считать `critical === flash_1_6h` и не выводить одну группу из другой.
- `predictions.active` не обязан равняться сумме critical/high/medium: low не выделен отдельным полем. Аналогично NORMAL не выделен отдельным urgency-счётчиком.
- Summary нельзя вычислять из списка predictions в React-компонентах, hooks, adapters или mocks. Нельзя подменять summary локальным расчётом при ошибке API. Coverage и остальные значения тоже сохраняются из ответа.
- На `/overview` summary используется для общей полосы, времени snapshot, coverage и нарядов. Единственная составная метрика: «Срочные ≤24 ч» = `flash1To6h + urgent6To24h`; нельзя вычислять её из risk counts.

Domain model `DashboardSummary` сохраняет вложенные группы и использует camelCase:

```text
generated_at → generatedAt
model_version → modelVersion
channels.ml_supported → channels.mlSupported
channels.ml_unsupported → channels.mlUnsupported
channels.coverage_percent → channels.coveragePercent
predictions.flash_1_6h → predictions.flash1To6h
predictions.urgent_6_24h → predictions.urgent6To24h
predictions.planned_24_48h → predictions.planned24To48h
tickets.completed_today → tickets.completedToday
```

Остальные названия полей не меняются. `toDashboardSummary()` только переносит поля, без вычислений. Query key: `dashboardKeys.summary()` → `['dashboard', 'summary']`; общий prefix `dashboardKeys.all`. Hook: `useDashboardSummary()`, через общий `apiGet` с AbortSignal и политикой QueryClient.

Mock fixture — синтетический snapshot сети, независимо от шести prediction fixtures: 12 480 каналов, 9 984 ML-supported, 2 496 unsupported, coverage 80%; 137 активных прогнозов, 8 critical / 24 high / 61 medium; urgency 6 / 26 / 61; 186 объектов, 42 affected и 5 critical; 12 draft, 19 approved, 7 completed today. Timestamp `2026-09-20T15:42:00Z`, model version `7.2`. Значения фиксированные для воспроизводимых тестов, не фактическое состояние инфраструктуры.

## 9. Остальные API DTO

```ts
export interface ObjectDto {
  object_id: number;
  object_name: string;
  parent_object_id: number | null;
  subsystem: string;
}
export interface SystemDto {
  status: "operational" | "degraded";
  updated_at: string;
}
```

`toObject` → `InfrastructureObject` (`id`, `name`, `parentObjectId`, `subsystem`). System query переводит `updated_at` в `updatedAt`.

`TicketDto` и `toTicket` определены в разделе 17 и живут в `dto/ticket.ts` и `adapters/ticket.ts`.

Telemetry domain определён в разделе 16: `TelemetrySeries` / `TelemetryPoint` и endpoint `GET /sensors/:channelId/telemetry`. Прежний placeholder `TelemetrySample` больше не используется.

## 10. Endpoints, client, Query и mock mode

Все endpoints относительно `VITE_API_BASE_URL`:

| Method | Endpoint                      | Response                                              |
| ------ | ----------------------------- | ----------------------------------------------------- |
| GET    | `/system`                     | SystemDto                                             |
| GET    | `/dashboard/summary`          | DashboardSummaryDto                                   |
| GET    | `/predictions`                | PredictionDto[], filters `object_id`, `risk_level`    |
| GET    | `/predictions/:id`            | PredictionDto; 404 при отсутствии                     |
| GET    | `/objects`                    | ObjectDto[]                                           |
| GET    | `/objects/status-summary`     | ObjectStatusSummaryDto[], отдельные агрегаты объектов |
| GET    | `/objects/:id`                | ObjectDetailDto; 404 при отсутствии                   |
| GET    | `/objects/:objectId/topology` | ObjectTopologyDto; 404 при отсутствии объекта         |
| GET    | `/sensors/:channelId/telemetry` | TelemetryResponseDto; `date_from`, `date_to`, `limit` ≤ 1000 |
| GET    | `/tickets`                    | TicketDto[]; фильтры `status`, `search`, `prediction_id`, `object_id` |
| GET    | `/tickets/:ticketId`          | TicketDto; 404 при отсутствии                         |
| POST   | `/tickets`                    | CreateTicketRequestDto → TicketDto (201)              |
| PATCH  | `/tickets/:ticketId/status`   | UpdateTicketStatusRequestDto → TicketDto              |

List endpoints возвращают массивы. Write endpoints — только по нарядам (раздел 17); они идут через общий `apiSend`.

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_ENABLE_MOCKS=true
```

Без base URL используется `/api/v1`. Только строка `true` включает MSW; false использует backend без изменений React-компонентов. MSW запускается до render приложения. После изменения env нужен restart Vite или новая production build. VITE-переменные публичные, не для секретов.

Общий `ApiError`: message, status, code (`NETWORK_ERROR`, `HTTP_ERROR`, `INVALID_RESPONSE`). HTTP errors могут содержать JSON `{ message: string }`. Отмена запроса не превращается в network error. `alert()` запрещён.

Query keys централизованы: `predictionKeys.all/list(filters)/detail(id)`, `objectKeys.all/list()/statusSummary()/detail(id)/topology(id)`, `telemetryKeys.all/sensor(channelId, params)`, `ticketKeys.all/list(filters)/detail(id)`, `systemKeys.all`, `dashboardKeys.all/summary()`. QueryClient: staleTime 60 секунд, gcTime 5 минут, один retry для network/server errors, без retry на 4xx; refetch on focus. System status polling — 60 секунд. Summary отдельный polling пока не имеет.

UI states: loading, error, empty, success, stale. Cached data сохраняется при ошибке обновления с предупреждением, retry доступен пользователю.

Mock list endpoints поддерживают `?scenario=empty|error|slow`; это исключительно тестовые параметры. Summary возвращает объект с задержкой 250 ms, не пустой массив. Ошибки summary в тестах задаются MSW override. Production frontend backend URL не хардкодится в components.

## 11. Проверки и ограничения интеграции

Перед завершением изменений: `npm run typecheck`, `npm test`, `npm run build`, `npm run format:check`, `npm run test:browser` (check-browser → check-overview → check-object-workspace → check-objects-registry → check-predictions-registry → check-prediction-investigation → check-tickets → check-theme → check-analytics → check-review), `npm run test:real`. При системном Node 18 на текущем компьютере используется `frontend/scripts/npm.ps1`, выбирающий доступный Node 24.

Проверки должны сохранять сценарии 46% = critical, unsupported ML, отсутствие пересчёта backend aggregate, московское время при другой browser timezone, routing, клавиатурный фокус, loading/error/empty/stale и mock/real mode. Браузерные тесты запускаются в Edge или Chrome.

Известные ограничения:

- Настоящий HTTP backend пока не подключён. `backend_app_ml_predictor.py` — ML-модуль; его fallback low / 1% / ИТС 99 для неизвестных датчиков не соответствует этому frontend-контракту. Backend-обёртка должна выдавать явный `prediction_supported=false` и nullable ML-поля.
- TypeScript DTO не заменяют runtime schema validation; сейчас client проверяет HTTP и корректность JSON.
- Авторизация, роли/права, realtime и virtualized tables не реализованы. Наряды `/api/v1` и решения диспетчера `/api/v2` имеют отдельные ограниченные mutation workflows; review queue использует cursor pagination.
- Prediction Investigation остаётся shell и показывает route ID; detail API integration для прогноза относится к Task 04. Object Workspace уже проверяет существование объекта через `/objects/:id`.
- Для cross-origin backend требуется CORS; для production hosting нужен SPA fallback и mocks=false.

Task 02 использует `pages/overview`, независимые агрегаты, prediction domain data и существующие UI primitives. Recharts не используется на Operational Center.

## 12. Task 02 — Operational Center

Цель `/overview`: за 3–5 секунд понять срочность проблем, затронутые объекты и перейти к расследованию. Это оперативное рабочее место без charts, giant KPI cards и декоративных панелей.

Layout: компактный header («Оперативный центр», «Текущее состояние инженерной инфраструктуры», `summary.generatedAt` в МСК); единая summary strip высотой около 64–72 px; общий workspace с очередью рисков около 65–70% и объектной панелью около 30–35%. Наряды и coverage вторичны. Desktop 1920×1080 и 1366×768; общий horizontal overflow запрещён, локальный scroll таблицы допустим.

Summary strip: active, critical, flash1To6h + urgent6To24h, affected / total и число critical objects. Числа максимум 20–24 px. Coverage — готовый `coveragePercent` 0..100, например `80% · 9 984 / 12 480 каналов`. Ticket strip: draft, approved, completedToday и ссылка `/tickets`.

### Очередь рисков

Используется существующий `GET /predictions` и `usePredictions` с параметром **`view=operational`**. Это frontend-facing контракт приоритетной выборки, не отдельный агрегат. Ответ по-прежнему `PredictionDto[]`. Без `view` mock возвращает неизменные шесть foundation fixtures; при `view=operational` — отдельные 24 demo-прогноза (5 critical, 7 high, 12 medium; 8 объектов; все 5 ML-доменов). `/predictions/:id` разрешает ID обоих наборов.

Adapter для operational view оставляет только supported predictions с risk medium/high/critical; unsupported и low исключены. Сортировка: FLASH_1_6H → URGENT_6_24H → PLANNED_24_48H → NORMAL → неизвестная срочность; внутри probability DESC (null последним), ID как стабильный tie-breaker. Это упорядочивание готовых значений, не вычисление severity или urgency. Сортировка находится вне presentation markup.

Колонки: Срочность, Риск, Объект, Пикет, Датчик, Тип, Вероятность, ИТС, Обновлено. При ограниченной ширине Тип/Пикет/ИТС/Обновлено могут иметь пониженный responsive priority, но срочность, риск, объект, датчик и вероятность остаются видимыми. Доступно полное время в МСК через tooltip; короткое время тоже МСК.

Filters только по urgency («Все / 1–6 ч / 6–24 ч / 24–48 ч»), объекту и поисковой строке sensor/object/piket. Это фильтрация загруженной выборки без пересчёта глобальных агрегатов. Показывается фактическое количество видимых и загруженных строк, подпись «Показаны приоритетные прогнозы», а не все 137.

Клик строки и Enter → `/predictions/:predictionId`. Видимый focus, корректная table semantics; без nested buttons. Object links → `/objects/:objectId`. Detail pages остаются shells.

### Object Status Summary — новый согласованный контракт

**`GET /objects/status-summary`** возвращает массив `ObjectStatusSummaryDto[]`, отдельный backend aggregate. Статический route должен иметь приоритет перед `/objects/:id`.

```ts
export interface ObjectStatusSummaryDto {
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

Domain `ObjectStatusSummary`: objectId, objectName, riskLevel, activePredictions, criticalPredictions, highPredictions, mlSupportedChannels, channelsTotal, updatedAt. Adapter переносит значения; frontend не вычисляет risk/counts по predictions или `/objects`. Query key: `objectKeys.statusSummary()`; hook `useObjectStatusSummary()`.

Default sorting в adapter: critical → high → medium → low/null; затем criticalPredictions DESC, objectId. Панель отображает объекты с activePredictions > 0, явное число загруженных объектов. Mock содержит 8 самостоятельных объектных агрегатов с названиями Альфа, Бета, Фита, Кси, Тау, Дельта, Гамма, Омега. Это приоритетная выборка, а не все 42 затронутых объекта.

### Независимые состояния и проверка

Summary, predictions и object summary загружаются независимо: compact skeleton strip / table rows / list skeleton. Initial error локален и содержит retry. Failed refresh сохраняет cached data и показывает `StaleState`. Пустая очередь: «Активных рисков нет» / «Система не обнаружила прогнозов, требующих внимания диспетчера.»; пустой результат фильтра имеет отдельное сообщение и сброс filters. Object panel может оставаться видимой при пустой очереди.

Обновление запускается локальными controls каждого блока. Topbar хранит system status; на overview timestamp API скрыт, чтобы не смешивать его с `summary.generatedAt`. Summary fixture и foundation fixtures остаются неизменными. Для тестов доступны MSW overrides, включая independent failure, loading и stale.

Обязательные tests: summary rendering, 46% critical, urgency order, unsupported exclusion, row navigation, local loading/errors, empty queue, Moscow timestamp, coverage 80% (не 8000%), сохранение cached data после failed refresh. Browser: 1920×1080 и 1366×768, keyboard flow sidebar → filters → queue → objects, локальный table scroll, screenshots обеих ширин и loading/error блока.

## 13. Task 03 — Object Workspace

Цель `/objects/:objectId`: за несколько секунд понять состояние объекта, увидеть, где локализованы проблемы, и перейти к расследованию конкретного прогноза. Workflow: объект → проблемный участок → прогноз → расследование.

Страница — не набор карточек. Главный визуальный объект — линейная инженерная мнемосхема по пикетам. Географическая карта, fake map, floor plan, network graph, canvas graph, node editor, grid карточек датчиков и декоративная SVG-схема без привязки к данным запрещены.

Порядок блоков: компактный header, одна summary strip, топология, таблица прогнозов. На 1920×1080 одновременно видны header, summary, топология и не менее восьми строк прогнозов. Реализация в `pages/object-workspace/`: `ObjectWorkspacePage`, `ObjectHeader`, `ObjectSummary`, `ObjectTopology`, `TopologySegment`, `TopologyTooltipContent`, `ObjectPredictions`, `ObjectPredictionFilters`, `object-workspace-model.ts`, `object-workspace.css`.

Общие для Operational Center и Object Workspace стили (`.urgency-filter`, `.queue-row`, `.queue-footer`, `.heading-count`, `.queue-sort-hint`, `.queue-sensor-link`, `.nowrap`) находятся в `styles/globals.css`, а не в `pages/overview/overview.css`. Дублирующие компоненты (`ObjectRiskBadgeV2` и аналоги) не создаются: используются существующие DataTable, RiskBadge, UrgencyBadge, Button, IconButton, SearchInput, Select, Tooltip, Skeleton, EmptyState, ErrorState, StaleState и formatters.

### Object detail — расширенный контракт `/objects/:id`

`GET /objects/:id` возвращает `ObjectDetailDto` вместо прежнего `ObjectDto`. `ObjectDto` сохраняется для списка `/objects`.

```ts
export interface ObjectDetailDto {
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

Domain `ObjectDetail`: objectId, objectName, parentObjectId, objectType, channelsTotal, mlSupportedChannels, riskLevel, activePredictions, criticalPredictions, highPredictions, updatedAt. `toObjectDetail()` только переносит поля. Hook `useObjectDetail(id)`, key `objectKeys.detail(id)`. Прежний `useObject()` удалён.

Header: имя объекта как `h1`; вторичная строка `objectType · channelsTotal каналов · ML-покрытие N%`; справа `updatedAt` в МСК и локальный контрол обновления. Summary strip — одна полоса без KPI cards: Состояние (RiskBadge), Критические, Высокие, Активные риски, ML-покрытие. Числа не крупнее 22 px; semantic color занимает минимальную площадь.

ML-покрытие — вторичная информация: `Math.round(mlSupportedChannels / channelsTotal * 100)` плюс подпись `722 / 860 каналов` и простой горизонтальный индикатор. Donut и pie charts запрещены. Это округление двух счётчиков для отображения, а не пересчёт backend-агрегата: `risk_level` и counts всегда берутся из ответа.

### Topology — новый endpoint `/objects/:objectId/topology`

Статические и вложенные object-routes регистрируются выше паттерна `/objects/:id`.

```ts
export interface ObjectTopologyDto {
  object_id: number;
  object_name: string;
  piket_min: number | null;
  piket_max: number | null;
  updated_at: string;
  segments: TopologySegmentDto[];
}
export interface TopologySegmentDto {
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
```

Domain `ObjectTopology` / `TopologySegment` — camelCase. `toObjectTopology()` переносит поля и сортирует segments по `piketFrom`; `risk_level` и counts участка приходят готовым backend aggregate и никогда не выводятся из прогнозов. Hook `useObjectTopology(id)`, key `objectKeys.topology(id)`.

Segment — реальный логический участок (`ПК0 → ПК42`, `ПК42 → ПК88+50`). Участки непрерывны: `piket_from` каждого следующего равен `piket_to` предыдущего, поэтому ни один пикет не попадает в неопределённый разрыв.

### Topology rendering

Собственный React + SVG компонент; graph/network/topology библиотеки не подключаются. SVG рисуется в CSS-пикселях: ширина измеряется `ResizeObserver` (fallback `TOPOLOGY_FALLBACK_WIDTH = 1200`, он же используется в jsdom), `viewBox` равен измеренной ширине, поэтому толщина линий и кегль не зависят от ширины рабочей области.

Позиционирование: домен `[piketMin ?? первый piketFrom, piketMax ?? последний piketTo]`, при вырожденном домене верхняя граница поднимается на 1. `x(p) = PADDING + (p - from) / (to - from) * (width - 2 * PADDING)`. Длина участка — `x(piketTo) - x(piketFrom)`, с нижней границей `MIN_SEGMENT_WIDTH` для кликабельности вырожденно коротких участков. Одинаковая ширина у всех участков считается ошибкой: `ПК0 → ПК100` примерно вдвое длиннее `ПК100 → ПК150`.

Внешний вид: normal (low/null) — тонкая нейтральная линия `--text-muted`; medium/high/critical — semantic color и большая толщина. Glow, gradient и заливка экрана цветом запрещены; критический участок остаётся линией, а не областью.

Piket labels: кандидаты — границы участков и домена. Обязательно сохраняются первая, последняя и границы выбранного участка; далее без коллизий добавляются границы проблемных (high/critical) участков, затем остальные. Подписи участков выводятся только для проблемных и выбранного, с собственным минимальным зазором. Тридцать перекрывающихся подписей недопустимы.

Tooltip использует общий `Tooltip`: диапазон пикетов, название участка, риск, активные/критические/высокие прогнозы, макс. вероятность. Compact, без большой тени и gradient.

Topology показывает состояние участка и не утверждает точку отказа: формулировки вида «Отказ произойдёт на ПК88,5» запрещены.

### Selection, keyboard и фильтрация по пикетам

Каждый участок — `role="button"`, `tabIndex=0`, `aria-pressed`, видимый focus ring. Клик, Enter и Space выбирают участок; повторная активация снимает выбор. Accessible name несёт диапазон, название, уровень риска и число прогнозов, поэтому цвет не является единственным носителем информации.

Выбранный участок выделен небольшим увеличением толщины и сдержанным контуром, без glow. Под схемой — компактная строка `Выбран участок: ПК 88+50 — ПК 112 · Вентшахта ВШ-3 · 4 прогноза` и кнопка «Сбросить». Отдельная большая карточка выбора не создаётся.

Фильтр по участку:

```ts
prediction.piketValue !== null &&
  prediction.piketValue >= segment.piketFrom &&
  prediction.piketValue <= segment.piketTo;
```

Границы включаются с обеих сторон, поэтому прогноз ровно на общей границе виден в обоих соседних участках. Прогноз с `piketValue === null` не попадает ни в один числовой диапазон и остаётся виден только без выбранного участка.

### Прогнозы объекта

Используется существующий Prediction domain и `GET /predictions?object_id=:objectId`; отдельный Prediction DTO не создаётся. Колонки: Срочность, Риск, Пикет, Датчик, Тип, Вероятность, ИТС, Обновлено. Колонка «Объект» не показывается. При ограниченной ширине «Тип» имеет пониженный responsive priority.

Сортировка та же, что в Operational Center, через общий `compareByUrgency` из `api/adapters/operational-queue.ts`: FLASH_1_6H → URGENT_6_24H → PLANNED_24_48H → NORMAL → неизвестная срочность, внутри `failureProbability` DESC, ID как tie-breaker. Mapping не дублируется. В отличие от очереди рисков, low и unsupported прогнозы объекта не отбрасываются.

Фильтры: срочность (сегментированная группа), риск (Select), поиск по датчику, типу и пикету. Поиск по объекту не нужен. Это фильтрация загруженной выборки, отображается `Показано N из M загруженных`. Страница не превращается в Predictions Registry.

Клик строки и Enter → `/predictions/:predictionId`; Prediction Investigation остаётся shell.

### Состояния

Object detail, topology и predictions загружаются независимо, каждый со своим skeleton, ErrorState с retry и `StaleState` при неудачном обновлении поверх cached data. Отказ одного endpoint не разрушает страницу.

- Object 404 (`ApiError.status === 404`) → «Объект не найден» / «Объект с указанным идентификатором отсутствует или недоступен.» и ссылка «К списку объектов». Нечисловой `objectId` обрабатывается так же.
- Пустая топология (`segments: []`) → «Топология объекта недоступна» / «Для объекта пока не сформирована структура участков по пикетам.»; прогнозы остаются.
- Пустые прогнозы → «Активных прогнозов для объекта нет»; топология остаётся.
- Topology skeleton повторяет геометрию будущего блока; giant spinner на всю страницу не используется.

### Mock data

Демо-объект — `объект Фита` (203): 20 участков ПК0–ПК400 с локализованными проблемными зонами (три critical, три high, пять medium, остальные спокойные), 860 каналов, 722 ML-supported, 24 прогноза разных типов и срочностей, включая один канал без `piket_value`. Механический чередующийся паттерн normal/critical не используется. Объекты 201–208 имеют компактные топологии и наборы прогнозов; 101 и 102 не имеют топологии и служат демонстрацией пустого состояния.

`objectDetailFixtures` строится из тех же `objectStatusFixtures`, поэтому `/objects/status-summary` и `/objects/:id` сообщают одинаковые counts. Mock `/predictions` выбирает источник явно: `view=operational` → очередь Operational Center; `object_id` с собственным набором → набор Object Workspace; иначе — шесть foundation fixtures. Тест `api/mocks/object-workspace.test.ts` проверяет, что опубликованные агрегаты объекта и участков совпадают с записями самого mock API, чтобы UI не имел повода что-либо пересчитывать.

`?scenario=empty` для топологии возвращает объект с пустым `segments`, а не массив. Для браузерных проверок доступен `setObjectWorkspaceScenario(worker, endpoint, state, objectId)`.

### Проверки Task 03

Unit: object detail rendering, proportional segment widths, critical segment semantics, accessible names, mouse и keyboard selection, сброс выбора, numeric piket filtering и исключение `piketValue === null`, фильтры, prediction navigation, urgency ordering, 46% ANALOG_TEMP остаётся critical, независимые ошибки topology/predictions, пустая топология, пустые прогнозы, object 404, московские timestamps, cached data после failed refresh, геометрия и label thinning, pluralisation и `formatPiket`.

Browser (`scripts/check-object-workspace.mjs`, включён в `npm run test:browser`): dark и light при 1920×1080 и 1366×768, отсутствие page-level horizontal overflow, отсутствие `.badge` и залитых risk pills, пропорциональная геометрия, различие цвета critical и нейтрального участка, tooltip без тени, отсутствие наложения подписей участков, выбор мышью и с клавиатуры, видимый focus ring, переход в прогноз, независимые ошибки, пустые состояния и object 404. Скриншоты: `object-workspace-{dark,light}-{1920,1366}.png`, `object-workspace-selected-critical.png`, `object-workspace-topology-error.png`.

Ограничение объёма Task 03: telemetry chart и Prediction Investigation в него не входили — они реализованы отдельно в разделе 16.

## 14. Objects Registry — `/objects`

Реестр объектов инженерной инфраструктуры: плотная enterprise-таблица, из которой диспетчер переходит в Object Workspace. Страница реализована в `pages/objects/` (`ObjectsPage`, `ObjectsFilters`, `ObjectsRegistryTable`, `registry-model.ts`, `objects-page.css`) и не создаёт дублирующих примитивов: используются общие DataTable, RiskBadge, Button, SearchInput, Select, Skeleton, EmptyState, ErrorState, StaleState и formatters.

### Источник данных

Используется существующий агрегат **`GET /objects/status-summary`** через `useObjectStatusSummary()` и `objectKeys.statusSummary()`. Новый endpoint не вводится, отдельный Object DTO не создаётся.

`riskLevel`, `activePredictions`, `criticalPredictions`, `highPredictions`, `mlSupportedChannels` и `channelsTotal` приходят готовыми с backend. Frontend не выводит риск объекта из прогнозов и не пересчитывает counts. `registryCoverage()` только делит два присланных счётчика каналов для отображения — это форматирование, а не восстановление покрытия по прогнозам.

### Колонки, фильтры и сортировка

Колонки: Объект, Риск, Активные, Критические, Высокие, ML-покрытие, Обновлено. Время — в `Europe/Moscow` через общий `formatDateTime`.

Фильтры: поиск по названию объекта и фильтр по уровню риска (`RiskLevel | 'all'`). Поиск по прогнозам и датчикам на этой странице не нужен. Фильтрация применяется к загруженной выборке; отображается фактическое `Показано N из M загруженных объектов`.

Default sorting в `selectObjects()` — упорядочивание готовых значений, не вычисление severity:

1. `riskLevel`: critical → high → medium → low → null;
2. `criticalPredictions` DESC;
3. `activePredictions` DESC;
4. `objectName` (`Intl.Collator('ru')`);
5. `objectId` как стабильный tie-breaker.

### Навигация и состояния

Клик строки и Enter на сфокусированной строке → `/objects/:objectId` (Object Workspace раздела 13). Реестр не перехватывает detail route. Видимый focus, корректная table semantics, без nested buttons.

Состояния: loading (skeleton строк), initial error с retry, пустой ответ API, пустой результат фильтра с отдельным сообщением и сбросом, `StaleState` поверх cached data после неудачного обновления. Обновление запускается локальным контролом страницы. Обе темы обязательны.

### Ограничение

`GET /objects/status-summary` — приоритетная выборка: adapter оставляет только объекты с `activePredictions > 0`. Поэтому реестр сейчас показывает **только объекты с активными прогнозами**, а не весь каталог. Полный список объектов, включая `active_predictions = 0`, потребует расширения backend-контракта и в текущий объём не входит.

## 15. Predictions Registry — `/predictions`

Операционный реестр прогнозов: плотная таблица по всей загруженной выборке с комбинируемыми фильтрами и сортировкой. Реализация в `pages/predictions/` (`PredictionsPage`, `PredictionsFilters`, `PredictionsRegistryTable`, `predictions-registry-model.ts`, `predictions-page.css`). Новый Prediction DTO не создаётся — используется существующий domain раздела 7.

### Источник данных

Используется существующий `usePredictions()` и `GET /predictions` с frontend-facing параметром `view=operational` (раздел 12). Отдельный агрегат не вводится. Ответ — `PredictionDto[]`, далее общий `toPrediction()`.

### Фильтры и сортировка

Фильтры: срочность, риск, объект и поисковая строка по датчику, типу, объекту и пикету. Фильтры комбинируются по «И»: строка должна удовлетворять всем активным условиям одновременно. Сброс возвращает все четыре фильтра в исходное состояние. Это фильтрация загруженной выборки, глобальные агрегаты не пересчитываются; счётчик результата отражает фактически загруженные строки.

Default sorting использует общий **`compareByUrgency`** из `api/adapters/operational-queue.ts`: FLASH_1_6H → URGENT_6_24H → PLANNED_24_48H → NORMAL → неизвестная срочность, внутри `failureProbability` DESC (null последним), ID как стабильный tie-breaker. Локальная копия urgency mapping запрещена — это единственный источник порядка срочности, общий с Operational Center и Object Workspace.

Пользовательская сортировка доступна по вероятности, времени обновления и объекту; `compareByUrgency` остаётся финальным tie-breaker, поэтому порядок внутри равных значений стабилен. Сортировка по вероятности учитывает `predictionSupported`: у неподдерживаемых каналов значение считается отсутствующим и уходит в конец независимо от направления.

### Семантика ML и навигация

Готовые значения не пересчитываются: `46%` для `ANALOG_TEMP` остаётся `critical`. Риск и срочность отображаются нейтральным текстом с маленьким semantic-маркером; залитые цветные капсулы не используются.

Клик строки и Enter → `/predictions/:predictionId`. Prediction Investigation пока остаётся shell.

### Состояния

loading, initial error с retry, пустой ответ API, пустой результат фильтра с отдельным сообщением и сбросом, `StaleState` поверх cached data после неудачного обновления. Обе темы обязательны. На 1920×1080 в первом экране видно не менее 15 строк.

### Ограничения и будущее требование

`view=operational` — приоритетная выборка: adapter оставляет только supported прогнозы с риском medium/high/critical. Поэтому реестр сейчас **не содержит low и ML-unsupported прогнозов** и не является полным реестром всех активных прогнозов сети.

Полный registry (включая low и unsupported), серверная пагинация и серверная сортировка требуют расширения backend-контракта и в текущий объём не входят. До этого счётчик результата описывает загруженную выборку, а не общее число прогнозов из `dashboard.summary.predictions.active`.

## 16. Task 04 — Prediction Investigation

Центральный рабочий экран расследования одного прогноза: `/predictions/:predictionId`. Экран отвечает на пять вопросов диспетчера — что произошло, насколько это срочно, где проблема, почему модель считает прогноз рискованным и что рекомендуется сделать. Это не аналитический dashboard.

Порядок блоков повторяет порядок принятия решения: header прогноза → телеметрия и контекстная панель (риск, вероятность, ИТС, факторы, рекомендация, действие) → технические данные. На 1920×1080 в первом экране умещаются header, риск и срочность, график телеметрии, вероятность и ИТС, факторы, рекомендация и CTA.

Реализация в `pages/prediction-investigation/`: `PredictionInvestigationPage`, `PredictionHeader`, `PredictionContextPanel`, `PredictionRiskSummary`, `RiskFactors`, `RecommendationSection`, `TelemetrySection`, `NumericTelemetryChart`, `StateTelemetryChart`, `TelemetryRangeControl`, `telemetry-chart-parts.tsx`, `PredictionTechnicalDetails`, `prediction-investigation-model.ts`, `prediction-investigation.css`. Новых зависимостей не добавлено: график построен на уже установленном Recharts.

### Prediction detail

Используется существующий `GET /predictions/:predictionId`, существующие `PredictionDto` и `Prediction`, hook `usePrediction(id)` и key `predictionKeys.detail(id)`. Отдельная detail-модель не создаётся.

Header: `sensorType` как eyebrow, `sensorName` как `h1`, контекстная строка «объект (ссылка на `/objects/:objectId`) · пикет · подсистема», справа `generatedAt` в МСК, review status и ID прогноза. Технические поля вынесены в отдельный блок и не конкурируют с рабочей информацией.

Review status отображается сдержанным `workflow-status` badge; общий словарь меток — `reviewStatusLabels` в `utils/formatters.ts` (используется и Predictions Registry).

### Риск, срочность, ИТС

`riskLevel`, `maintenanceUrgency`, `failureProbability` и `healthIndex` выводятся ровно так, как их прислал backend. Frontend ничего не пересчитывает: `ANALOG_TEMP` с вероятностью 46% остаётся `critical` и `FLASH_1_6H`.

Срочность формулируется только по `maintenanceUrgency`: FLASH_1_6H → «Требуется проверка в течение 1–6 часов», URGENT_6_24H → «в течение 6–24 часов», PLANNED_24_48H → «Плановая проверка в течение 24–48 часов», NORMAL → «Штатный режим наблюдения», null → «Срочность обслуживания не определена».

`leadTimeHours` не является моментом отказа и никогда не подаётся как «отказ произойдёт через N часов». Он присутствует только в технических данных с пометкой «ориентировочно».

ИТС выводится компактно как `54 / 100` с простым линейным индикатором. Donut, speedometer и circular gauge запрещены.

### Факторы риска и рекомендация

`topRiskFactors` выводится нумерованным списком с нейтральной типографикой и разделителями; semantic-цвет к каждому пункту не применяется, отдельные цветные карточки не создаются. Строка фактора отображается как есть — дополнительные числовые поля поверх неё не выдумываются. Пустой список даёт честное сообщение, а не заглушку.

`recommendation` выводится отдельной секцией дословно. Frontend не переписывает и не генерирует рекомендацию.

### Unsupported ML

При `predictionSupported === false` секция модели показывает «ML-анализ недоступен» и пояснение «Тип датчика пока не входит в область активного предиктивного мониторинга». Подстановка low / 1% / ИТС 99 запрещена; факторы и рекомендация модели не выводятся. Телеметрия при этом остаётся доступной, а действие по наряду не блокируется автоматически.

### Telemetry — новый endpoint

**`GET /sensors/:channelId/telemetry`**, query-параметры `date_from`, `date_to`, `limit` (`limit <= 1000`).

```ts
export type TelemetryValueType = 'numeric' | 'state';
export type TelemetryStatusCode = 'normal' | 'failure' | 'alarm' | 'unknown';

export interface TelemetryPointDto {
  timestamp: string;
  raw_value: string;
  numeric_value: number | null;
  status_code: TelemetryStatusCode;
  is_alarm: boolean;
  is_chatter: boolean;
}
export interface TelemetryResponseDto {
  channel_id: number;
  sensor_name: string;
  sensor_type: string;
  value_type: TelemetryValueType;
  unit: string | null;
  points_count: number;
  telemetry: TelemetryPointDto[];
}
```

Domain `TelemetrySeries` / `TelemetryPoint` (camelCase: `rawValue`, `numericValue`, `statusCode`, `isAlarm`, `isChatter`, `valueType`, `pointsCount`). `toTelemetrySeries()` переносит поля и сортирует точки по времени; DTO в chart-компоненты не передаётся. Прежний placeholder `TelemetrySample` заменён этой моделью.

Hook `useSensorTelemetry(channelId, { range })`, keys `telemetryKeys.all` и `telemetryKeys.sensor(channelId, params)`, общий `apiGet` с AbortSignal. Запрос включается только когда известен `channelId` загруженного прогноза.

### Range semantics

Контролы периода: `6 ч`, `24 ч`, `48 ч`, по умолчанию `24 ч`. Полноценный calendar range picker в этот этап не входит.

UI хранит токен `'6h' | '24h' | '48h'`; query-слой преобразует его в абсолютные UTC-инстанты и формирует реальные `date_from` / `date_to` / `limit` (96 / 144 / 192 точек). Query key содержит токен диапазона, окно вычисляется в `queryFn`, поэтому ключ стабилен. Ручное прибавление timezone offset запрещено: работа идёт с epoch/UTC, а отображение — через московские formatters.

### Визуализация

`valueType = numeric` → line chart: тонкая линия, сдержанная сетка, подписи осей, без gradient fill и без декоративной анимации. Разрывы данных не соединяются (`connectNulls={false}`).

`valueType = state` → step chart (`stepAfter`). Плавная интерполяция между состояниями запрещена. Внутренний числовой индекс используется только для позиционирования; подписи оси и tooltip всегда показывают реальный `rawValue` (`Норма`, `Просадка`, `Отказ`).

**Прогнозная линия будущего запрещена.** ML-контракт возвращает вероятность риска, а не будущий временной ряд телеметрии. Forecast line, future dashed signal, predicted value и confidence band будущего не рисуются; данные графика никогда не выходят за последний измеренный timestamp.

`is_alarm` и `is_chatter` показываются точечными маркерами на самой точке, без заливки всего графика и без мигающей анимации. Список «События периода» дублирует их текстом и схлопывает подряд идущие одинаковые события в одну запись.

Tooltip: московское время, значение с единицей измерения либо реальное состояние, плюс пометки «Аварийное значение» / «Дребезг сигнала».

### Локальные метрики и доступность

Из загруженного ряда допустимо вычислять только обычные статистики: min, max, последнее значение, число точек. Они используются в подписи под графиком и в screen-reader summary вида «Телеметрия: Температура ВШ-3, 24 часа. 144 точек. Минимум 21,6 °C, максимум 27,3 °C, последнее значение 27,3 °C». Это статистика выборки, а не ML-семантика: риск, срочность, ИТС и вероятность будущего отказа из телеметрии не выводятся.

График помечен `role="img"` с этим summary; текстовое описание доступно через `figcaption`. Контролы периода, CTA, ссылка на объект и раскрытие технических данных доступны с клавиатуры; состояние не передаётся одним лишь цветом.

### Ticket handoff

Primary action «Создать наряд» ведёт на `/tickets?predictionId=<predictionId>`. Мутации, форма, drawer и имитация успешного создания наряда в Task 04 не реализуются — это handoff в Task 05.

Если `ticketId !== null`, primary CTA заменяется блоком «Наряд уже создан #WO-…» со ссылкой `/tickets?ticketId=<ticketId>`; detail-маршрут наряда пока отсутствует. При unsupported ML действие остаётся доступным.

### Состояния

Prediction detail и telemetry — независимые источники. Если не загрузился прогноз, страница показывает ErrorState с retry либо, при 404, экран «Прогноз не найден» с переходом «К журналу прогнозов». Если не загрузилась телеметрия, контекст прогноза сохраняется, а блок графика показывает «Не удалось загрузить телеметрию. Данные прогноза остаются доступны.» с retry.

Telemetry также поддерживает loading (skeleton в области графика при доступном контексте), пустой ответ («Телеметрия отсутствует» / «За выбранный период данные не получены.») и `StaleState` поверх сохранённых данных после неудачного обновления — график при этом не очищается.

### Mock-сценарии

Фикстуры телеметрии детерминированы (стабильный псевдошум по индексу точки) и строятся под запрошенное окно: канал 30004 — числовая температура с шумным участком, плато «зависшего младшего бита АЦП» и alarm-точками; 30005 — состояния фазы с просадкой, серией дребезга и отказом; 30016 — числовой CO; 1006 — дверь (unsupported ML, телеметрия есть); 1003 — насос с уже созданным нарядом `WO-2026-0917`. Канал без фикстуры возвращает пустой ряд. `?scenario=error|empty|slow` поддерживается; для браузерных проверок доступен `setTelemetryScenario(worker, state)`.

Факторы и рекомендации mock-прогнозов авторские: явные наборы для демонстрационных прогнозов и наборы по `model_domain` для остальных. Они являются содержимым backend и не генерируются frontend.

### Проверки Task 04

Unit: рендер детали прогноза, 46% critical, формулировка срочности, факторы, рекомендация, числовая и state-телеметрия, переключение диапазона с проверкой абсолютных параметров, отсутствие прогнозной линии, маркеры chatter и alarm, loading телеметрии при доступном контексте, независимая ошибка телеметрии, пустая телеметрия, stale, unsupported ML без 1% и ИТС 99, 404 прогноза, переход к объекту, handoff в наряды, состояние существующего наряда, московские timestamps, обе темы, клавиатурный доступ и accessibility summary.

Browser (`scripts/check-prediction-investigation.mjs`, включён в `npm run test:browser`): dark и light при 1920×1080 и 1366×768, отсутствие page-level overflow, отсутствие залитых risk pills, незалитая линия графика, alarm/chatter маркеры, московский tooltip, подписи оси состояний, диапазоны 6/24/48 ч с клавиатуры, раскрытие технических данных с клавиатуры, unsupported ML, пустая телеметрия, локальная ошибка телеметрии, существующий наряд и переход в `/tickets`. Скриншоты: `prediction-investigation-{dark,light}-{1920,1366}.png`, `prediction-investigation-state-telemetry.png`, `prediction-investigation-unsupported.png`, `prediction-investigation-telemetry-error.png`, `prediction-investigation-no-telemetry.png`.

### Ограничения

- Breadcrumb в `AppLayout` формируется по route ID и показывает идентификатор прогноза, а не цепочку «Прогнозы / объект / датчик»: осмысленный breadcrumb требует общего redesign breadcrumb-системы. На странице есть собственная ссылка «← Прогнозы».
- Telemetry backend пока mock: реальный источник и ретеншн не определены.
- Пользовательский выбор произвольного интервала (calendar range) не реализован.
- Task 05 не начат: создание наряда, форма, drawer, мутации, бригады, QR, Tickets Registry и аналитика не реализуются.

## 17. Task 05 — Наряды (Tickets / Work Orders)

`/tickets` — рабочий журнал нарядов, замыкающий основной workflow: риск → прогноз → расследование → создание наряда → обработка наряда. Реестр остаётся плотной enterprise-таблицей: kanban, workflow-карточки, board и card grid не используются.

Реализация в `pages/tickets/`: `TicketsPage`, `TicketsRegistryTable`, `TicketsFilters`, `TicketDetailDrawer`, `CreateTicketDrawer`, `TicketStatusActions`, `TicketSourceContext`, `ticket-registry-model.ts`, `ticket-form-model.ts`, `tickets-page.css`. Общий `ConfirmDialog` добавлен в `components/ui/` поверх уже установленного Radix Dialog; `window.confirm` не используется. Новых зависимостей, в том числе form- и toast-библиотек, не добавлено.

### Ticket DTO → domain

`TicketDto` вынесен из `dto/resources.ts` в `dto/ticket.ts` и расширен; адаптер — `adapters/ticket.ts`.

```ts
export interface TicketDto {
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
export interface CreateTicketRequestDto {
  prediction_id: string | null;
  object_id: number;
  title: string;
  description: string;
  assignee: string | null;
}
export interface UpdateTicketStatusRequestDto {
  status: TicketStatus;
}
```

Domain `Ticket` — те же поля в camelCase (`id`, `predictionId`, `objectId`, `objectName`, `sensorName`, `piket`, `title`, `description`, `status`, `priority`, `assignee`, `createdAt`, `updatedAt`, `completedAt`). `toTicket()` только переносит поля.

`priority` — это сохранённый `riskLevel` исходного прогноза. Он копируется при создании и никогда не выводится из `failureProbability`. У ручного наряда и у неподдерживаемого ML-канала `priority = null`.

`assigneeOptions` — небольшой справочник бригад в `domain/ticket/types.ts`. Полноценная система сотрудников, роли и авторизация в объём не входят.

### Lifecycle

Канонические статусы: `draft`, `approved`, `rejected`, `completed`. Статусы `created`, `open`, `closed`, `new`, `pending` не вводятся.

Допустимые переходы:

```text
draft → approved
draft → rejected
approved → completed
```

Обратные и сквозные переходы (`completed → draft`, `rejected → approved`, `completed → rejected`, `draft → completed`) запрещены.

Правило живёт в `domain/ticket/types.ts` (`ticketTransitions`, `getAllowedTicketTransitions`, `isAllowedTicketTransition`) и используется UI только для того, чтобы показать доступные действия. Валидация перехода обязательна и на стороне API: mock повторно проверяет переход и отвечает `409`. Полагаться только на disabled-кнопки нельзя.

### Endpoints

| Method | Endpoint                     | Назначение                                              |
| ------ | ---------------------------- | ------------------------------------------------------- |
| GET    | `/tickets`                   | TicketDto[]; фильтры `status`, `search`, `prediction_id`, `object_id` |
| GET    | `/tickets/:ticketId`         | TicketDto; 404 при отсутствии                           |
| POST   | `/tickets`                   | CreateTicketRequestDto → TicketDto (201)                |
| PATCH  | `/tickets/:ticketId/status`  | UpdateTicketStatusRequestDto → TicketDto                |

`POST /tickets` назначает `ticket_id`, `status = draft`, `created_at` и `updated_at` на стороне backend; клиент их не передаёт. Generic JSON patch не используется — смена статуса имеет отдельный endpoint. Серверная пагинация не вводится.

Ошибки mock API: `422` — нарушение длины `title`/`description`, `404` — неизвестный прогноз или наряд, `409` — дубликат наряда для прогноза либо недопустимый переход.

Write-запросы идут через общий `apiSend('POST' | 'PATCH', …)` в `api/client/http.ts`, поэтому форма ошибки, сообщения и отмена совпадают с `apiGet`.

### Query и мутации

Keys: `ticketKeys.all / list(filters) / detail(id)`. Hooks: `useTickets(filters)`, `useTicket(id)`, `useCreateTicket()`, `useUpdateTicketStatus()`. Мутации выполняются только через TanStack Query, прямой `fetch()` из компонентов запрещён.

Optimistic update не используется: после успешной мутации обновляется detail-кэш и инвалидируются затронутые ключи. `useCreateTicket` дополнительно инвалидирует `predictionKeys.all`, потому что создание наряда меняет и исходный прогноз.

### Реестр

Колонки: Наряд, Статус, Название, Объект, Источник, Приоритет, Исполнитель, Создан, Обновлён. «Источник» — идентификатор прогноза либо «Ручной». На ширине до 1500 px колонка «Создан» скрывается; значение остаётся в detail drawer.

Статус отображается существующим `StatusBadge` в сдержанном стиле `workflow-status` (radius 4 px, subtle border и background, нейтральная типографика). Четыре ярких цветных капсулы не используются. Приоритет — semantic dot через `RiskBadge`, без filled pill.

Сортировка по умолчанию: `draft → approved → rejected → completed`, внутри `updatedAt` DESC, затем `id`. Требующие решения наряды всегда сверху.

Фильтры: поиск (по `ticketId`, названию, объекту, `predictionId`, исполнителю; case-insensitive, trim) и статус. Фильтрация выполняется по загруженной выборке. Счётчик показывает `15 нарядов`, а после фильтров — `4 из 15 нарядов`.

Клик строки и Enter открывают detail drawer; отдельный detail-route в Task 05 не вводится. Состояние синхронизировано с query-параметром `ticketId`, что даёт deep-link из Prediction Investigation.

### Query-параметры `/tickets`

- `?ticketId=WO-…` — открыть detail drawer сразу, без дополнительного клика. Неизвестный идентификатор даёт локальное «Наряд не найден», реестр остаётся рабочим; закрытие удаляет параметр из URL.
- `?predictionId=OW-…` — открыть create flow с контекстом прогноза и предзаполненной формой. Неизвестный прогноз даёт локальное «Прогноз не найден», реестр остаётся доступным.

Оба параметра взаимоисключающие: открытие наряда удаляет `predictionId`.

### Create drawer

Используется существующий Drawer, отдельная страница создания не создаётся. Форма плотная, controls совпадают с общими 32–36 px.

Блок «Источник» — компактный readonly-контекст (идентификатор прогноза, датчик, объект · пикет, risk dot и urgency marker), не карточка.

Prefill из прогноза: `title` = `Проверка: <sensorName>`; `description` собирается из уровня риска, датчика, расположения и **существующей** `recommendation` прогноза. Новые рекомендации frontend не генерирует и не переписывает. Оба поля редактируются.

Валидация: `title` — trim, 3–120 символов; `description` — trim, 10–2000 символов; исполнитель необязателен; объект обязателен только для ручного наряда. Ошибки выводятся inline и связаны с полем через `aria-describedby`; `alert()` не используется.

Ручной наряд создаётся кнопкой «Новый наряд»; объект выбирается из существующего `/objects` через `useObjects()`. Отдельный Objects API и собственный список объектов не вводятся.

После успешного `POST`: create-режим закрывается, кэш нарядов инвалидируется, открывается detail нового наряда, прогноз получает `ticketId` и `reviewStatus = ticket_created`. Незавершённая форма при закрытии drawer просто сбрасывается.

### Duplicate protection

Один прогноз — максимум один наряд. Если у прогноза уже есть наряд, create flow показывает «Для прогноза уже создан наряд» с идентификатором и кнопкой «Открыть наряд»; форма не отображается. Mock API независимо отклоняет повторный `prediction_id` с `409`.

### Detail drawer

Идентификатор наряда, статус, приоритет, название, объект (ссылка на `/objects/:objectId`), источник и «Открыть прогноз» (ссылка на `/predictions/:predictionId`), датчик и пикет, исполнитель, `createdAt`, `updatedAt` и `completedAt` — все в `Europe/Moscow` через существующие formatters.

Действия соответствуют статусу: `draft` → «Согласовать» и «Отклонить»; `approved` → «Отметить выполненным»; `rejected` и `completed` — действий нет, вместо них поясняющая строка. Лес disabled-кнопок не показывается.

Каждое действие подтверждается через `ConfirmDialog`. «Отклонить» и «Отметить выполненным» предупреждают о необратимости; reason при отклонении не запрашивается, поскольку backend-контракт такого поля не определяет. Ошибка мутации выводится внутри диалога подтверждения — вне его Radix помечает контент `aria-hidden`, и сообщение было бы недоступно. Drawer при ошибке не закрывается, данные не теряются, повтор доступен.

### Синхронизация с прогнозом

Прогнозы не хранят свой наряд: единственный источник истины — ticket store. Mock применяет `applyTicketState()` ко всем выдаваемым прогнозам, поэтому `ticket_id` и `review_status = ticket_created` появляются одинаково и у фикстур, и у нарядов, созданных мутацией. После создания Prediction Investigation показывает «Наряд уже создан», а не CTA.

### Mock dataset и persistence

15 нарядов: 5 draft, 4 approved, 2 rejected, 4 completed, из них 3 ручных без прогноза и 3 с `completed_at`. `WO-2026-0917` связан с `HYDRO-003` — сценарий существующего наряда из Task 04. Прогноз `OW-004` намеренно оставлен без наряда: это демонстрационный прогноз для create flow.

Созданные наряды хранятся в in-memory состоянии mock и живут в пределах сессии страницы. Полная перезагрузка страницы сбрасывает их к фикстурам; persistence между перезапусками dev-сервера не требуется. Для тестов экспортирован `resetTicketStore()`, он вызывается в `afterEach`, поэтому изменяемое состояние не делает тесты нестабильными.

### Состояния

loading (skeleton строк), initial error с retry, пустой ответ API («Наряды отсутствуют» / «Рабочие задания пока не создавались.»), пустой результат фильтра с отдельным сообщением и сбросом, `StaleState` поверх сохранённых строк после неудачного обновления. Detail drawer при deep-link открывается со skeleton и не блокирует реестр.

### Проверки Task 05

Unit: рендер реестра, сортировка по умолчанию, фильтр статуса, поиск, комбинация фильтров, сброс, счётчик результата, открытие detail кликом и Enter, deep-link `ticketId`, отсутствующий наряд, deep-link `predictionId`, prefill, отсутствующий прогноз, валидация формы, создание черновика, защита от дубликата, сохранение формы при ошибке мутации, три допустимых перехода, отклонение недопустимого перехода на стороне API, терминальные статусы без действий, Escape в диалоге подтверждения, связь прогноза с нарядом после создания, consistency фикстур в обе стороны, один наряд на прогноз, loading, error, empty, filtered empty, stale, московские timestamps, навигация к объекту и прогнозу, обе темы.

Browser (`scripts/check-tickets.mjs`, включён в `npm run test:browser`): dark и light при 1920×1080 и 1366×768, отсутствие page-level overflow, сдержанные статусы без цветных капсул, фильтры и поиск, detail drawer по Enter и deep-link, workflow A (создание из расследования с обратной связью в прогноз), workflow B (согласование и завершение), workflow C (отклонение), терминальные статусы без действий, неизвестный наряд и защита от дубликата. Скриншоты: `tickets-registry-{dark,light}-{1920,1366}.png`, `tickets-create-drawer.png`, `tickets-detail-drawer.png`, `tickets-approved.png`, `tickets-completed.png`.

### Ограничения

- Серверная фильтрация параметрами `/tickets` реализована в mock, но реестр работает с загруженной выборкой; серверная пагинация не вводится.
- Наряды, созданные мутацией, живут только в пределах сессии страницы.
- Reason при отклонении, история изменений статуса, вложения и бригадный справочник не реализованы — соответствующего backend-контракта нет.
- Detail-route наряда (`/tickets/:ticketId`) не вводится: состояние выражено query-параметром.
- Аналитика по нарядам (SLA, MTTR, дашборды) в Task 05 не реализуется.

## 18. Task 06 — Analytics

`/analytics` — аналитическое рабочее пространство инженера и руководителя смены. Реализация в `pages/analytics/`: отдельные компоненты summary strip, range control, Recharts timeline, горизонтальных распределений, top objects и ML coverage. Новых зависимостей нет. Завершённые Object Workspace, Prediction Investigation и Ticket lifecycle не переписаны.

### API, DTO и domain

`GET /analytics/summary?range=24h|7d|30d`. Default UI и mock endpoint — `7d`; неподдерживаемый range возвращает HTTP 400. Ответ — самостоятельный backend aggregate. Нельзя собирать его из `/predictions`, `/tickets`, `/objects` или вычислять open tickets / risk score в React.

```ts
type AnalyticsRange = '24h' | '7d' | '30d';
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
```

DTO: `api/dto/analytics.ts`; `toAnalyticsSummary` явно переводит snake_case в camelCase. Domain: `AnalyticsSummary`, `AnalyticsRiskTimelinePoint`, `AnalyticsUrgencyDistribution`, `AnalyticsObjectRisk`, `AnalyticsTicketStatus`, `AnalyticsMlDomainCoverage` в `domain/analytics/types.ts`. Charts получают domain, не DTO. Adapter сохраняет backend order объектов без сортировки и weighted scoring.

Pipeline: HTTP → DTO → adapter → domain → TanStack Query → UI. `useAnalyticsSummary(range)`, `analyticsKeys.all`, `analyticsKeys.summary(range)`; ключ содержит период, `apiGet` получает AbortSignal. `keepPreviousData` сохраняет предыдущую выборку при смене ключа; последняя успешная domain snapshot сохраняется на странице и при ошибке нового периода. Данные соседних диапазонов не смешиваются.

### Семантика агрегирования

- `generated_at` — момент среза; `range` — окно истории, оканчивающееся этим моментом. Все timestamps — абсолютные ISO-инстанты, отображение только Europe/Moscow.
- `active_predictions`, `critical_predictions`, `high_predictions`, `open_tickets`, `ml_coverage_percent`, urgency, top objects, ticket status и domain coverage — текущий snapshot на `generated_at`, не суммы исторических точек. Поэтому эти показатели могут совпадать между периодами.
- `completed_tickets` — число завершений внутри выбранного окна; эта вторичная метрика явно подписана «Выполнено за период». Она может отличаться от текущего количества нарядов в статусе completed, включающего более ранние завершения.
- Timeline — исторические количества активных рисков, а не количество новых событий или будущих аварий. Последняя точка согласована с текущими critical/high; low в графике не обязателен. Точки упорядочены и находятся внутри окна.
- Open tickets передаётся готовым числом, хотя семантически относится к draft + approved. Ticket distribution сохраняет canonical статусы draft, approved, rejected, completed и их порядок; labels берутся из общей карты, используемой `StatusBadge`.
- Urgency относится ко всем активным рискам, использует существующие `MaintenanceUrgency` и текстовые обозначения. Нормальный режим не означает отсутствие прогноза.
- Top objects — ограниченный ранжированный список; суммы по нему не обязаны равняться общим totals. Object ID/name согласованы с каталогом; клик/Enter ведёт к `/objects/:objectId`.
- Coverage — готовый процент 0..100 и supported/total по домену, не risk score. Общий процент взвешен по числу каналов; frontend не усредняет проценты доменов. Поддержано ≤ всего; при нулевом знаменателе backend должен возвращать 0. Human labels собраны в едином `getModelDomainLabel`.

### Mock и состояния

Фикстуры `api/mocks/analytics.ts` независимы от list endpoints и session-scoped ticket store. Snapshot — 20.09.2026 18:42 МСК: 137 активных, 8 critical, 24 high, 9 открытых нарядов, 80% ML. Для 24h/7d/30d заданы 13/8/16 исторических срезов с интервалами 2 часа / 1 день / 2 дня. История авторская, детерминированная, не реконструируется из текущих прогнозов, runtime random отсутствует. Изменения mock-нарядов не пересчитывают этот демонстрационный исторический snapshot.

Отсутствие агрегата: HTTP 200 с правильным range/generated_at, нулевыми totals и всеми массивами пустыми (`emptyAnalytics`). Такой ответ показывает «Аналитические данные отсутствуют» / «За выбранный период агрегаты пока не сформированы». Нулевой риск при наличии исторических точек или coverage не считается отсутствием аналитики.

Initial loading повторяет summary, timeline, urgency и lower sections skeleton. Initial error использует общий ErrorState с retry. При failed refresh сохраняются charts и общий StaleState. При смене периода сохраняются предыдущие данные и явная подпись «Показаны данные за …», включая неудавшийся запрос; метрики и график никогда не переименовываются в ещё не загруженный диапазон. Обновление повторяет запрос выбранного периода. Browser-only `setAnalyticsScenario` позволяет проверить loading/error/empty без изменения production UI.

### Представление и доступность

Одна компактная summary strip; semantic-red допустим только для critical. Timeline — три тонкие Recharts LineChart линии в существующих risk tokens, без gradient/area/glow. Ось 24h использует московские часы, 7d/30d — даты с прореживанием. Tooltip — полный московский timestamp и значения всех серий. Диаграммы срочности и статусов — нейтральные горизонтальные полосы; semantic marker дополняет urgency label. Donut/pie отсутствуют.

У каждого chart есть meaningful aria-label и текстовый summary. Timeline дополнительно предоставляет доступную с клавиатуры таблицу всех точек. Приоритетные строки объектов фокусируемы и открываются по Enter. Risk — dot + label; coverage — нейтральный процент/полоса и поддержано/всего. Операционные числа tabular. Dark/light используют общие tokens, page-level горизонтальный overflow запрещён.

### Проверки и ограничения

Unit tests проверяют DTO/domain, keys/ranges, границы и порядок timeline, положительность counts, уникальность dimensions, coverage consistency, независимый open-tickets aggregate, все состояния, навигацию, доступность, московское время и отсутствие вымышленных метрик.

`scripts/check-analytics.mjs` — девятый browser script в `test:browser`, существующие восемь сохранены. Матрица: dark/light 1920×1080 и 1366×768, 24h/30d, реальное изменение линий, keyboard select, tooltip, object navigation, loading/error/empty/stale и сохранение предыдущего периода. Screenshots: `analytics-{dark,light}-{1920,1366}.png`, `analytics-{24h,30d}.png`, дополнительные tooltip/loading/coverage. Требуется визуальный просмотр.

Ограничения: Analytics пока использует mock aggregates; lifecycle history отсутствует, MTTR/SLA и model-quality metrics (accuracy, precision, recall, F1, ROC-AUC) не считаются; arbitrary date picker отсутствует. Analytics не предсказывает количество будущих аварий. Backend integration, auth, realtime/WebSocket, pagination overhaul и production hardening в Task 06 не входят.

## Theme System (Task 02.2)

`ThemePreference = 'light' | 'dark' | 'system'`; `ResolvedTheme = 'light' | 'dark'`.
По умолчанию — `system`. Ключ localStorage `dolos-theme` содержит именно preference;
значение `system` не заменяется результатом разрешения. Отсутствующее, некорректное или
недоступное хранилище означает `system`. При запрещённой записи выбор действует в текущей сессии.

Блокирующий `public/theme-init.js` в head до React читает preference и устанавливает
`html[data-theme]`. Этот же runtime используется `ThemeProvider` (React Context) и
`useTheme()`: `preference`, `resolvedTheme`, `setPreference`. Скрипт входит в production
как отдельный локальный asset и должен быть разрешён политикой CSP (`script-src 'self'`).
CSS задаёт фон корня и соответствующий `color-scheme` до отрисовки приложения.

Provider подписывается на `matchMedia('(prefers-color-scheme: dark)')`, удаляет listener
при unmount и применяет изменения ОС только для `system`. Explicit light/dark остаётся
неизменным. Настройка доступна в существующем drawer «Профиль», поле «Тема интерфейса»:
«Системная», «Светлая», «Тёмная». Layout и продуктовая логика от темы не зависят.

Обе палитры определены в `src/styles/tokens.css`; геометрия и компонентные CSS общие.
Canvas/surface/elevated/hover, borders, primary/secondary/muted text, risk и status,
accent/focus имеют значения для каждой темы. Дополнительные токены: `--accent-hover`,
`--on-accent`, `--danger-bg/border/text/hover`, `--shadow-popover`, `--overlay`,
`--brand-border`, `--nav-active-bg/border`, `--avatar-bg/border`, `--bg-skeleton`.
Muted text скорректирован для контраста; light semantic colors темнее dark аналогов.
Skeleton без shimmer. Поверхности разделяются фоном и границами, тень только у popover.

Новые компоненты используют semantic CSS variables, а не hardcoded palette, локальные
`isDark` ветвления или копии CSS для каждой темы. Risk/urgency сохраняют нейтральный
текст и маленький цветной dot/marker; текст обязателен. Workflow badge остаётся
сдержанным. Новые состояния необходимо проверять в обеих темах, включая focus,
hover, disabled, loading, empty, error, stale и unsupported. Числа и ML-семантика
не зависят от темы: 46% температуры остаётся critical.

Проверки: theme unit tests, `scripts/check-theme.mjs`, существующие browser checks.
Theme browser check требует свежий `npm run build`, сам запускает preview на 4175,
проверяет production bootstrap с заблокированным JS приложения, обе палитры,
контраст текста/маркеров/focus, профиль, persistence, runtime OS changes и компоненты.
Скриншоты overview dark/light 1920×1080 и 1366×768 — `frontend/test-results/`.

## Historical Review и решения диспетчера (Tasks 10B.2–10B.3)

`/review` и `/review/:draftId` — отдельный historical workflow поверх `/api/v2`; он не заменяет
legacy `/predictions`. Источник — `dispatcher_api_v1` с base path `/api/v2`. Queue использует
Meta, Objects и flat Drafts с фильтрами `review_state`, `basis_kind`, `object_id` и cursor
pagination. Score подписан только как «Балл модели», не переводится в проценты и не означает
вероятность отказа, риск или срочность. Naive historical timestamps выводятся буквально через
`formatV2HistoricalTimestamp`; им не назначается МСК/UTC.

Detail загружает Draft, Evidence и append-only `GET /drafts/{draft_id}/decisions`. Pending draft
разрешает `POST /drafts/{draft_id}/decisions` с `decision: approved|rejected`, обязательным
`reason` и стабильным `idempotency_key` одной пользовательской попытки. Author определяется
backend-сессией. После success инвалидируются только v2 draft list, текущий detail и history.
409 означает, что решение уже сохранено: overwrite запрещён, UI обновляет detail/history и
показывает отдельное conflict-состояние. `decided_at` — timezone-aware серверное событие и
форматируется как операционное время Europe/Moscow.

Approval не создаёт наряд автоматически. Correction mutation, elevated-role UI, work-order
creation, auth, replay и v2 analytics не входят в реализованный workflow. История умеет показывать
`supersedes_decision_id` и `work_order_id`, если backend вернул их, без кнопки изменения решения.
