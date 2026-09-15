# Инструкция для разработчика бэкенда (Саня, Backend)

Данный документ является исчерпывающим техническим руководством для Сани (или субагента, выполняющего задачи бэкенда). Все интерфейсы согласованы с капитаном команды и зафиксированы в [INTEGRATION_SPEC.md](file:///g:/lct2/INTEGRATION_SPEC.md) и [ARCHITECTURE_AND_ROLES.md](file:///g:/lct2/ARCHITECTURE_AND_ROLES.md).

---

## 0. Как скормить эту задачу ИИ-агенту (Cursor, Claude, Copilot)

### Пакет файлов для контекста агента (Context Pack):
Саня прикрепляет в контекст своего агента ровно 4 файла:
1. `TASK_ANALYSIS.md` – бизнес-контекст ДЖКХ, проблематика Москоллектора, критерии оценки жюри;
2. `DATA_AUDIT.md` – структура справочников, типы датчиков, 3 уровня иерархии объектов для сидинга базы данных;
3. `INTEGRATION_SPEC.md` – технический закон проекта (форматы DateTime, Pydantic-модели, REST API, даунсэмплинг, RBAC, отчеты, Docker);
4. `BACKEND_SANYA_GUIDE.md` – данная персональная инструкция разработчика бэкенда.

### Готовый стартовый промпт для нейросети:
> «Ты – Senior Backend Developer команды Dolos на хакатоне ЛЦТ 2026. Изучи прикрепленные файлы TASK_ANALYSIS.md, DATA_AUDIT.md и INTEGRATION_SPEC.md для глубокого понимания предметной области ДЖКХ Москвы и архитектурных контрактов. Твоя зона ответственности описана в BACKEND_SANYA_GUIDE.md. Разрабатывай сервис СТРОГО в директории backend/. Ни при каких обстоятельствах не изменяй схемы данных и имена эндпоинтов из INTEGRATION_SPEC.md. Не пытайся читать 15 ГБ сырых CSV, для тестов используй только срез dataset/representative_slice/telemetry_sample_100k.csv. Начни с развертывания каркаса FastAPI, моделей SQLAlchemy для PostgreSQL 15, сидинга справочников и заглушки DummyPredictor.»

---

## 1. Границы ответственности и исключение размытых задач

### Что Саня ДЕЛАЕТ:
1. Разворачивает серверное приложение на FastAPI (Python 3.11+).
2. Настраивает реляционную базу данных: в Docker развертывает PostgreSQL 15 (`postgres:15-alpine`), локально поддерживает SQLite через переменную окружения `DATABASE_URL`.
3. Реализует автозагрузку (seeding) справочников при старте приложения: 95 объектов из `справочник_объектов_диспетчер.csv` и 11 485 каналов из `справочник_каналов_датчиков.csv`.
4. Реализует все эндпоинты REST API по спецификации [INTEGRATION_SPEC.md](file:///g:/lct2/INTEGRATION_SPEC.md).
5. Реализует класс-заглушку `DummyPredictor` для немедленной отдачи предиктивной аналитики на фронтенд.
6. Обеспечивает стыковочный интерфейс инференса: когда Слава передаст файл весов `catboost_sensor_failure.cbm`, Саня подключает его одной строчкой в синглтон-предиктор.
7. Реализует выгрузку отчетов в формате Excel (`openpyxl`) и PDF (`reportlab`).
8. Реализует клиент к Open-Meteo API с кэшированием погоды Москвы на 1 час.
9. Пакует проект в многоэтапный Dockerfile и `docker-compose.yml`.

### Что Саня НЕ ДЕЛАЕТ (строгие границы):
- Саня НЕ обучает ML-модели и не подбирает гиперпараметры (это зона Славы).
- Саня НЕ обрабатывает 15 ГБ сырых CSV целиком (используется только тестовый срез [telemetry_sample_100k.csv](file:///g:/lct2/dataset/representative_slice/telemetry_sample_100k.csv)).
- Саня НЕ настраивает сложный корпоративный LDAP/AD (ролевая модель RBAC реализуется через заголовок `X-User-Role`).
- Саня НЕ верстает интерфейс и графики (это зона Ромы).

---

## 2. Архитектура репозитория бэкенда

Саня организует код в папке `backend/`:

```
backend/
├── app/
│   ├── api/
│   │   ├── deps.py             # Зависимости (сессия БД, текущая роль RBAC)
│   │   └── v1/
│   │       ├── objects.py      # /api/v1/objects (дерево коллекторов)
│   │       ├── sensors.py      # /api/v1/sensors (телеметрия, даунсэмплинг)
│   │       ├── predictions.py  # /api/v1/predictions (прогнозы сбоев)
│   │       ├── tickets.py      # /api/v1/tickets (наряды на ТО/ППР)
│   │       ├── reports.py      # /api/v1/reports (генерация xlsx и pdf)
│   │       └── weather.py      # /api/v1/weather (Open-Meteo)
│   ├── core/
│   │   ├── config.py           # Settings (DATABASE_URL, CORS, пути)
│   │   └── database.py         # SQLAlchemy engine и SessionLocal
│   ├── db/
│   │   ├── init_db.py          # Автоматический сидинг справочников
│   │   └── models.py           # ORM-модели (Object, Channel, Ticket, Log)
│   ├── ml/
│   │   ├── predictor.py        # Интерфейс предиктора (DummyPredictor / CatBoost)
│   │   └── weights/            # Папка для весов модели от Славы
│   ├── schemas/
│   │   └── contracts.py        # Pydantic v2 схемы (1 в 1 по INTEGRATION_SPEC.md)
│   └── main.py                 # Точка входа FastAPI
├── tests/                      # Быстрые pytest-тесты эндпоинтов
├── Dockerfile
├── requirements.txt
└── docker-compose.yml
```

---

## 3. Модели базы данных и правила сидинга

Саня создает ORM-модели (SQLAlchemy):
1. `CollectorObject`: `id` (int, PK), `name` (str), `level` (int), `parent_id` (int, nullable), `object_type` (str).
2. `SensorChannel`: `id` (int, PK), `subsystem` (str), `sensor_type` (str), `tag` (str), `sensor_name` (str), `tag_root` (str), `piket` (str).
3. `MaintenanceTicket`: `id` (str, PK), `prediction_id` (str), `channel_id` (int), `object_id` (int), `piket` (str), `work_type` (str), `priority` (str), `target_hours` (int), `status` (str: `draft`, `approved`, `rejected`, `completed`), `comment` (str), `assigned_brigade` (str), `created_at` (datetime).
4. `PredictionRecord`: `id` (str, PK), `channel_id` (int), `failure_probability` (float), `risk_category` (str), `forecast_horizon_hours` (int), `primary_cause` (str), `recommended_action` (str), `generated_at` (datetime).

**Сидинг при старте (в `main.py` lifespan)**:
Если таблица `CollectorObject` пуста, приложение читает `dataset/справочник_объектов_диспетчер.csv` и `dataset/справочник_каналов_датчиков.csv` и вставляет записи в базу данных.

---

## 4. Реализация предиктора (ML-заглушка)

Саня создает `backend/app/ml/predictor.py`:

```python
from pydantic import BaseModel
from typing import List, Optional

class SensorRiskInput(BaseModel):
    channel_id: int
    sensor_type: str
    subsystem: str
    tag_root: str
    piket: str
    flapping_count_1h: int = 0
    flapping_count_24h: int = 0
    alarm_ratio_24h: float = 0.0
    numeric_std_24h: Optional[float] = None
    last_numeric_value: Optional[float] = None
    hours_since_last_alarm: float = 999.0

class SensorRiskOutput(BaseModel):
    channel_id: int
    failure_probability: float
    risk_category: str
    forecast_horizon_hours: int = 24
    primary_cause: str
    recommended_action: str

class DummyPredictor:
    def predict(self, item: SensorRiskInput) -> SensorRiskOutput:
        # Базовая эвристика до передачи весов от Славы
        if item.flapping_count_24h > 5 or item.alarm_ratio_24h > 0.15:
            return SensorRiskOutput(
                channel_id=item.channel_id,
                failure_probability=0.89,
                risk_category="critical",
                primary_cause="Высокая частота аппаратного дребезга контактов",
                recommended_action="Протяжка клеммных колодок или замена прибора"
            )
        return SensorRiskOutput(
            channel_id=item.channel_id,
            failure_probability=0.07,
            risk_category="low",
            primary_cause="Показания стабильны, аномалий нет",
            recommended_action="Штатный мониторинг СМВУ"
        )

# Глобальный синглтон предиктора
predictor = DummyPredictor()
```

---

## 5. Модуль генерации отчетов и метеоданных

1. **Excel отчет (`GET /api/v1/reports/incidents.xlsx`)**:
   - Использовать библиотеку `openpyxl`.
   - Формировать красивую таблицу с колонками: ID наряда, Дата создания, Объект, Пикет, Канал, Тип датчика, Вероятность отказа, Причина, Рекомендация, Статус.
   - Возвращать через `StreamingResponse` с заголовком `Content-Disposition: attachment; filename=incidents_report.xlsx`.

2. **PDF отчет (`GET /api/v1/reports/summary.pdf`)**:
   - Использовать библиотеку `reportlab`.
   - Формировать титульную справку с логотипом Москоллектора, датой выгрузки, сводкой по 16 объектам и списком критических рисков.

3. **Метеоданные (`GET /api/v1/weather/current`)**:
   - Делать GET-запрос к `https://api.open-meteo.com/v1/forecast?latitude=55.7522&longitude=37.6156&current=temperature_2m,relative_humidity_2m,surface_pressure,precipitation`.
   - Кэшировать ответ в памяти приложения на 3600 секунд. При ошибке сети отдавать дефолтный JSON с температурой Москвы.

---

## 6. Требования к Docker и переменным окружения

Файл `docker-compose.yml` в корне проекта:
```yaml
version: '3.8'

services:
  db:
    image: postgres:15-alpine
    container_name: moscollector_db
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgrespassword
      POSTGRES_DB: moscollector
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres"]
      interval: 5s
      timeout: 5s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: moscollector_backend
    environment:
      DATABASE_URL: postgresql+asyncpg://postgres:postgrespassword@db:5432/moscollector
      CORS_ORIGINS: "*"
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

volumes:
  pgdata:
```
