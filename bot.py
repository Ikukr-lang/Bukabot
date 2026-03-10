import asyncio
import logging
import sqlite3
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton

# Токены (замените на свои)
BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
PAYMENTS_TOKEN = "YOUR_PAYMENTS_TOKEN_HERE"  # Тестовый токен из BotFather

# Настройка логирования
logging.basicConfig(level=logging.INFO)

# База данных
conn = sqlite3.connect('bookmaker.db')
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, balance REAL DEFAULT 0)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS bets (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, event TEXT, amount REAL, odds REAL, status TEXT)''')
conn.commit()

# Состояния для FSM
class BetForm(StatesGroup):
    event = State()
    amount = State()

# Объект бота и диспетчер
bot = Bot(token=BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Меню клавиатура
main_menu = ReplyKeyboardMarkup(resize_keyboard=True, keyboard=[
    [KeyboardButton(text="События"), KeyboardButton(text="Мои ставки")],
    [KeyboardButton(text="Баланс"), KeyboardButton(text="Пополнить")]
])

# Фейковые события (замените на API, например, requests.get('https://api.the-odds-api.com/...'))
events = {
    "Матч: Реал - Барселона": {"Победа Реала": 2.0, "Ничья": 3.5, "Победа Барсы": 2.5},
    "Теннис: Федерер - Надаль": {"Победа Федерера": 1.8, "Победа Надаля": 2.2}
}

# Хэндлер на /start
@dp.message(Command("start"))
async def start(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    conn.commit()
    await message.answer("Добро пожаловать в букмекерскую контору! Выберите действие:", reply_markup=main_menu)

# Просмотр событий
@dp.message(lambda message: message.text == "События")
async def show_events(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for event in events:
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=event, callback_data=f"event_{event}")])
    await message.answer("Доступные события:", reply_markup=keyboard)

# Callback для события
@dp.callback_query(lambda query: query.data.startswith("event_"))
async def select_event(callback: types.CallbackQuery, state: FSMContext):
    event = callback.data.split("_")[1]
    await state.set_state(BetForm.event)
    await state.set_data({"event": event})
    keyboard = InlineKeyboardMarkup(inline_keyboard=[])
    for outcome, odds in events[event].items():
        keyboard.inline_keyboard.append([InlineKeyboardButton(text=f"{outcome} (коэф. {odds})", callback_data=f"outcome_{outcome}_{odds}")])
    await callback.message.answer(f"Выберите исход для {event}:", reply_markup=keyboard)
    await callback.answer()

# Callback для исхода
@dp.callback_query(lambda query: query.data.startswith("outcome_"))
async def select_outcome(callback: types.CallbackQuery, state: FSMContext):
    parts = callback.data.split("_")
    outcome = parts[1]
    odds = float(parts[2])
    data = await state.get_data()
    event = data["event"]
    await state.set_state(BetForm.amount)
    await state.set_data({"event": event, "outcome": outcome, "odds": odds})
    await callback.message.answer("Введите сумму ставки:")
    await callback.answer()

# Ввод суммы ставки
@dp.message(BetForm.amount)
async def place_bet(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        data = await state.get_data()
        user_id = message.from_user.id
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = cursor.fetchone()[0]
        if amount > balance:
            await message.answer("Недостаточно средств!")
            return
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
        cursor.execute("INSERT INTO bets (user_id, event, amount, odds, status) VALUES (?, ?, ?, ?, ?)",
                       (user_id, f"{data['event']} - {data['outcome']}", amount, data['odds'], "В ожидании"))
        conn.commit()
        await message.answer(f"Ставка размещена: {amount} на {data['outcome']} с коэф. {data['odds']}")
    except ValueError:
        await message.answer("Введите число!")
    await state.clear()

# Мои ставки
@dp.message(lambda message: message.text == "Мои ставки")
async def my_bets(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT event, amount, odds, status FROM bets WHERE user_id=?", (user_id,))
    bets = cursor.fetchall()
    if not bets:
        await message.answer("У вас нет ставок.")
        return
    response = "Ваши ставки:\n"
    for bet in bets:
        response += f"{bet[0]} - {bet[1]} руб. (коэф. {bet[2]}) - {bet[3]}\n"
    await message.answer(response)

# Баланс
@dp.message(lambda message: message.text == "Баланс")
async def balance(message: types.Message):
    user_id = message.from_user.id
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
    bal = cursor.fetchone()[0]
    await message.answer(f"Ваш баланс: {bal} руб.")

# Пополнение (тестовые платежи)
@dp.message(lambda message: message.text == "Пополнить")
async def top_up(message: types.Message):
    prices = [types.LabeledPrice(label='Пополнение на 100 руб.', amount=10000)]  # в копейках
    await bot.send_invoice(
        chat_id=message.chat.id,
        title='Пополнение баланса',
        description='Тестовое пополнение',
        payload='topup_100',
        provider_token=PAYMENTS_TOKEN,
        currency='RUB',
        prices=prices
    )

# Обработка успешного платежа
@dp.pre_checkout_query()
async def pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(lambda message: message.successful_payment)
async def successful_payment(message: types.Message):
    user_id = message.from_user.id
    amount = message.successful_payment.total_amount / 100  # в рублях
    cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
    conn.commit()
    await message.answer(f"Баланс пополнен на {amount} руб.")

# Запуск бота
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
