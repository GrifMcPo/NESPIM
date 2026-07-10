import os
import logging
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import asyncio
import socket
import struct

# --- НАСТРОЙКИ ДЛЯ RUSTIX ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
RCON_HOST = "f1.rustix.me"   # IP твоего сервера на Rustix
RCON_PORT = 25575            # Порт RCON (стандартный)
RCON_PASS = "__871410__grifmcproRCON"  # Пароль RCON

if not TELEGRAM_TOKEN or not ADMIN_CHAT_ID:
    raise RuntimeError("TELEGRAM_TOKEN и ADMIN_CHAT_ID должны быть заданы!")

# --- КЛАСС ДЛЯ РАБОТЫ С RCON ---
class RconClient:
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self._send_auth()

    def _send_auth(self):
        # Пакет авторизации RCON
        packet = struct.pack('<iii', 10, 0, 0) + self.password.encode('utf-8') + b'\x00'
        self.sock.send(packet)
        response = self.sock.recv(4096)
        if len(response) < 4:
            raise ConnectionError("RCON авторизация не удалась")

    def command(self, cmd):
        # Отправка команды и получение ответа
        packet = struct.pack('<iii', 10, 1, 0) + cmd.encode('utf-8') + b'\x00'
        self.sock.send(packet)
        data = self.sock.recv(4096)
        if len(data) > 12:
            return data[12:-1].decode('utf-8', errors='ignore')
        return "OK"

# --- ОБРАБОТЧИКИ КОМАНД БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    await update.message.reply_text(
        "🔌 **RCON бот активен**\n"
        "Используй: `/rcon <команда>`\n"
        "Пример: `/rcon list`"
    )

async def rcon_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Введите команду после /rcon")
        return

    command = ' '.join(context.args)
    try:
        rcon = RconClient(RCON_HOST, RCON_PORT, RCON_PASS)
        rcon.connect()
        result = rcon.command(command)
        # Обрезаем ответ, если он слишком длинный (Telegram лимит 4096 символов)
        if len(result) > 4000:
            result = result[:4000] + "\n... (обрезано)"
        await update.message.reply_text(
            f"💻 **Ответ сервера:**\n```\n{result}\n```",
            parse_mode='Markdown'
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка при выполнении команды: {e}")

# --- ЗАПУСК БОТА ---
async def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rcon", rcon_cmd))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    return app

# --- FLASK ДЛЯ RENDER (чтобы держать бота активным) ---
app = Flask(__name__)

@app.route('/')
def index():
    return "RCON Bot is running"

@app.route('/health')
def health():
    return "OK"

# --- ТОЧКА ВХОДА ---
if __name__ == "__main__":
    # Запускаем бота в фоновом потоке
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    bot_app = loop.run_until_complete(run_bot())

    # Запускаем Flask для Render
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
