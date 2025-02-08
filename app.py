# app.py
from flask import Flask, render_template, request, jsonify
import telegram
import asyncio
import threading
import sqlite3

# Подставьте тот же токен, что и в bot.py
TELEGRAM_BOT_TOKEN = "8046219766:AAGFsWXIFTEPe8aaTBimVyWm2au2f-uIYSs"
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

# Инициируем Flask. Папку с шаблонами замените при необходимости
app = Flask(__name__, template_folder='templates')

DB_PATH = "app.db"

def init_db():
    """Создаёт таблицу invitations, если она ещё не существует."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS invitations (
            id TEXT PRIMARY KEY,
            design TEXT,
            intro TEXT,
            proposal TEXT,
            times TEXT,
            chat_id TEXT
        )
    ''')
    conn.commit()
    conn.close()

# Вместо @app.before_first_request просто вызываем init_db() сразу
init_db()

# Создаём глобальный event loop, чтобы вызывать send_message из Flask
loop = asyncio.new_event_loop()

def run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=run_loop, args=(loop,), daemon=True).start()

def send_message_sync(chat_id, message):
    """Отправляет сообщение в Телеграм, используя global event loop."""
    future = asyncio.run_coroutine_threadsafe(
        bot.send_message(chat_id=chat_id, text=message),
        loop
    )
    return future.result(timeout=10)

def get_invitation(invite_id):
    """Получает данные приглашения из БД по ID."""
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT design, intro, proposal, times, chat_id FROM invitations WHERE id = ?', (invite_id,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "id": invite_id,
            "design": row[0],
            "intro": row[1],
            "proposal": row[2],
            "times": row[3].split("\n"),  # times храним в одной строке, разделённой \n
            "chat_id": row[4]
        }
    return None

@app.route('/invite/<invite_id>', methods=['GET'])
def invite(invite_id):
    """
    Основная страница приглашения.
    Здесь выводится дизайн, тексты (intro, proposal) и кнопки "не могу" / "выберу время".
    """
    data = get_invitation(invite_id)
    if not data:
        return "Приглашение не найдено или было удалено.", 404
    return render_template('invite.html', data=data)

@app.route('/choose_time', methods=['GET', 'POST'])
def choose_time():
    """Страница выбора времени."""
    if request.method == 'GET':
        invite_id = request.args.get('id')
        data = get_invitation(invite_id)
        if not data:
            return "Приглашение не найдено", 404
        return render_template(
            'choose_time.html',
            design=data["design"],
            intro=data["intro"],
            proposal=data["proposal"],
            times=data["times"],
            chat_id=data["chat_id"],
            invite_id=invite_id
        )
    else:
        # Обрабатываем POST с выбранным временем
        selected_time = request.form.get('selected_time')
        invite_id = request.form.get('invite_id')
        data = get_invitation(invite_id)
        if not data:
            return "Приглашение не найдено (возможно, устарело).", 404

        chat_id = data["chat_id"]
        message = f"Девушка выбрала время для встречи: {selected_time}"
        try:
            send_message_sync(chat_id, message)
        except Exception as e:
            print("Ошибка при отправке сообщения в Telegram:", e)
        return render_template(
            'confirmation.html',
            design=data["design"],
            intro=data["intro"],
            proposal=data["proposal"],
            selected_time=selected_time
        )

@app.route('/response', methods=['POST'])
def response():
    """
    AJAX-эндпоинт для ответа "Извини, не могу".
    Когда пользователь в шаблоне нажимает кнопку "Извини, не могу",
    фронтэнд шлёт POST /response c {chat_id, response}.
    """
    data = request.get_json()
    chat_id = data.get('chat_id')
    response_text = data.get('response')
    selected_time = data.get('selected_time', '')

    message = f"Девушка ответила: {response_text}"
    if selected_time:
        message += f"\nВыбранное время: {selected_time}"

    try:
        if chat_id is not None:
            chat_id = int(chat_id)
        send_message_sync(chat_id, message)
    except Exception as e:
        print("Ошибка при отправке ответа в Telegram:", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    # Запуск Flask на 5000 порту. Меняйте при необходимости.
    app.run(host="0.0.0.0", port=5000, debug=True)
