import os
import sqlite3
import qrcode
from io import BytesIO
from telegram import Update, ReplyKeyboardRemove, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, ConversationHandler, CallbackQueryHandler, CallbackContext

# Telegram Bot Token (вставьте сюда токен своего бота)
TELEGRAM_BOT_TOKEN = '7737841966:AAFIgmwHXNw1mvYZ8a4Jysl9KH1b_hb1x-c'

# Определение состояний для ConversationHandler
NAME, DATETIME, TEXT1, TEXT2, PHOTO, PHOTO_CONFIRM, CONFIRM, CHOOSE_FIELD, EDIT_TEXT, EDIT_PHOTO = range(10)

# Настройки путей и базы данных
BASE_URL = "http://your-server.com"  # Адрес вашего сервера (измените на свой домен или IP)
DB_FILE = "invitations.db"
STATIC_INVITES_DIR = os.path.join("static", "invites")
STATIC_TMP_DIR = os.path.join("static", "tmp")

# Обеспечить наличие необходимых директорий
os.makedirs(STATIC_INVITES_DIR, exist_ok=True)
os.makedirs(STATIC_TMP_DIR, exist_ok=True)

def start(update: Update, context: CallbackContext) -> int:
    """Начало диалога по команде /start: приветствие и запрос названия события."""
    update.message.reply_text(
        "Привет! Я помогу создать онлайн-приглашение.\n"
        "Давайте начнём.\n"
        "Как называется Ваше событие или имя приглашения?",
        reply_markup=ReplyKeyboardRemove()
    )
    return NAME

def cancel(update: Update, context: CallbackContext) -> int:
    """Обработка команды /cancel: отмена создания приглашения на любом этапе."""
    # Удаляем временное изображение, если было сохранено
    temp_image = context.user_data.get("photo_temp_path")
    if temp_image and os.path.exists(temp_image):
        try:
            os.remove(temp_image)
        except OSError:
            pass
    # Очищаем данные пользователя
    context.user_data.clear()
    update.message.reply_text("Создание приглашения отменено. Если захотите начать заново, отправьте команду /start.")
    return ConversationHandler.END

def name_handler(update: Update, context: CallbackContext) -> int:
    """Получение названия события/приглашения."""
    name = update.message.text.strip()
    # Валидация названия
    if not name:
        update.message.reply_text("Название не может быть пустым. Пожалуйста, введите название события или приглашения.")
        return NAME
    if len(name) > 100:
        update.message.reply_text("Название слишком длинное (более 100 символов). Пожалуйста, введите покороче.")
        return NAME
    # Сохранение названия
    context.user_data["name"] = name
    # Запрос даты и времени
    update.message.reply_text(
        f"Отлично, событие называется: {name}.\n"
        "Теперь укажите дату и время события (например, 25 декабря 2025, 18:00):"
    )
    return DATETIME

def date_handler(update: Update, context: CallbackContext) -> int:
    """Получение даты и времени мероприятия."""
    event_time = update.message.text.strip()
    # Валидация ввода
    if not event_time:
        update.message.reply_text("Дата/время не может быть пустым. Пожалуйста, укажите дату и время проведения мероприятия.")
        return DATETIME
    if len(event_time) > 100:
        update.message.reply_text("Слишком длинное описание даты/времени. Пожалуйста, укажите чуть короче.")
        return DATETIME
    # Сохранение даты и времени
    context.user_data["datetime"] = event_time
    # Запрос основного текста приглашения (страница 1)
    update.message.reply_text(
        "Хорошо. Теперь введите основной текст приглашения (страница 1).\n"
        "Например, несколько приветственных слов или основную информацию о событии."
    )
    return TEXT1

def text1_handler(update: Update, context: CallbackContext) -> int:
    """Получение текста для первой страницы приглашения."""
    text1 = update.message.text.strip()
    # Валидация текста
    if not text1:
        update.message.reply_text("Текст не должен быть пустым. Пожалуйста, введите текст для первой страницы приглашения.")
        return TEXT1
    if len(text1) > 1000:
        update.message.reply_text("Текст слишком длинный (более 1000 символов). Пожалуйста, сократите и попробуйте снова.")
        return TEXT1
    # Сохранение текста страницы 1
    context.user_data["text1"] = text1
    # Запрос дополнительного текста (страница 2)
    update.message.reply_text(
        "Теперь введите дополнительный текст приглашения (страница 2).\n"
        "Например, подробности о мероприятии, адрес или другую дополнительную информацию."
    )
    return TEXT2

