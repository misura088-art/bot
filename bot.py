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

# Список назв кнопок для ігнорування при пересилці
MENU_BUTTONS = [
    "📝 Надіслати анонімку", 
    "📊 Статистика", 
    "🛠 Адмін-панель", 
    "✨ Підбадьори мене", 
    "📜 Правила", 
    "⏳ Мій час",
    "🔓 Зняти КД користувачу",
    "🔙 Головне меню"
]

# --- КЛАВІАТУРИ ---
def get_main_menu(is_admin=False):
    buttons = [
        [KeyboardButton(text="📝 Надіслати анонімку")],
        [KeyboardButton(text="✨ Підбадьори мене"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📜 Правила"), KeyboardButton(text="⏳ Мій час")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="🛠 Адмін-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- ПЕРЕВІРКА АДМІНА ---
async def check_is_admin(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except:
        return False

# --- ОБРОБКА ПРИВАТНИХ ПОВІДОМЛЕНЬ ---
@dp.message(F.chat.type == ChatType.PRIVATE)
async def handle_private_messages(message: Message):
    global total_messages
    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)

    # 1. Якщо це команда /start
    if message.text == "/start":
        await message.answer("Вітаю в Підслухано!", reply_markup=get_main_menu(is_admin))
        return

    # 2. ПЕРЕВІРКА: Якщо текст повідомлення — це назва кнопки, НЕ пересилаємо його
    if message.text in MENU_BUTTONS:
        if message.text == "📊 Статистика":
            await message.answer(f"📈 Надіслано анонімок: <b>{total_messages}</b>")
        elif message.text == "✨ Підбадьори мене":
            await message.answer("Ти молодець! Твоя історія змінить чийсь день. ✨")
        elif message.text == "📜 Правила":
            await message.answer("Правила прості: будь ввічливим і анонімним. 🤫")
        elif message.text == "⏳ Мій час":
            if user_id in user_cooldowns:
                rem = int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[user_id])) / 60)
                if rem > 0:
                    await message.answer(f"⏳ Зачекай ще {rem} хв.")
                    return
            await message.answer("✅ Можеш писати!")
        elif message.text == "🛠 Адмін-панель" and is_admin:
            # Тут можна додати логіку адмін-панелі
            await message.answer("🔧 Адмін-панель активована.")
        return

    # 3. Логіка пересилки анонімки (тільки якщо це не кнопка)
    if not is_admin and user_id in user_cooldowns:
        if time.time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            await message.answer("⏳ Зачекайте, ваш час ще не настав!")
            return

    try:
        admin_info = f"\n\n(ID: <code>{user_id}</code>)"
        if message.text:
            await bot.send_message(GROUP_ID, f"📩 <b>Нове анонімне повідомлення:</b>\n\n{message.text}{admin_info}")
        elif message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=f"📩 <b>Нове фото:</b>{admin_info}")
        
        total_messages += 1
        if not is_admin: user_cooldowns[user_id] = time.time()
        await message.answer("✅ Надіслано анонімно!")
    except:
        await message.answer("❌ Помилка відправки.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
