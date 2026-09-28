# Dolos · Frontend Foundation

Task 01: desktop-first каркас системы предиктивного мониторинга. Task 02: `/overview` — Operational Center с очередью рисков, сводкой и состоянием объектов. Остальные продуктовые страницы остаются shell screens. Task 03 не начат.

Source of truth для следующих задач: [docs/FRONTEND_CONTRACT_V2.md](../docs/FRONTEND_CONTRACT_V2.md). README описывает запуск и реализацию; нормативная frontend-спецификация находится в контракте.

## Запуск

Требуется **Node.js 24+**, npm. Версии зависимостей закреплены в `package-lock.json`.

```powershell
cd C:\Users\Pc\Desktop\лцт\frontend
npm install
npm run dev
```

Адрес: http://127.0.0.1:5173. `.env` уже содержит настройки локального mock-режима; `.env.example` — образец.

На текущем компьютере системный Node.js 18 устарел для выбранного стека. Локальная обёртка использует доступный Node.js 24 из runtime Codex, не изменяя системную установку:

```powershell
.\scripts\npm.ps1 install
.\scripts\npm.ps1 run dev
.\scripts\npm.ps1 run build
.\scripts\npm.ps1 test
```

На другом компьютере установите Node.js 24+. Обёртка зависит от наличия `npm.cmd` и либо подходящего системного Node, либо bundled runtime Codex.

## Архитектура

React + TypeScript strict + Vite; React Router; TanStack Query; Tailwind CSS; Lucide; MSW. Recharts установлен для следующих этапов, графики сейчас не создаются. Radix используется только как headless-механика tooltip, dropdown, tabs и drawer; визуальные стили собственные.

Поток данных: `HTTP → API DTO → adapter → domain → UI model → component`. DTO не передаются в presentation-компоненты. В `api/queries` размещены query hooks и фабрики ключей. Продуктовые shell-страницы не загружают фиктивные KPI.

```text
frontend/
├── .env.example
├── package.json / package-lock.json
├── public/mockServiceWorker.js
├── scripts/
│   ├── npm.ps1
│   ├── check-browser.mjs
│   └── check-real-mode.mjs
└── src/
    ├── main.tsx
    ├── app/
    │   ├── App.tsx
    │   ├── layouts/         AppLayout, Sidebar, SystemStatus
    │   ├── providers/       QueryClient, TooltipProvider, ErrorBoundary
    │   └── router/          routes, navigation
    ├── api/
    │   ├── client/          config, ApiError, abortable HTTP GET
    │   ├── dto/             PredictionDto, DashboardSummaryDto, resource DTOs
    │   ├── adapters/        DTO → domain
    │   ├── queries/         hooks, key factories
    │   └── mocks/           MSW handlers, prediction fixtures, independent summary
    ├── domain/              prediction, object, telemetry, ticket, dashboard
    ├── components/
    │   ├── ui/
    │   ├── data-display/
    │   ├── navigation/
    │   └── feedback/
    ├── pages/
    │   ├── overview/
    │   ├── objects/
    │   ├── object-workspace/
    │   ├── predictions/
    │   ├── prediction-investigation/
    │   ├── tickets/
    │   ├── analytics/
    │   └── foundation/      technical showcase, UI row adapter
    ├── styles/              tokens.css, globals.css
    ├── test/                setup
    └── utils/               formatters, risk/urgency labels
```

## Routes

- `/` → `/overview`.
- `/overview`, `/objects`, `/objects/:objectId`.
- `/predictions`, `/predictions/:predictionId`.
- `/tickets`, `/analytics`.
- `/foundation` — технический стенд, только при `VITE_ENABLE_MOCKS=true`. Открывается через «Состояние системы». Не является продуктовым реестром прогнозов.
- Неизвестный URL → экран «Страница не найдена».

## Design system и компоненты

`styles/tokens.css` содержит палитру, semantic colors, размеры текста, spacing, радиусы, геометрию и transitions. Sidebar — 224 px; topbar — 52 px; controls — 32 px; table rows — 40 px. На ширине менее 1100 px sidebar сворачивается до 64 px. Числа используют tabular numerals. Focus-visible, skip link, keyboard navigation, accessible names и reduced-motion предусмотрены.

Созданы:

