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
    CallbackQueryHandler, ConversationHandler, MessageHandler, filters
)

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("BOT_TOKEN")
owner_chat_id_str = os.getenv("OWNER_CHAT_ID")

if TOKEN is None:
    raise ValueError("Environment variable BOT_TOKEN is not set!")
if owner_chat_id_str is None:
    raise ValueError("Environment variable OWNER_CHAT_ID is not set!")

CHAT_ID = int(owner_chat_id_str)
DATA_FILE = "customers.json"

ADD_CUSTOMER, DELETE_CUSTOMER = range(2)

def load_customers():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    return {}

def save_customers(customers):
    with open(DATA_FILE, "w") as f:
        json.dump(customers, f)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[
        InlineKeyboardButton("➕ Add Customer", callback_data="add_customer"),
        InlineKeyboardButton("🗑️ Delete Customer", callback_data="delete_customer"),
        InlineKeyboardButton("📋 Show Customers", callback_data="show_customers")
    ]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Welcome to the Customer Management Bot! Use the buttons below to manage customers.",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "add_customer":
        await query.message.reply_text("Please type the name of the new customer:")
        return ADD_CUSTOMER

    elif data == "delete_customer":
        await query.message.reply_text("Please type the name of the customer to delete:")
        return DELETE_CUSTOMER

    elif data == "show_customers":
        customers = load_customers()
        if not customers:
            await query.message.reply_text("No customers currently.")
            return ConversationHandler.END

        text = "Customers List:\n\n"
        for name, info in customers.items():
            status = "✅ Paid" if info["paid"] else "❌ Not Paid"
            text += f"{name} (Added on: {info['join_date']}) - {status}\n"
        await query.message.reply_text(text)
        return ConversationHandler.END

    elif data.startswith("paid_"):
        name = data[5:]
        customers = load_customers()
        if name in customers and not customers[name]["paid"]:
            customers[name]["paid"] = True
            save_customers(customers)
            await query.edit_message_text(f"Payment recorded for customer: {name}")
            await send_customers_list(update)
        return ConversationHandler.END

async def receive_customer_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    customers = load_customers()

    if name in customers:
        await update.message.reply_text(f"Customer {name} already exists.")
        return ConversationHandler.END

    today = datetime.date.today().isoformat()
    customers[name] = {"join_date": today, "paid": False}
    save_customers(customers)
    await update.message.reply_text(f"Customer {name} added successfully.")
    await send_customers_list(update)
    return ConversationHandler.END

async def receive_delete_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    customers = load_customers()

    if name not in customers:
        await update.message.reply_text(f"Customer {name} does not exist.")
        return ConversationHandler.END

    del customers[name]
    save_customers(customers)
    await update.message.reply_text(f"Customer {name} has been deleted.")
    await send_customers_list(update)
    return ConversationHandler.END

async def send_customers_list(update: Update):
    customers = load_customers()
    if not customers:
        await update.message.reply_text("No customers currently.")
        return

    text = "Customers List:\n\n"
    keyboard = []

    for name, info in customers.items():
        status = "✅ Paid" if info["paid"] else "❌ Not Paid"
        text += f"{name} (Added on: {info['join_date']}) - {status}\n"
        if not info["paid"]:
            keyboard.append([
                InlineKeyboardButton(f"Mark Paid: {name}",
                                     callback_data=f"paid_{name}")
            ])

    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None
    if update.message:
        await update.message.reply_text(text, reply_markup=reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(text, reply_markup=reply_markup)

async def remind_customers(app):
    customers = load_customers()
    today = datetime.date.today()
    to_remind = []
    for name, info in customers.items():
        if info["paid"]:
            continue
        join_date = datetime.date.fromisoformat(info["join_date"])
        delta = (today - join_date).days
        if delta >= 1:
            to_remind.append(name)

    if to_remind:
        try:
            text = "Reminder: The following customers have not paid:\n" + "\n".join(to_remind)
            await app.bot.send_message(CHAT_ID, text)
        except Exception as e:
            print("Error sending reminder:", e)

async def scheduled_reminder(app):
    while True:
        now = datetime.datetime.now()
        target_time = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if now >= target_time:
            target_time += datetime.timedelta(days=1)
        wait_seconds = (target_time - now).total_seconds()
        print(f"Waiting {wait_seconds} seconds until 9 AM")
        await asyncio.sleep(wait_seconds)
        await remind_customers(app)

async def handle_web(request):
    return web.Response(text="Fadi Bot is running ✅")

async def run_web_server():
    port = int(os.environ.get("PORT", 8080))
    print(f"Starting web server on port {port} ...")
    app = web.Application()
    app.router.add_get("/", handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()

async def main():
    # ✅ حماية: تأكد أن البوت لا يعمل إلا على Render
    if os.environ.get("RENDER") != "true":
        raise RuntimeError("⛔️ لا تشغل البوت يدويًا! هو يعمل تلقائيًا على Render فقط.")

    asyncio.create_task(run_web_server())

    app = ApplicationBuilder().token(TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="add_customer"),
            CallbackQueryHandler(button_handler, pattern="delete_customer")
        ],
        states={
            ADD_CUSTOMER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_customer_name)
            ],
            DELETE_CUSTOMER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, receive_delete_name)
            ],
        },
        fallbacks=[]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler, pattern="^paid_"))
    app.add_handler(CallbackQueryHandler(button_handler))

    asyncio.create_task(scheduled_reminder(app))

    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
