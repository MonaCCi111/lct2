# Dolos — Frontend Contract V2

Актуальная frontend-спецификация. Этот файл — **source of truth для последующих задач**: архитектура, визуальные ограничения, доменная семантика, API-контракты и правила времени. README описывает запуск и проверку, но не переопределяет этот контракт. Изменения требований нужно отражать здесь вместе с кодом и тестами.

Состояние: Task 01 (Frontend Foundation), Task 02 (`/overview` — Operational Center) и Task 03 (`/objects/:objectId` — Object Workspace) реализованы. Остальные продуктовые страницы остаются shell screens. Task 04 (Prediction Investigation, telemetry charts, наряды, аналитика) не входит в текущий объём.

## 1. Назначение и границы текущего этапа

Dolos — система предиктивного мониторинга инженерной инфраструктуры, рабочий инструмент диспетчера. На текущем этапе реализованы application shell, routing, design tokens, reusable primitives, domain types, API client, DTO adapters, TanStack Query и mock API.

Кроме `/overview` и `/objects/:objectId`, продуктовые страницы остаются минимальными shell screens: заголовок, breadcrumb и аккуратный placeholder. Telemetry charts, Prediction Investigation, Predictions Registry, ticket creation flow и analytics charts реализуются отдельными задачами.

Task 02 разрешает подключить Dashboard Summary к `/overview` в рамках спецификации раздела 12. Task 03 добавляет Object Workspace в рамках раздела 13. Существующая архитектура сохраняется.

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
| `/objects`                   | Объекты                                                     |
| `/objects/:objectId`         | Object Workspace: состояние, топология по пикетам, прогнозы |
| `/predictions`               | Прогнозы                                                    |
| `/predictions/:predictionId` | Prediction Investigation shell                              |
| `/tickets`                   | Наряды                                                      |
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
export interface TicketDto {
  ticket_id: string;
  prediction_id: string;
  title: string;
  status: TicketStatus;
  created_at: string;
}
export interface SystemDto {
  status: "operational" | "degraded";
  updated_at: string;
}
```

`toObject` → `InfrastructureObject` (`id`, `name`, `parentObjectId`, `subsystem`); `toTicket` → `Ticket` (`id`, `predictionId`, `title`, `status`, `createdAt`). System query переводит `updated_at` в `updatedAt`.

Telemetry domain foundation: `channelId`, `timestamp`, nullable `value`, `unit`, `quality: 'valid' | 'missing' | 'invalid'`. Telemetry API и графики пока не определены.

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
| GET    | `/tickets`                    | TicketDto[]; сейчас пустой mock list                  |

List endpoints возвращают массивы. Write endpoints и создание нарядов в этот этап не входят.

```env
VITE_API_BASE_URL=http://localhost:8000/api/v1
VITE_ENABLE_MOCKS=true
```

Без base URL используется `/api/v1`. Только строка `true` включает MSW; false использует backend без изменений React-компонентов. MSW запускается до render приложения. После изменения env нужен restart Vite или новая production build. VITE-переменные публичные, не для секретов.

Общий `ApiError`: message, status, code (`NETWORK_ERROR`, `HTTP_ERROR`, `INVALID_RESPONSE`). HTTP errors могут содержать JSON `{ message: string }`. Отмена запроса не превращается в network error. `alert()` запрещён.

Query keys централизованы: `predictionKeys.all/list(filters)/detail(id)`, `objectKeys.all/list()/statusSummary()/detail(id)/topology(id)`, `ticketKeys.all`, `systemKeys.all`, `dashboardKeys.all/summary()`. QueryClient: staleTime 60 секунд, gcTime 5 минут, один retry для network/server errors, без retry на 4xx; refetch on focus. System status polling — 60 секунд. Summary отдельный polling пока не имеет.

UI states: loading, error, empty, success, stale. Cached data сохраняется при ошибке обновления с предупреждением, retry доступен пользователю.

Mock list endpoints поддерживают `?scenario=empty|error|slow`; это исключительно тестовые параметры. Summary возвращает объект с задержкой 250 ms, не пустой массив. Ошибки summary в тестах задаются MSW override. Production frontend backend URL не хардкодится в components.

## 11. Проверки и ограничения интеграции

Перед завершением изменений: `npm run typecheck`, `npm test`, `npm run build`, `npm run format:check`, `npm run test:browser` (check-browser → check-overview → check-object-workspace → check-theme), `npm run test:real`. При системном Node 18 на текущем компьютере используется `frontend/scripts/npm.ps1`, выбирающий доступный Node 24.

Проверки должны сохранять сценарии 46% = critical, unsupported ML, отсутствие пересчёта backend aggregate, московское время при другой browser timezone, routing, клавиатурный фокус, loading/error/empty/stale и mock/real mode. Браузерные тесты запускаются в Edge или Chrome.

Известные ограничения:

- Настоящий HTTP backend пока не подключён. `backend_app_ml_predictor.py` — ML-модуль; его fallback low / 1% / ИТС 99 для неизвестных датчиков не соответствует этому frontend-контракту. Backend-обёртка должна выдавать явный `prediction_supported=false` и nullable ML-поля.
- TypeScript DTO не заменяют runtime schema validation; сейчас client проверяет HTTP и корректность JSON.
- Авторизация, роли/права, mutations, pagination, realtime, virtualized tables и продуктовые workflows не реализованы.
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

Task 04 не начинается: telemetry chart, Prediction Investigation, Root Cause Analysis UI, ticket creation drawer, ticket mutations и supervisor analytics не реализуются.

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
