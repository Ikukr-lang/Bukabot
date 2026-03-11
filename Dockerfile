FROM python:3.12-slim

# ==================== УСТАНОВКА TESSERACT (eng + rus) ====================
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    tesseract-ocr-rus \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# ==================== РАБОЧАЯ ДИРЕКТОРИЯ ====================
WORKDIR /app

# ==================== PYTHON ЗАВИСИМОСТИ ====================
# Можно через requirements.txt, а можно сразу:
RUN pip install --no-cache-dir \
    aiogram \
    pillow \
    pytesseract

# ==================== КОД БОТА ====================
# Переименовываем файл (пробел в имени — плохо для Docker)
COPY "bot.py" bot.py

# Если хочешь использовать requirements.txt:
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt
# COPY "bot 2.py" bot.py

# ==================== ЗАПУСК ====================
CMD ["python", "bot.py"]
