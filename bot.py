import os
import asyncio
import threading
import time
import random
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode, ChatMemberStatus, ChatType
from aiogram.client.default import DefaultBotProperties

# --- СЕКЦІЯ RENDER (HEALTH CHECK) ---
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
GROUP_ID = int(os.getenv("GROUP_ID"))
COOLDOWN_SECONDS = 30 * 60 

user_cooldowns = {}
total_messages = 0

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# --- КОНСТАНТИ КНОПОК (БЕЗ ЗАЙВИХ СИМВОЛІВ) ---
B_SEND = "📝 Надіслати"
B_STATS = "📊 Статистика"
B_ADMIN = "🛠 Адмін"
B_RULES = "📜 Правила"
B_TIME = "⏳ Мій час"
B_BACK = "🔙 Назад"
B_UNBLOCK = "🔓 Зняти КД"

ALL_MENU_BUTTONS = [B_SEND, B_STATS, B_ADMIN, B_RULES, B_TIME, B_BACK, B_UNBLOCK]

# --- КЛАВІАТУРИ ---
def get_main_menu(is_admin=False):
    kb = [
        [KeyboardButton(text=B_SEND)],
        [KeyboardButton(text=B_TIME), KeyboardButton(text=B_STATS)],
        [KeyboardButton(text=B_RULES)]
    ]
    if is_admin:
        kb.append([KeyboardButton(text=B_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cooldown_menu():
    buttons = []
    now = time.time()
    for uid, l_time in list(user_cooldowns.items()):
        if now - l_time < COOLDOWN_SECONDS:
            buttons.append([KeyboardButton(text=f"Unlock:{uid}")])
    buttons.append([KeyboardButton(text=B_BACK)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- ПЕРЕВІРКА АДМІНА ---
async def check_is_admin(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- ОБРОБНИКИ ---

# 1. ВИДАЛЕННЯ КНОПОК У ГРУПІ (АНТИ-СПАМ)
@dp.message(F.chat.id == GROUP_ID)
async def group_guard(message: Message):
    if message.text and (any(b in message.text for b in ALL_MENU_BUTTONS) or "Unlock:" in message.text):
        try: await message.delete()
        except: pass

# 2. ОБРОБКА КОМАНД ТА КНОПОК (ПРИВАТ)
@dp.message(F.chat.type == ChatType.PRIVATE, (F.text.in_(ALL_MENU_BUTTONS) | F.text.startswith("Unlock:") | CommandStart()))
async def handle_private_menu(message: Message):
    global total_messages
    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)

    if message.text == "/start" or message.text == B_BACK:
        await message.answer("🏠 Головне меню:", reply_markup=get_main_menu(is_admin))
    
    elif message.text == B_STATS:
        await message.answer(f"📈 Статистика:\nПовідомлень: {total_messages}\nВ КД: {len(user_cooldowns)}")
    
    elif message.text == B_TIME:
        if user_id in user_cooldowns:
            rem = int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[user_id])) / 60)
            if rem > 0: return await message.answer(f"⏳ Чекати ще {rem} хв.")
        await message.answer("✅ Можеш писати!")

    elif message.text == B_ADMIN and is_admin:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=B_UNBLOCK)], [KeyboardButton(text=B_BACK)]], resize_keyboard=True)
        await message.answer("🔧 Адмін-панель:", reply_markup=kb)

    elif message.text == B_UNBLOCK and is_admin:
        menu = get_cooldown_menu()
        await message.answer("Оберіть кого розблокувати:", reply_markup=menu)

    elif message.text.startswith("Unlock:") and is_admin:
        try:
            tid = int(message.text.split(":")[1])
            if tid in user_cooldowns:
                del user_cooldowns[tid]
                await message.answer(f"✅ {tid} розблоковано!", reply_markup=get_cooldown_menu())
        except: await message.answer("Помилка.")

# 3. АНОНІМКА (ТІЛЬКИ ЯКЩО ЦЕ НЕ КНОПКА)
@dp.message(F.chat.type == ChatType.PRIVATE)
async def anonymous_sender(message: Message):
    if message.text in ALL_MENU_BUTTONS: return # Жорсткий блок

    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)

    if not is_admin and user_id in user_cooldowns:
        if time.time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            return await message.answer("⏳ Зачекай, КД!")

    try:
        tag = f'<a href="tg://user?id={user_id}">📍</a>'
        header = f"📩 <b>Анонімно {tag}</b>\n\n"
        
        if message.text:
            await bot.send_message(GROUP_ID, header + message.text)
        elif message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=header + (message.caption or ""))
        
        total_messages += 1
        if not is_admin: user_cooldowns[user_id] = time.time()
        await message.answer("✅ Надіслано!")
    except: await message.answer("❌ Помилка.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
