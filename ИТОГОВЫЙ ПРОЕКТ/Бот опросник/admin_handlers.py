from datetime import datetime
import time
import requests
from telebot.types import Message, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from init_bot import bot, user_states
from sqlalchemy import select
from db_adapter import (
    add_question_to_db, add_choice_to_db, get_all_questions,
    delete_question_and_related, get_all_statistics, get_question_with_choices,
    edit_question_text, edit_choice_text, delete_choice, add_choice_to_question,
    get_engine, Session, Question, Choice
)
from config import is_admin, get_admin_ids, EMOJI
from logger_config import logger

# Состояния для создания вопроса
WAITING_QUESTION = "waiting_question"
WAITING_CHOICES = "waiting_choices"

# Состояния для редактирования
WAITING_EDIT_QUESTION = "waiting_edit_question"
WAITING_EDIT_CHOICE = "waiting_edit_choice"
WAITING_NEW_CHOICE = "waiting_new_choice"

def send_message_with_retry(chat_id, text, reply_markup=None, reply_to_message_id=None):
    """Отправка сообщения с повторными попытками при ошибке"""
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            return bot.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                reply_to_message_id=reply_to_message_id
            )
        except requests.exceptions.ConnectionError as e:
            if attempt == max_retries - 1:
                logger.error(f"Не удалось отправить сообщение после {max_retries} попыток: {e}")
                raise
            logger.warning(f"Попытка {attempt + 1} не удалась, повторная попытка через {retry_delay} сек.")
            time.sleep(retry_delay)
        except Exception as e:
            logger.error(f"Неожиданная ошибка при отправке сообщения: {e}")
            raise

def admin_required(func):
    """Декоратор для проверки прав администратора"""
    def wrapper(message, *args, **kwargs):
        user_id = message.from_user.id
        logger.debug(f"Проверка прав администратора для пользователя {user_id}")
        logger.debug(f"Список администраторов: {get_admin_ids()}")
        
        if not is_admin(user_id):
            logger.warning(f"Отказано в доступе пользователю {user_id}")
            try:
                send_message_with_retry(
                    message.chat.id,
                    f"{EMOJI['error']} У вас нет прав для выполнения этой команды.",
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения об отказе в доступе: {e}")
            return
        logger.debug(f"Доступ разрешен пользователю {user_id}")
        return func(message, *args, **kwargs)
    return wrapper

@bot.message_handler(commands=['admin'])
@admin_required
def admin_menu(message: Message):
    """Показать админское меню"""
    logger.debug(f"Вызвана команда /admin пользователем {message.from_user.id}")
    logger.debug(f"Информация о пользователе: {message.from_user}")
    
    try:
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.add(KeyboardButton(f"{EMOJI['create']} Создать вопрос"))
        markup.add(KeyboardButton(f"{EMOJI['edit']} Редактировать вопрос"))
        markup.add(KeyboardButton(f"{EMOJI['delete']} Удалить вопрос"))
        markup.add(KeyboardButton(f"{EMOJI['stats']} Общая статистика"))
        
        send_message_with_retry(
            message.chat.id,
            f"{EMOJI['question']} Выберите действие:",
            reply_markup=markup,
            reply_to_message_id=message.message_id
        )
        logger.debug("Отправлено админское меню")
    except Exception as e:
        logger.error(f"Ошибка при отображении админского меню: {e}")
        send_message_with_retry(
            message.chat.id,
            f"{EMOJI['error']} Произошла ошибка при отображении меню. Попробуйте позже.",
            reply_to_message_id=message.message_id
        )

@bot.message_handler(func=lambda message: message.text == f"{EMOJI['create']} Создать вопрос")
@admin_required
def start_create_question(message: Message):
    """Начать процесс создания вопроса"""
    user_states[message.from_user.id] = WAITING_QUESTION
    try:
        send_message_with_retry(
            message.chat.id,
            f"{EMOJI['question']} Введите текст вопроса:",
            reply_to_message_id=message.message_id
        )
    except Exception as e:
        logger.error(f"Ошибка при отправке сообщения для создания вопроса: {e}")

@bot.message_handler(func=lambda message: user_states.get(message.from_user.id) == WAITING_QUESTION)
@admin_required
def handle_question_text(message: Message):
    """Обработать текст вопроса"""
    try:
        question_id = add_question_to_db(message.text, datetime.now())
        user_states[message.from_user.id] = (WAITING_CHOICES, question_id)
        try:
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['answer']} Теперь введите варианты ответов, каждый с новой строки:",
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения для ввода вариантов ответа: {e}")
    except Exception as e:
        logger.error(f"Ошибка при создании вопроса: {str(e)}")
        try:
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['error']} Произошла ошибка при создании вопроса. Попробуйте еще раз.",
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке создания вопроса: {e}")
        del user_states[message.from_user.id]

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.from_user.id), tuple) and user_states.get(message.from_user.id)[0] == WAITING_CHOICES)
@admin_required
def handle_choices(message: Message):
    """Обработать варианты ответов"""
    try:
        _, question_id = user_states[message.from_user.id]
        choices = [choice.strip() for choice in message.text.split('\n') if choice.strip()]
        
        if len(choices) < 2:
            try:
                send_message_with_retry(
                    message.chat.id,
                    f"{EMOJI['warning']} Нужно ввести как минимум 2 варианта ответа. Попробуйте еще раз:",
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения об ошибке ввода вариантов ответа: {e}")
            return
            
        for choice in choices:
            add_choice_to_db(choice, question_id)
            
        del user_states[message.from_user.id]
        try:
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['success']} Вопрос успешно создан!",
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об успешном создании вопроса: {e}")
    except Exception as e:
        logger.error(f"Ошибка при добавлении вариантов ответа: {str(e)}")
        try:
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['error']} Произошла ошибка при добавлении вариантов ответа. Попробуйте создать вопрос заново.",
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке добавления вариантов ответа: {e}")
        del user_states[message.from_user.id]

