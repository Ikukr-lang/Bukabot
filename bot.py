import asyncio
import logging
import re
from io import BytesIO

import requests
from bs4 import BeautifulSoup
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, BufferedInputFile
from aiogram.filters import Command

import edge_tts

# ←←← ВСТАВЬ СВОЙ ТОКЕН ←←←
BOT_TOKEN = "8538478896:AAFAD2fPNLXD2Rfhk6VtoDI9cBkaHlCgl5g"

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

URL_PATTERN = re.compile(r'https?://\S+')


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! 👋\n\n"
        "Отправь мне **полную ссылку** на страницу (например, матч Hattrick).\n"
        "Я отправлю ссылку обратно и озвучу **весь текст этой страницы** мужским голосом."
    )


@dp.message(F.text)
async def handle_url(message: Message):
    urls = URL_PATTERN.findall(message.text)
    if not urls:
        await message.answer("❗ Отправь полную ссылку (начинается с http или https)")
        return

    url = urls[0]  # берём первую ссылку из сообщения

    # Отправляем ссылку
    await message.answer(
        f"✅ <b>Ссылка:</b>\n"
        f"<a href='{url}'>{url}</a>",
        parse_mode="HTML"
    )

    # Загружаем страницу
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Убираем всё лишнее
        for tag in soup(["script", "style", "nav", "header", "footer", "aside", "form"]):
            tag.decompose()

        # Берём основной текст
        main_content = (
            soup.find("div", id="main") or
            soup.find("div", class_=re.compile("main|content|report")) or
            soup.body
        )
        page_text = main_content.get_text(separator="\n", strip=True) if main_content else soup.get_text(separator="\n", strip=True)

        # Чистим лишние переносы
        page_text = re.sub(r'\n+', '\n', page_text).strip()

        # Проверка на требование логина
        lower_text = page_text.lower()
        if any(word in lower_text for word in ["log in", "войти", "авториз", "login", "sign in", "вход"]):
            voice_text = "Страница требует входа в аккаунт. Полный текст недоступен без логина. Откройте ссылку в браузере после авторизации."
        else:
            # Ограничиваем длину (примерно 4-5 минут речи)
            if len(page_text) > 5000:
                page_text = page_text[:5000] + "\n... (страница очень длинная, озвучена основная часть)"
            voice_text = f"Текст страницы. {page_text}"

    except Exception as e:
        logging.error(f"Ошибка загрузки: {e}")
        voice_text = f"Не удалось загрузить страницу. Попробуйте открыть ссылку вручную."

    # Озвучиваем мужским голосом
    try:
        communicate = edge_tts.Communicate(voice_text, voice="ru-RU-DmitryNeural")
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        voice_file = BufferedInputFile(audio_data, filename="page_voice.mp3")
        await message.answer_voice(
            voice_file,
            caption="🎙️ Озвучка текста страницы (мужской голос)"
        )
    except Exception as e:
        logging.error(f"TTS error: {e}")
        await message.answer("❌ Ссылка отправлена, но озвучка не получилась.")


async def main():
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
