import os
import asyncio
import threading
import time
import random
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode, ChatMemberStatus, ChatType
from aiogram.client.default import DefaultBotProperties

# --- СЕКЦІЯ ДЛЯ RENDER ---
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
total_messages = 0
waiting_for_id = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- ПЕРЕВІРКА АДМІНА ---
async def check_is_admin(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except:
        return False

# --- ОБРОБКА ПОВІДОМЛЕНЬ У ГРУПІ (ВІД АДМІНІВ) ---
@dp.message(F.chat.id == int(GROUP_ID))
async def handle_group_admin_messages(message: Message):
    # Якщо адмін пише в групу, бот робить це оголошенням
    if await check_is_admin(message.from_user.id):
        if message.text:
            # Видаляємо повідомлення адміна, щоб замінити його ботівським (опціонально)
            try:
                await message.delete()
            except:
                pass
            
            await message.answer(f"📢 <b>Оголошення від адміна:</b>\n\n{message.text}")

# --- ОБРОБКА ПРИВАТНИХ ПОВІДОМЛЕНЬ (АНОНІМКИ) ---
@dp.message(F.chat.type == ChatType.PRIVATE)
async def handle_private_messages(message: Message):
    global total_messages
    user_id = message.from_user.id
    
    # Реакція на команди меню
    if message.text == "/start":
        is_admin = await check_is_admin(user_id)
        buttons = [[KeyboardButton(text="📝 Надіслати анонімку")], [KeyboardButton(text="📊 Статистика")]]
        if is_admin: buttons.append([KeyboardButton(text="🛠 Адмін-панель")])
        await message.answer("Вітаю в Підслухано!", reply_markup=ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True))
        return

    # Логіка анонімки (перевірка КД і пересилка)
    is_admin = await check_is_admin(user_id)
    if not is_admin and user_id in user_cooldowns:
        if time.time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            await message.answer("⏳ Зачекайте!")
            return

    try:
        admin_info = f"\n\n(ID: <code>{user_id}</code>)"
        if message.text:
            await bot.send_message(GROUP_ID, f"📩 <b>Нове анонімне повідомлення:</b>\n\n{message.text}{admin_info}")
            total_messages += 1
            if not is_admin: user_cooldowns[user_id] = time.time()
            await message.answer("✅ Надіслано!")
    except:
        await message.answer("❌ Помилка.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
