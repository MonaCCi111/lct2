# Backend — сервис прогнозирования инцидентов коллекторов (команда Dolos, ЛЦТ 2026, кейс №8)

FastAPI + SQLAlchemy 2 (async) + PostgreSQL 15. Отдаёт фронтенду диспетчера ОДС прогнозы отказов датчиков СМВУ,
телеметрию, схему пикетов, наряды на ТО, аналитику, отчёты Excel/PDF и погоду Москвы.

## Запуск

### Docker (для жюри) — одна команда
```bash
cd backend
docker compose up --build
```
- API: http://localhost:8000, Swagger: http://localhost:8000/docs
- PostgreSQL 15 (`postgres:15-alpine`), том `pgdata`
- При первом старте схема создаётся автоматически, справочники и срез телеметрии загружаются из `data/`
  (≈10 с), затем в фоне строится почасовая история рисков для аналитики. Никаких ручных миграций.

### Локально без Docker (SQLite)
```bash
cd backend
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```
По умолчанию `DATABASE_URL=sqlite+aiosqlite:///./app.db`. Чтобы пересоздать базу — удалить `app.db`.

### Переменные окружения
| Переменная | По умолчанию | Назначение |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./app.db` | В Docker: `postgresql+asyncpg://postgres:postgrespassword@db:5432/moscollector` |
| `CORS_ORIGINS` | `*` | Список через запятую |
| `DATA_DIR` | `./data` | Справочники и срез телеметрии |
| `ML_HANDOFF_DIR` | `./data/ml_handoff` | Пакет Славы (`integration/backend_sanya`), опционально |
| `TELEMETRY_REPLAY_SHIFT` | `true` | Сдвиг среза телеметрии к текущему моменту (см. ниже) |

## Данные

| Файл | Содержимое |
|---|---|
| `data/catalog/справочник_объектов_диспетчер.csv` | 95 объектов, 3 уровня (район → 16 коллекторов → ДП/ДУ/отсеки) |
| `data/catalog/справочник_каналов_датчиков.csv` | 11 485 каналов, 19 типов датчиков, 6 подсистем |
| `data/telemetry_sample_100k.csv` | 67 858 записей, 347 каналов, 01–08.01.2026 (срез из `dataset/representative_slice`) |

Нормализация по INTEGRATION_SPEC §1.2–1.4: `значение_датчика` → `raw_value` / `numeric_value` / `status_code`
(`normal | failure | alarm | unknown`); `t/f/True/False` → boolean; повторные заголовки и даты `1970-01-01` отбрасываются.
Пикет парсится из названия датчика (`ТЕМП ПК275+9` → `ПК275+9`, 275.09).

**Режим воспроизведения.** Срез телеметрии относится к январю 2026. Фронт запрашивает окна «последние 6/24/48 ч»
от текущего времени, поэтому при загрузке все метки сдвигаются так, чтобы последняя запись совпала с моментом старта.
Отключается `TELEMETRY_REPLAY_SHIFT=false`.

**Привязка каналов к объектам.** Справочник каналов взят из пакета ML (`integration/backend_sanya/data/catalog`),
в нём есть колонка `ид_объект` — объект 3 уровня (например, канал 228571 → 5343 «объект Кси ПК202-ПК302»).
Счётчики и риск в v1 суммируются вверх по дереву: объект 3 уровня → коллектор → район.

## ML

`app/ml/predictor.py` — контракт `SensorRiskInput` / `SensorRiskOutput` (INTEGRATION_SPEC §2.3) и `DummyPredictor`.
Признаки (`app/ml/features.py`) считаются по окну 24 ч: число смен статуса за 1/24 ч (дребезг), доля тревог,
σ числовых показаний, часы с последней тревоги. Заглушка: правило спека §2.4 (дребезг > 5 или тревог > 20% → 0.88,
critical) плюс градуированный балл для остальных. Прогнозы пересчитываются при старте и при `POST /telemetry/ingest`.

