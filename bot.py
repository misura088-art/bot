import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# Отримуємо змінні з налаштувань Render
# Примітка: Render автоматично передає їх як рядки
BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

# Ініціалізація бота з виправленням для версії 3.7.0+
# Саме тут була помилка TypeError у логах
bot = Bot(
    token=BOT_TOKEN, 
    default=DefaultBotProperties(parse_mode=ParseMode.HTML)
)
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привіт! Надішли своє повідомлення і я передам його в групу.")
    
@dp.message()
async def forward_to_group(message: Message):
    # Перевіряємо, чи є в повідомленні текст
    if message.text:
        await message.answer("✅ Ваше повідомлення надіслано адміністратору.")
        await bot.send_message(
            chat_id=GROUP_ID,
            text=f"📩 Повідомлення від {message.from_user.full_name} (@{message.from_user.username}):\n\n{message.text}"
        )

async def main():
    # Очищаємо чергу повідомлень перед запуском
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())




