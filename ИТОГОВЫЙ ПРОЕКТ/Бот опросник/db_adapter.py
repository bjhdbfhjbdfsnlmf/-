from datetime import datetime

import sqlalchemy
from sqlalchemy import select, update, delete
from sqlalchemy.sql.expression import func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, Session
from logger_config import logger
from typing import List, Dict, Tuple

DATABASE_PATH = 'survey.db'

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


def get_engine():
    return sqlalchemy.create_engine(f'sqlite:///{DATABASE_PATH}', connect_args={'check_same_thread': False})


def get_session() -> Session:
    return Session(get_engine())


def decorator_add_session(func):
    def wrapper(*args, **kwargs):
        session = get_session()
        try:
            return func(*args, session=session, **kwargs)
        finally:
            session.close()
    return wrapper


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
    """
    добавить вопрос в бд
    """
    try:
        question = Question(question_text=question_text, publish_date=publish_date)
        session.add(question)
        session.commit()
        return question.id
    except Exception as e:
        logger.error(f"Ошибка при добавлении вопроса: {str(e)}")
        session.rollback()
        raise


@decorator_add_session
def add_choice_to_db(choice_text: str, question_id: int, session: Session):
    """
    добавить ответ в бд
    """
    try:
        choice = Choice(choice_text=choice_text, question_id=question_id)
        session.add(choice)
        session.commit()
    except Exception as e:
        logger.error(f"Ошибка при добавлении варианта ответа: {str(e)}")
        session.rollback()
        raise


@decorator_add_session
def delete_question_by_id_db(question_id: int, session: Session):
    """
    удалить вопрос, варианты ответа,
    а также всю статистику связанную с ним из бд
    """
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
    """
    получить статистику пользователей
    """
    stmt = (
        select(Question.question_text, Choice.choice_text, Choice.votes)
        .select_from(UserStat)
        .join(Choice, UserStat.choice_id == Choice.id)
        .join(Question, Choice.question_id == Question.id)
    )
    result = session.execute(stmt)
    out = []
    for row in result:
        out.append(row)
    return out


@decorator_add_session
def get_personal_stat(telegram_id: int, session: Session) -> list[list]:
    """
    получить личную статистику пользователя
    """
    stmt = (
        select(Question.question_text, Choice.choice_text)
        .select_from(UserStat)
        .where(UserStat.tg_user_id == telegram_id)
        .join(Choice, UserStat.choice_id == Choice.id)
        .join(Question, Choice.question_id == Question.id)
    )
    result = session.execute(stmt)
    out = []
    for row in result:
        out.append(row)
    return out


@decorator_add_session
def get_random_question(telegram_id: int, session: Session) -> tuple:
    """
    Получить случайный, неотвеченный вопрос из бд
    """
    logger.debug(f"Получение случайного вопроса для пользователя {telegram_id}")
    try:
        # Получаем вопрос, на который пользователь еще не отвечал
        stmt = (
            select(Question)
            .where(
                Question.id.notin_(
                    select(UserStat.question_id)
                    .where(UserStat.tg_user_id == telegram_id)
                )
            )
            .order_by(func.random())
            .limit(1)
        )

        logger.debug(f"SQL запрос: {str(stmt)}")
        result = session.execute(stmt).first()
        
        if result is None:
            logger.info(f"Для пользователя {telegram_id} не осталось неотвеченных вопросов")
            return (-1, "Вы ответили на все доступные вопросы!")

        question = result[0]  # Получаем объект Question из результата
        logger.info(f"Получен вопрос {question.id} для пользователя {telegram_id}")
        return (question.id, question.question_text)
    except Exception as e:
        logger.error(f"Ошибка при получении вопроса: {str(e)}")
        raise


@decorator_add_session
def get_choices_by_question_id(question_id: int, session: Session) -> list[tuple]:
    """
    получить ответы по заданному question_id
    """
    logger.debug(f"Получение вариантов ответа для вопроса {question_id}")
    try:
        choices = [
            (choice.id, choice.choice_text)
            for choice in session.scalars(
                select(Choice)
                .where(Choice.question_id == question_id)
                .order_by(Choice.id)
            )
        ]
        logger.debug(f"Получены варианты ответов: {choices}")
        return choices
    except Exception as e:
        logger.error(f"Ошибка при получении вариантов ответа: {str(e)}")
        raise


@decorator_add_session
def add_user_answer(telegram_id: int, question_id: int, choice_id: int, session: Session):
    """
    Добавить ответ пользователя и обновить статистику
    """
    logger.debug(f"Добавление ответа пользователя {telegram_id} на вопрос {question_id}, выбран вариант {choice_id}")
    try:
        # Проверяем, не отвечал ли пользователь уже на этот вопрос
        existing_answer = session.query(UserStat).filter_by(
            tg_user_id=telegram_id,
            question_id=question_id
        ).first()
        
        if existing_answer:
            logger.warning(f"Пользователь {telegram_id} уже отвечал на вопрос {question_id}")
            raise Exception("Вы уже отвечали на этот вопрос")
            
        # Добавляем статистику пользователя
        user_stat = UserStat(
            tg_user_id=telegram_id,
            question_id=question_id,
            choice_id=choice_id
        )
        session.add(user_stat)
        
        # Обновляем количество голосов для выбранного варианта
        stmt = (
            update(Choice)
            .where(Choice.id == choice_id)
            .values(votes=Choice.votes + 1)
        )
        session.execute(stmt)
        
        # Сохраняем изменения
        session.commit()
        logger.info(f"Ответ пользователя {telegram_id} успешно сохранен")
    except Exception as e:
        logger.error(f"Ошибка при сохранении ответа пользователя: {str(e)}")
        session.rollback()
        raise