- `Button` (primary, secondary, ghost, danger), `IconButton`.
- `Input`, `Select`, `SearchInput`.
- `Badge`, `RiskBadge`, `UrgencyBadge`, `StatusBadge`.
- `Tooltip`, `Dropdown`, `Tabs`, `Drawer`.
- `Panel`, `Divider`, `Breadcrumbs`, `PageHeader`, `PageShell`.
- `Table`, `TableHead`, `TableBody`, `TableRow`, `TableHeader`, `TableCell`.
- Generic `DataTable<T>`, `TruncatedText`, controlled `SortState`.
- `Skeleton`, `LoadingState`, `EmptyState`, `ErrorState`, `StaleState`, `UnsupportedMlState`, `ErrorBoundary`.

Сортировка DataTable управляется вызывающим компонентом через `sort` / `onSort`, подходит для серверной сортировки. Sticky header, alignment, ellipsis/tooltip и состояния данных встроены. Большие таблицы пока не виртуализированы.

## API и mock endpoints

Все адреса относительно `VITE_API_BASE_URL`:

| Метод | Endpoint                  | Ответ                                                    |
| ----- | ------------------------- | -------------------------------------------------------- |
| GET   | `/system`                 | `status`, `updated_at`                                   |
| GET   | `/predictions`            | `PredictionDto[]`; filters: `object_id`, `risk_level`    |
| GET   | `/predictions/:id`        | `PredictionDto` или 404                                  |
| GET   | `/objects`                | `ObjectDto[]`                                            |
| GET   | `/objects/status-summary` | `ObjectStatusSummaryDto[]`, приоритетная сводка объектов |
| GET   | `/objects/:id`            | `ObjectDto` или 404                                      |
| GET   | `/tickets`                | `TicketDto[]`, сейчас пустой список                      |
| GET   | `/dashboard/summary`      | `DashboardSummaryDto`, отдельный backend aggregate       |

Для list endpoints доступны `?scenario=empty`, `?scenario=error` (503), `?scenario=slow` (2500 ms). Остальные mock-запросы имеют небольшую задержку, позволяющую проверить loading. Это тестовые параметры MSW, а не согласованный контракт backend.

`useDashboardSummary()` получает `/dashboard/summary`, адаптирует ответ в `DashboardSummary` и использует ключ `dashboardKeys.summary()`. Summary не вычисляется из predictions, objects или tickets. Mock fixture описывает сеть из 12 480 каналов и 186 объектов; шесть foundation fixtures — неизменные граничные сценарии. На `/overview` summary отображает глобальные counts, время snapshot, наряды и coverage. «Срочные ≤24 ч» — сумма двух готовых urgency aggregate полей, а не risk counts.

Очередь использует `usePredictions({ view: 'operational' })` → `/predictions?view=operational`. Отдельный demo dataset содержит 24 прогноза: 5 critical, 7 high, 12 medium, восемь объектов и все пять ML-доменов. Adapter исключает unsupported/low и сортирует по urgency, затем probability DESC. Фильтры применяются к загруженной выборке; количество строк не выдаётся за глобальные 137. Object status получает отдельные backend aggregates через `useObjectStatusSummary()`. Ошибки, loading и cached stale data каждого блока обрабатываются независимо. Перемещение к detail shells доступно кликом и Enter.

`ApiError` нормализует HTTP, сетевые ошибки и невалидный JSON. AbortSignal сохраняет отмену запросов. QueryClient: staleTime 60 секунд, cache GC 5 минут, один retry для сетевых/серверных ошибок, без retry на 4xx. Статус API обновляется раз в минуту. При ошибке обновления сохранённые данные доступны с предупреждением.

## Семантика ML

Frontend **не вычисляет** риск, срочность и ИТС из вероятности. Адаптер переносит их из backend. Если `prediction_supported=false`, ML-поля нормализуются в `null`, факторы — в пустой список. UI показывает «ML-анализ недоступен» и `—`.

| Fixture   | Домен           | Вероятность | Риск     | Срочность      |
| --------- | --------------- | ----------- | -------- | -------------- |
| TEMP-001  | ANALOG_TEMP     | 46%         | critical | FLASH_1_6H     |
| POWER-002 | POWER_PHASE     | 82%         | critical | FLASH_1_6H     |
| HYDRO-003 | HYDRO_MECHANICS | 63%         | high     | URGENT_6_24H   |
| GAS-004   | ANALOG_GAS      | 41%         | medium   | PLANNED_24_48H |
| FIRE-005  | FIRE_SAFETY     | 8%          | low      | NORMAL         |
| DOOR-006  | null, КД Дверь  | null        | null     | null           |

