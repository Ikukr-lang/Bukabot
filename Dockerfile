# ==================== Dockerfile для Hattrick xG-бота ====================

FROM python:3.12-slim

# Устанавливаем только нужные пакеты
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Копируем файлы
COPY bot\ 2.py bot.py
COPY requirements.txt .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -r requirements.txt

# Переменная окружения для токена (можно задать при запуске)
ENV BOT_TOKEN=""

# Запуск бота
CMD ["python", "bot.py"]
