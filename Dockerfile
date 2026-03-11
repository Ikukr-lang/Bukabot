FROM python:3.12-slim-bookworm

# === УСТАНОВКА TESSERACT OCR + ЯЗЫКИ (eng + rus) ===
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-rus \
    libjpeg62-turbo \
    libpng16-16 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Устанавливаем Python-зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код бота
# Если файл называется "bot 2.py" — оставь как есть
# Лучше переименуй в bot.py для удобства
COPY bot.py .

# Запуск бота
CMD ["python", "bot.py"]
