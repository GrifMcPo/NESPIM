import os
import logging
import asyncio
import socket
import struct
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# --- НАСТРОЙКИ ---
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ADMIN_CHAT_ID = int(os.environ.get("ADMIN_CHAT_ID", "0"))
RCON_HOST = "f1.rustix.me"  # твой IP
RCON_PORT = 25575
RCON_PASS = "__871410__grifmcproRCON"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if not TELEGRAM_TOKEN or not ADMIN_CHAT_ID:
    raise RuntimeError("TELEGRAM_TOKEN и ADMIN_CHAT_ID должны быть заданы!")

# --- RCON КЛИЕНТ ---
class RconClient:
    def __init__(self, host, port, password):
        self.host = host
        self.port = port
        self.password = password
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        packet = struct.pack('<iii', 10, 0, 0) + self.password.encode('utf-8') + b'\x00'
        self.sock.send(packet)
        response = self.sock.recv(4096)
        if len(response) < 4:
            raise ConnectionError("RCON auth failed")

    def command(self, cmd):
        packet = struct.pack('<iii', 10, 1, 0) + cmd.encode('utf-8') + b'\x00'
        self.sock.send(packet)
        data = self.sock.recv(4096)
        if len(data) > 12:
            return data[12:-1].decode('utf-8', errors='ignore')
        return "OK"

# --- КОМАНДЫ БОТА ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    logger.info(f"Команда /start от {user_id}")
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    await update.message.reply_text("✅ RCON бот активен!\nИспользуй /rcon list")

async def rcon_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id != ADMIN_CHAT_ID:
        await update.message.reply_text("⛔ Доступ запрещён.")
        return
    if not context.args:
        await update.message.reply_text("ℹ️ Введите команду после /rcon")
        return
    cmd = ' '.join(context.args)
    try:
        rcon = RconClient(RCON_HOST, RCON_PORT, RCON_PASS)
        rcon.connect()
        result = rcon.command(cmd)
        await update.message.reply_text(f"💻 Ответ:\n```\n{result[:4000]}\n```", parse_mode='Markdown')
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# --- ЗАПУСК БОТА В ФОНЕ ---
def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("rcon", rcon_cmd))
    app.run_polling()

# --- FLASK ДЛЯ RENDER ---
app = Flask(__name__)

@app.route('/')
def index():
    return "RCON Bot is running"

@app.route('/health')
def health():
    return "OK"

# --- ТОЧКА ВХОДА ---
if __name__ == "__main__":
    # Запускаем бота в отдельном потоке
    import threading
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    
    # Запускаем Flask
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
