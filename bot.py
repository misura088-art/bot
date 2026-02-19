import os
import asyncio
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import threading
from aiogram import Bot, Dispatcher
from aiogram.types import Message
from aiogram.filters import CommandStart
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

# --- СЕКЦІЯ ДЛЯ RENDER (ЩОБ НЕ БУЛО TIMEOUT) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_check():
    port = int(os.getenv("PORT", 8080))
    server = ThreadingHTTPServer(('0.0.0.0', port), HealthCheckHandler)
    server.serve_forever()
# ----------------------------------------------

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROUP_ID = os.getenv("GROUP_ID")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

@dp.message(CommandStart())
async def start(message: Message):
    await message.answer("👋 Привіт! Надішли своє повідомлення, і я передам його в групу **анонімно**.")

@dp.message()
async def forward_to_group(message: Message):
    if message.text:
        # Тепер тут немає імені та юзернейма відправника
        await bot.send_message(
            chat_id=GROUP_ID, 
            text=f"📩 **Нове анонімне повідомлення:**\n\n{message.text}"
        )
        await message.answer("✅ Ваше повідомлення надіслано анонімно.")

async def main():
    # Запускаємо веб-сервер у окремому потоці для Render
    threading.Thread(target=run_health_check, daemon=True).start()
    
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
