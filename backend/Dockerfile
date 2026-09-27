# Многоэтапная сборка: зависимости отдельно от кода (кэш слоёв)
FROM python:3.11-slim AS builder
WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

FROM python:3.11-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY --from=builder /install /usr/local
# Только код, справочники, срез телеметрии и веса. Никаких .7z и сырых CSV (INTEGRATION_SPEC §5.3).
COPY app ./app
COPY data ./data
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=5s --retries=10 CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
