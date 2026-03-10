import asyncio
import logging
from io import BytesIO

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
        "Отправь мне **только цифры** — ID матча из Hattrick.\n"
        "Я дам ссылку на описание матча и озвучу её мужским голосом."
    )


@dp.message(F.text.regexp(r"^\d+$"))  # только цифры
async def handle_match_id(message: Message):
    match_id = message.text.strip()
    url = f"https://www.hattrick.org/Club/Matches/Match.aspx?matchID={match_id}"

    # Текст, который будет озвучен мужским голосом
    voice_text = (
        f"Ссылка на описание матча с идентификатором {match_id}. "
        "Откройте её для просмотра полного отчёта о матче."
    )

    # Отправляем текстовую ссылку
    await message.answer(
        f"✅ <b>Полная ссылка на описание матча:</b>\n"
        f"<a href='{url}'>{url}</a>",
        parse_mode="HTML"
    )

    # Озвучиваем мужским голосом (edge-tts)
    try:
        communicate = edge_tts.Communicate(voice_text, voice="ru-RU-DmitryNeural")
        audio_data = b""
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                audio_data += chunk["data"]

        voice_file = BufferedInputFile(audio_data, filename="hattrick_match.mp3")
        await message.answer_voice(
            voice_file,
            caption="🎙️ Озвучка ссылки (мужской голос)"
        )
    except Exception as e:
        logging.error(f"TTS error: {e}")
        await message.answer("❌ Не удалось озвучить, но ссылка выше работает.")


@dp.message()
async def any_other(message: Message):
    await message.answer("❗ Отправь только цифры — ID матча (например: 738853046)")


async def main():
    logging.basicConfig(level=logging.INFO)
    print("Бот запущен...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
