import os
import asyncio
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher
from aiogram.types import Message
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
COOLDOWN_SECONDS = 30 * 60  # Зменшено до 30 хвилин (1800 секунд)

# Словник для кд: {user_id: timestamp}
user_cooldowns = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привіт! Надішли повідомлення, і я передам його в групу **анонімно**.\n\n"
                         "⚠️ Обмеження: 1 повідомлення на 30 хвилин (крім адмінів).")

@dp.message()
async def forward_to_group(message: Message):
    if not message.text:
        return

    user_id = message.from_user.id
    current_time = time.time()

    # ПЕРЕВІРКА НА АДМІНІСТРАТОРА
    is_admin = False
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
            is_admin = True
    except Exception:
        is_admin = False

    # Перевірка кд (тільки якщо НЕ адмін)
    if not is_admin and user_id in user_cooldowns:
        last_time = user_cooldowns[user_id]
        time_passed = current_time - last_time

        if time_passed < COOLDOWN_SECONDS:
            remaining_time = int((COOLDOWN_SECONDS - time_passed) / 60)
            await message.answer(f"⏳ Зачекайте ще **{remaining_time} хв.** перед наступним відправленням.")
            return

    # Відправка повідомлення
    try:
        await bot.send_message(
            chat_id=GROUP_ID,
            text=f"📩 **Нове анонімне повідомлення:**\n\n{message.text}"
        )
        # Оновлюємо час тільки для звичайних користувачів
        if not is_admin:
            user_cooldowns[user_id] = current_time
            
        await message.answer("✅ Ваше повідомлення надіслано анонімно.")
    except Exception as e:
        await message.answer("❌ Помилка при відправці. Переконайтеся, що бот є в групі.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
