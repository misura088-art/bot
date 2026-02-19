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
COOLDOWN_SECONDS = 1800 

user_cooldowns = {}
waiting_for_id = {} # Для ручного введення ID

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- KEYBOARDS ---
def get_main_menu(is_admin=False):
    kb = [
        [KeyboardButton(text="📝 Надіслати анонімку")],
        [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="⏳ Мій час")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="🛠 Адмін-панель")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

# --- UTILS ---
async def check_admin(user_id):
    try:
        m = await bot.get_chat_member(GROUP_ID, user_id)
        return m.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- HANDLERS ---

# 1. КОМАНДА СТАРТ
@dp.message(CommandStart())
async def cmd_start(message: Message):
    if message.chat.type != ChatType.PRIVATE: return
    admin = await check_admin(message.from_user.id)
    await message.answer("Привіт! Використовуй меню:", reply_markup=get_main_menu(admin))

# 2. ОБРОБКА КНОПОК МЕНЮ
@dp.message(F.chat.type == ChatType.PRIVATE, F.text.in_(["📊 Статистика", "⏳ Мій час", "🛠 Адмін-панель", "🔙 Назад"]))
async def menu_logic(message: Message):
    uid = message.from_user.id
    admin = await check_admin(uid)

    if message.text == "📊 Статистика":
        await message.answer(f"Активних КД: {len(user_cooldowns)}")
    
    elif message.text == "⏳ Мій час":
        if uid in user_cooldowns:
            rem = int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[uid])) / 60)
            if rem > 0: return await message.answer(f"⏳ Зачекай {rem} хв.")
        await message.answer("✅ Можеш писати!")

    elif message.text == "🛠 Адмін-панель" and admin:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔓 Зняти КД")], [KeyboardButton(text="🔙 Назад")]], resize_keyboard=True)
        await message.answer("Адмін-меню. Натисни кнопку нижче:", reply_markup=kb)
    
    elif message.text == "🔙 Назад":
        await message.answer("Головне меню:", reply_markup=get_main_menu(admin))

# 3. ЛОГІКА ЗНЯТТЯ КД (РУЧНЕ ВВЕДЕННЯ ID)
@dp.message(F.chat.type == ChatType.PRIVATE, F.text == "🔓 Зняти КД")
async def ask_id(message: Message):
    if await check_admin(message.from_user.id):
        waiting_for_id[message.from_user.id] = True
        await message.answer("Надішліть ID користувача одним числом:")

# 4. ПРИЙОМ ID ТА ПЕРЕСИЛАННЯ АНОНІМКИ
@dp.message(F.chat.type == ChatType.PRIVATE)
async def main_handler(message: Message):
    uid = message.from_user.id
    
    # Якщо адмін вводить ID для розблокування
    if uid in waiting_for_id:
        try:
            target = int(message.text)
            if target in user_cooldowns: del user_cooldowns[target]
            await message.answer(f"✅ Користувача {target} розблоковано.")
        except: await message.answer("Введіть тільки цифри ID.")
        del waiting_for_id[uid]
        return

    # Якщо це звичайна анонімка
    if message.text == "📝 Надіслати анонімку":
        return await message.answer("Просто напиши текст або надішли фото — я одразу перешлю!")

    admin = await check_admin(uid)
    if not admin and uid in user_cooldowns:
        if time.time() - user_cooldowns[uid] < COOLDOWN_SECONDS:
            return await message.answer("⏳ Рано! Зачекай.")

    # Пересилання
    try:
        tag = f'<a href="tg://user?id={uid}">📍</a>'
        header = f"📩 <b>Анонімка {tag}</b>\n\n"
        
        if message.text:
            await bot.send_message(GROUP_ID, header + message.text)
        elif message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=header + (message.caption or ""))
        
        if not admin: user_cooldowns[uid] = time.time()
        await message.answer("✅ Надіслано!")
    except:
        await message.answer("Помилка відправки.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True) # Видаляє старий спам
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
