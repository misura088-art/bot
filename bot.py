import os
import asyncio
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode, ChatMemberStatus, ChatType
from aiogram.client.default import DefaultBotProperties

# --- HEALTH CHECK FOR RENDER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    port = int(os.getenv("PORT", 8080))
    server = ThreadingHTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()

# --- CONFIG ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))
COOLDOWN_SECONDS = 30 * 60 

user_cooldowns = {}
waiting_for_id = {}

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- KEYBOARDS ---
def get_main_menu(is_admin=False):
    kb = [
        [KeyboardButton(text="📝 Надіслати анонімку")],
        [KeyboardButton(text="✨ Підбадьори мене"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📜 Правила"), KeyboardButton(text="⏳ Мій час")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Адмін-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

admin_kb = ReplyKeyboardMarkup(keyboard=[
    [KeyboardButton(text="🔓 Зняти КД користувачу")],
    [KeyboardButton(text="🔙 Головне меню")]
], resize_keyboard=True)

# --- UTILS ---
async def check_is_admin(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- HANDLERS ---

@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.chat.type != ChatType.PRIVATE: return
    is_admin = await check_is_admin(message.from_user.id)
    await message.answer("👋 Вітаю! Використовуй кнопки меню:", reply_markup=get_main_menu(is_admin))

# 1. ОБРОБКА КНОПОК (ПРІОРИТЕТ)
@dp.message(F.chat.type == ChatType.PRIVATE, F.text.in_([
    "📊 Статистика", "✨ Підбадьори мене", "📜 Правила", 
    "⏳ Мій час", "🛠 Адмін-панель", "🔙 Головне меню", "🔓 Зняти КД користувачу"
]))
async def handle_menus(message: Message):
    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)
    
    if message.text == "📊 Статистика":
        await message.answer(f"👥 Кількість активних КД: {len(user_cooldowns)}")
    elif message.text == "📜 Правила":
        await message.answer("Будь ласка, не надсилайте спам.")
    elif message.text == "⏳ Мій час":
        if user_id in user_cooldowns:
            rem = int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[user_id])) / 60)
            if rem > 0: return await message.answer(f"⏳ Зачекай {rem} хв.")
        await message.answer("✅ Ти можеш писати!")
    elif message.text == "🛠 Адмін-панель" and is_admin:
        await message.answer("🔧 Адмін-меню:", reply_markup=admin_kb)
    elif message.text == "🔓 Зняти КД користувачу" and is_admin:
        waiting_for_id[user_id] = True
        await message.answer("Введіть ID користувача (тільки цифри):")
    elif message.text == "🔙 Головне меню":
        await message.answer("Повертаємось...", reply_markup=get_main_menu(is_admin))

# 2. ПЕРЕСИЛАННЯ АНОНІМКИ (ЯКЩО ЦЕ НЕ КНОПКА)
@dp.message(F.chat.type == ChatType.PRIVATE)
async def process_anonymous(message: Message):
    user_id = message.from_user.id
    
    # Скидання КД адміном
    if user_id in waiting_for_id:
        try:
            tid = int(message.text)
            if tid in user_cooldowns: 
                del user_cooldowns[tid]
                await message.answer(f"✅ КД для {tid} знято!")
            else: await message.answer("❌ ID не знайдено.")
        except: await message.answer("❌ Введіть число.")
        del waiting_for_id[user_id]
        return

    # Перевірка КД
    is_admin = await check_is_admin(user_id)
    if not is_admin and user_id in user_cooldowns:
        if time.time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            return await message.answer("⏳ Рано! Зачекай.")

    # Пересилання
    try:
        # Прихований ID у символі 📍
        admin_tag = f'<a href="tg://user?id={user_id}">📍</a>'
        text = f"📩 <b>Анонімне повідомлення {admin_tag}</b>\n\n"
        
        if message.text:
            await bot.send_message(GROUP_ID, text + message.text)
        elif message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=text + (message.caption or ""))
        
        if not is_admin: user_cooldowns[user_id] = time.time()
        await message.answer("✅ Надіслано!")
    except: await message.answer("❌ Помилка.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
