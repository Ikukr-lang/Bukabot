import logging
import os
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InputFile
import requests
from bs4 import BeautifulSoup
import pyttsx3
from pydub import AudioSegment

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# Инициализация бота с переменной окружения
TOKEN = os.getenv('BOT_TOKEN')
if not TOKEN:
    raise ValueError("BOT_TOKEN не задан в переменных окружения!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# Обработчик команды /start
@dp.message(Command('start'))
async def start(message: types.Message):
    await message.reply("Привет! Отправь мне URL страницы, и я озвучу её текст мужским голосом.")

# Обработчик текстовых сообщений (ожидаем URL)
@dp.message()
async def handle_url(message: types.Message):
    url = message.text.strip()
    if not url.startswith('http'):
        await message.reply("Пожалуйста, отправь valid URL.")
        return

    try:
        # Парсинг текста с сайта
        response = requests.get(url)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        text = ' '.join(p.get_text() for p in soup.find_all('p'))  # Извлекаем текст из параграфов
        if not text:
            await message.reply("Не удалось извлечь текст с страницы.")
            return

        # Ограничим текст до 1000 символов для теста
        text = text[:1000]

        # TTS с мужским голосом (pyttsx3)
        engine = pyttsx3.init()
        voices = engine.getProperty('voices')
        engine.setProperty('voice', voices[0].id)  # 0 - обычно мужской
        engine.setProperty('rate', 150)

        # Сохраняем в WAV
        wav_file = 'output.wav'
        engine.save_to_file(text, wav_file)
        engine.runAndWait()

        # Конвертируем в OGG
        ogg_file = 'output.ogg'
        audio = AudioSegment.from_wav(wav_file)
        audio.export(ogg_file, format='ogg', codec='libopus')

        # Отправляем voice message
        await bot.send_voice(message.chat.id, InputFile(ogg_file))

        # Удаляем файлы
        os.remove(wav_file)
        os.remove(ogg_file)

    except Exception as e:
        await message.reply(f"Ошибка: {str(e)}")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == '__main__':
    asyncio.run(main())
