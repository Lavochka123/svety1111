from flask import Flask, render_template, request, redirect, url_for, jsonify
import telegram, asyncio, threading, sqlite3, json
TELEGRAM_BOT_TOKEN = "8046219766:AAGFsWXIFTEPe8aaTBimVyWm2au2f-uIYSs"  # замените на ваш токен
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)
app = Flask(__name__, template_folder='template')
DB_PATH = "app.db"

def init_db():
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
init_db()

# Setup async loop for notifications
loop = asyncio.new_event_loop()
def run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()
threading.Thread(target=run_loop, args=(loop,), daemon=True).start()

def send_message_sync(chat_id, message):
    future = asyncio.run_coroutine_threadsafe(
        bot.send_message(chat_id=chat_id, text=message), loop)
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

# Перенаправление: если design начинается с "g_design", считаем это поздравлением
@app.route('/invite/<invite_id>')
def invitation_redirect(invite_id):
    data = get_invitation(invite_id)
    if data and data.get("chat_id"):
        try:
            send_message_sync(data["chat_id"], f"Ваше приглашение {invite_id} было посещено!")
        except Exception as e:
            print("Ошибка при отправке уведомления:", e)
    if data and data["design"].startswith("g_design"):
         return redirect(url_for('greeting', invite_id=invite_id))
    else:
         return redirect(url_for('page1', invite_id=invite_id))

@app.route('/invite/<invite_id>/page1')
def page1(invite_id):
    data = get_invitation(invite_id)
    if not data:
         return "Приглашение не найдено.", 404
    try:
         send_message_sync(data["chat_id"], f"Ваше приглашение {invite_id} было посещено!")
    except Exception as e:
         print("Ошибка:", e)
    return render_template('page1.html', data=data)

@app.route('/invite/<invite_id>/page2')
def page2(invite_id):
    data = get_invitation(invite_id)
    if not data:
         return "Приглашение не найдено.", 404
    return render_template('page2.html', data=data)

@app.route('/invite/<invite_id>/page3')
def page3(invite_id):
    data = get_invitation(invite_id)
    if not data:
         return "Приглашение не найдено.", 404
    return render_template('page3.html', data=data)

@app.route('/invite/<invite_id>/page4', methods=['GET','POST'])
def page4(invite_id):
    data = get_invitation(invite_id)
    if not data:
         return "Приглашение не найдено.", 404
    if request.method == 'GET':
         return render_template('page4.html', data=data)
    selected_time = request.form.get('selected_time')
    if not selected_time:
         return "Вы не выбрали время!", 400
    try:
         send_message_sync(data["chat_id"], f"Девушка выбрала время: {selected_time}")
    except Exception as e:
         print("Ошибка:", e)
    return redirect(url_for('page5', invite_id=invite_id, selected_time=selected_time))

@app.route('/invite/<invite_id>/page5', methods=['GET'])
def page5(invite_id):
    data = get_invitation(invite_id)
    if not data:
         return "Приглашение не найдено.", 404
    selected_time = request.args.get('selected_time', '')
    return render_template('page5.html', data=data, selected_time=selected_time)

# Отдельный маршрут для поздравления с 8 марта
@app.route('/invite/<invite_id>/greeting', methods=['GET'])
def greeting(invite_id):
    data = get_invitation(invite_id)
    if not data:
         return "Поздравление не найдено.", 404
    try:
         send_message_sync(data["chat_id"], f"Ваше поздравление {invite_id} было посещено!")
    except Exception as e:
         print("Ошибка:", e)
    return render_template('greeting.html', data=data)

@app.route('/response', methods=['POST'])
def response():
    req_data = request.get_json()
    chat_id = req_data.get('chat_id')
    response_text = req_data.get('response', 'Извини, не могу')
    try:
         send_message_sync(int(chat_id), f"Девушка ответила: {response_text}")
    except Exception as e:
         print("Ошибка:", e)
         return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "ok"}), 200

@app.route('/comment', methods=['POST'])
def comment():
    invite_id = request.form.get('invite_id')
    comment_text = request.form.get('comment', '').strip()
    data = get_invitation(invite_id)
    if not data:
         return "Приглашение не найдено.", 404
    try:
         send_message_sync(int(data["chat_id"]), f"Девушка оставила комментарий: {comment_text}")
    except Exception as e:
         print("Ошибка:", e)
         return "Ошибка при отправке комментария.", 500
    return render_template('thanks_comment.html', data=data)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
