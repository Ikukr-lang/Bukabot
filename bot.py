import asyncio
import io
import re
import math
from os import getenv

from PIL import Image, ImageEnhance, ImageFilter
import easyocr
import numpy as np

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command

# ==================== РЕЙТИНГИ ====================
rating_base = {
    "disastrous": 0, "wretched": 1, "poor": 2, "weak": 3, "inadequate": 4,
    "passable": 5, "solid": 6, "excellent": 7, "formidable": 8, "outstanding": 9,
    "brilliant": 10, "magnificent": 11, "utopian": 12, "divine": 13,
    "катастрофический": 0, "убогий": 1, "плохой": 2, "слабый": 3, "недостаточный": 4,
    "приемлемый": 5, "солидный": 6, "отличный": 7, "грозный": 8, "выдающийся": 9,
    "блестящий": 10, "великолепный": 11, "утопический": 12, "божественный": 13,
}

sub_map = {
    "very low": 0.0, "low": 0.25, "high": 0.50, "very high": 0.75,
    "очень низкий": 0.0, "низкий": 0.25, "высокий": 0.50, "очень высокий": 0.75,
}

def parse_ratings(text: str):
    teams = {"Home": {}, "Away": {}}
    current_team = None
    lines = text.lower().splitlines()

    for line in lines:
        line = line.strip()
        if "home" in line or "ваша команда" in line:
            current_team = "Home"
        elif "away" in line or "соперник" in line:
            current_team = "Away"

        if current_team and any(x in line for x in ["defence", "attack", "midfield", "защита", "атака", "полузащита"]):
            # Более мягкий regex (учитывает лишние символы и пробелы)
            m = re.search(r"(left|central|right|midfield|левая|центральная|правая|полузащита)[\s:]+([a-zа-я]+)[\s(]+(very low|low|high|very high|очень низкий|низкий|высокий|очень высокий)", line, re.I)
            if m:
                sector = m.group(1).strip()
                base = m.group(2).strip()
                sub = m.group(3).strip().lower()
                if base in rating_base and sub in sub_map:
                    value = rating_base[base] + sub_map[sub]
                    sector_norm = {
                        "left defence": "LD", "central defence": "CD", "right defence": "RD",
                        "midfield": "MF", "left attack": "LA", "central attack": "CA", "right attack": "RA",
                        "левая защита": "LD", "центральная защита": "CD", "правая защита": "RD",
                        "полузащита": "MF", "левая атака": "LA", "центральная атака": "CA", "правая атака": "RA"
                    }.get(sector.lower(), sector[:2].upper())
                    teams[current_team][sector_norm] = value

    return teams["Home"], teams["Away"]

# ==================== РАСЧЁТ (без изменений) ====================
def calculate_xg(team1, team2):
    mf1 = team1.get("MF", 7.0)
    mf2 = team2.get("MF", 7.0)
    e = 2.72
    chances1 = 9.0 * (mf1 ** e) / (mf1 ** e + mf2 ** e)
    chances2 = 9.0 - chances1

    att1 = (team1.get("LA", 0) + team1.get("CA", 0) + team1.get("RA", 0)) / 3
    def2 = (team2.get("LD", 0) + team2.get("CD", 0) + team2.get("RD", 0)) / 3
    att2 = (team2.get("LA", 0) + team2.get("CA", 0) + team2.get("RA", 0)) / 3
    def1 = (team1.get("LD", 0) + team1.get("CD", 0) + team1.get("RD", 0)) / 3

    p1 = max(0.05, min(0.95, 0.425 + 0.085 * (att1 - def2)))
    p2 = max(0.05, min(0.95, 0.425 + 0.085 * (att2 - def1)))

    return round(chances1 * p1, 2), round(chances2 * p2, 2)

def poisson_win_prob(lam1, lam2):
    p1_win = p_draw = p2_win = 0.0
    for g1 in range(13):
        pmf1 = math.exp(-lam1) * (lam1 ** g1) / math.factorial(g1)
        for g2 in range(13):
            pmf2 = math.exp(-lam2) * (lam2 ** g2) / math.factorial(g2)
            prob = pmf1 * pmf2
            if g1 > g2: p1_win += prob
            elif g1 == g2: p_draw += prob
            else: p2_win += prob
    return round(p1_win * 100, 1), round(p_draw * 100, 1), round(p2_win * 100, 1)

# ==================== EasyOCR (улучшенный) ====================
reader = easyocr.Reader(['en', 'ru'], gpu=False, download_enabled=True)

# ==================== БОТ ====================
token = getenv("BOT_TOKEN")
if not token:
    raise ValueError("BOT_TOKEN не найден!")

bot = Bot(token=token)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply("👋 Отправь скриншот блока **Ratings** — теперь с улучшенным EasyOCR + отладкой!")

@dp.message(F.text)
async def handle_text(message: Message):
    await message.reply("❌ Пришли скриншот Ratings.")

@dp.message(F.photo)
async def handle_photo(message: Message):
    await message.reply("📸 Читаю улучшенным EasyOCR...")

    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)

        def ocr_process(data):
            # Улучшенная предобработка
            image = Image.open(io.BytesIO(data)).convert('RGB')
            w, h = image.size
            if w > 1800:  # ресайз больших скринов
                ratio = 1800 / w
                image = image.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)

            image = ImageEnhance.Contrast(image).enhance(3.5)
            image = ImageEnhance.Sharpness(image).enhance(2.5)
            image = image.filter(ImageFilter.MEDIAN_FILTER)

            # EasyOCR с фильтром уверенности
            result = reader.readtext(
                np.array(image),
                detail=1,
                paragraph=False,
                width_ths=0.7,
                height_ths=0.7
            )
            # Берём только уверенные строки
            lines = [text for (_, text, conf) in result if conf > 0.4]
            return '\n'.join(lines)

        raw_text = await asyncio.to_thread(ocr_process, file_bytes)
        home, away = parse_ratings(raw_text)

        if len(home) < 3 or len(away) < 3:
            raise ValueError("Мало данных")

        xg_home, xg_away = calculate_xg(home, away)
        win_h, draw, win_a = poisson_win_prob(xg_home, xg_away)

        result = f"""🔥 **Анализ по скриншоту**

xG Home: **{xg_home}** | xG Away: **{xg_away}**

🏆 **Вероятности:**
✅ Home — **{win_h}%**
🤝 Ничья — **{draw}%**
❌ Away — **{win_a}%**

{'🏆 Home явный фаворит!' if win_h > 65 else '🏆 Away фаворит!' if win_a > 65 else '🤝 Матч равный'}"""
        
        await message.reply(result, parse_mode="Markdown")

    except Exception as e:
        await message.reply(
            f"⚠️ OCR не смог распарсить рейтинги.\n\n"
            f"**Raw текст, который увидел OCR:**\n```\n{raw_text}\n```\n\n"
            "Скопируй этот блок и пришли мне — подправим парсер за 1 минуту!\n"
            "Или попробуй другой скриншот."
        )

async def main():
    print("🤖 Бот запущен с улучшенным EasyOCR + отладкой")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
