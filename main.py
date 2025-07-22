import nest_asyncio
nest_asyncio.apply()

import json
import datetime
import asyncio
import os
import logging
from aiohttp import web
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
OWNER_CHAT_ID = int(os.getenv("OWNER_CHAT_ID"))

REMINDER_TEXT = "⏰ تذكير يومي: لا تنسَ متابعة الزبائن المتأخرين!"

async def send_reminder(context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=OWNER_CHAT_ID, text=REMINDER_TEXT)

async def scheduled_reminder(application):
    while True:
        # الوقت الحالي بتوقيت لبنان (UTC+3)
        now = datetime.datetime.utcnow() + datetime.timedelta(hours=3)
        target_time = now.replace(hour=9, minute=0, second=0, microsecond=0)

        # إذا الوقت تجاوز 9:00 اليوم، حدد التذكير لليوم التالي
        if now >= target_time:
            target_time += datetime.timedelta(days=1)

        wait_seconds = (target_time - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        await application.bot.send_message(chat_id=OWNER_CHAT_ID, text=REMINDER_TEXT)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 البوت يعمل! سيتم إرسال التذكير يوميًا الساعة 9 صباحًا.")

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))

    app.loop.create_task(scheduled_reminder(app))

    async def handle(request):
        return web.Response(text="OK")

    app.run_polling()

if __name__ == "__main__":
    main()