**Подключение боевой модели:** в `load_predictor()` вернуть объект с методами `predict(SensorRiskInput) -> SensorRiskOutput`,
`supports(sensor_type) -> bool` и атрибутом `model_version`. Веса кладутся в `app/ml/weights/`.

## API v1 (`/api/v1`)

Формы ответов совпадают с тем, что потребляет фронтенд (`frontend-dolos: docs/BACKEND_API_CONTRACT_V1.md`),
плюс имена из INTEGRATION_SPEC. Роль передаётся заголовком `X-User-Role: dispatcher | supervisor` (по умолчанию dispatcher),
автор действий — `X-User-Id` (до появления аутентификации).

| Метод | Путь | Назначение |
|---|---|---|
| GET | `/system` | Состояние сервиса |
| GET | `/dashboard/summary` | Сводка: каналы, прогнозы по риску/срочности, объекты, наряды |
| GET | `/objects` | Плоский справочник объектов (`?level=2` — только коллекторы) |
| GET | `/objects/status-summary` | Риск и счётчики по 16 коллекторам (`?scope=all` — все объекты) |
| GET | `/objects/{id}` | Карточка объекта |
| GET | `/objects/{id}/topology` | Линейная схема коллектора по пикетам (сегменты = объекты 3 уровня с диапазоном ПК) |
| GET | `/predictions` | Прогнозы (`view=operational`, `object_id`, `risk_level`, `subsystem`, `min_probability`) |
| GET | `/predictions/sensors` | Реестр в обёртке `{total_predictions, generated_at, items}` (ARCHITECTURE §3.2) |
| GET | `/predictions/{id}` | Прогноз по каналу (`pred-<tag_root>-<channel_id>`) |
| GET | `/sensors/{channel_id}/telemetry` | Ряд телеметрии: `date_from`, `date_to`, `limit` ≤ 1000; даунсэмплинг сохраняет все смены статуса, флаг `is_chatter` |
| POST | `/telemetry/ingest` | Пакетная загрузка с нормализацией и пересчётом прогноза |
| GET | `/tickets` | Наряды (`status`, `search`, `prediction_id`, `object_id`) |
| GET | `/tickets/{id}` | Наряд |
| POST | `/tickets` | Создание (201). Один прогноз → не более одного наряда (иначе 409) |
| PATCH | `/tickets/{id}/status` | `draft → approved/rejected`, `approved → completed`; иначе 409; `rejected` требует `comment` |
| POST | `/tickets/feedback` | Решение диспетчера по прогнозу с причиной |
| GET | `/analytics/summary` | `range=24h|7d|30d`: итоги, почасовая динамика рисков, срочность, топ объектов, покрытие ML |
| GET | `/reports/incidents.xlsx` | Реестр прогнозов и нарядов (openpyxl) |
| GET | `/reports/summary.pdf` | Справка для руководства (reportlab, шрифт DejaVu в `app/reports/fonts`) |
| GET | `/weather/current` | Погода Москвы (Open-Meteo), кэш 1 ч, дефолт при недоступности сети |

Время в ответах — ISO 8601 с `+03:00`. Ошибки — единое тело:
```json
{"error_code": "RESOURCE_NOT_FOUND", "code": "RESOURCE_NOT_FOUND", "message": "…", "details": null, "timestamp": "2026-09-27T22:00:00+03:00"}
```
Коды: 400 — некорректный запрос, 403 — неизвестная роль, 404 — нет сущности, 409 — конфликт/недопустимый переход,
422 — нарушение длины полей наряда.

## API v2 (`/api/v2`) — исторический разбор черновиков ML

Контракт: `data/ml_handoff/api_contract_v1.json` (`dispatcher_api_v1`). Все 25 маршрутов:
`meta`, `model-types`, `objects`, `overview`, `channels`, `situations` (+`evidence`), `groups`, `drafts` (+`evidence`,
`decisions`, `decision-corrections`), `work-orders`, `charts/cases`, `fire-history`, `replays` (+`events`).

