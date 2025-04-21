from flask import Flask, render_template
import sqlite3

DB_FILE = "invitations.db"
app = Flask(__name__)

@app.route("/invite/<int:invite_id>")
def invite_page(invite_id):
    # Подключаемся к базе данных
    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    # Убеждаемся, что таблица существует (если нет приглашений, создадим таблицу)
    cur.execute("""CREATE TABLE IF NOT EXISTS invitations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    datetime TEXT,
                    text1 TEXT,
                    text2 TEXT,
                    image_path TEXT
                  )""")
    conn.commit()
    # Получаем данные приглашения по ID
    cur.execute("SELECT name, datetime, text1, text2, image_path FROM invitations WHERE id = ?", (invite_id,))
    row = cur.fetchone()
    conn.close()
    if row is None:
        # Если приглашение не найдено, возвращаем 404
        return "Приглашение не найдено", 404
    name, datetime, text1, text2, image_path = row
    # Рендерим HTML-шаблон приглашения с подставленными данными
    return render_template("invite.html", name=name, datetime=datetime, text1=text1, text2=text2, image_path=image_path)

@app.route("/")
def index():
    # Простая домашняя страница (для проверки работы сервера)
    return "Telegram Invite Bot is running."

if __name__ == "__main__":
    # Запуск Flask-приложения для локального тестирования
    app.run(host="0.0.0.0", port=5000)
