import asyncio
import io
import re
import math
from os import getenv

from PIL import Image, ImageEnhance, ImageFilter
import pytesseract

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import Command

# ==================== РЕЙТИНГИ (только English, т.к. OCR на eng) ====================
rating_base = {
    "disastrous": 0, "wretched": 1, "poor": 2, "weak": 3, "inadequate": 4,
    "passable": 5, "solid": 6, "excellent": 7, "formidable": 8, "outstanding": 9,
    "brilliant": 10, "magnificent": 11, "utopian": 12, "divine": 13,
}

sub_map = {"very low": 0.0, "low": 0.25, "high": 0.50, "very high": 0.75}

def parse_ratings(text: str):
    teams = {"Home": {}, "Away": {}}
    current_team = None

    for line in text.lower().splitlines():
        line = line.strip()
        if "home" in line:
            current_team = "Home"
        elif "away" in line:
            current_team = "Away"

        if current_team and any(x in line for x in ["defence", "attack", "midfield"]):
            m = re.search(r"(left|central|right|midfield).*?:\s*([a-z]+)\s*\((.*?)\)", line, re.I)
            if m:
                sector = m.group(1).strip()
                base = m.group(2).strip()
                sub = m.group(3).strip().lower()
                if base in rating_base and sub in sub_map:
                    value = rating_base[base] + sub_map[sub]
                    sector_norm = {
                        "left defence": "LD", "central defence": "CD", "right defence": "RD",
                        "midfield": "MF", "left attack": "LA", "central attack": "CA", "right attack": "RA"
                    }.get(sector.lower(), sector[:2].upper())
                    teams[current_team][sector_norm] = value

    return teams["Home"], teams["Away"]

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

# ==================== БОТ ====================
token = getenv("BOT_TOKEN")
if not token:
    raise ValueError("Установи переменную окружения BOT_TOKEN")

bot = Bot(token=token)
dp = Dispatcher()

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Кидай **ссылку** на матч или сразу **скриншот** блока Ratings (Home + Away + Possession).\n\n"
        "Важно: в Hattrick → Settings → Language = **English** перед скриншотом!"
    )

@dp.message(F.text)
async def handle_text(message: Message):
    text = message.text.strip()
    m = re.search(r"matchID=(\d+)", text, re.I)
    if m:
        await message.reply(
            f"✅ MatchID {m.group(1)} найден!\n\n"
            "Теперь пришли **скриншот** Ratings (Home + Away + Possession). Я сам прочитаю через OCR!"
        )
        return
    await message.reply("❌ Пришли ссылку или скриншот.")

@dp.message(F.photo)
async def handle_photo(message: Message):
    await message.reply("📸 Получил скриншот! Читаю OCR... (2–4 секунды)")

    file = await bot.get_file(message.photo[-1].file_id)
    file_bytes = await bot.download_file(file.file_path)

    def ocr_process(data: bytes):
        image = Image.open(io.BytesIO(data)).convert('L')
        image = image.filter(ImageFilter.MEDIAN_FILTER)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)

        custom_config = r'--oem 3 --psm 6'
        return pytesseract.image_to_string(image, config=custom_config, lang='eng')

    raw_text = await asyncio.to_thread(ocr_process, file_bytes)

    home, away = parse_ratings(raw_text)

    if not home or not away or len(home) < 4:
        await message.reply("❌ Не удалось прочитать рейтинги.\nСделай скриншот **чётче** и пришли заново.")
        return

    xg_home, xg_away = calculate_xg(home, away)
    win_h, draw, win_a = poisson_win_prob(xg_home, xg_away)

    result = f"""🔥 **Анализ по скриншоту (алгоритм Hattrick)**

xG Home: **{xg_home}** | xG Away: **{xg_away}**

🏆 **Вероятности:**
✅ Home ближе к победе — **{win_h}%**
🤝 Ничья — **{draw}%**
❌ Away ближе к поражению — **{win_a}%**

{'🏆 Home был явным фаворитом!' if win_h > 65 else '🏆 Away был фаворитом!' if win_a > 65 else '🤝 Матч равный — решил рандом'}"""
    
    await message.reply(result, parse_mode="Markdown")

async def main():
    print("🤖 Бот на aiogram запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
