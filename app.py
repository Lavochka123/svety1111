# app.py
from flask import Flask, render_template, request, jsonify
import telegram
import asyncio
import threading
import sqlite3

TELEGRAM_BOT_TOKEN = "8046219766:AAGFsWXIFTEPe8aaTBimVyWm2au2f-uIYSs"
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

app = Flask(__name__, template_folder='template')
DB_PATH = "app.db"

def init_db():
    """Создаёт таблицу invitations, если её нет."""
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
            "times": row[3].split("\n"),
            "chat_id": row[4]
        }
    return None

@app.route('/invite/<invite_id>', methods=['GET'])
def invite_page(invite_id):
    """
    Основная страница приглашения.
    """
    data = get_invitation(invite_id)
    if not data:
        return "Приглашение не найдено или было удалено.", 404
    return render_template('invite.html', data=data)

@app.route('/choose_time', methods=['GET', 'POST'])
def choose_time():
    """
    Страница выбора времени.
    GET: рендерим список вариантов.
    POST: пользователь выбирает время -> отправляем в Telegram.
    """
    if request.method == 'GET':
        invite_id = request.args.get('id')
        if not invite_id:
            return "Параметр id не указан", 400
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
            invite_id=data["id"]
        )
    else:
        # POST: пользователь выбрал время
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
    AJAX-эндпоинт (пример) для ответа "Извини, не могу".
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
    # Запуск Flask
    app.run(host="0.0.0.0", port=5000, debug=True)
