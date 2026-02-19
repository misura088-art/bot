import os
import asyncio
import threading
import time
import random
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode, ChatMemberStatus
from aiogram.client.default import DefaultBotProperties

# --- СЕКЦІЯ ДЛЯ RENDER (HEALTH CHECK) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    port = int(os.getenv("PORT", 8080))
    server = ThreadingHTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- НАЛАШТУВАННЯ ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")
COOLDOWN_SECONDS = 30 * 60 

user_cooldowns = {}
total_messages = 0  # Проста статистика

# Списки для рандому
MOTIVATION = [
    "Твоя історія варта того, щоб її почули! ✨",
    "Не тримай це в собі, розкажи нам... 🤫",
    "Сьогодні чудовий день для зізнань! 📝",
    "Тут тебе ніхто не засудить. Пиши! 🤝"
]

# --- МЕНЮ ---
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Надіслати анонімку")],
        [KeyboardButton(text="✨ Підбадьори мене"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📜 Правила"), KeyboardButton(text="⏳ Мій час")]
    ],
    resize_keyboard=True
)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        f"👋 Вітаємо у боті <b>Підслухано</b>!\n\n"
        f"Ми створили безпечне місце для твоїх думок. Скористайся меню нижче!",
        reply_markup=main_menu
    )

# --- НОВІ ПРИКОЛЬНІ КОМАНДИ ---

@dp.message(F.text == "✨ Підбадьори мене")
async def inspire(message: Message):
    phrase = random.choice(MOTIVATION)
    await message.answer(phrase)

@dp.message(F.text == "📊 Статистика")
async def stats(message: Message):
    await message.answer(
        f"📈 <b>Статистика проекту:</b>\n\n"
        f"📩 Надіслано анонімок: <b>{total_messages}</b>\n"
        f"👥 Активних авторів зараз: <b>{len(user_cooldowns)}</b>\n\n"
        f"Дякуємо, що ви з нами!"
    )

@dp.message(Command("help"))
async def help_cmd(message: Message):
    await message.answer(
        "❓ <b>Як це працює?</b>\n\n"
        "1. Просто надішли мені текст, фото або відео.\n"
        "2. Я видалю твоє ім'я і перешлю це адмінам.\n"
        "3. Пам'ятай про КД — 30 хвилин між постами.\n\n"
        "Все анонімно на 100%!"
    )

# --- БАЗОВА ЛОГІКА ---

@dp.message(F.text == "📜 Правила")
async def rules(message: Message):
    await message.answer("<b>Правила:</b> Не спамити, не ображати, бути чесним. 🤐")

@dp.message(F.text == "⏳ Мій час")
async def check_time(message: Message):
    user_id = message.from_user.id
    if user_id in user_cooldowns:
        time_passed = time.time() - user_cooldowns[user_id]
        if time_passed < COOLDOWN_SECONDS:
            rem = int((COOLDOWN_SECONDS - time_passed) / 60)
            await message.answer(f"⏳ Тобі потрібно зачекати ще <b>{rem} хв.</b>")
            return
    await message.answer("✅ Ти можеш надсилати повідомлення!")

@dp.message(F.text == "📝 Надіслати анонімку")
async def instruct(message: Message):
    await message.answer("Я чекаю на твій контент... Просто надсилай файл або текст!")

@dp.message(F.text | F.photo | F.video | F.voice)
async def handle_anonymous_message(message: Message):
    global total_messages
    if message.text in ["📝 Надіслати анонімку", "📜 Правила", "⏳ Мій час", "✨ Підбадьори мене", "📊 Статистика"]:
        return

    user_id = message.from_user.id
    current_time = time.time()

    is_admin = False
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            is_admin = True
    except: is_admin = False

    if not is_admin and user_id in user_cooldowns:
        if current_time - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            rem = int((COOLDOWN_SECONDS - (current_time - user_cooldowns[user_id])) / 60)
            await message.answer(f"⏳ Зачекай ще {rem} хв.")
            return

    try:
        caption = "📩 <b>Нове анонімне повідомлення:</b>"
        if message.caption: caption += f"\n\n{message.caption}"
        elif message.text: caption += f"\n\n{message.text}"

        if message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=caption)
        elif message.video:
            await bot.send_video(GROUP_ID, message.video.file_id, caption=caption)
        elif message.voice:
            await bot.send_message(GROUP_ID, "📩 <b>Анонімне голосове:</b>")
            await bot.send_voice(GROUP_ID, message.voice.file_id)
        elif message.text:
            await bot.send_message(GROUP_ID, caption)

        total_messages += 1 # Додаємо до статистики
        if not is_admin: user_cooldowns[user_id] = current_time
        await message.answer("✅ Надіслано!", reply_markup=main_menu)
    except:
        await message.answer("❌ Помилка відправки.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
