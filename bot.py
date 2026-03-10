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


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "Привет! 👋\n\n"
        "Отправь мне **только цифры** — ID матча Hattrick.\n"
        "Я дам ссылку и озвучу **полное описание матча** мужским голосом (то, что написано на странице)."
    )


@dp.message(F.text.regexp(r"^\d+$"))
async def handle_match_id(message: Message):
    match_id = message.text.strip()
    url = f"https://www.hattrick.org/Club/Matches/Match.aspx?matchID={match_id}"

    # Отправляем ссылку
    await message.answer(
        f"✅ <b>Ссылка на матч:</b>\n"
        f"<a href='{url}'>{url}</a>",
        parse_mode="HTML"
    )

    # Загружаем страницу и извлекаем текст
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                          "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36"
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        # Убираем лишнее (скрипты, стили, меню)
        for tag in soup(["script", "style", "nav", "header", "footer", "aside"]):
            tag.decompose()

        # Берём основной текст страницы
        main_content = soup.find("div", id="main") or soup.find("div", class_="main") or soup.body
        report_text = main_content.get_text(separator="\n", strip=True) if main_content else soup.get_text(separator="\n", strip=True)

        # Чистим лишние переносы
        report_text = re.sub(r'\n+', '\n', report_text).strip()

        # Проверка на требование логина
        lower_text = report_text.lower()
        if any(word in lower_text for word in ["log in", "войти", "авториз", "login", "sign in"]):
            voice_text = "Страница матча требует входа в аккаунт Hattrick. Полный отчёт недоступен без логина. Откройте ссылку в браузере после входа."
        else:
            # Ограничиваем длину для удобной озвучки (примерно 4–5 минут речи)
            if len(report_text) > 5000:
                report_text = report_text[:5000] + "\n... (полный отчёт слишком длинный, озвучена основная часть)"
            voice_text = f"Описание матча. {report_text}"

    except Exception as e:
        logging.error(f"Ошибка загрузки страницы: {e}")
        voice_text = f"Не удалось загрузить страницу матча. Откройте ссылку вручную: {url}"

    # Озвучиваем мужским голосом
    try:
        communicate = edge_tts.Communicate(voice_text, voice="ru-RU-DmitryNeural")
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        voice_file = BufferedInputFile(audio_data, filename="hattrick_match.mp3")
        await message.answer_voice(
            voice_file,
            caption="🎙️ Полное описание матча (мужской голос)"
        )
    except Exception as e:
        logging.error(f"TTS error: {e}")
        await message.answer("❌ Ссылка отправлена, но озвучка не получилась.")


@dp.message()
async def any_other(message: Message):
    await message.answer("❗ Отправь только цифры — ID матча (например: 738853046)")


async def main():
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
