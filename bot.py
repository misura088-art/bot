import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = int(os.getenv("GROUP_ID"))

bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привіт! Надішли своє повідомлення і я передам його в групу.")
    
@dp.message()
async def forward_to_group(message: Message):
    await message.answer("✅ Ваше повідомлення надіслано адміністратору.")
    await bot.send_message(
        GROUP_ID,
        f"📩 Повідомлення від {message.from_user.full_name} (@{message.from_user.username}):\n{message.text}"
    )

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())