@decorator_add_session
def get_all_questions(session: Session) -> List[Question]:
    """
    Получить все вопросы из базы данных
    
    Args:
        session (Session): Сессия базы данных
    
    Returns:
        List[Question]: Список всех вопросов
    """
    try:
        stmt = select(Question).order_by(Question.id)
        questions = list(session.scalars(stmt).all())
        logger.info(f"Получено {len(questions)} вопросов из базы данных")
        return questions
    except Exception as e:
        logger.error(f"Ошибка при получении списка вопросов: {e}")
        raise


@decorator_add_session
def get_question_by_id(question_id: int, session: Session) -> Question:
    """
    Получить вопрос по его ID
    """
    question = session.execute(select(Question).where(Question.id == question_id)).scalar()
    if not question:
        raise ValueError(f"Вопрос с ID {question_id} не найден")
    return question


@decorator_add_session
def delete_question_and_related(question_id: int, session: Session) -> None:
    """
    Удалить вопрос и все связанные с ним данные
    
    Args:
        question_id (int): ID вопроса для удаления
        session (Session): Сессия базы данных
    """
    try:
        # Проверяем существование вопроса
        question = session.execute(select(Question).where(Question.id == question_id)).scalar()
        if not question:
            logger.warning(f"Попытка удаления несуществующего вопроса с ID {question_id}")
            return

        # Удаляем связанную статистику
        session.execute(delete(UserStat).where(UserStat.question_id == question_id))
        
        # Удаляем варианты ответов
        session.execute(delete(Choice).where(Choice.question_id == question_id))
        
        # Удаляем сам вопрос
        session.execute(delete(Question).where(Question.id == question_id))
        
        session.commit()
        logger.info(f"Вопрос с ID {question_id} и все связанные данные успешно удалены")
    except Exception as e:
        logger.error(f"Ошибка при удалении вопроса {question_id}: {e}")
        session.rollback()
        raise


@decorator_add_session
def get_question_statistics(question_id: int, session: Session) -> Dict[str, any]:
    """
    Получить статистику по конкретному вопросу
    """
    question = session.execute(select(Question).where(Question.id == question_id)).scalar()
    if not question:
        raise ValueError(f"Вопрос с ID {question_id} не найден")
        
    choices = session.scalars(select(Choice).where(Choice.question_id == question_id)).all()
    total_responses = session.scalars(select(UserStat).where(UserStat.question_id == question_id)).count()
    
    choice_stats = []
    for choice in choices:
        count = session.scalars(select(UserStat).where(UserStat.question_id == question_id, UserStat.choice_id == choice.id)).count()
        choice_stats.append({
            'text': choice.choice_text,
            'count': count
        })
    
    return {
        'question_text': question.question_text,
        'total_responses': total_responses,
        'choices': choice_stats
    }


@decorator_add_session
def get_all_statistics(session: Session) -> List[Dict[str, any]]:
    """
    Получить статистику по всем вопросам
    """
    questions = session.scalars(select(Question)).all()
    stats = []
    
    for question in questions:
        try:
            stats.append(get_question_statistics(question.id, session))
        except Exception as e:
            logger.error(f"Ошибка при получении статистики для вопроса {question.id}: {str(e)}")
            continue
            
    return stats


def get_question_with_choices(question_id: int):
    """Получить вопрос и варианты ответов по ID"""
    session = Session()
    try:
        question = session.execute(select(Question).where(Question.id == question_id)).scalar()
        if question:
            choices = session.scalars(select(Choice).where(Choice.question_id == question_id)).all()
            return question, choices
        return None, None
    except Exception as e:
        logger.error(f"Ошибка при получении вопроса: {e}")
        raise
    finally:
        session.close()


def edit_question_text(question_id: int, new_text: str):
    """Изменить текст вопроса"""
    session = Session()
    try:
        question = session.execute(select(Question).where(Question.id == question_id)).scalar()
        if question:
            question.question_text = new_text
            session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при редактировании вопроса: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def edit_choice_text(choice_id: int, new_text: str):
    """Изменить текст варианта ответа"""
    session = Session()
    try:
        choice = session.execute(select(Choice).where(Choice.id == choice_id)).scalar()
        if choice:
            choice.choice_text = new_text
            session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при редактировании варианта ответа: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def delete_choice(choice_id: int):
    """Удалить вариант ответа"""
    session = Session()
    try:
        choice = session.execute(select(Choice).where(Choice.id == choice_id)).scalar()
        if choice:
            session.delete(choice)
            session.commit()
            return True
        return False
    except Exception as e:
        logger.error(f"Ошибка при удалении варианта ответа: {e}")
        session.rollback()
        raise
    finally:
        session.close()


def add_choice_to_question(question_id: int, choice_text: str):
    """Добавить новый вариант ответа к существующему вопросу"""
    session = Session()
    try:
        question = session.execute(select(Question).where(Question.id == question_id)).scalar()
        if question:
            new_choice = Choice(question_id=question_id, choice_text=choice_text)
            session.add(new_choice)
            session.commit()
            return new_choice.id
        return None
    except Exception as e:
        logger.error(f"Ошибка при добавлении варианта ответа: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    # print(get_all_stat())
    # print(get_personal_stat(369937974))
    print(get_random_question(369937974))
    # print(get_choices_by_question_id(1))
    # create_tables_in_db()
    # add_question_to_db("test-question", datetime.now())
    # add_choice_to_db("test-choice", 20)
    # add_user_answer(369937974, 3, 1)