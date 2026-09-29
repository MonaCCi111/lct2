# Развёртывание Dolos на сервере

Стенд состоит из трёх контейнеров: PostgreSQL, API (FastAPI) и интерфейс (nginx). Наружу открыт только порт 80. nginx раздаёт интерфейс и передаёт `/api/*` и `/docs` в API.

## Требования к серверу

- Linux (Ubuntu 22.04/24.04 или Debian 12), 2 vCPU, 4 ГБ RAM, 15 ГБ диска;
- публичный IP, открытый порт 80 (и 443, если нужен HTTPS).

## Установка

```bash
# Docker, Compose и Git LFS
curl -fsSL https://get.docker.com | sh
sudo apt-get install -y git git-lfs
git lfs install

# Код и данные ML (Parquet хранятся в LFS, без них API перейдёт на fixtures)
git clone https://github.com/MonaCCi111/lct2.git
cd lct2
git lfs pull

# Сборка и запуск
sudo docker compose up -d --build
```

Первый старт API занимает несколько минут: заполняется база и загружается пакет ML. Ход запуска:

```bash
sudo docker compose logs -f backend
```

Когда в логе появится `startup complete`, откройте:

- интерфейс: `http://<IP-сервера>/overview`;
- документация API: `http://<IP-сервера>/docs`;
- проверка данных: `http://<IP-сервера>/api/v2/meta` (поле `data_source` должно быть `ml_handoff_parquet`).

## Обновление

```bash
git pull && git lfs pull
sudo docker compose up -d --build
```

## Настройки

Переменные задаются в файле `.env` рядом с `docker-compose.yml`:

| Переменная | По умолчанию | Назначение |
| --- | --- | --- |
| `HTTP_PORT` | `80` | внешний порт интерфейса |
| `POSTGRES_PASSWORD` | `postgrespassword` | пароль базы (порт БД наружу не открыт) |
| `DATABASE_URL` | PostgreSQL в контейнере `db` | можно указать `sqlite+aiosqlite:///./app.db` |

## HTTPS (при наличии домена)

Направьте A-запись домена на IP сервера и поставьте перед стендом Caddy, он сам получит сертификат:

```bash
echo "HTTP_PORT=8080" > .env && sudo docker compose up -d
sudo apt-get install -y caddy
echo "ваш-домен.ru { reverse_proxy 127.0.0.1:8080 }" | sudo tee /etc/caddy/Caddyfile
sudo systemctl reload caddy
```
