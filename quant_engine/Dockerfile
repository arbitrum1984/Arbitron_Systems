# --- Stage 1: Build ---
FROM python:3.10-slim as builder

# Установка системных зависимостей для сборки Qlib
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /build

# Установка зависимостей в отдельную директорию (используем venv или просто --user)
COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# --- Stage 2: Final ---
FROM python:3.10-slim

WORKDIR /app

# Копируем только установленные библиотеки из builder
COPY --from=builder /install /usr/local

# Копируем код
COPY . .

# Переменная для Qlib данных
ENV QLIB_DATA_DIR=/data/qlib_data \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Порт для API
EXPOSE 8001

# Запуск API сервера
CMD ["uvicorn", "inference_api:app", "--host", "0.0.0.0", "--port", "8001"]