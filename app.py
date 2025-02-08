# app.py
from flask import Flask, render_template, request, jsonify
import telegram
import asyncio
import threading

app = Flask(__name__, template_folder='template')

# Токен Telegram‑бота (тот же, что используется в bot.py)
TELEGRAM_BOT_TOKEN = "8046219766:AAGFsWXIFTEPe8aaTBimVyWm2au2f-uIYSs"
bot = telegram.Bot(token=TELEGRAM_BOT_TOKEN)

list = {
    34: {
        'design': 'gay',
        'intro': 'gay',
        'proposal': 'gay',
        'times': 'gay',
        'chat_id': 'gay'
    }
}

# Создаем глобальный event loop и запускаем его в отдельном потоке
loop = asyncio.new_event_loop()

def run_loop(loop):
    asyncio.set_event_loop(loop)
    loop.run_forever()

threading.Thread(target=run_loop, args=(loop,), daemon=True).start()

def send_message_sync(chat_id, message):
    """
    Отправляет сообщение с использованием глобального event loop.
    Блокирует выполнение до завершения задачи (с таймаутом 10 секунд).
    """
    future = asyncio.run_coroutine_threadsafe(
        
        bot.send_message(chat_id=chat_id, text=message), loop
    )
    return future.result(timeout=10)

@app.route('/invite/<invite_id>', methods=['GET'])
def invite(invite_id):

    design = request.args.get('design', 'design_elegant')
    intro = request.args.get('intro', 'Привет! Я подготовил для тебя нечто особенное...')
    proposal = request.args.get('proposal', 'Давай проведём этот вечер вместе. Я знаю уютное место!')
    chat_id = request.args.get('chat_id', invite_id)
    times = request.args.getlist('times') or ['🕗 19:00 | 21 января', '🌙 20:30 | 22 января', '☕ 17:00 | 23 января']
    invite_data = {
        'design': design,
        'intro': intro,
        'proposal': proposal,
        'times': times,
        'chat_id': chat_id
    }
    return render_template('invite.html', data=invite_data)

@app.route('/choose_time', methods=['GET', 'POST'])
def choose_time():
    if request.method == 'GET':
        design = request.args.get('design', 'design_elegant')
        intro = request.args.get('intro', 'Привет! Я подготовил для тебя нечто особенное...')
        proposal = request.args.get('proposal', 'Давай проведём этот вечер вместе. Я знаю уютное место!')
        chat_id = request.args.get('chat_id', None)
        times = ['🕗 19:00 | 21 января', '🌙 20:30 | 22 января', '☕ 17:00 | 23 января']
        return render_template('choose_time.html', design=design, intro=intro, proposal=proposal, times=times, chat_id=chat_id)
    else:
        selected_time = request.form.get('selected_time')
        design = request.form.get('design')
        intro = request.form.get('intro')
        proposal = request.form.get('proposal')
        chat_id = request.form.get('chat_id')
        if chat_id:
            try:
                chat_id = int(chat_id)
            except Exception as e:
                print("Ошибка преобразования chat_id:", e)
            message = f"Отличные новости!\nДевушка выбрала время для встречи:\n{selected_time}"
            try:
                send_message_sync(chat_id, message)
            except Exception as e:
                print("Ошибка при отправке сообщения в Telegram:", e)
        return render_template('confirmation.html', design=design, intro=intro, proposal=proposal,
                               selected_time=selected_time)

@app.route('/response', methods=['POST'])
def response():
    data = request.get_json()
    chat_id = data.get('chat_id')
    response_text = data.get('response')
    selected_time = data.get('selected_time', '')
    message = f"Девушка ответила: {response_text}"
    if selected_time:
        message += f"\nВыбранное время: {selected_time}"
    if chat_id:
        try:
            chat_id = int(chat_id)
        except Exception as e:
            print("Ошибка преобразования chat_id:", e)
    try:
        send_message_sync(chat_id, message)
    except Exception as e:
        print("Ошибка при отправке ответа в Telegram:", e)
        return jsonify({"status": "error", "message": str(e)}), 500
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000, debug=True)

