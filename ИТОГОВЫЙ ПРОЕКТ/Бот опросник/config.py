# -*- coding: utf-8 -*-
from typing import List
from logger_config import logger

# Конфигурация бота
BOT_TOKEN = '7729923493:AAGggO84vLpLCJFkrdma9vZ8ScySHig5DMM'
ADMIN_IDS = [5533566321]  # ID администраторов

# Эмодзи для кнопок и сообщений
EMOJI = {
    'create': '📝',    # Создать
    'edit': '✏️',      # Редактировать
    'delete': '🗑️',    # Удалить
    'stats': '📊',     # Статистика
    'add': '➕',       # Добавить
    'save': '💾',      # Сохранить
    'cancel': '❌',    # Отмена
    'back': '◀️',      # Назад
    'next': '▶️',      # Далее
    'question': '❓',   # Вопрос
    'answer': '✅',     # Ответ
    'warning': '⚠️',   # Предупреждение
    'error': '❌',     # Ошибка
    'success': '✅',    # Успех
    'options': '🔄'    # Варианты ответов
}

def get_bot_token() -> str:
    """Получить токен бота"""
    return BOT_TOKEN

def get_admin_ids() -> List[int]:
    """Получить список ID администраторов"""
    return ADMIN_IDS

def get_channel_id() -> str:
    """Получить ID канала"""
    channel_id = 'CHANNEL_ID'
    return channel_id

def is_admin(user_id: int) -> bool:
    """Проверить, является ли пользователь администратором"""
    try:
        # Преобразуем user_id в int, если он пришел как строка
        user_id = int(user_id)
        logger.info(f"=== Проверка прав администратора ===")
        logger.info(f"Входящий user_id: {user_id} (тип: {type(user_id)})")
        logger.info(f"Список админов: {ADMIN_IDS}")
        logger.info(f"Типы ID в списке админов: {[type(admin_id) for admin_id in ADMIN_IDS]}")
        result = user_id in ADMIN_IDS
        logger.info(f"Результат проверки: {result}")
        logger.info(f"================================")
        return result
    except (ValueError, TypeError) as e:
        logger.error(f"Ошибка при проверке прав администратора: {e}")
        return False
