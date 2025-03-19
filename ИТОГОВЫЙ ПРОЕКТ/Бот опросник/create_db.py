import sqlite3
from datetime import datetime

# Создаем соединение с базой данных (если файла нет, он будет создан)
conn = sqlite3.connect('survey.db')
cursor = conn.cursor()

# Создаем таблицу вопросов (question)
cursor.execute('''
CREATE TABLE IF NOT EXISTS question (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text VARCHAR(255) NOT NULL,
    publish_date TIMESTAMP NOT NULL
)
''')

# Создаем таблицу вариантов ответа (choice)
cursor.execute('''
CREATE TABLE IF NOT EXISTS choice (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    choice_text VARCHAR(255) NOT NULL,
    votes INTEGER DEFAULT 0,
    question_id INTEGER,
    FOREIGN KEY (question_id) REFERENCES question(id)
)
''')

# Создаем таблицу статистики пользователей (user_stat)
cursor.execute('''
CREATE TABLE IF NOT EXISTS user_stat (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_user_id INTEGER NOT NULL,
    question_id INTEGER,
    choice_id INTEGER,
    FOREIGN KEY (question_id) REFERENCES question(id),
    FOREIGN KEY (choice_id) REFERENCES choice(id)
)
''')

# Добавляем тестовые данные
# Добавляем первый вопрос
cursor.execute('''
INSERT INTO question (question_text, publish_date) VALUES (?, ?)
''', ('Во всех ли городах России есть вечный огонь?', datetime.now()))
question1_id = cursor.lastrowid

# Добавляем варианты ответов для первого вопроса
cursor.execute('INSERT INTO choice (choice_text, votes, question_id) VALUES (?, ?, ?)', ('Да', 15, question1_id))
cursor.execute('INSERT INTO choice (choice_text, votes, question_id) VALUES (?, ?, ?)', ('Нет', 2, question1_id))
cursor.execute('INSERT INTO choice (choice_text, votes, question_id) VALUES (?, ?, ?)', ('Не знаю', 5, question1_id))

# Добавляем второй вопрос
cursor.execute('''
INSERT INTO question (question_text, publish_date) VALUES (?, ?)
''', ('Вам нравится ваша школа?', datetime.now()))
question2_id = cursor.lastrowid

# Добавляем варианты ответов для второго вопроса
cursor.execute('INSERT INTO choice (choice_text, votes, question_id) VALUES (?, ?, ?)', ('Да, очень', 7, question2_id))
cursor.execute('INSERT INTO choice (choice_text, votes, question_id) VALUES (?, ?, ?)', ('Нет', 8, question2_id))

# Сохраняем изменения и закрываем соединение
conn.commit()
conn.close()

print("База данных успешно создана и заполнена тестовыми данными!")