@bot.message_handler(func=lambda message: message.text == f"{EMOJI['delete']} Удалить вопрос")
@admin_required
def show_questions_for_deletion(message: Message):
    """Показать список вопросов для удаления"""
    logger.info(f"Пользователь {message.from_user.id} запросил список вопросов для удаления")
    try:
        with Session(get_engine()) as session:
            questions = session.execute(select(Question)).scalars().all()
            logger.info(f"Получен список вопросов: {len(questions)} вопросов")
            
        if not questions:
            try:
                send_message_with_retry(
                    message.chat.id,
                    f"{EMOJI['warning']} В базе нет вопросов.",
                    reply_to_message_id=message.message_id
                )
                logger.info("Отправлено сообщение об отсутствии вопросов")
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения об отсутствии вопросов: {e}")
            return
            
        markup = InlineKeyboardMarkup(row_width=1)
        question_list = f"{EMOJI['question']} Список вопросов:\n\n"
        
        for i, question in enumerate(questions, 1):
            question_list += f"{i}. {question.question_text}\n"
            markup.add(InlineKeyboardButton(
                f"{EMOJI['delete']} Удалить вопрос {i}",
                callback_data=f"delete_{question.id}"
            ))
        
        markup.add(InlineKeyboardButton(
            f"{EMOJI['back']} Вернуться в главное меню",
            callback_data="admin_menu_return"
        ))
        
        logger.info(f"Подготовлен список из {len(questions)} вопросов для отображения")
            
        try:
            send_message_with_retry(
                message.chat.id,
                question_list,
                reply_markup=markup,
                reply_to_message_id=message.message_id
            )
            logger.info("Список вопросов успешно отправлен пользователю")
        except Exception as e:
            logger.error(f"Ошибка при отправке списка вопросов для удаления: {e}")
    except Exception as e:
        logger.error(f"Ошибка при получении списка вопросов: {str(e)}")
        try:
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['error']} Произошла ошибка при получении списка вопросов.",
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке получения списка вопросов: {e}")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def handle_question_deletion(call):
    """Обработать удаление вопроса"""
    logger.info(f"Пользователь {call.from_user.id} пытается удалить вопрос")
    
    if not is_admin(call.from_user.id):
        logger.warning(f"Попытка удаления вопроса неадминистратором: {call.from_user.id}")
        try:
            bot.answer_callback_query(call.id, f"{EMOJI['error']} У вас нет прав для выполнения этой команды.")
        except Exception as e:
            logger.error(f"Ошибка при отправке ответа на запрос удаления вопроса: {e}")
        return
        
    try:
        question_id = int(call.data.split('_')[1])
        logger.info(f"Попытка удаления вопроса с ID: {question_id}")
        
        with Session(get_engine()) as session:
            # Сначала получаем вопрос для логирования
            question = session.execute(select(Question).where(Question.id == question_id)).scalar()
            if question:
                logger.info(f"Удаляется вопрос: {question.question_text}")
            
            delete_question_and_related(question_id, session=session)
            logger.info(f"Вопрос с ID {question_id} успешно удален")
            
            # После удаления получаем обновленный список вопросов
            questions = session.execute(select(Question)).scalars().all()
            logger.info(f"Получен обновленный список вопросов: {len(questions)} вопросов")
            
        try:
            bot.answer_callback_query(call.id, f"{EMOJI['success']} Вопрос успешно удален!")
            logger.info("Отправлено подтверждение удаления")
        except Exception as e:
            logger.error(f"Ошибка при отправке ответа на запрос удаления вопроса: {e}")
            
        try:
            if not questions:  # Если вопросов больше нет
                message_text = f"{EMOJI['success']} Вопрос успешно удален!\n\n{EMOJI['info']} В базе больше нет вопросов."
                bot.edit_message_text(
                    message_text,
                    call.message.chat.id,
                    call.message.message_id
                )
                logger.info("Отправлено сообщение об отсутствии вопросов")
            else:  # Если есть другие вопросы, показываем обновленный список
                markup = InlineKeyboardMarkup(row_width=1)
                question_list = f"{EMOJI['success']} Вопрос успешно удален!\n\n{EMOJI['question']} Оставшиеся вопросы:\n\n"
                
                for i, question in enumerate(questions, 1):
                    question_list += f"{i}. {question.question_text}\n"
                    markup.add(InlineKeyboardButton(
                        f"{EMOJI['delete']} Удалить вопрос {i}",
                        callback_data=f"delete_{question.id}"
                    ))
                
                markup.add(InlineKeyboardButton(
                    f"{EMOJI['back']} Вернуться в главное меню",
                    callback_data="admin_menu_return"
                ))
                
                bot.edit_message_text(
                    question_list,
                    call.message.chat.id,
                    call.message.message_id,
                    reply_markup=markup
                )
                logger.info("Отправлен обновленный список вопросов")
        except Exception as e:
            logger.error(f"Ошибка при редактировании сообщения после удаления вопроса: {e}")
    except Exception as e:
        logger.error(f"Ошибка при удалении вопроса: {str(e)}")
        try:
            bot.answer_callback_query(call.id, f"{EMOJI['error']} Произошла ошибка при удалении вопроса.")
        except Exception as e:
            logger.error(f"Ошибка при отправке ответа на запрос удаления вопроса: {e}")

