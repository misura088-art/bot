import os
import asyncio
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
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
COOLDOWN_SECONDS = 30 * 60  # 30 хвилин

user_cooldowns = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- МЕНЮ (КНОПКИ) ---
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📝 Надіслати анонімку")],
        [KeyboardButton(text="📜 Правила"), KeyboardButton(text="⏳ Мій час")]
    ],
    resize_keyboard=True
)

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer(
        f"👋 Вітаємо у боті <b>Підслухано</b>!\n\n"
        f"Тут ти можеш поділитися своєю історією абсолютно анонімно.\n"
        f"Просто надішліть текст, фото, відео або голосове.",
        reply_markup=main_menu
    )

@dp.message(F.text == "📜 Правила")
async def rules(message: Message):
    await message.answer(
        "<b>Наші правила:</b>\n"
        "1. Без прямої образи особистості.\n"
        "2. Без реклами та спаму.\n"
        "3. Одне повідомлення на 30 хвилин.\n\n"
        "Всі повідомлення проходять модерацію!"
    )

@dp.message(F.text == "⏳ Мій час")
async def check_time(message: Message):
    user_id = message.from_user.id
    if user_id in user_cooldowns:
        time_passed = time.time() - user_cooldowns[user_id]
        if time_passed < COOLDOWN_SECONDS:
            rem = int((COOLDOWN_SECONDS - time_passed) / 60)
            await message.answer(f"⏳ Тобі потрібно зачекати ще <b>{rem} хв.</b>")
            return
    await message.answer("✅ Ти можеш надсилати повідомлення прямо зараз!")

@dp.message(F.text == "📝 Надіслати анонімку")
async def send_info(message: Message):
    await message.answer("Просто надішли мені те, чим хочеш поділитися (текст, фото або відео).")

@dp.message(F.text | F.photo | F.video | F.voice)
async def handle_anonymous_message(message: Message):
    # Ігноруємо кнопки меню
    if message.text in ["📝 Надіслати анонімку", "📜 Правила", "⏳ Мій час"]:
        return

    user_id = message.from_user.id
    current_time = time.time()

    # Перевірка на адміна
    is_admin = False
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            is_admin = True
    except:
        is_admin = False

    # Перевірка КД
    if not is_admin and user_id in user_cooldowns:
        if current_time - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            rem = int((COOLDOWN_SECONDS - (current_time - user_cooldowns[user_id])) / 60)
            await message.answer(f"⏳ Почекай ще {rem} хв.")
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
            await bot.send_message(GROUP_ID, "📩 <b>Анонімне голосове повідомлення:</b>")
            await bot.send_voice(GROUP_ID, message.voice.file_id)
        elif message.text:
            await bot.send_message(GROUP_ID, caption)

        if not is_admin:
            user_cooldowns[user_id] = current_time
        await message.answer("✅ Надіслано анонімно!", reply_markup=main_menu)
        
    except Exception as e:
        await message.answer("❌ Помилка. Можливо, бот не в групі.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
