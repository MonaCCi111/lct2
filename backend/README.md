# Dolos API

FastAPI обслуживает исторический диспетчерский маршрут `/api/v2` и прежний демонстрационный маршрут `/api/v1`. Текущий интерфейс использует v2. Полный порядок запуска фронта и бэкенда приведён в [корневом README](../README.md).

## Локальный запуск

Перед запуском выполните `git lfs pull` в корне репозитория. В PowerShell из каталога `backend`:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

По умолчанию используется локальная SQLite `app.db`. Схема и небольшой срез данных создаются при первом старте. OpenAPI доступен по `http://127.0.0.1:8000/docs`. Для запуска в Docker есть `docker-compose.yml` в этом каталоге; он поднимает API и PostgreSQL.

| Переменная | Назначение |
| --- | --- |
| `DATABASE_URL` | строка подключения SQLite или PostgreSQL |
| `CORS_ORIGINS` | разрешённые адреса браузерного фронта через запятую |
| `DATA_DIR` | справочники и демонстрационный срез для v1 |
| `ML_HANDOFF_DIR` | пакет ML для v2; по умолчанию `backend/data/ml_handoff` |
| `REPLAY_SOURCE_ROOT` | полный локальный архив для произвольного воспроизведения |
| `REPLAY_CATALOG` | справочник каналов для произвольного воспроизведения |
| `REPLAY_CACHE_DIR` | локальный кэш этих расчётов |

Пример значений находится в `.env.example`. Восемь готовых сценариев воспроизведения работают без `REPLAY_SOURCE_ROOT`.

## Исторический API v2

Контракт полей и маршрутов хранится в [api_contract_v1.json](data/ml_handoff/api_contract_v1.json). `GET /api/v2/meta` показывает версию данных и `data_source`. При корректно загруженном LFS источник равен `ml_handoff_parquet`; при отсутствии данных сервис может перейти на fixtures. Пакет содержит 12 627 каналов, 11 704 ситуации, 2 191 черновик и 1 621 группу.

Основные разделы API: `overview`, `objects`, `channels`, `situations`, `groups`, `drafts`, `work-orders`, `quality`, `coverage`, `fire-history` и `replays`. Исторические метки времени не имеют подтверждённой зоны и отдаются без `Z` или `+03:00`. Решения диспетчера и наряды сохраняются в локальной базе; серверные метки времени содержат зону. Повтор запроса с тем же `idempotency_key` возвращает прежнее решение. Конфликтующие решения требуют отдельного маршрута исправления.

`score` – внутренний балл конкретной модели, а не вероятность физической аварии. Достоверного реестра пожаров и числового ИТС в источнике нет. `live_ingestion_available=false` в `/meta` отражает отсутствие живого потока для v2.

## Проверка

```powershell
.\.venv\Scripts\python.exe -m pytest tests -q
```

Состав пакета и результаты ML-проверок описаны в [validation/FINAL_PRODUCT_V1_STATUS.txt](../validation/FINAL_PRODUCT_V1_STATUS.txt).
