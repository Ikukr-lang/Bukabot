import logging
import os  # Новый импорт
from aiogram import Bot, Dispatcher, executor, types
from aiogram.types import InputFile
import requests
from bs4 import BeautifulSoup
import pyttsx3
from pydub import AudioSegment

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота с переменной окружения
TOKEN = os.getenv('BOT_TOKEN')  # Читаем из переменной окружения
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения!")
bot = Bot(token=TOKEN)  # Используем переменную
dp = Dispatcher(bot)

# ... (остальной код без изменений: обработчики, TTS и т.д.) ...

# Запуск бота
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
