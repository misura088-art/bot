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

MENU_BUTTONS = ["📝 Надіслати анонімку", "📊 Статистика", "🛠 Адмін-панель", "✨ Підбадьори мене", "📜 Правила", "⏳ Мій час", "🔓 Зняти КД користувачу", "🔙 Головне меню"]

def get_main_menu(is_admin=False):
    buttons = [
        [KeyboardButton(text="📝 Надіслати анонімку")],
        [KeyboardButton(text="✨ Підбадьори мене"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="📜 Правила"), KeyboardButton(text="⏳ Мій час")]
    ]
    if is_admin:
        buttons.append([KeyboardButton(text="🛠 Адмін-панель")])
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

async def check_is_admin(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except: return False

@dp.message(F.chat.type == ChatType.PRIVATE)
async def handle_private(message: Message):
    global total_messages
    user_id = message.from_user.id
    is_admin = await check_is_admin(user_id)

    if message.text == "/start":
        await message.answer("Вітаю в Підслухано!", reply_markup=get_main_menu(is_admin))
        return

    # Адмін-логіка зняття КД
    if user_id in waiting_for_id:
        try:
            target_id = int(message.text)
            if target_id in user_cooldowns:
                del user_cooldowns[target_id]
                await message.answer(f"✅ КД для <code>{target_id}</code> знято!")
            else: await message.answer("❌ ID не знайдено в черзі.")
        except: await message.answer("❌ Введіть число.")
        del waiting_for_id[user_id]
        return

    if message.text in MENU_BUTTONS:
        if message.text == "📊 Статистика":
            await message.answer(f"📈 Надіслано анонімок: <b>{total_messages}</b>")
        elif message.text == "🛠 Адмін-панель" and is_admin:
            kb = ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="🔓 Зняти КД користувачу")], [KeyboardButton(text="🔙 Головне меню")]], resize_keyboard=True)
            await message.answer("🔧 Адмін-панель:", reply_markup=kb)
        elif message.text == "🔓 Зняти КД користувачу" and is_admin:
            waiting_for_id[user_id] = True
            await message.answer("Надішліть ID користувача:")
        elif message.text == "🔙 Головне меню":
            await message.answer("Головне меню:", reply_markup=get_main_menu(is_admin))
        return

    # Перевірка КД
    if not is_admin and user_id in user_cooldowns:
        if time.time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            await message.answer(f"⏳ Зачекайте {int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[user_id])) / 60)} хв.")
            return

    try:
        # ХИТРИЙ ПРИХОВАНИЙ ID (тільки для тих, хто знає куди тиснути)
        # Ми ховаємо ID у посилання на самого бота. Звичайний юзер бачить просто синій текст.
        admin_link = f'<a href="tg://user?id={user_id}">📍</a>' 
        caption = f"📩 <b>Нове анонімне повідомлення {admin_link}</b>"
        
        content = message.text if message.text else message.caption
        if content: caption += f"\n\n{content}"

        if message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=caption)
        elif message.video:
            await bot.send_video(GROUP_ID, message.video.file_id, caption=caption)
        elif message.text:
            await bot.send_message(GROUP_ID, caption)

        total_messages += 1
        if not is_admin: user_cooldowns[user_id] = time.time()
        await message.answer("✅ Надіслано анонімно!")
    except: await message.answer("❌ Помилка.")

async def main():
    threading.Thread(target=run_health_check, daemon=True).start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
    
