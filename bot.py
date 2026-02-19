import os
import asyncio
import threading
import time
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
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
# Список назв кнопок для автоматичного видалення з чату
MENU_BUTTONS = ["📝 Надіслати анонімку", "📊 Статистика", "🛠 Адмін-панель", "✨ Підбадьори мене", "📜 Правила", "⏳ Мій час", "🔓 Зняти КД", "🔙 Головне меню"]

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

def get_cooldown_users_menu():
    # Створюємо кнопки з ID користувачів, які зараз мають КД
    buttons = []
    current_time = time.time()
    for uid, last_time in list(user_cooldowns.items()):
        if current_time - last_time < COOLDOWN_SECONDS:
            buttons.append([KeyboardButton(text=f"Розблокувати {uid}")])
    
    buttons.append([KeyboardButton(text="🔙 Головне меню")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- UTILS ---
async def check_is_admin(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

# --- HANDLERS ---

# 1. ЗАХИСТ ЧАТУ: Видалення кнопок, якщо вони потрапили в групу
@dp.message(F.chat.id == GROUP_ID, F.text.in_(MENU_BUTTONS))
async def delete_menu_in_group(message: Message):
    try:
        await message.delete()
    except: pass

# 2. ОБРОБКА КНОПОК МЕНЮ (ПРИВАТ)
@dp.message(F.chat.type == ChatType.PRIVATE, F.text.in_(MENU_BUTTONS) | F.text.startswith("Розблокувати "))
async def handle_menus(message: Message):
    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)
    
    if message.text == "🛠 Адмін-панель" and is_admin:
        await message.answer("🔧 Адмін-меню:", reply_markup=ReplyKeyboardMarkup(
            keyboard=[[KeyboardButton(text="🔓 Зняти КД")], [KeyboardButton(text="🔙 Головне меню")]],
            resize_keyboard=True
        ))
    
    elif message.text == "🔓 Зняти КД" and is_admin:
        menu = get_cooldown_users_menu()
        await message.answer("Оберіть користувача зі списку тих, хто чекає:", reply_markup=menu)

    elif message.text.startswith("Розблокувати ") and is_admin:
        try:
            target_id = int(message.text.replace("Розблокувати ", ""))
            if target_id in user_cooldowns:
                del user_cooldowns[target_id]
                await message.answer(f"✅ Користувач {target_id} тепер може писати!", reply_markup=get_cooldown_users_menu())
            else:
                await message.answer("Користувача не знайдено або КД вже пройшло.")
        except: await message.answer("Помилка ID.")

    elif message.text == "🔙 Головне меню":
        await message.answer("Повертаємось...", reply_markup=get_main_menu(is_admin))
    
    elif message.text == "⏳ Мій час":
        if user_id in user_cooldowns:
            rem = int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[user_id])) / 60)
            if rem > 0: return await message.answer(f"⏳ Зачекай {rem} хв.")
        await message.answer("✅ Можеш писати!")
    
    # Інші кнопки... (Статистика, Правила тощо)

# 3. ПЕРЕСИЛАННЯ АНОНІМКИ
@dp.message(F.chat.type == ChatType.PRIVATE)
async def process_anonymous(message: Message):
    if message.text in MENU_BUTTONS or message.text == "/start": return
    
    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)
    
    if not is_admin and user_id in user_cooldowns:
        if time.time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            return await message.answer("⏳ Рано!")

    try:
        # Прихований ID 📍
        admin_tag = f'<a href="tg://user?id={user_id}">📍</a>'
        text_header = f"📩 <b>Анонімне повідомлення {admin_tag}</b>\n\n"
        
        if message.text:
            await bot.send_message(GROUP_ID, text_header + message.text)
        elif message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=text_header + (message.caption or ""))
        
        if not is_admin: user_cooldowns[user_id] = time.time()
        await message.answer("✅ Надіслано анонімно!")
    except: await message.answer("❌ Помилка.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
