from datetime import datetime
import sqlalchemy
from sqlalchemy import select, update, delete
from sqlalchemy.sql.expression import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from config import DATABASE_URL
from functools import wraps
import os
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Конфигурация базы данных из переменных окружения
DB_USERNAME = os.getenv('DB_USERNAME', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_NAME = os.getenv('DB_NAME', 'umschooldb')
DB_PORT = os.getenv('DB_PORT', '5432')

# Проверка наличия обязательных переменных
if not DB_PASSWORD:
    raise ValueError("DB_PASSWORD не найден в переменных окружения")

# URL для подключения к базе данных
DATABASE_URL = f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@localhost:{DB_PORT}/{DB_NAME}'

class Base(DeclarativeBase):
    pass


class Question(Base):
    __tablename__ = 'question'
    id: Mapped[int] = mapped_column(primary_key=True)
    question_text: Mapped[str] = mapped_column(sqlalchemy.String(255))
    publish_date: Mapped[datetime] = mapped_column(sqlalchemy.DateTime)

    def __repr__(self) -> str:
        return f'Question(id={self.id}, question_text={self.question_text}, publish_date={self.publish_date})'


class Choice(Base):
    __tablename__ = 'choice'
    id: Mapped[int] = mapped_column(primary_key=True)
    choice_text: Mapped[str] = mapped_column(sqlalchemy.String(255))
    votes: Mapped[int] = mapped_column(sqlalchemy.Integer, default=0)
    question_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey('question.id'))

    def __repr__(self) -> str:
        return f'Choice(id={self.id}, choice_text={self.choice_text}, votes={self.votes}, question_id={self.question_id})'


class UserStat(Base):
    __tablename__ = 'user_stat'
    id: Mapped[int] = mapped_column(primary_key=True)
    tg_user_id: Mapped[int] = mapped_column(sqlalchemy.Integer)
    question_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey('question.id'))
    choice_id: Mapped[int] = mapped_column(sqlalchemy.ForeignKey('choice.id'))

    def __repr__(self) -> str:
        return f'UserStat(id={self.id}, tg_user_id={self.tg_user_id}, question_id={self.question_id}, choice_id={self.choice_id})'


def decorator_add_session(func):
    """Декоратор для автоматического управления сессией базы данных"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        session = Session(get_engine())
        try:
            return func(*args, session=session, **kwargs)
        finally:
            session.close()
    return wrapper


def get_engine():
    """Создание движка базы данных"""
    return sqlalchemy.create_engine(DATABASE_URL)


def get_session() -> Session:
    """Получение сессии базы данных"""
    return Session(get_engine())


def create_tables_in_db():
    """
    создать таблицы в бд
    """
    engine = get_engine()
    Base.metadata.create_all(engine)


@decorator_add_session
def add_question_to_db(
    question_text: str, publish_date: datetime, session: Session
) -> int:
    """Добавление вопроса в базу данных"""
    with session.begin():
        question = Question(question_text=question_text, publish_date=publish_date)
        session.add(question)
        session.commit()
    return question.id


@decorator_add_session
def add_choice_to_db(choice_text: str, question_id: int, session: Session):
    """Добавление варианта ответа в базу данных"""
    with session.begin():
        choice = Choice(choice_text=choice_text, question_id=question_id)
        session.add(choice)
        session.commit()


@decorator_add_session
def delete_question_by_id_db(question_id: int, session: Session):
    """Удаление вопроса и связанных данных из базы данных"""
    with session.begin():
        stmt = delete(UserStat).where(UserStat.question_id == question_id)
        session.execute(stmt)
        stmt = delete(Choice).where(Choice.question_id == question_id)
        session.execute(stmt)
        stmt = delete(Question).where(Question.id == question_id)
        session.execute(stmt)
        session.commit()


@decorator_add_session
def get_all_stat(session: Session) -> list[list]:
    """Получение всей статистики"""
    stmt = (
        select(Question.question_text, Choice.choice_text, Choice.votes)
        .select_from(UserStat)
        .join(Choice, UserStat.choice_id == Choice.id)
        .join(Question, Choice.question_id == Question.id)
    )
    result = session.execute(stmt)
    return [row for row in result]


@decorator_add_session
def get_personal_stat(telegram_id: int, session: Session) -> list[list]:
    """Получение персональной статистики пользователя"""
    stmt = (
        select(Question.question_text, Choice.choice_text)
        .select_from(UserStat)
        .where(UserStat.tg_user_id == telegram_id)
        .join(Choice, UserStat.choice_id == Choice.id)
        .join(Question, Choice.question_id == Question.id)
    )
    result = session.execute(stmt)
    return [row for row in result]


@decorator_add_session
def get_random_question(telegram_id: int, session: Session) -> tuple:
    """Получение случайного неотвеченного вопроса"""
    stmt = (
        select(Question.id, Question.question_text)
        .select_from(Question)
        .where(
            Question.id.notin_(
                select(UserStat.question_id)
                .where(UserStat.tg_user_id == telegram_id)
                .where(UserStat.question_id == Question.id)
            )
        )
        .order_by(func.random())
        .limit(1)
    )

    question = session.execute(stmt).first()
    if question is None:
        return (-1, "")

    return (question.id, question.question_text)


@decorator_add_session
def get_choices_by_question_id(question_id: int, session: Session) -> list[str]:
    """Получение вариантов ответов для вопроса"""
    return [
        (choice.id, choice.choice_text)
        for choice in session.scalars(
            select(Choice.id, Choice.choice_text)
            .where(Choice.question_id == question_id)
            .order_by(Choice.id)
        )
    ]


@decorator_add_session
def add_user_vote_db(question_id: int, choice_id: int, telegram_id: int, session: Session):
    """Добавление голоса пользователя"""
    with session.begin():
        stmt = (
            update(Choice).
            where(Choice.id == choice_id).
            values(votes=Choice.votes+1)
        )
        session.execute(stmt)

        user_stat = UserStat(question_id=question_id, choice_id=choice_id, tg_user_id=telegram_id)
        session.add(user_stat)
        session.commit()


def register_handlers():
    """Регистрация всех обработчиков команд"""
    # Обработчики уже зарегистрированы через декораторы
    pass


if __name__ == "__main__":
    # print(get_all_stat())
    # print(get_personal_stat(369937974))
    print(get_random_question(369937974))
    # print(get_choices_by_question_id(1))
    # create_tables_in_db()
    # add_question_to_db("test-question", datetime.now())
    # add_choice_to_db("test-choice", 20)
    # add_user_vote_db(3, 369937974)

