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
total_messages = 0

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# Точні назви кнопок (мають збігатися з текстом на кнопках!)
BTN_SEND = "📝 Надіслати анонімку"
BTN_STATS = "📊 Статистика"
BTN_ADMIN = "🛠 Адмін-панель"
BTN_RULES = "📜 Правила"
BTN_TIME = "⏳ Мій час"
BTN_RELAX = "✨ Підбадьори мене"
BTN_UNBLOCK = "🔓 Зняти КД"
BTN_BACK = "🔙 Головне меню"

ALL_BUTTONS = [BTN_SEND, BTN_STATS, BTN_ADMIN, BTN_RULES, BTN_TIME, BTN_RELAX, BTN_UNBLOCK, BTN_BACK]

# --- KEYBOARDS ---
def get_main_menu(is_admin=False):
    kb = [
        [KeyboardButton(text=BTN_SEND)],
        [KeyboardButton(text=BTN_RELAX), KeyboardButton(text=BTN_STATS)],
        [KeyboardButton(text=BTN_RULES), KeyboardButton(text=BTN_TIME)]
    ]
    if is_admin:
        kb.append([KeyboardButton(text=BTN_ADMIN)])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def get_cooldown_users_menu():
    buttons = []
    current_time = time.time()
    count = 0
    for uid, last_time in list(user_cooldowns.items()):
        if current_time - last_time < COOLDOWN_SECONDS:
            buttons.append([KeyboardButton(text=f"Розблокувати {uid}")])
            count += 1
    buttons.append([KeyboardButton(text=BTN_BACK)])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True), count

async def check_is_admin(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- HANDLERS ---

# 1. ЗАХИСТ ГРУПИ
@dp.message(F.chat.id == GROUP_ID)
async def group_filter(message: Message):
    if message.text in ALL_BUTTONS or (message.text and message.text.startswith("Розблокувати ")):
        try: await message.delete()
        except: pass

# 2. ОБРОБКА МЕНЮ (ПРИВАТ) - МАЄ БУТИ ПЕРШОЮ
@dp.message(F.chat.type == ChatType.PRIVATE, (F.text.in_(ALL_BUTTONS) | F.text.startswith("Розблокувати ") | CommandStart()))
async def handle_menus(message: Message):
    global total_messages
    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)

    if message.text == "/start" or message.text == BTN_BACK:
        await message.answer("🏠 Головне меню:", reply_markup=get_main_menu(is_admin))
    
    elif message.text == BTN_STATS:
        await message.answer(f"📈 <b>Статистика:</b>\n\nПовідомлень: {total_messages}\nАктивних КД: {len(user_cooldowns)}")
    
    elif message.text == BTN_RULES:
        await message.answer("📝 Правила: Не спамити, бути ввічливим.")

    elif message.text == BTN_TIME:
        if user_id in user_cooldowns:
            rem = int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[user_id])) / 60)
            if rem > 0: return await message.answer(f"⏳ Чекай {rem} хв.")
        await message.answer("✅ Можеш писати!")

    elif message.text == BTN_ADMIN and is_admin:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text=BTN_UNBLOCK)], [KeyboardButton(text=BTN_BACK)]], resize_keyboard=True)
        await message.answer("🔧 Адмін-панель:", reply_markup=kb)

    elif message.text == BTN_UNBLOCK and is_admin:
        menu, count = get_cooldown_users_menu()
        txt = f"👤 У списку {count} людей." if count > 0 else "ℹ️ Зараз ніхто не чекає."
        await message.answer(txt, reply_markup=menu)

    elif message.text and message.text.startswith("Розблокувати ") and is_admin:
        try:
            tid = int(message.text.replace("Розблокувати ", ""))
            if tid in user_cooldowns:
                del user_cooldowns[tid]
                menu, _ = get_cooldown_users_menu()
                await message.answer(f"✅ ID {tid} розблоковано!", reply_markup=menu)
        except: await message.answer("Помилка.")

# 3. ПЕРЕСИЛАННЯ (АНОНІМКА)
@dp.message(F.chat.type == ChatType.PRIVATE)
async def process_anonymous(message: Message):
    # Якщо це випадкова кнопка, яка не потрапила в handle_menus
    if message.text in ALL_BUTTONS: return

    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)
    
    if not is_admin and user_id in user_cooldowns:
        if time.time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            return await message.answer("⏳ Зачекай, КД ще діє.")

    try:
        tag = f'<a href="tg://user?id={user_id}">📍</a>'
        header = f"📩 <b>Анонімно {tag}</b>\n\n"
        
        if message.text: await bot.send_message(GROUP_ID, header + message.text)
        elif message.photo: await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=header + (message.caption or ""))
        
        total_messages += 1
        if not is_admin: user_cooldowns[user_id] = time.time()
        await message.answer("✅ Надіслано!")
    except: await message.answer("Помилка відправки.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
