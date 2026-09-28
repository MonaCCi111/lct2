# Task 02 — Operational Center

Реализован только `/overview`. Object Workspace, Prediction Investigation, Tickets и Analytics остаются shell pages. Task 03 не начат.

## Результат

Компактный header показывает timestamp snapshot в МСК. Единая summary strip содержит глобальные backend counts; срочные ≤24 ч — сумма двух urgency aggregate полей. Общий workspace разделён примерно 68/32: слева плотная очередь рисков, справа объектные агрегаты, вторичная сводка нарядов и ML coverage. Нет charts, giant KPI cards, gradient/glow/glass.

В queue 24 отдельных demo predictions (5 critical, 7 high, 12 medium), восемь объектов и все пять ML-доменов. Сортировка urgency → probability DESC, без пересчёта риска. Температура 46% остаётся critical. Foundation fixtures не изменены. Queue count явно показывает загруженную выборку, а не все глобальные 137.

Фильтры: urgency, объект, поиск sensor/object/piket. Клик строки и Enter открывают prediction shell; ссылки объектов — object shell. Summary, queue и object status независимо загружаются и восстанавливаются после ошибки; failed refresh сохраняет cached data и показывает StaleState.

## API

- Добавлен `GET /objects/status-summary` → `ObjectStatusSummaryDto[]`, отдельный backend aggregate.
- Domain `ObjectStatusSummary`, adapter, `objectKeys.statusSummary()` и `useObjectStatusSummary()`.
- Существующий `GET /predictions` расширен `view=operational` для приоритетной выборки; используется существующий `usePredictions`. Response остаётся `PredictionDto[]`.
- Detail mock endpoints разрешают ID нового набора; `/objects/status-summary` зарегистрирован раньше `/objects/:id`.
- `GET /dashboard/summary` подключён к UI, DTO не изменён. Coverage 80 — это 80%, а не 8000%.
- Новые контракты до реализации зафиксированы в `FRONTEND_CONTRACT_V2.md`.

## Изменённые и добавленные файлы

Пути относительно корня проекта `C:\Users\Pc\Desktop\лцт`:

```text
docs/FRONTEND_CONTRACT_V2.md
docs/TASK02_REPORT.md
frontend/README.md
frontend/package.json
frontend/scripts/check-browser.mjs
frontend/scripts/check-overview.mjs
frontend/scripts/check-real-mode.mjs
frontend/src/api/dto/object-status.ts
frontend/src/domain/object/status.ts
frontend/src/api/adapters/object-status.ts
frontend/src/api/adapters/operational-queue.ts
frontend/src/api/adapters/operational.test.ts
frontend/src/api/mocks/operational.ts
frontend/src/api/mocks/scenarios.ts
frontend/src/api/mocks/handlers.ts
frontend/src/api/queries/hooks.ts
frontend/src/api/queries/keys.ts
frontend/src/app/layouts/AppLayout.tsx
frontend/src/components/data-display/DataTable.tsx
frontend/src/utils/formatters.ts
frontend/src/pages/overview/OverviewPage.tsx
frontend/src/pages/overview/OverviewPage.test.tsx
frontend/src/pages/overview/SummaryStrip.tsx
frontend/src/pages/overview/RiskQueue.tsx
frontend/src/pages/overview/QueueFilters.tsx
frontend/src/pages/overview/queue-model.ts
frontend/src/pages/overview/ObjectStatusPanel.tsx
frontend/src/pages/overview/OperationalStatus.tsx
frontend/src/pages/overview/overview.css
```

DataTable расширен опциональными row props, column classes, empty description/action и количеством skeleton rows. Остальные его потребители сохраняют прежнее поведение. AppLayout скрывает на overview дополнительный timestamp API, чтобы не смешивать его со временем snapshot. Общие Intl formatters создаются один раз на модуль.

## Tests и команды проверки

```powershell
cd C:\Users\Pc\Desktop\лцт\frontend
.\scripts\npm.ps1 run typecheck
.\scripts\npm.ps1 test
.\scripts\npm.ps1 run build
.\scripts\npm.ps1 run format:check
.\scripts\npm.ps1 run test:browser
.\scripts\npm.ps1 run test:real
```

44 unit/integration tests в восьми test files, включая 17 новых проверок Operational Center:

- Summary counts, Moscow timestamp, coverage 80%, ticket counts.
- 46% critical, urgency-first ordering, probability tie ordering, null probability.
- Unsupported/low exclusion и неизменность foundation data.
- Click/Enter navigation, ссылки объектов, filters и reset.
- Независимая загрузка, summary error при работающей queue, predictions error при работающей summary, object error.
- Empty queue без подмены global summary нулями.
- Cached data после failed refresh каждого из трёх источников.
- Object aggregates сохраняются без пересчёта риска; dataset содержит все ML-домены.

Browser checks: 1920×1080, 1366×768, дополнительная ширина shell 800; нет общего horizontal overflow; читаемая правая колонка; на Full HD минимум десять строк и coverage в первом viewport. Tab проходит sidebar → filters → queue → objects. Проверяются MSW, real HTTP mode, Московское время в браузерах Tokyo/Los Angeles, независимые ошибки, retry, empty и stale. Browser-test overrides импортируются только тестовым сценарием и не являются пользовательским control.

## Screenshots

- [Overview 1920×1080](../frontend/test-results/overview-1920.png)
- [Overview 1366×768](../frontend/test-results/overview-1366.png)
- [Queue loading](../frontend/test-results/overview-loading.png)
- [Summary error, queue и объекты работают](../frontend/test-results/overview-summary-error.png)
- [Queue error, summary и объекты работают](../frontend/test-results/overview-queue-error.png)
- [Cached queue после failed refresh](../frontend/test-results/overview-stale.png)

## Ограничения

- Настоящий backend пока не подключён. Он должен реализовать object aggregate endpoint и operational view по контракту; real-mode test использует тестовый HTTP-сервер.
- Mock snapshot фиксированный: 20.09.2026, 18:42 МСК. Это demo, не актуальные данные инфраструктуры.
- Queue и object panel — приоритетные выборки; они не содержат все 137 рисков и 42 затронутых объекта. Filters действуют только на загруженные predictions.
- Dashboard обновляется вручную по блокам и при возврате фокуса согласно QueryClient; отдельного polling или realtime нет.
- На 1366×768 разрешён вертикальный scroll страницы; Type скрыт, важные колонки доступны, table имеет собственный scroll.
- Pagination и virtualized tables не добавлены. Остальные продуктовые экраны остаются shells.
