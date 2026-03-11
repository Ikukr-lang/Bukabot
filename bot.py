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

# ==================== ОБНОВЛЁННЫЙ ПАРСЕР ДЛЯ HATTRICK.ORG ====================
def parse_ratings(text: str):
    teams = {"Home": {}, "Away": {}}

    sector_map = {
        "midfield": "MF",
        "right defense": "RD", "right defence": "RD",
        "central defense": "CD", "central defence": "CD",
        "left defense": "LD", "left defence": "LD",
        "right attack": "RA",
        "central attack": "CA",
        "left attack": "LA",
    }

    for line in text.splitlines():
        line = line.strip()
        if not line or any(skip in line.lower() for skip in ["rating details", "indirect set pieces", "match plan"]):
            continue

        # Ищем название сектора + два числа (Home и Away)
        match = re.search(
            r'(midfield|right\s+defen[cs]e|central\s+defen[cs]e|left\s+defen[cs]e|right\s+attack|central\s+attack|left\s+attack)'
            r'.*?(\d+[.,]\d{2}).*?(\d+[.,]\d{2})',
            line,
            re.IGNORECASE
        )
        if match:
            sector_raw = match.group(1).strip().lower()
            try:
                val_home = float(match.group(2).replace(',', '.'))
                val_away = float(match.group(3).replace(',', '.'))
                sector_norm = sector_map.get(sector_raw, sector_raw[:2].upper())
                teams["Home"][sector_norm] = val_home
                teams["Away"][sector_norm] = val_away
            except ValueError:
                continue

    return teams["Home"], teams["Away"]


# ==================== РАСЧЁТ ====================
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
bot = Bot(token=token)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.reply(
        "👋 Кидай ссылку на матч или **скриншот** блока Ratings.\n"
        "Теперь бот идеально читает hattrick.org (новые рейтинги titanic/supernatural и т.д.)!"
    )


@dp.message(F.text)
async def handle_text(message: Message):
    text = message.text.strip()
    if re.search(r"matchID=(\d+)", text, re.I):
        await message.reply("✅ MatchID найден! Пришли скриншот Ratings.")
        return
    await message.reply("❌ Пришли ссылку или скриншот.")


@dp.message(F.photo)
async def handle_photo(message: Message):
    await message.reply("📸 Получил скриншот! Читаю OCR...")

    try:
        file = await bot.get_file(message.photo[-1].file_id)
        file_bytes = await bot.download_file(file.file_path)

        def ocr_process(data):
            image = Image.open(io.BytesIO(data)).convert('L')
            image = image.filter(ImageFilter.MEDIAN_FILTER)
            image = ImageEnhance.Contrast(image).enhance(2.5)
            image = ImageEnhance.Sharpness(image).enhance(2.0)

            config = r'--oem 3 --psm 6'
            return pytesseract.image_to_string(image, config=config, lang='eng+rus')

        raw_text = await asyncio.to_thread(ocr_process, file_bytes)
        home, away = parse_ratings(raw_text)

        if not home or not away or len(home) < 3:
            raise ValueError("Не распарсил рейтинги")

        xg_home, xg_away = calculate_xg(home, away)
        win_h, draw, win_a = poisson_win_prob(xg_home, xg_away)

        result = f"""🔥 **Анализ по скриншоту**

xG Home: **{xg_home}** | xG Away: **{xg_away}**

🏆 **Вероятности:**
✅ Home ближе к победе — **{win_h}%**
🤝 Ничья — **{draw}%**
❌ Away ближе к поражению — **{win_a}%**

{'🏆 Home был явным фаворитом!' if win_h > 65 else '🏆 Away был фаворитом!' if win_a > 65 else '🤝 Матч равный'}"""
        
        await message.reply(result, parse_mode="Markdown")

    except Exception as e:
        await message.reply(
            "⚠️ OCR не сработал.\n\n"
            "Просто **скопируй текст** из матча (от слова Ratings до Possession) и пришли мне — посчитаю мгновенно!"
        )


async def main():
    print("🤖 Бот запущен (обновлённый парсер hattrick.org)")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
