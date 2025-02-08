import logging
import qrcode
import os
from urllib.parse import quote
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ConversationHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    CallbackContext
)

# Стадии диалога
DESIGN, INTRO, PROPOSAL, TIMES = range(4)

# Настройка логирования
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)


async def start(update: Update, context: CallbackContext) -> int:
    """Начало диалога с пользователем"""
    await update.message.reply_text(
        "Настоящее свидание начинается с красивого приглашения. Давай сделаем его идеальным!\n\n"
        "Выбери дизайн для открытки:"
    )
    keyboard = [
        [InlineKeyboardButton("🎆 Элегантная ночь", callback_data="design_elegant")],
        [InlineKeyboardButton("🌹 Романтика", callback_data="design_romantic")],
        [InlineKeyboardButton("🎶 Музыка и кино", callback_data="design_music")],
        [InlineKeyboardButton("💡 Минимализм", callback_data="design_minimal")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text("Выбери один из вариантов:", reply_markup=reply_markup)
    return DESIGN


async def design_choice(update: Update, context: CallbackContext) -> int:
    """Обработка выбора дизайна"""
    query = update.callback_query
    await query.answer()
    design = query.data
    context.user_data["design"] = design
    await query.edit_message_text(
        text=f"Ты выбрал {design}. Введи вступительный текст для приглашения:"
    )
    return INTRO


async def get_intro(update: Update, context: CallbackContext) -> int:
    """Получение вступительного текста"""
    intro_text = update.message.text
    context.user_data["intro"] = intro_text
    await update.message.reply_text("Теперь напиши само предложение для встречи:")
    return PROPOSAL


async def get_proposal(update: Update, context: CallbackContext) -> int:
    """Получение текста приглашения"""
    proposal_text = update.message.text
    context.user_data["proposal"] = proposal_text
    await update.message.reply_text(
        "Укажи 3 варианта времени для встречи (например, в формате:\n"
        "🕗 19:00 | 21 января\n"
        "🌙 20:30 | 22 января\n"
        "☕ 17:00 | 23 января)"
    )
    return TIMES


async def get_times(update: Update, context: CallbackContext) -> int:
    """Получение вариантов времени, генерация ссылки и QR-кода"""
    times_text = update.message.text
    context.user_data["times"] = times_text.splitlines()  # Разбиваем варианты по строкам

    # Получаем сохранённые данные
    design = context.user_data.get("design", "design_elegant")
    intro = context.user_data.get("intro", "Привет! Я подготовил для тебя нечто особенное...")
    proposal = context.user_data.get("proposal", "Давай проведём этот вечер вместе. Я знаю уютное место!")
    times = context.user_data.get("times", ["🕗 19:00 | 21 января", "🌙 20:30 | 22 января", "☕ 17:00 | 23 января"])

    # Кодируем строки для URL
    encoded_intro = quote(intro)
    encoded_proposal = quote(proposal)

    # Получаем chat_id текущего чата
    chat_id = update.effective_chat.id

    # Формируем URL для приглашения (ЗАМЕНИТЬ НА ВАШ ДОМЕН ИЛИ NGROK)
    public_url = "http://svety.uz"  # Если у вас есть публичный домен, укажите его здесь
    invite_url = (f"{public_url}/invite/{chat_id}?"
                  f"design={design}&intro={encoded_intro}&proposal={encoded_proposal}"
                  f"&chat_id={chat_id}")
    511614471
   #//http://81.162.55.37:5000/invite/511614471

    # Генерация QR-кода
    img = qrcode.make(invite_url)
    img_path = "invite_qr.png"
    img.save(img_path)

    # Отправляем QR-код с подписью
    with open(img_path, "rb") as photo:
        await update.message.reply_photo(
            photo=photo,
            caption=f"Отлично! Мини-сайт готов.\n\n"
                    f"📌 Открыть приглашение: {invite_url}"
        )

    # Удаляем QR-код после отправки (опционально)
    os.remove(img_path)

    return ConversationHandler.END


def main():
    """Запуск Telegram-бота"""
    application = ApplicationBuilder().token("8046219766:AAGFsWXIFTEPe8aaTBimVyWm2au2f-uIYSs").build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            DESIGN: [CallbackQueryHandler(design_choice)],
            INTRO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_intro)],
            PROPOSAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_proposal)],
            TIMES: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_times)]
        },
        fallbacks=[]
    )

    application.add_handler(conv_handler)
    application.run_polling()


if __name__ == "__main__":
    main()
