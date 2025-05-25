from datetime import datetime
from telebot import types
from init_bot import bot
from logger_config import logger
from config import EMOJI, is_admin, get_admin_ids
from db_adapter import (
    add_question_to_db,
    add_choice_to_db,
    get_random_question,
    get_choices_by_question_id,
    get_personal_stat,
    get_all_stat,
    add_user_vote_db,
    delete_question_by_id_db,
    get_all_questions
)

# Словарь для хранения текущего состояния пользователя
user_states = {}

def register_handlers():
    """Регистрация всех обработчиков команд"""
    # Обработчики регистрируются через декораторы
    logger.info("Обработчики команд зарегистрированы")

@bot.message_handler(commands=['start'])
def start(message):
    logger.info(f"Пользователь {message.from_user.id} запустил бота")
    logger.info(f"Тип ID пользователя: {type(message.from_user.id)}")
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.add(types.KeyboardButton("Пройти опрос"))
    markup.add(types.KeyboardButton("Моя статистика"))
    
    is_user_admin = is_admin(message.from_user.id)
    logger.info(f"Проверка на админа: user_id={message.from_user.id}, результат={is_user_admin}")
    
    if is_user_admin:
        logger.info(f"Пользователь {message.from_user.id} является администратором")
        markup.add(types.KeyboardButton("Общая статистика"))
        markup.add(types.KeyboardButton("Создать вопрос"))
        markup.add(types.KeyboardButton(f"{EMOJI['delete']} Удалить вопрос"))
    else:
        logger.info(f"Пользователь {message.from_user.id} НЕ является администратором")
    
    bot.reply_to(message, 
                "Привет! Я бот для проведения опросов.\nВыберите действие:",
                reply_markup=markup)

@bot.message_handler(func=lambda message: message.text == "Пройти опрос")
def handle_survey(message):
    logger.info(f"Пользователь {message.from_user.id} запросил новый вопрос")
    try:
        logger.debug("Получаем случайный вопрос...")
        question_id, question_text = get_random_question(message.from_user.id)
        logger.debug(f"Получен вопрос: id={question_id}, text={question_text}")
        
        if question_id == -1:
            logger.info(f"У пользователя {message.from_user.id} не осталось неотвеченных вопросов")
            bot.reply_to(message, "Вы уже ответили на все вопросы!")
            return

        # Получаем варианты ответов
        choices = get_choices_by_question_id(question_id)
        logger.debug(f"Получены варианты ответов для вопроса {question_id}")
        
        # Создаем клавиатуру с вариантами ответов
        markup = types.InlineKeyboardMarkup()
        for choice_id, choice_text in choices:
            callback_data = f"answer_{question_id}_{choice_id}"
            markup.add(types.InlineKeyboardButton(choice_text, callback_data=callback_data))
        
        # Отправляем вопрос пользователю
        bot.reply_to(message, f"Вопрос: {question_text}", reply_markup=markup)
        logger.info(f"Отправлен вопрос пользователю {message.from_user.id}")
        
    except Exception as e:
        logger.error(f"Ошибка при обработке запроса на опрос: {str(e)}")
        bot.reply_to(message, "Произошла ошибка при получении вопроса. Попробуйте позже.")

@bot.message_handler(func=lambda message: message.text == "Моя статистика")
def handle_personal_stats(message):
    try:
        stats = get_personal_stat(message.from_user.id)
        if not stats:
            bot.reply_to(message, "У вас пока нет статистики.")
            return
            
        response = "Ваша статистика:\n\n" + "\n".join(
            f"Вопрос: {question_text}\nВаш ответ: {choice_text}"
            for question_text, choice_text in stats
        )
        bot.reply_to(message, response)
    except Exception as e:
        logger.error(f"Ошибка при получении персональной статистики: {str(e)}")
        bot.reply_to(message, "Произошла ошибка при получении статистики. Попробуйте позже.")

