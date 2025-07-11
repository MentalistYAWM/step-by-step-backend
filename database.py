import sqlite3
from werkzeug.security import generate_password_hash

# Ім'я файлу, де буде зберігатися база даних
DATABASE_NAME = 'my_training_data.db'

def create_database_tables():
    """
    Ця функція створює таблиці в базі даних,
    якщо їх ще немає.
    """
    # Підключаємося до бази даних (якщо файлу немає, він створиться)
    conn = sqlite3.connect(DATABASE_NAME)
    cursor = conn.cursor()

    # Створюємо таблицю для користувачів (де буде їх логін, пароль тощо)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')

    # Створюємо таблицю для прогресу користувачів (вага, завершені тренування)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            date TEXT NOT NULL,
            weight REAL,
            workouts_completed INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users (id)
        )
    ''')

    # ОНОВЛЕНА ТАБЛИЦЯ: workout_templates з додаванням is_global
    cursor.execute("PRAGMA table_info(workout_templates)")
    columns = [column[1] for column in cursor.fetchall()]

    if 'workout_templates' not in columns: # Якщо таблиці взагалі немає, створюємо її
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS workout_templates (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                description TEXT,
                exercises_json TEXT, -- Зберігатиме JSON-рядок зі списком вправ, підходів, повторень
                is_global BOOLEAN DEFAULT 0, -- НОВА КОЛОНКА: 0 (False) для особистих, 1 (True) для глобальних
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        ''')
    elif 'is_global' not in columns: # Якщо таблиця є, але колонки is_global немає, додаємо її
        cursor.execute('''
            ALTER TABLE workout_templates ADD COLUMN is_global BOOLEAN DEFAULT 0
        ''')
        print("Колонка 'is_global' додана до таблиці 'workout_templates'.")

    # НОВА ТАБЛИЦЯ: user_workouts для зберігання фактичних виконаних/запланованих тренувань
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_workouts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            template_id INTEGER NOT NULL, -- Посилання на шаблон тренування
            workout_date TEXT NOT NULL, -- Дата, коли це тренування було заплановано/виконано
            status TEXT DEFAULT 'upcoming', -- Може бути 'upcoming', 'in-progress', 'completed'
            -- Можна також скопіювати name, description, exercises_json з шаблону,
            -- щоб зберегти стан тренування на момент його створення,
            -- навіть якщо шаблон пізніше зміниться.
            name TEXT NOT NULL,
            description TEXT,
            exercises_json TEXT,
            FOREIGN KEY (user_id) REFERENCES users (id),
            FOREIGN KEY (template_id) REFERENCES workout_templates (id)
        )
    ''')

    # Зберігаємо зміни
    conn.commit()
    # Закриваємо з'єднання
    conn.close()
    print("База даних успішно створена або оновлена.")

# Ця частина коду запускається, коли ти запускаєш database.py
if __name__ == '__main__':
    create_database_tables()
