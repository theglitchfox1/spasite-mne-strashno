import telebot
import sqlite3
import threading
import time
from datetime import datetime

bot = telebot.TeleBot("7307622759:AAEMHB6SqT79lHs9GgNcJXivC96yOWf8TKs")  

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('todo_bot.db')
    cursor = conn.cursor()
    
    # Таблица задач
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        task TEXT,
        category TEXT DEFAULT 'Без категории',
        is_completed BOOLEAN DEFAULT FALSE
    )
    ''')
    
    # Таблица напоминаний
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS reminders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id INTEGER,
        reminder_time TEXT,
        FOREIGN KEY (task_id) REFERENCES tasks(id)
    )
    ''')
    
    conn.commit()
    conn.close()

# Запуск инициализации БД
init_db()

# Функция для проверки напоминаний в фоне
def check_reminders():
    while True:
        conn = sqlite3.connect('todo_bot.db')
        cursor = conn.cursor()
        now = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        # Ищем напоминания, которые должны сработать
        cursor.execute('''
        SELECT reminders.task_id, tasks.user_id, tasks.task 
        FROM reminders 
        JOIN tasks ON reminders.task_id = tasks.id 
        WHERE reminders.reminder_time <= ?
        ''', (now,))
        
        reminders = cursor.fetchall()
        
        for reminder in reminders:
            task_id, user_id, task_text = reminder
            bot.send_message(
                user_id,
                f" Напоминание: {task_text}"
            )
            # Удаление напоминания
            cursor.execute("DELETE FROM reminders WHERE task_id = ?", (task_id,))
        
        conn.commit()
        conn.close()
        time.sleep(60)  # Проверка каждую минуту

# Запуск потока для напоминаний
reminder_thread = threading.Thread(target=check_reminders)
reminder_thread.daemon = True
reminder_thread.start()

# Команда /start
@bot.message_handler(commands=['start'])
def start(message):
    bot.send_message(
        message.chat.id,
        " *To-Do Bot*\n\n"
        "Доступные команды:\n"
        "/add [категория] [задача] - добавить задачу\n"
        "/list - показать все задачи\n"
        "/done [номер] - отметить как выполненную\n"
        "/delete [номер] - удалить задачу\n"
        "/remind [номер] [гггг-мм-дд чч:мм] - установить напоминание\n\n"
        "Пример:\n"
        "/add Работа Сделать отчёт\n"
        "/remind 1 2025-12-31 23:59",
        parse_mode="Markdown"
    )

# Команда /add
@bot.message_handler(commands=['add'])
def add_task(message):
    try:
        _, category, *task_parts = message.text.split(maxsplit=2)
        task_text = ' '.join(task_parts)
    except ValueError:
        bot.reply_to(message, " Формат: /add [категория] [задача]")
        return

    conn = sqlite3.connect('todo_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO tasks (user_id, task, category) VALUES (?, ?, ?)",
        (message.chat.id, task_text, category)
    )
    conn.commit()
    conn.close()
    bot.reply_to(message, f" Добавлено в '{category}': {task_text}")

# Команда /list
@bot.message_handler(commands=['list'])
def list_tasks(message):
    conn = sqlite3.connect('todo_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, task, category, is_completed FROM tasks WHERE user_id = ?",
        (message.chat.id,)
    )
    tasks = cursor.fetchall()
    conn.close()

    if not tasks:
        bot.send_message(message.chat.id, "🗑 Список задач пуст!")
        return

    tasks_by_category = {}
    for task in tasks:
        task_id, task_text, category, is_completed = task
        if category not in tasks_by_category:
            tasks_by_category[category] = []
        status = "✅" if is_completed else "❌"
        tasks_by_category[category].append(f"{task_id}. {task_text} {status}")

    response = [" *Ваши задачи:*"]
    for category, tasks_list in tasks_by_category.items():
        response.append(f"\n*{category}*")
        response.extend(tasks_list)
    
    bot.send_message(message.chat.id, "\n".join(response), parse_mode="Markdown")

# Команда /done
@bot.message_handler(commands=['done'])
def mark_done(message):
    try:
        task_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, " Укажите номер задачи: /done [номер]")
        return
    
    conn = sqlite3.connect('todo_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE tasks SET is_completed = TRUE WHERE id = ? AND user_id = ?",
        (task_id, message.chat.id)
    )
    conn.commit()
    conn.close()
    bot.reply_to(message, f" Задача {task_id} выполнена!")

# Команда /delete
@bot.message_handler(commands=['delete'])
def delete_task(message):
    try:
        task_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, " Укажите номер задачи: /delete [номер]")
        return
    
    conn = sqlite3.connect('todo_bot.db')
    cursor = conn.cursor()
    cursor.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, message.chat.id)
    )
    conn.commit()
    conn.close()
    bot.reply_to(message, f"🗑 Задача {task_id} удалена!")

# Команда /remind
@bot.message_handler(commands=['remind'])
def set_reminder(message):
    try:
        _, task_id, reminder_time = message.text.split(maxsplit=2)
        task_id = int(task_id)
    except ValueError:
        bot.reply_to(message, " Формат: /remind [номер] [гггг-мм-дд чч:мм]")
        return

    conn = sqlite3.connect('todo_bot.db')
    cursor = conn.cursor()
    
    # Проверяем, существует ли задача
    cursor.execute(
        "SELECT id FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, message.chat.id)
    )
    if not cursor.fetchone():
        bot.reply_to(message, "Задачи с таким номером не существует!")
        conn.close()
        return
    
    cursor.execute(
        "INSERT INTO reminders (task_id, reminder_time) VALUES (?, ?)",
        (task_id, reminder_time)
    )
    conn.commit()
    conn.close()
    bot.reply_to(message, f" Напоминание установлено на {reminder_time}")

# Запуск бота
if __name__ == "__main__":
    print("Бот запущен!")
    bot.polling()