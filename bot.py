import logging
import os
import qrcode
import sqlite3
import uuid
import asyncio
import threading

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

# Состояния диалога:
# OPTION – начальный выбор между приглашением и поздравлением
# I_DESIGN – выбор темы для приглашения
# I_PHOTO_UPLOAD – загрузка фото для приглашения (если выбран вариант custom)
# I_PAGE1 – текст первой страницы приглашения
# I_PAGE2 – текст второй страницы приглашения
# I_PAGE3 – текст третьей страницы приглашения
# I_SENDER – имя отправителя приглашения
# I_TIMES – варианты времени для приглашения
# G_DESIGN – выбор фона для поздравления с 8 марта
# G_PHOTO_UPLOAD – загрузка фото для поздравления (если выбран вариант custom)
# G_TEXT – поздравительный текст
# G_SENDER – имя (от кого поздравление)
OPTION, I_DESIGN, I_PHOTO_UPLOAD, I_PAGE1, I_PAGE2, I_PAGE3, I_SENDER, I_TIMES, G_DESIGN, G_PHOTO_UPLOAD, G_TEXT, G_SENDER = range(12)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
PUBLIC_URL = "https://svety.uz"  # публичный URL (с HTTPS)
DB_PATH = "app.db"
TELEGRAM_BOT_TOKEN = "7737841966:AAFIgmwHXNw1mvYZ8a4Jysl9KH1b_hb1x-c"  # Замените на ваш реальный токен
bot = Bot(token=TELEGRAM_BOT_TOKEN)

def create_table_if_not_exists():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS invitations (
            id TEXT PRIMARY KEY,
            design TEXT,
            bg_image TEXT,
            page1 TEXT,
            page2 TEXT,
            page3 TEXT,
            sender TEXT,
            times TEXT,
            chat_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

create_table_if_not_exists()

# Создаем event loop для асинхронных операций Telegram
loop = asyncio.new_event_loop()
def run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()
threading.Thread(target=run_loop, args=(loop,), daemon=True).start()

def send_message_sync(chat_id, message):
    future = asyncio.run_coroutine_threadsafe(
        bot.send_message(chat_id=chat_id, text=message),
        loop
    )
    return future.result(timeout=10)

def get_invitation(invite_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT design, bg_image, page1, page2, page3, sender, times, chat_id FROM invitations WHERE id = ?', (invite_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "id": invite_id,
            "design": row[0],
            "bg_image": row[1],
            "page1": row[2],
            "page2": row[3],
            "page3": row[4],
            "sender": row[5],
            "times": row[6].split("\n") if row[6] else [],
            "chat_id": row[7]
        }
    return None

def save_invitation(design, bg_image, page1, page2, page3, sender, times, chat_id):
    invite_id = str(uuid.uuid4())
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO invitations (id, design, bg_image, page1, page2, page3, sender, times, chat_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        invite_id,
        design,
        bg_image,
        page1,
        page2,
        page3,
        sender,
        "\n".join(times),
        str(chat_id)
    ))
    conn.commit()
    conn.close()
    return invite_id