@bot.message_handler(func=lambda message: message.text == "Общая статистика" and is_admin(message.from_user.id))
def handle_all_stats(message):
    try:
        stats = get_all_stat()
        if not stats:
            bot.reply_to(message, "Статистика пока отсутствует.")
            return
            
        response_lines = ["Общая статистика:\n"]
        for question_text, choice_text, count in stats:
            response_lines.append(f"Вопрос: {question_text}\nОтвет: {choice_text}\nКоличество: {count}\n")
            
        response = "\n".join(response_lines)
        bot.reply_to(message, response)
    except Exception as e:
        logger.error(f"Ошибка при получении общей статистики: {str(e)}")
        bot.reply_to(message, "Произошла ошибка при получении статистики. Попробуйте позже.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('answer_'))
def handle_answer(call):
    try:
        # Разбираем callback_data
        _, question_id, choice_id = call.data.split('_')
        question_id = int(question_id)
        choice_id = int(choice_id)
        
        # Сохраняем ответ пользователя
        add_user_vote_db(question_id, choice_id, call.from_user.id)
        
        # Отправляем подтверждение
        bot.answer_callback_query(call.id, "Ваш ответ записан!")
        
        # Обновляем сообщение
        bot.edit_message_text(
            "Спасибо за ваш ответ! Нажмите 'Пройти опрос' для следующего вопроса.",
            call.message.chat.id,
            call.message.message_id
        )
        
    except Exception as e:
        logger.error(f"Ошибка при обработке ответа: {str(e)}")
        bot.answer_callback_query(call.id, "Произошла ошибка при сохранении ответа.")

@bot.message_handler(func=lambda message: message.text == "Создать вопрос" and is_admin(message.from_user.id))
def handle_create_question_start(message):
    logger.info(f"Администратор {message.from_user.id} запросил создание вопроса")
    try:
        msg = bot.reply_to(message, "Введите текст вопроса:")
        bot.register_next_step_handler(msg, process_question_text)
    except Exception as e:
        error_msg = f"Ошибка при обработке создания вопроса: {str(e)}"
        logger.error(error_msg)
        bot.reply_to(message, "Произошла ошибка при создании вопроса. Попробуйте позже.")

def process_question_text(message):
    logger.info(f"Получен текст вопроса от администратора {message.from_user.id}: {message.text}")
    try:
        question_id = add_question_to_db(message.text, datetime.now())
        logger.debug(f"Вопрос {question_id} добавлен в базу данных")
        msg = bot.reply_to(message, 
                          "Теперь введите варианты ответов, каждый с новой строки:")
        bot.register_next_step_handler(msg, process_choices, question_id)
    except Exception as e:
        error_msg = f"Ошибка при обработке текста вопроса: {str(e)}"
        logger.error(error_msg)
        bot.reply_to(message, "Произошла ошибка при добавлении вопроса. Попробуйте позже.")

def process_choices(message, question_id):
    logger.info(f"Получены варианты ответов для вопроса {question_id} от администратора {message.from_user.id}: {message.text}")
    try:
        choices = message.text.split('\n')
        for choice in choices:
            if choice.strip():
                add_choice_to_db(choice.strip(), question_id)
                logger.debug(f"Вариант ответа '{choice.strip()}' добавлен для вопроса {question_id}")
        
        bot.reply_to(message, "Вопрос успешно создан!")
    except Exception as e:
        error_msg = f"Ошибка при обработке вариантов ответов: {str(e)}"
        logger.error(error_msg)
        bot.reply_to(message, "Произошла ошибка при добавлении вариантов ответов. Попробуйте позже.")

@bot.message_handler(func=lambda message: message.text == f"{EMOJI['delete']} Удалить вопрос" and is_admin(message.from_user.id))
def handle_delete_question(message):
    logger.info(f"Администратор {message.from_user.id} запросил удаление вопроса")
    try:
        # Получаем список всех вопросов
        questions = get_all_questions()
        if not questions:
            logger.info(f"Нет доступных вопросов для удаления")
            bot.reply_to(message, "Нет доступных вопросов для удаления!")
            return
        
        markup = types.InlineKeyboardMarkup()
        for question in questions:
            callback_data = f"delete_{question.id}"
            markup.add(types.InlineKeyboardButton(question.question_text[:50] + "...", callback_data=callback_data))
        
        bot.reply_to(message, "Выберите вопрос для удаления:", reply_markup=markup)
    except Exception as e:
        error_msg = f"Ошибка при обработке удаления вопроса: {str(e)}"
        logger.error(error_msg)
        bot.reply_to(message, "Произошла ошибка при удалении вопроса. Попробуйте позже.")

@bot.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def handle_delete(call):
    try:
        question_id = int(call.data.split('_')[1])
        logger.info(f"Попытка удаления вопроса {question_id}")
        
        delete_question_by_id_db(question_id)
        
        bot.answer_callback_query(call.id, "Вопрос успешно удален!")
        bot.edit_message_text(
            "Вопрос был успешно удален!",
            call.message.chat.id,
            call.message.message_id
        )
    except Exception as e:
        error_msg = f"Ошибка при обработке удаления вопроса: {str(e)}"
        logger.error(error_msg)
        bot.answer_callback_query(call.id, "Произошла ошибка при удалении вопроса")