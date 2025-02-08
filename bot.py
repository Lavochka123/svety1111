import logging
import os
import qrcode
import sqlite3
import uuid

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes
)

# Этапы диалога
DESIGN, PAGE1, PAGE2, PAGE3, TIMES = range(5)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)

# Укажите реальный публичный URL вашего веб-сайта:
PUBLIC_URL = "http://svety.uz"

# Подключение к базе данных (файл лежит в той же папке)
DB_PATH = "app.db"


def create_table_if_not_exists():
    """Создаёт таблицу invitations, если она ещё не существует."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS invitations (
            id TEXT PRIMARY KEY,
            design TEXT,
            intro TEXT,       -- Сюда кладём объединённые page1 + page2
            proposal TEXT,    -- Сюда кладём page3
            times TEXT,
            chat_id TEXT
        )
    ''')
    conn.commit()
    conn.close()


def save_invitation(design, intro, proposal, times, chat_id):
    """
    Сохраняет приглашение в БД и возвращает сгенерированный ID (UUID).
    times — это список строк (варианты времени).
    """
    unique_id = str(uuid.uuid4())  # Генерируем уникальный ключ
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        INSERT INTO invitations (id, design, intro, proposal, times, chat_id)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (unique_id, design, intro, proposal, "\n".join(times), str(chat_id)))
    conn.commit()
    conn.close()
    return unique_id


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Начало диалога с пользователем"""
    create_table_if_not_exists()

    await update.message.reply_text(
        "Привет! Давай создадим красивое приглашение на свидание!\n\n"
        "Для начала выбери дизайн открытки:"
    )
    keyboard = [
        [InlineKeyboardButton("🎆 Элегантная ночь", callback_data="design_elegant")],
        [InlineKeyboardButton("🌹 Романтика", callback_data="design_romantic")],
        [InlineKeyboardButton("🎶 Музыка и кино", callback_data="design_music")],
        [InlineKeyboardButton("💡 Минимализм", callback_data="design_minimal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "Выбери один из вариантов:",
        reply_markup=reply_markup
    )
    return DESIGN


async def design_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """Обработка выбора дизайна (Шаг 0)"""
    query = update.callback_query
    await query.answer()
    design = query.data
    context.user_data["design"] = design

    await query.edit_message_text(
        text=(
            f"Ты выбрал дизайн: {design}.\n\n"
            "Теперь введи **первую страницу** текста, например:\n"
            "«Дорогая Настя! Хочу сказать, что ты... (и т.д.)»"
        )
    )
    return PAGE1


async def get_page1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получение текста «первой страницы» (Например, «Дорогая Настя…»)
    """
    page1_text = update.message.text.strip()
    context.user_data["page1"] = page1_text

    await update.message.reply_text(
        "Отлично! Теперь давай создадим **вторую страницу** — "
        "подготовительная часть (интрига или лёгкое предисловие). Например:\n\n"
        "«Ты мне очень нравишься, и я решил(а) подготовить кое-что особенное... (и т.д.)»"
    )
    return PAGE2


async def get_page2(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получение текста «второй страницы» (Подготовительная часть).
    """
    page2_text = update.message.text.strip()
    context.user_data["page2"] = page2_text

    await update.message.reply_text(
        "Прекрасно! Теперь переходим к **третьей странице** — "
        "само приглашение на свидание. Например:\n\n"
        "«Я хочу провести с тобой особенный вечер... Давай встретимся... (и т.д.)»"
    )
    return PAGE3


async def get_page3(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получение «третьей страницы» (основное приглашение).
    """
    page3_text = update.message.text.strip()
    context.user_data["page3"] = page3_text

    await update.message.reply_text(
        "Отлично! Теперь укажи 3 варианта времени (каждый с новой строки). Например:\n\n"
        "🕗 19:00 | 21 января\n"
        "🌙 20:30 | 22 января\n"
        "☕ 17:00 | 23 января"
    )
    return TIMES


async def get_times(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """
    Получение вариантов времени, сохранение в БД,
    генерация короткой ссылки (с ID вместо длинных GET-параметров)
    и отправка QR-кода.
    """
    times_text = update.message.text
    times_list = [line.strip() for line in times_text.splitlines() if line.strip()]

    design = context.user_data.get("design", "design_elegant")

    # Объединяем page1 и page2 в одно поле "intro"
    page1 = context.user_data.get("page1", "")
    page2 = context.user_data.get("page2", "")
    intro_combined = page1 + "\n\n" + page2  # разделяем двумя пустыми строками

    # Третья страница станет proposal
    proposal_text = context.user_data.get("page3", "")

    chat_id = update.effective_chat.id

    # Сохраняем в БД
    invite_id = save_invitation(design, intro_combined, proposal_text, times_list, chat_id)

    # Формируем короткий URL
    invite_url = f"{PUBLIC_URL}/invite/{invite_id}"

    # Генерация QR-кода
    img = qrcode.make(invite_url)
    img_path = "invite_qr.png"
    img.save(img_path)

    # Отправляем QR-код с итоговым сообщением
    with open(img_path, "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=(
                f"Отлично! Твоё приглашение готово.\n\n"
                f"Вот ссылка: {invite_url}\n\n"
                f"Отправь её адресату (или QR-код), чтобы она могла увидеть твоё сообщение!"
            )
        )

    # Удаляем QR-код (если не нужен)
    os.remove(img_path)

    return ConversationHandler.END


def main():
    """Запуск Telegram-бота"""
    BOT_TOKEN = "8046219766:AAGFsWXIFTEPe8aaTBimVyWm2au2f-uIYSs"

    application = ApplicationBuilder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            DESIGN: [CallbackQueryHandler(design_choice)],
            PAGE1: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_page1)],
            PAGE2: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_page2)],
            PAGE3: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_page3)],
            TIMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_times)]
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