- **Данные.** Исторический пакет (отсечка 30.06.2026) лежит в `data/ml_handoff/data/**.parquet` (Git LFS, 35 файлов,
  SHA256 сверены с `package_manifest.json`) и при старте загружается в память (pyarrow). Контрольные числа совпадают с
  пакетом ML: 12 627 каналов, 11 704 ситуации, 2 191 черновик, 1 621 группа, 1 142 канала вне справочника, 8 сценариев.
  Если репозиторий склонирован без LFS, сервис переходит на `fixtures_v1.json`; `GET /meta` → `data_source` это покажет.
- **Время.** Исторические метки отдаются буквально `YYYY-MM-DDTHH:MM:SS` без зоны; `at`/`from`/`to` с `Z` или
  смещением → 422. Всё с `available_at > at` скрыто. Серверные `decided_at`/`created_at` — с `+03:00`.
- **Решения.** `POST /drafts/{id}/decisions`: `decision`, непустой `reason`, `idempotency_key`; автор из `X-User-Id`.
  Тот же ключ → прежний ответ (200); другое решение по уже решённому черновику → 409. Исправление — только
  `decision-corrections` с ролью `supervisor` (иначе 403) и `expected_decision_id` (иначе 409). История append-only.
- **Наряды.** `POST /work-orders` только после `approved` (иначе 409), один на черновик, ID выдаёт бэкенд
  (`WO2-2026-00001`); связь видна в `Draft.decision.work_order_id`.
- **Пагинация.** `{items, next_cursor}`, `limit` по умолчанию 50, максимум 200, курсор непрозрачный.
- В очереди только действующие модели из `runtime_policy_v1.json` (`power_phase_scada_v2`, `pump_scada_v1`);
  `score` отдаётся как есть, `its_value` и `real_fire_count` остаются `null`.

Если parquet пришли указателями (клон без LFS): `git lfs install && git lfs pull` в корне репозитория.

## Тесты
```bash
cd backend && pytest -q
```

## Демо-сценарий (INTEGRATION_SPEC §6)
```bash
curl localhost:8000/api/v1/objects/status-summary                  # объект Кси в красной зоне
curl localhost:8000/api/v1/objects/5327/topology                   # сегмент ПК202-ПК302 критический
curl localhost:8000/api/v1/predictions/pred-847-228571             # ТЕМП ПК275+9: дребезг, риск ≥ 88%
curl "localhost:8000/api/v1/sensors/228571/telemetry?limit=500"    # Норма/Неисправен каждые секунды
curl -X POST localhost:8000/api/v1/tickets -H 'Content-Type: application/json' \
  -d '{"prediction_id":"pred-847-228571","object_id":5327,"title":"Протяжка клемм ПК275","description":"Протяжка клеммных соединений на ПК275","assignee":"ЭТР-3"}'
curl -X PATCH localhost:8000/api/v1/tickets/WO-2026-0001/status -H 'Content-Type: application/json' -d '{"status":"approved"}'
```

## Структура
```
app/
  api/v1, api/v2 роутеры REST;  api/deps.py — сессия БД и RBAC;  api/errors.py — формат ошибок
  core/          настройки, подключение к БД, работа со временем (МСК)
  db/            ORM-модели и сидинг справочников
  ml/            контракт предиктора, заглушка, расчёт признаков
  reports/       генераторы xlsx/pdf и шрифты
  schemas/       Pydantic v2 контракты
  services/      нормализация, скоринг, агрегаты, сериализация
  v2/            загрузка исторического пакета ML (pyarrow) для API v2
data/            справочники, срез телеметрии, data/ml_handoff — пакет ML
```

## Ограничения текущей версии
- API v2 — исторический режим; живой поток требует инкрементального расчёта признаков от ML (ещё не выпущен).
- Прогнозы v1 — от `DummyPredictor`; вероятности эвристические до подключения моделей ML.
- `live_ingestion_available=false`: инкрементальный расчёт признаков для живого потока ML ещё не выпущен.
