import os
import asyncio
import threading
import time
import random
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
from aiogram.filters import CommandStart, Command
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
COOLDOWN_SECONDS = 30 * 60 

user_cooldowns = {}
total_messages = 0
waiting_for_id = {} # Для відстеження стану адміна

# Списки для рандому
MOTIVATION = [
    "Твоя історія варта того, щоб її почули! ✨",
    "Не тримай це в собі, розкажи нам... 🤫",
    "Сьогодні чудовий день для зізнань! 📝",
    "Тут тебе ніхто не засудить. Пиши! 🤝"
]

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

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

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🔓 Зняти КД користувачу")],
        [KeyboardButton(text="🔙 Головне меню")]
    ],
    resize_keyboard=True
)

# --- ФУНКЦІЯ ПЕРЕВІРКИ АДМІНА ---
async def check_is_admin(user_id):
    try:
        member = await bot.get_chat_member(chat_id=GROUP_ID, user_id=user_id)
        return member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]
    except:
        return False

# --- ОБРОБНИКИ КОМАНД ---

@dp.message(CommandStart())
async def start(message: Message):
    is_admin = await check_is_admin(message.from_user.id)
    await message.answer(
        "👋 Вітаємо у боті <b>Підслухано</b>!\nСкористайся меню нижче:",
        reply_markup=get_main_menu(is_admin)
    )

@dp.message(F.text == "🛠 Адмін-панель")
async def admin_panel(message: Message):
    if await check_is_admin(message.from_user.id):
        await message.answer("🔧 Ласкаво просимо в адмін-панель:", reply_markup=admin_menu)

@dp.message(F.text == "🔙 Головне меню")
async def back_to_main(message: Message):
    is_admin = await check_is_admin(message.from_user.id)
    await message.answer("Повертаємось...", reply_markup=get_main_menu(is_admin))

@dp.message(F.text == "🔓 Зняти КД користувачу")
async def ask_user_id(message: Message):
    if await check_is_admin(message.from_user.id):
        waiting_for_id[message.from_user.id] = True
        await message.answer("Введіть <b>ID користувача</b>, якому потрібно зняти обмеження часі:")

@dp.message(F.text == "📊 Статистика")
async def stats(message: Message):
    await message.answer(
        f"📈 <b>Статистика проекту:</b>\n\n"
        f"📩 Надіслано анонімок: <b>{total_messages}</b>\n"
        f"👥 Користувачів у базі КД: <b>{len(user_cooldowns)}</b>"
    )

@dp.message(F.text == "✨ Підбадьори мене")
async def inspire(message: Message):
    await message.answer(random.choice(MOTIVATION))

# --- ЛОГІКА ПЕРЕСИЛАННЯ ТА АДМІН-ДІЙ ---

@dp.message()
async def handle_all_messages(message: Message):
    global total_messages
    user_id = message.from_user.id

    # 1. Перевірка, чи це адмін вводить ID для зняття КД
    if user_id in waiting_for_id:
        try:
            target_id = int(message.text)
            if target_id in user_cooldowns:
                del user_cooldowns[target_id]
                await message.answer(f"✅ КД для користувача <code>{target_id}</code> успішно знято!")
            else:
                await message.answer("❌ Цього користувача немає в черзі обмежень або він ще нічого не писав.")
        except ValueError:
            await message.answer("❌ Будь ласка, введіть коректне число (ID).")
        
        del waiting_for_id[user_id]
        return

    # Ігноруємо кнопки меню
    if message.text in ["📝 Надіслати анонімку", "📜 Правила", "⏳ Мій час", "✨ Підбадьори мене", "📊 Статистика", "🛠 Адмін-панель", "🔓 Зняти КД користувачу", "🔙 Головне меню"]:
        if message.text == "📜 Правила":
            await message.answer("Будьте ввічливими та анонімними! 🤗")
        elif message.text == "⏳ Мій час":
            if user_id in user_cooldowns:
                rem = int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[user_id])) / 60)
                if rem > 0:
                    await message.answer(f"⏳ Зачекай ще {rem} хв.")
                    return
            await message.answer("✅ Можеш писати!")
        return

    # 2. Логіка анонімки
    is_admin = await check_is_admin(user_id)
    if not is_admin and user_id in user_cooldowns:
        if time.time() - user_cooldowns[user_id] < COOLDOWN_SECONDS:
            rem = int((COOLDOWN_SECONDS - (time.time() - user_cooldowns[user_id])) / 60)
            await message.answer(f"⏳ Зачекай ще {rem} хв.")
            return

    try:
        # Додаємо ID користувача для адмінів у групі, щоб вони могли його забанити або зняти КД
        admin_info = f"\n\n(ID для адмінів: <code>{user_id}</code>)"
        caption = "📩 <b>Нове анонімне повідомлення:</b>"
        
        if message.caption: caption += f"\n\n{message.caption}"
        elif message.text: caption += f"\n\n{message.text}"

        full_text_for_group = caption + admin_info

        if message.photo:
            await bot.send_photo(GROUP_ID, message.photo[-1].file_id, caption=full_text_for_group)
        elif message.video:
            await bot.send_video(GROUP_ID, message.video.file_id, caption=full_text_for_group)
        elif message.voice:
            await bot.send_message(GROUP_ID, f"📩 <b>Анонімне голосове:</b>{admin_info}")
            await bot.send_voice(GROUP_ID, message.voice.file_id)
        elif message.text:
            await bot.send_message(GROUP_ID, full_text_for_group)

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
