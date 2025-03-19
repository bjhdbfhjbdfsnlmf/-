import os
from db_adapter import create_tables_in_db
from initial_questions import initialize_database

# Удаляем старую базу данных
if os.path.exists('survey.db'):
    os.remove('survey.db')
    print("Старая база данных удалена")

# Создаем новую базу данных
create_tables_in_db()
print("Создана новая база данных")

# Инициализируем базу данных вопросами
initialize_database()
print("База данных заполнена вопросами")
