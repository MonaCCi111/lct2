# Dolos – интерфейс диспетчера

React 19, TypeScript, Vite. Основной маршрут работает с историческим API v2: обзор, объекты, каналы, ситуации, очередь черновиков, аналитика, история дымовых сигналов и воспроизведение. Страницы прежнего API v1 доступны по `/legacy/*`.

## Запуск

Требуется Node.js 24.15+ и работающий бэкенд на порту 8000.

```powershell
Copy-Item .env.example .env
(Get-Content .env) -replace 'VITE_ENABLE_MOCKS=true', 'VITE_ENABLE_MOCKS=false' | Set-Content .env
npm.cmd ci
npm.cmd run dev
```

Откройте `http://127.0.0.1:5173/overview`. В `.env.example` включены mocks для автономной разработки; для реальной интеграции нужен `VITE_ENABLE_MOCKS=false`. Переменные `VITE_API_BASE_URL` и `VITE_API_V2_BASE_URL` задают адреса API. После изменения `.env` перезапустите Vite.

## Страницы

| Адрес | Назначение |
| --- | --- |
| `/overview` | сводка на выбранный момент |
| `/objects`, `/channels`, `/situations` | реестры и детальные карточки |
| `/review` | группы черновиков, решения и наряды |
| `/analytics` | качество, охват и нагрузка |
| `/fire-history` | история дымовых сигналов без заявления о подтверждённых пожарах |
| `/replay` | сценарии и ползунок исторического времени |

Проверьте сборку и тесты командами `npm.cmd run build`, `npm.cmd test`, `npm.cmd run test:browser`. Полный запуск и ограничения данных описаны в [корневом README](../README.md). Контракт API v2: [api_contract_v1.json](../backend/data/ml_handoff/api_contract_v1.json).
