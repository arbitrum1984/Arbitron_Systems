# Используем Python 3.10 (Slim версия легче и быстрее)
FROM python:3.10-slim

# Настройки Python:
# PYTHONUNBUFFERED=1 — чтобы логи сразу шли в консоль (важно для Докера)
# PYTHONDONTWRITEBYTECODE=1 — не создавать мусорные файлы .pyc
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# Рабочая папка внутри контейнера
WORKDIR /app

# 1. Сначала копируем только файл зависимостей
# Это нужно, чтобы Docker не переустанавливал библиотеки при каждом изменении кода
COPY requirements.txt .

# 2. Устанавливаем библиотеки
RUN pip install --no-cache-dir -r requirements.txt

# Устанавливаем браузер Chromium для Playwright и его зависимости
RUN playwright install chromium --with-deps

# 3. Теперь копируем весь остальной код (папки app, static и т.д.)
COPY . .

# Открываем порт, на котором висит FastAPI
EXPOSE 8000

# Запускаем приложение
# "app.main:app" означает: папка app -> файл main.py -> объект app
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]