@bot.callback_query_handler(func=lambda call: call.data == "admin_menu_return")
def handle_admin_menu_return(call):
    """Обработчик возврата в главное меню администратора"""
    try:
        # Удаляем сообщение со списком вопросов
        bot.delete_message(call.message.chat.id, call.message.message_id)
        # Показываем главное меню администратора
        admin_menu(call.message)
    except Exception as e:
        logger.error(f"Ошибка при возврате в главное меню: {e}")

@bot.message_handler(func=lambda message: message.text == f"{EMOJI['stats']} Общая статистика")
@admin_required
def show_statistics(message: Message):
    """Показать общую статистику"""
    try:
        stats = get_all_statistics()
        if not stats:
            try:
                send_message_with_retry(
                    message.chat.id,
                    f"{EMOJI['warning']} Статистика пока отсутствует.",
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения об отсутствии статистики: {e}")
            return
            
        response = f"{EMOJI['stats']} Общая статистика по опросам:\n\n"
        
        for question_text, choices in stats.items():
            response += f"{EMOJI['question']} {question_text}\n"
            total_answers = sum(count for _, count in choices.items())
            
            for choice_text, count in choices.items():
                percentage = (count / total_answers * 100) if total_answers > 0 else 0
                response += f"{EMOJI['answer']} {choice_text}: {count} ({percentage:.1f}%)\n"
            response += "\n"
            
        # Разбиваем на части, если сообщение слишком длинное
        if len(response) > 4096:
            for x in range(0, len(response), 4096):
                try:
                    send_message_with_retry(
                        message.chat.id,
                        response[x:x+4096],
                        reply_to_message_id=message.message_id
                    )
                except Exception as e:
                    logger.error(f"Ошибка при отправке сообщения со статистикой: {e}")
        else:
            try:
                send_message_with_retry(
                    message.chat.id,
                    response,
                    reply_to_message_id=message.message_id
                )
            except Exception as e:
                logger.error(f"Ошибка при отправке сообщения со статистикой: {e}")
    except Exception as e:
        logger.error(f"Ошибка при получении статистики: {str(e)}")
        try:
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['error']} Произошла ошибка при получении статистики.",
                reply_to_message_id=message.message_id
            )
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения об ошибке получения статистики: {e}")