Форматтеры: `formatProbability`, `formatHealthIndex`, `formatDateTime`, `formatRelativeTime`, `getRiskLabel`, `getUrgencyLabel`. Все операционные даты отображаются в `Europe/Moscow`, независимо от timezone браузера: `20.09.2026, 18:42 МСК`. Строковые timestamps API должны содержать `Z` или явное смещение `±HH:MM`; неоднозначные строки без timezone, невалидные значения и `null` отображаются как `—`. Числа трактуются как epoch milliseconds. Относительное время считается по разнице абсолютных моментов времени.

## Environment

| Variable            | Default/local value            | Назначение                                                      |
| ------------------- | ------------------------------ | --------------------------------------------------------------- |
| `VITE_API_BASE_URL` | `http://localhost:8000/api/v1` | Общий base URL; без настройки fallback `/api/v1`                |
| `VITE_ENABLE_MOCKS` | `true` в локальном `.env`      | Только точное `true` запускает MSW; иначе реальные HTTP-запросы |

Для реального backend создайте `.env.local` и задайте `VITE_ENABLE_MOCKS=false` и актуальный URL. После изменения env перезапустите Vite; для production выполните новую сборку. Не помещайте секреты в `VITE_*`: эти значения публичны в браузере.

## Проверка

```powershell
npm run typecheck
npm test
npm run build
npm run format:check

# При запущенном npm run dev на 5173:
npm run test:browser

# Сам запускает отдельный Vite на 5174 и тестовый HTTP backend:
npm run test:real
```

В браузерных проверках используется установленный Microsoft Edge. Можно задать `BROWSER_CHANNEL=chrome`. `TEST_BASE_URL` меняет адрес для `test:browser`.

Проверки охватывают strict TypeScript, production build, форматирование, адаптеры, критический риск при 46%, unsupported, API filters/errors/cancellation, таблицу, московское время и независимые агрегаты. Operational Center tests проверяют summary/coverage, urgency order, filters, navigation, local loading/errors, empty и cached stale data. `test:browser` запускает общий сценарий и `scripts/check-overview.mjs`: routes, keyboard flow, MSW, независимые состояния блоков, retry, layouts 1920/1366 и компактный shell 800. Browser timezone — Tokyo или Los Angeles; UI остаётся московским. Real mode проверяется с тестовым HTTP backend без MSW. Скриншоты сохраняются в `test-results/`.

## Известные ограничения и интеграция

- Актуальные endpoints, DTO, правила времени и ML зафиксированы в `../docs/FRONTEND_CONTRACT_V2.md`; backend должен реализовать этот контракт.
- `../backend_app_ml_predictor.py` — ML-модуль, не HTTP-сервер. Его fallback для неизвестных датчиков сейчас возвращает low / 1% / ИТС 99. Backend-обёртка должна выдавать явный `prediction_supported=false` и nullable ML-поля по frontend-контракту. Frontend не определяет поддержку модели по названию датчика.
- Настоящий backend ещё не подключён. Проверка real mode использует небольшой тестовый HTTP-сервер. Для другого origin backend должен настроить CORS.
- Полный runtime schema validation ответов не добавлен; пока есть TypeScript DTO и проверка корректности JSON.
- Авторизация, роли/права, mutations, pagination, realtime-подписки и продуктовые workflows не входят в Task 01.
- Детальные страницы пока показывают route ID, без проверки существования сущности. API detail queries и 404 response подготовлены для следующего этапа.
- Fixtures — синтетические данные, не фактическое состояние объектов. Recharts установлен, но не используется до реализации графиков.
- Для production-хостинга необходим SPA fallback на `index.html`; запускать сборку следует с `VITE_ENABLE_MOCKS=false`.

## Operational Center и следующие этапы

`pages/overview` содержит компактную summary strip и единый двухколоночный workspace: слева queue, справа object status, tickets и coverage. Sorting/filtering/formatting вынесены из markup. Никаких графиков или дополнительных продуктовых страниц в Task 02. Новый ObjectStatusSummary DTO и operational view согласованы в source-of-truth контракте; настоящий backend должен их реализовать. Demo — фиксированный snapshot, не live telemetry; pagination, auto polling Dashboard и virtualized tables пока отсутствуют. Для ручного обновления у каждого блока есть отдельный control. Подробный перечень файлов и результатов — [Task 02 report](../docs/TASK02_REPORT.md).

## Тема интерфейса

Откройте «Профиль» → «Тема интерфейса» и выберите «Системная», «Светлая» или «Тёмная».
По умолчанию используется системная тема, которая следует изменениям темы ОС без
перезагрузки. Выбор сохраняется в этом браузере; светлая и тёмная темы действуют
независимо от ОС. Если браузер запрещает localStorage, выбор действует до перезагрузки.
