from flask import Flask, render_template, request, redirect, url_for, session, flash
import sqlite3
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = 'super_secret_key_for_students' # Нужен для работы сессий (входа)

# --- Функции для работы с базой данных ---
def get_db_connection():
    conn = sqlite3.connect('database.db')
    conn.row_factory = sqlite3.Row # Позволяет обращаться к столбцам по имени
    return conn

def init_db():
    """Создает таблицы при первом запуске"""
    conn = get_db_connection()
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        username TEXT UNIQUE NOT NULL,
                        password TEXT NOT NULL)''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS subjects (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        user_id INTEGER NOT NULL,
                        name TEXT NOT NULL,
                        FOREIGN KEY (user_id) REFERENCES users (id))''')
    
    conn.execute('''CREATE TABLE IF NOT EXISTS tasks (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        subject_id INTEGER NOT NULL,
                        title TEXT NOT NULL,
                        deadline DATETIME NOT NULL,
                        is_done BOOLEAN NOT NULL DEFAULT 0,
                        FOREIGN KEY (subject_id) REFERENCES subjects (id))''')
    conn.commit()
    conn.close()

# --- Маршруты (Routes) ---

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    conn = get_db_connection()
    # Получаем задачи текущего пользователя, сортируя по дедлайну
    tasks = conn.execute('''
        SELECT tasks.id, tasks.title, tasks.deadline, tasks.is_done, subjects.name as subject_name 
        FROM tasks 
        JOIN subjects ON tasks.subject_id = subjects.id 
        WHERE subjects.user_id = ? 
        ORDER BY tasks.deadline ASC
    ''', (session['user_id'],)).fetchall()
    conn.close()

    # Преобразуем строку даты в объект datetime для сравнения в шаблоне
    tasks_list = []
    now = datetime.now()
    for task in tasks:
        task_dict = dict(task)
        # Формат даты из HTML input type="datetime-local" - "YYYY-MM-DDTHH:MM"
        task_dict['deadline_dt'] = datetime.strptime(task['deadline'], '%Y-%m-%dT%H:%M')
        task_dict['is_urgent'] = (task_dict['deadline_dt'] - now).days <= 3 and not task['is_done']
        tasks_list.append(task_dict)

    return render_template('index.html', tasks=tasks_list, now=now)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        
        # Если пользователя нет - регистрируем (упрощенная логика для проекта)
        if user is None:
            hashed_pw = generate_password_hash(password)
            conn.execute('INSERT INTO users (username, password) VALUES (?, ?)', (username, hashed_pw))
            conn.commit()
            user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
            flash('Регистрация успешна!', 'success')
        
        if check_password_hash(user['password'], password):
            session['user_id'] = user['id']
            session['username'] = user['username']
            conn.close()
            return redirect(url_for('index'))
        else:
            flash('Неверный пароль', 'danger')
        conn.close()
    
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/add', methods=['GET', 'POST'])
def add_task():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    conn = get_db_connection()
    
    if request.method == 'POST':
        subject_name = request.form['subject']
        title = request.form['title']
        deadline = request.form['deadline']
        
        # Проверяем, существует ли такой предмет у пользователя
        subject = conn.execute('SELECT id FROM subjects WHERE name = ? AND user_id = ?', 
                               (subject_name, session['user_id'])).fetchone()
        
        if subject is None:
            # Если нет - создаем новый
            cursor = conn.execute('INSERT INTO subjects (user_id, name) VALUES (?, ?)', 
                                  (session['user_id'], subject_name))
            subject_id = cursor.lastrowid
        else:
            subject_id = subject['id']
            
        conn.execute('INSERT INTO tasks (subject_id, title, deadline) VALUES (?, ?, ?)', 
                     (subject_id, title, deadline))
        conn.commit()
        conn.close()
        flash('Задача добавлена!', 'success')
        return redirect(url_for('index'))

    conn.close()
    return render_template('add.html')

@app.route('/toggle/<int:task_id>')
def toggle_task(task_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
        
    conn = get_db_connection()
    task = conn.execute('SELECT is_done FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if task:
        new_status = 0 if task['is_done'] else 1
        conn.execute('UPDATE tasks SET is_done = ? WHERE id = ?', (new_status, task_id))
        conn.commit()
    conn.close()
    return redirect(url_for('index'))

if __name__ == '__main__':
    init_db() # Инициализация БД при запуске
    app.run(debug=True)