@bot.message_handler(func=lambda message: message.text == f"{EMOJI['edit']} Редактировать вопрос")
@admin_required
def edit_question_menu(message: Message):
    """Показать список вопросов для редактирования"""
    try:
        with Session(get_engine()) as session:
            questions = session.execute(select(Question)).scalars().all()
            if not questions:
                send_message_with_retry(
                    message.chat.id,
                    f"{EMOJI['warning']} В базе нет вопросов.",
                    reply_to_message_id=message.message_id
                )
                return
                
            markup = InlineKeyboardMarkup(row_width=2)
            question_list = f"{EMOJI['question']} Выберите вопрос для редактирования:\n\n"
            
            for i, question in enumerate(questions, 1):
                question_list += f"{i}. {question.question_text}\n"
                markup.add(
                    InlineKeyboardButton(f"{EMOJI['edit']} {i}", callback_data=f"edit_q_{question.id}"),
                    InlineKeyboardButton(f"{EMOJI['options']} Варианты {i}", callback_data=f"edit_choices_{question.id}")
                )
            
            send_message_with_retry(
                message.chat.id,
                question_list,
                reply_markup=markup,
                reply_to_message_id=message.message_id
            )
    except Exception as e:
        logger.error(f"Ошибка при получении списка вопросов: {e}")
        send_message_with_retry(
            message.chat.id,
            f"{EMOJI['error']} Произошла ошибка при получении списка вопросов.",
            reply_to_message_id=message.message_id
        )

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_q_'))
def handle_edit_question_request(call):
    """Обработка запроса на редактирование текста вопроса"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, f"{EMOJI['error']} У вас нет прав для выполнения этой команды.")
        return
        
    try:
        question_id = int(call.data.split('_')[2])
        with Session(get_engine()) as session:
            question = session.execute(select(Question).where(Question.id == question_id)).scalar()
        
        if not question:
            bot.answer_callback_query(call.id, f"{EMOJI['error']} Вопрос не найден.")
            return
            
        user_states[call.from_user.id] = (WAITING_EDIT_QUESTION, question_id)
        
        bot.edit_message_text(
            f"{EMOJI['question']} Текущий текст вопроса:\n{question.question_text}\n\n{EMOJI['edit']} Введите новый текст вопроса:",
            call.message.chat.id,
            call.message.message_id
        )
    except Exception as e:
        logger.error(f"Ошибка при запросе редактирования вопроса: {e}")
        bot.answer_callback_query(call.id, f"{EMOJI['error']} Произошла ошибка. Попробуйте позже.")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.from_user.id), tuple) and user_states.get(message.from_user.id)[0] == WAITING_EDIT_QUESTION)
@admin_required
def handle_edit_question(message: Message):
    """Обработка нового текста вопроса"""
    try:
        state_data = user_states.get(message.from_user.id)
        question_id = state_data[1]
        
        if edit_question_text(question_id, message.text):
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['success']} Текст вопроса успешно обновлен!",
                reply_to_message_id=message.message_id
            )
        else:
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['error']} Вопрос не найден.",
                reply_to_message_id=message.message_id
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении текста вопроса: {e}")
        send_message_with_retry(
            message.chat.id,
            f"{EMOJI['error']} Произошла ошибка при обновлении вопроса.",
            reply_to_message_id=message.message_id
        )
    finally:
        del user_states[message.from_user.id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_choices_'))
def handle_edit_choices_request(call):
    """Показать варианты ответов для редактирования"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, f"{EMOJI['error']} У вас нет прав для выполнения этой команды.")
        return
        
    try:
        question_id = int(call.data.split('_')[2])
        with Session(get_engine()) as session:
            question = session.execute(select(Question).where(Question.id == question_id)).scalar()
            choices = session.execute(select(Choice).where(Choice.question_id == question_id)).scalars().all()
        
        if not question:
            bot.answer_callback_query(call.id, f"{EMOJI['error']} Вопрос не найден.")
            return
            
        markup = InlineKeyboardMarkup(row_width=2)
        choices_text = f"{EMOJI['answer']} Варианты ответов для вопроса:\n{question.question_text}\n\n"
        
        for i, choice in enumerate(choices, 1):
            choices_text += f"{i}. {choice.choice_text}\n"
            markup.add(
                InlineKeyboardButton(f"{EMOJI['edit']} {i}", callback_data=f"edit_ch_{choice.id}"),
                InlineKeyboardButton(f"{EMOJI['delete']} {i}", callback_data=f"del_ch_{choice.id}")
            )
        
        markup.add(InlineKeyboardButton(f"{EMOJI['add']} Добавить вариант", callback_data=f"add_ch_{question_id}"))
        
        bot.edit_message_text(
            choices_text,
            call.message.chat.id,
            call.message.message_id,
            reply_markup=markup
        )
    except Exception as e:
        logger.error(f"Ошибка при показе вариантов ответов: {e}")
        bot.answer_callback_query(call.id, f"{EMOJI['error']} Произошла ошибка. Попробуйте позже.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('edit_ch_'))
def handle_edit_choice_request(call):
    """Запрос на редактирование варианта ответа"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, f"{EMOJI['error']} У вас нет прав для выполнения этой команды.")
        return
        
    try:
        choice_id = int(call.data.split('_')[2])
        user_states[call.from_user.id] = (WAITING_EDIT_CHOICE, choice_id)
        
        bot.edit_message_text(
            f"{EMOJI['edit']} Введите новый текст для варианта ответа:",
            call.message.chat.id,
            call.message.message_id
        )
    except Exception as e:
        logger.error(f"Ошибка при запросе редактирования варианта: {e}")
        bot.answer_callback_query(call.id, f"{EMOJI['error']} Произошла ошибка. Попробуйте позже.")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.from_user.id), tuple) and user_states.get(message.from_user.id)[0] == WAITING_EDIT_CHOICE)
@admin_required
def handle_edit_choice(message: Message):
    """Обработка нового текста варианта ответа"""
    try:
        state_data = user_states.get(message.from_user.id)
        choice_id = state_data[1]
        
        if edit_choice_text(choice_id, message.text):
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['success']} Вариант ответа успешно обновлен!",
                reply_to_message_id=message.message_id
            )
        else:
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['error']} Вариант ответа не найден.",
                reply_to_message_id=message.message_id
            )
    except Exception as e:
        logger.error(f"Ошибка при обновлении варианта ответа: {e}")
        send_message_with_retry(
            message.chat.id,
            f"{EMOJI['error']} Произошла ошибка при обновлении варианта ответа.",
            reply_to_message_id=message.message_id
        )
    finally:
        del user_states[message.from_user.id]

@bot.callback_query_handler(func=lambda call: call.data.startswith('del_ch_'))
def handle_delete_choice(call):
    """Удаление варианта ответа"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, f"{EMOJI['error']} У вас нет прав для выполнения этой команды.")
        return
        
    try:
        choice_id = int(call.data.split('_')[2])
        
        if delete_choice(choice_id):
            bot.answer_callback_query(call.id, f"{EMOJI['success']} Вариант ответа успешно удален!")
            # Обновляем список вариантов
            question_id = call.message.text.split('\n')[0].split(':')[1].strip()
            handle_edit_choices_request(call)
        else:
            bot.answer_callback_query(call.id, f"{EMOJI['error']} Вариант ответа не найден.")
    except Exception as e:
        logger.error(f"Ошибка при удалении варианта ответа: {e}")
        bot.answer_callback_query(call.id, f"{EMOJI['error']} Произошла ошибка. Попробуйте позже.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('add_ch_'))
def handle_add_choice_request(call):
    """Запрос на добавление нового варианта ответа"""
    if not is_admin(call.from_user.id):
        bot.answer_callback_query(call.id, f"{EMOJI['error']} У вас нет прав для выполнения этой команды.")
        return
        
    try:
        question_id = int(call.data.split('_')[2])
        user_states[call.from_user.id] = (WAITING_NEW_CHOICE, question_id)
        
        bot.edit_message_text(
            f"{EMOJI['add']} Введите текст нового варианта ответа:",
            call.message.chat.id,
            call.message.message_id
        )
    except Exception as e:
        logger.error(f"Ошибка при запросе добавления варианта: {e}")
        bot.answer_callback_query(call.id, f"{EMOJI['error']} Произошла ошибка. Попробуйте позже.")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.from_user.id), tuple) and user_states.get(message.from_user.id)[0] == WAITING_NEW_CHOICE)
@admin_required
def handle_add_choice(message: Message):
    """Обработка текста нового варианта ответа"""
    try:
        state_data = user_states.get(message.from_user.id)
        question_id = state_data[1]
        
        if add_choice_to_question(question_id, message.text):
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['success']} Новый вариант ответа успешно добавлен!",
                reply_to_message_id=message.message_id
            )
        else:
            send_message_with_retry(
                message.chat.id,
                f"{EMOJI['error']} Вопрос не найден.",
                reply_to_message_id=message.message_id
            )
    except Exception as e:
        logger.error(f"Ошибка при добавлении варианта ответа: {e}")
        send_message_with_retry(
            message.chat.id,
            f"{EMOJI['error']} Произошла ошибка при добавлении варианта ответа.",
            reply_to_message_id=message.message_id
        )
    finally:
        del user_states[message.from_user.id]
