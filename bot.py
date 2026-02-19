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

# Список назв кнопок
MENU_BUTTONS = ["📝 Надіслати анонімку", "📊 Статистика", "🛠 Адмін-панель", "✨ Підбадьори мене", "📜 Правила", "⏳ Мій час", "🔓 Зняти КД", "🔙 Головне меню"]
MOTIVATION = ["Ти неймовірний! ✨", "Твоя історія змінить чийсь день! 😊", "Не бійся бути собою! 🌈", "Ми чекаємо на твої думки! ✍️"]

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

def get_cooldown_users_menu():
    buttons = []
    current_time = time.time()
    for uid, last_time in list(user_cooldowns.items()):
        if current_time - last_time < COOLDOWN_SECONDS:
            buttons.append([KeyboardButton(text=f"Розблокувати {uid}")])
    buttons.append([KeyboardButton(text="🔙 Головне меню")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def check_is_admin(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- HANDLERS ---

# 1. ЗАХИСТ ГРУПИ (ВИДАЛЯЄМО КНОПКИ, ЯКЩО ВОНИ ПРОСКОЧИЛИ)
@dp.message(F.chat.id == GROUP_ID)
async def group_filter(message: Message):
    if message.text in MENU_BUTTONS or (message.text and message.text.startswith("Розблокувати ")):
        try:
            await message.delete()
        except:
            pass

# 2. ОБРОБКА МЕНЮ ТА КНОПОК (ПРИВАТ)
@dp.message(F.chat.type == ChatType.PRIVATE, (F.text.in_(MENU_BUTTONS) | F.text.startswith("Розблокувати ") | F.text == "/start"))
async def handle_menus(message: Message):
    global total_messages
    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)

    if message.text == "/start" or message.text == "🔙 Головне меню":
        await message.answer("🏠 Головне меню:", reply_markup=get_main_menu(is_admin))
    
    elif message.text == "📊 Статистика":
        await message.answer(f"📈 <b>Статистика:</b>\n\nНадіслано повідомлень: {total_messages}\nЛюдей у КД: {len(user_cooldowns)}")
    
    elif message.text == "✨ Підбадьори мене":
        await message.answer(random.choice(MOTIVATION))
    
    elif message.text == "📜 Правила":
        await message.answer("📝 <b>Правила:</b>\n1. Будь ввічливим.\n2. Жодної реклами.\n3. КД — 30 хвилин.")
    
    elif message.text == "⏳ Мій час":
        if user_id in user_cooldowns:
            rem = int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[user_id])) / 60)
            if rem > 0: return await message.answer(f"⏳ Тобі ще чекати {rem} хв.")
        await message.answer("✅ Ти можеш надсилати анонімку!")

    elif message.text == "🛠 Адмін-панель" and is_admin:
        kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔓 Зняти КД")], [KeyboardButton(text="🔙 Головне меню")]], resize_keyboard=True)
        await message.answer("🔧 Адмін-панель:", reply_markup=kb)

    elif message.text == "🔓 Зняти КД" and is_admin:
        await message.answer("Оберіть користувача для розблокування:", reply_markup=get_cooldown_users_menu())

    elif message.text.startswith("Розблокувати ") and is_admin:
        try:
            target_id = int(message.text.replace("Розблокувати ", ""))
            if target_id in user_cooldowns:
                del user_cooldowns[target_id]
                await message.answer(f"✅ ID {target_id} розблоковано!", reply_markup=get_cooldown_users_menu())
            else: await message.answer("❌ Користувач уже не в КД.")
        except: await message.answer("❌ Помилка ID.")

# 3. ПЕРЕСИЛАННЯ (АНОНІМКА) - ТУТ ДОДАНО ЖОРСТКИЙ ФІЛЬТР
@dp.message(F.chat.type == ChatType.PRIVATE)
async def process_anonymous(message: Message):
    # ЯКЩО ЦЕ КНОПКА - ІГНОРУЄМО (ЩОБ НЕ ПРОСКОЧИЛА)
    if message.text in MENU_BUTTONS or (message.text and message.text.startswith("Розблокувати ")):
        return

    if not (message.text or message.photo or message.video or message.voice): return
    
    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)
    
    if not is_admin and user_id in user_cooldowns:
        if time.time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            return await message.answer("⏳ Зачекай, КД ще не минуло.")

    try:
        admin_tag = f'<a href="tg://user?id={user_id}">📍</a>'
        header = f"📩 <b>Нове анонімне повідомлення {admin_tag}</b>\n\n"
        
        if message.text:
            await bot.send_message(GROUP_ID, header + message.text)
        elif message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=header + (message.caption or ""))
        elif message.video:
            await bot.send_video(GROUP_ID, message.video.file_id, caption=header + (message.caption or ""))
        elif message.voice:
            await bot.send_message(GROUP_ID, f"🎤 <b>Анонімне голосове {admin_tag}</b>")
            await bot.send_voice(GROUP_ID, message.voice.file_id)

        global total_messages
        total_messages += 1
        if not is_admin: user_cooldowns[user_id] = time.time()
        await message.answer("✅ Надіслано анонімно!")
    except Exception as e:
        await message.answer("❌ Помилка відправки. Перевір права бота в групі.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
