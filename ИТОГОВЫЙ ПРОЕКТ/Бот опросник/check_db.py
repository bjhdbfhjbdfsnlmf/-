from db_adapter import get_session
from sqlalchemy import select
from db_adapter import Question, Choice

session = get_session()

# Проверяем количество вопросов
questions = session.scalars(select(Question)).all()
print(f"Количество вопросов в базе: {len(questions)}")
for q in questions:
    print(f"\nВопрос {q.id}: {q.question_text}")
    choices = session.scalars(select(Choice).where(Choice.question_id == q.id)).all()
    print(f"Варианты ответов:")
    for c in choices:
        print(f"- {c.choice_text}")

session.close()