def text2_handler(update: Update, context: CallbackContext) -> int:
    """Получение текста для второй страницы приглашения."""
    text2 = update.message.text.strip()
    # Валидация текста
    if not text2:
        update.message.reply_text("Текст не должен быть пустым. Пожалуйста, введите текст для второй страницы приглашения.")
        return TEXT2
    if len(text2) > 1000:
        update.message.reply_text("Текст слишком длинный (более 1000 символов). Пожалуйста, сократите его и попробуйте снова.")
        return TEXT2
    # Сохранение текста страницы 2
    context.user_data["text2"] = text2
    # Запрос фонового изображения
    update.message.reply_text(
        "Теперь отправьте фоновое изображение для приглашения.\n"
        "Это может быть фотография или картинка, которая будет на заднем плане приглашения."
    )
    return PHOTO

def photo_handler(update: Update, context: CallbackContext) -> int:
    """Обработка загруженного пользователем фото (фонового изображения)."""
    photo_file = None
    if update.message.photo:
        # Если фото отправлено как изображение, берем самый большой размер
        photo_file = update.message.photo[-1].get_file()
    elif update.message.document and update.message.document.mime_type and update.message.document.mime_type.startswith("image"):
        # Если изображение отправлено как документ
        photo_file = update.message.document.get_file()
    else:
        update.message.reply_text("Пожалуйста, отправьте изображение (фото) для фона приглашения.")
        return PHOTO
    # Получаем расширение файла, если доступно
    file_path = photo_file.file_path  # URL файла на серверах Telegram
    ext = os.path.splitext(file_path)[1] if file_path else ".jpg"
    if ext == "":
        ext = ".jpg"
    # Формируем уникальное имя для временного файла
    chat_id = update.message.chat_id
    timestamp = int(update.message.date.timestamp())
    tmp_filename = f"bg_{chat_id}_{timestamp}{ext}"
    tmp_path = os.path.join(STATIC_TMP_DIR, tmp_filename)
    # Скачиваем файл во временную папку
    photo_file.download(tmp_path)
    # Если ранее уже было сохранено временное изображение (например, пользователь решил сменить фото)
    old_temp = context.user_data.get("photo_temp_path")
    if old_temp and old_temp != tmp_path and os.path.exists(old_temp):
        try:
            os.remove(old_temp)
        except OSError:
            pass
    # Сохраняем путь к новому временному файлу в данных пользователя
    context.user_data["photo_temp_path"] = tmp_path
    # Показываем пользователю превью фото и запрашиваем подтверждение
    context.bot.send_photo(chat_id=update.message.chat_id, photo=open(tmp_path, "rb"),
                            caption="Предпросмотр фонового изображения. Использовать это изображение?",
                            reply_markup=InlineKeyboardMarkup([
                                [InlineKeyboardButton("Да", callback_data="photo_yes"), InlineKeyboardButton("Нет", callback_data="photo_no")]
                            ]))
    # Переходим к состоянию подтверждения фото
    return PHOTO_CONFIRM

def photo_confirm_handler(update: Update, context: CallbackContext) -> int:
    """Обработка ответа пользователя на использование загруженного фонового фото."""
    query = update.callback_query
    if not query:
        # Не должно происходить, но на всякий случай остаемся в состоянии ожидания
        return PHOTO_CONFIRM
    query.answer()
    choice = query.data
    if choice == "photo_yes":
        # Пользователь подтвердил использование фото — формируем сводку данных приглашения
        name = context.user_data.get("name", "")
        datetime = context.user_data.get("datetime", "")
        text1 = context.user_data.get("text1", "")
        text2 = context.user_data.get("text2", "")
        summary = (f"*Проверьте данные приглашения:*\n"
                   f"*Название:* {name}\n"
                   f"*Дата и время:* {datetime}\n"
                   f"*Текст страницы 1:* {text1}\n"
                   f"*Текст страницы 2:* {text2}\n"
                   f"*Фоновое изображение:* приложено\n\n"
                   f"Всё верно?")
        # Отправляем сообщение-резюме с Inline-кнопками "Создать" и "Изменить"
        context.bot.send_message(chat_id=query.message.chat_id, text=summary, parse_mode="Markdown",
                                 reply_markup=InlineKeyboardMarkup([
                                     [InlineKeyboardButton("Создать", callback_data="create_invite"),
                                      InlineKeyboardButton("Изменить", callback_data="edit_invite")]
                                 ]))
        return CONFIRM
    elif choice == "photo_no":
        # Пользователь отказался от этого фото — удаляем временный файл и предлагаем отправить другой
        temp_path = context.user_data.get("photo_temp_path")
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        context.user_data["photo_temp_path"] = None
        context.bot.send_message(chat_id=query.message.chat_id, text="Хорошо, отправьте другое изображение для фона.")
        return PHOTO
    # В остальных случаях остаемся в этом же состоянии
    return PHOTO_CONFIRM