# --- Начальный выбор варианта ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text(
        "Добро пожаловать!\nВыберите, что вы хотите создать:\n\n1. Приглашение на свидание\n2. Поздравление с 8 марта"
    )
    keyboard = [
        [InlineKeyboardButton("Приглашение на свидание", callback_data="invitation")],
        [InlineKeyboardButton("Поздравление с 8 марта", callback_data="greeting")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выберите вариант:", reply_markup=reply_markup)
    return OPTION

async def option_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data
    if choice == "invitation":
        await query.edit_message_text("Вы выбрали приглашение на свидание.")
        keyboard = [
            [InlineKeyboardButton("🎆 Элегантная ночь", callback_data="design_elegant")],
            [InlineKeyboardButton("🌹 Романтика", callback_data="design_romantic")],
            [InlineKeyboardButton("🎶 Музыка и кино", callback_data="design_music")],
            [InlineKeyboardButton("🖼 Загрузить своё фото", callback_data="design_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите тему для приглашения:", reply_markup=reply_markup)
        return I_DESIGN
    elif choice == "greeting":
        await query.edit_message_text("Вы выбрали поздравление с 8 марта.")
        keyboard = [
            [InlineKeyboardButton("💐 Цветы 1", callback_data="g_design_1")],
            [InlineKeyboardButton("💐 Цветы 2", callback_data="g_design_2")],
            [InlineKeyboardButton("💐 Цветы 3", callback_data="g_design_3")],
            [InlineKeyboardButton("🖼 Загрузить своё фото", callback_data="g_design_custom")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.message.reply_text("Выберите фон для поздравления:", reply_markup=reply_markup)
        return G_DESIGN

# --- Invitation Flow ---
async def invitation_design_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data  # design_elegant, design_romantic, design_music, design_custom
    context.user_data["design"] = choice
    if choice == "design_custom":
        await query.edit_message_text("Пожалуйста, отправьте фотографию для фона приглашения.")
        return I_PHOTO_UPLOAD
    else:
        predefined = {
            "design_elegant": "designs/elegant.jpg",
            "design_romantic": "designs/romantic.jpg",
            "design_music": "designs/music.jpg"
        }
        context.user_data["bg_image"] = predefined.get(choice, "")
        await query.edit_message_text("Введите текст для первой страницы приглашения:")
        return I_PAGE1

async def invitation_handle_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text("Это не фотография. Пожалуйста, отправьте фото.")
        return I_PHOTO_UPLOAD
    photo = update.message.photo[-1]
    file = await photo.get_file()
    filename = f"{uuid.uuid4()}.jpg"
    upload_dir = "static/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    await file.download_to_drive(file_path)
    context.user_data["bg_image"] = "uploads/" + filename
    await update.message.reply_text("Введите текст для первой страницы приглашения:")
    return I_PAGE1

async def invitation_get_page1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["page1"] = update.message.text.strip()
    await update.message.reply_text("Введите текст для второй страницы:")
    return I_PAGE2

async def invitation_get_page2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["page2"] = update.message.text.strip()
    await update.message.reply_text("Введите текст для третьей страницы приглашения:")
    return I_PAGE3

async def invitation_get_page3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["page3"] = update.message.text.strip()
    await update.message.reply_text("Введите ваше имя (от кого приглашение):")
    return I_SENDER

async def invitation_get_sender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["sender"] = update.message.text.strip()
    await update.message.reply_text("Введите варианты времени для встречи (каждый с новой строки):")
    return I_TIMES

async def invitation_get_times(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    times_text = update.message.text
    times_list = [line.strip() for line in times_text.splitlines() if line.strip()]
    chat_id = update.effective_chat.id
    invite_id = save_invitation(
        context.user_data.get("design", ""),
        context.user_data.get("bg_image", ""),
        context.user_data.get("page1", ""),
        context.user_data.get("page2", ""),
        context.user_data.get("page3", ""),
        context.user_data.get("sender", ""),
        times_list,
        chat_id
    )
    invite_url = f"{PUBLIC_URL}/invite/{invite_id}"
    img = qrcode.make(invite_url)
    img_path = "invite_qr.png"
    img.save(img_path)
    with open(img_path, "rb") as photo:
        await update.message.reply_photo(photo=photo, caption=f"Приглашение готово!\nВот ваша ссылка: {invite_url}")
    os.remove(img_path)
    return ConversationHandler.END

# --- Greeting Flow ---
async def greeting_design_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    choice = query.data  # g_design_1, g_design_2, g_design_3, g_design_custom
    context.user_data["g_design"] = choice
    if choice == "g_design_custom":
        await query.edit_message_text("Пожалуйста, отправьте фотографию для фона поздравления.")
        return G_PHOTO_UPLOAD
    else:
        predefined = {
            "g_design_1": "greetings/1.jpeg",  # используем расширение .jpeg
            "g_design_2": "greetings/2.jpeg",
            "g_design_3": "greetings/3.jpeg"
        }
        context.user_data["bg_image"] = predefined.get(choice, "")
        await query.edit_message_text("Введите поздравительный текст:")
        return G_TEXT

async def greeting_handle_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not update.message.photo:
        await update.message.reply_text("Это не фотография. Пожалуйста, отправьте фото.")
        return G_PHOTO_UPLOAD
    photo = update.message.photo[-1]
    file = await photo.get_file()
    filename = f"{uuid.uuid4()}.jpg"
    upload_dir = "static/uploads"
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    await file.download_to_drive(file_path)
    context.user_data["bg_image"] = "uploads/" + filename
    await update.message.reply_text("Введите поздравительный текст:")
    return G_TEXT

async def greeting_get_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["g_text"] = update.message.text.strip()
    await update.message.reply_text("Введите ваше имя (от кого поздравление, от кого эти цветы):")
    return G_SENDER

async def greeting_get_sender(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data["sender"] = update.message.text.strip()
    chat_id = update.effective_chat.id
    invite_id = save_invitation(
        context.user_data.get("g_design", ""),
        context.user_data.get("bg_image", ""),
        context.user_data.get("g_text", ""),
        "", "",  # пустые для второй и третьей страниц
        context.user_data.get("sender", ""),
        ["Поздравление с 8 марта"],
        chat_id
    )
    invite_url = f"{PUBLIC_URL}/invite/{invite_id}"
    img = qrcode.make(invite_url)
    img_path = "invite_qr.png"
    img.save(img_path)
    with open(img_path, "rb") as photo:
        await update.message.reply_photo(photo=photo, caption=f"Поздравление готово!\nВот ваша ссылка: {invite_url}")
    os.remove(img_path)
    return ConversationHandler.END

def main():
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            OPTION: [CallbackQueryHandler(option_choice, pattern="^(invitation|greeting)$")],
            # Invitation flow:
            I_DESIGN: [CallbackQueryHandler(invitation_design_choice, pattern="^design_.*$")],
            I_PHOTO_UPLOAD: [MessageHandler(filters.PHOTO, invitation_handle_photo_upload)],
            I_PAGE1: [MessageHandler(filters.TEXT & ~filters.COMMAND, invitation_get_page1)],
            I_PAGE2: [MessageHandler(filters.TEXT & ~filters.COMMAND, invitation_get_page2)],
            I_PAGE3: [MessageHandler(filters.TEXT & ~filters.COMMAND, invitation_get_page3)],
            I_SENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, invitation_get_sender)],
            I_TIMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, invitation_get_times)],
            # Greeting flow:
            G_DESIGN: [CallbackQueryHandler(greeting_design_choice, pattern="^g_design_.*$")],
            G_PHOTO_UPLOAD: [MessageHandler(filters.PHOTO, greeting_handle_photo_upload)],
            G_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, greeting_get_text)],
            G_SENDER: [MessageHandler(filters.TEXT & ~filters.COMMAND, greeting_get_sender)]
        },
        fallbacks=[]
    )
    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == "__main__":
    main()
