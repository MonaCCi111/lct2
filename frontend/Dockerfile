# Сборка интерфейса и раздача через nginx. API проксируется на сервис backend (см. nginx.conf).
FROM node:24-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
# Относительные адреса: браузер обращается к тому же домену, nginx передаёт запросы бэкенду.
ENV VITE_API_BASE_URL=/api/v1 \
    VITE_API_V2_BASE_URL=/api/v2 \
    VITE_ENABLE_MOCKS=false
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