def confirm_handler(update: Update, context: CallbackContext) -> int:
    """Обработка выбора на этапе финального подтверждения: создание или редактирование."""
    query = update.callback_query
    if not query:
        return CONFIRM
    query.answer()
    choice = query.data
    if choice == "create_invite":
        # Пользователь подтвердил создание приглашения
        name = context.user_data.get("name", "")
        datetime = context.user_data.get("datetime", "")
        text1 = context.user_data.get("text1", "")
        text2 = context.user_data.get("text2", "")
        photo_temp_path = context.user_data.get("photo_temp_path")
        # Сохранение приглашения в базу данных
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""CREATE TABLE IF NOT EXISTS invitations (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT,
                        datetime TEXT,
                        text1 TEXT,
                        text2 TEXT,
                        image_path TEXT
                      )""")
        conn.commit()
        cur.execute("INSERT INTO invitations (name, datetime, text1, text2, image_path) VALUES (?, ?, ?, ?, ?)",
                    (name, datetime, text1, text2, ""))
        invite_id = cur.lastrowid
        # Обработка сохранения изображения на постоянное хранение
        image_rel_path = ""
        if photo_temp_path:
            ext = os.path.splitext(photo_temp_path)[1]  # расширение временного файла
            final_image_name = f"invite_{invite_id}{ext}"
            final_image_path = os.path.join(STATIC_INVITES_DIR, final_image_name)
            try:
                os.replace(photo_temp_path, final_image_path)
            except OSError:
                # Если не удалось переместить, копируем и удаляем исходник
                import shutil
                shutil.copy(photo_temp_path, final_image_path)
                os.remove(photo_temp_path)
            image_rel_path = os.path.join("invites", final_image_name)
            cur.execute("UPDATE invitations SET image_path = ? WHERE id = ?", (image_rel_path, invite_id))
        conn.commit()
        conn.close()
        # Формируем ссылку на приглашение
        invite_link = f"{BASE_URL}/invite/{invite_id}"
        # Генерируем QR-код для ссылки
        qr = qrcode.QRCode(box_size=10, border=2)
        qr.add_data(invite_link)
        qr.make(fit=True)
        qr_img = qr.make_image(fill_color="black", back_color="white")
        qr_bytes = BytesIO()
        qr_img.save(qr_bytes, format="PNG")
        qr_bytes.seek(0)
        # Отправляем ссылку и QR-код пользователю
        context.bot.send_message(chat_id=query.message.chat_id,
                                 text=f"✅ Приглашение создано!\nВот ссылка: {invite_link}\nМожете поделиться ею или QR-кодом ниже.")
        context.bot.send_photo(chat_id=query.message.chat_id, photo=qr_bytes, filename="qrcode.png", caption="QR-код для приглашения")
        # Завершаем разговор и очищаем данные
        context.user_data.clear()
        return ConversationHandler.END
    elif choice == "edit_invite":
        # Пользователь выбрал редактирование данных — предлагаем выбор поля для изменения
        keyboard = [
            [InlineKeyboardButton("Имя", callback_data="edit_field_name"),
             InlineKeyboardButton("Дата/время", callback_data="edit_field_datetime")],
            [InlineKeyboardButton("Текст 1", callback_data="edit_field_text1"),
             InlineKeyboardButton("Текст 2", callback_data="edit_field_text2")],
            [InlineKeyboardButton("Фон. изображение", callback_data="edit_field_photo")]
        ]
        context.bot.send_message(chat_id=query.message.chat_id, text="Что нужно исправить?",
                                 reply_markup=InlineKeyboardMarkup(keyboard))
        return CHOOSE_FIELD
    return CONFIRM

def choose_field_handler(update: Update, context: CallbackContext) -> int:
    """Обработка выбора поля, которое пользователь хочет отредактировать."""
    query = update.callback_query
    if not query:
        return CHOOSE_FIELD
    query.answer()
    data = query.data
    chat_id = query.message.chat_id
    # В зависимости от выбранного поля, запрашиваем новый ввод
    if data == "edit_field_name":
        context.bot.send_message(chat_id=chat_id, text="Отправьте новое название события:")
        context.user_data["editing_field"] = "name"
        return EDIT_TEXT
    elif data == "edit_field_datetime":
        context.bot.send_message(chat_id=chat_id, text="Отправьте новую дату и время мероприятия:")
        context.user_data["editing_field"] = "datetime"
        return EDIT_TEXT
    elif data == "edit_field_text1":
        context.bot.send_message(chat_id=chat_id, text="Отправьте новый текст для страницы 1:")
        context.user_data["editing_field"] = "text1"
        return EDIT_TEXT
    elif data == "edit_field_text2":
        context.bot.send_message(chat_id=chat_id, text="Отправьте новый текст для страницы 2:")
        context.user_data["editing_field"] = "text2"
        return EDIT_TEXT
    elif data == "edit_field_photo":
        context.bot.send_message(chat_id=chat_id, text="Отправьте новое фоновое изображение:")
        context.user_data["editing_field"] = "photo"
        return EDIT_PHOTO
    # Если пришло что-то неожиданное, остаемся в том же состоянии
    return CHOOSE_FIELD

def edit_text_handler(update: Update, context: CallbackContext) -> int:
    """Получение нового значения для текстового поля при редактировании."""
    field = context.user_data.get("editing_field")
    new_value = update.message.text.strip()
    # Проверка на пустоту
    if not new_value:
        update.message.reply_text("Пустое значение недопустимо. Пожалуйста, введите данные.")
        return EDIT_TEXT
    # Проверка на длину в зависимости от поля
    if field in ("name", "datetime") and len(new_value) > 100:
        update.message.reply_text("Слишком длинный текст, пожалуйста, сократите.")
        return EDIT_TEXT
    if field in ("text1", "text2") and len(new_value) > 1000:
        update.message.reply_text("Слишком длинный текст, пожалуйста, сократите.")
        return EDIT_TEXT
    # Сохранение нового значения
    context.user_data[field] = new_value
    # Очистка флага редактируемого поля
    context.user_data.pop("editing_field", None)
    # Вывод обновленной сводки данных
    name = context.user_data.get("name", "")
    datetime = context.user_data.get("datetime", "")
    text1 = context.user_data.get("text1", "")
    text2 = context.user_data.get("text2", "")
    summary = (f"*Обновленные данные приглашения:*\n"
               f"*Название:* {name}\n"
               f"*Дата и время:* {datetime}\n"
               f"*Текст страницы 1:* {text1}\n"
               f"*Текст страницы 2:* {text2}\n"
               f"*Фоновое изображение:* приложено\n\n"
               f"Всё верно?")
    update.message.reply_text(summary, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup([
        [InlineKeyboardButton("Создать", callback_data="create_invite"),
         InlineKeyboardButton("Изменить", callback_data="edit_invite")]
    ]))
    return CONFIRM

def edit_photo_handler(update: Update, context: CallbackContext) -> int:
    """Обработка нового изображения при редактировании фото."""
    # Здесь переиспользуем логику стандартного обработчика фото
    return photo_handler(update, context)

def main():
    """Запуск бота."""
    updater = Updater(TELEGRAM_BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    # Определение ConversationHandler для диалога создания приглашения
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(Filters.text & ~Filters.command, name_handler)],
            DATETIME: [MessageHandler(Filters.text & ~Filters.command, date_handler)],
            TEXT1: [MessageHandler(Filters.text & ~Filters.command, text1_handler)],
            TEXT2: [MessageHandler(Filters.text & ~Filters.command, text2_handler)],
            PHOTO: [MessageHandler((Filters.photo | Filters.document.category("image")) & ~Filters.command, photo_handler)],
            PHOTO_CONFIRM: [
                CallbackQueryHandler(photo_confirm_handler, pattern="^photo_yes$|^photo_no$"),
                MessageHandler((Filters.photo | Filters.document.category("image")) & ~Filters.command, photo_handler)
            ],
            CONFIRM: [
                CallbackQueryHandler(confirm_handler, pattern="^create_invite$|^edit_invite$"),
                MessageHandler(Filters.text & ~Filters.command,
                               lambda update, ctx: update.message.reply_text("Пожалуйста, воспользуйтесь кнопками ниже для подтверждения или изменения."))
            ],
            CHOOSE_FIELD: [CallbackQueryHandler(choose_field_handler, pattern="^edit_field_")],
            EDIT_TEXT: [MessageHandler(Filters.text & ~Filters.command, edit_text_handler)],
            EDIT_PHOTO: [
                MessageHandler((Filters.photo | Filters.document.category("image")) & ~Filters.command, edit_photo_handler),
                CallbackQueryHandler(photo_confirm_handler, pattern="^photo_yes$|^photo_no$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )
    dp.add_handler(conv_handler)
    # Дополнительно добавляем отдельный обработчик /cancel вне разговора (на всякий случай)
    dp.add_handler(CommandHandler("cancel", cancel))
    # Запуск бота
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
