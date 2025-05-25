# -*- coding: utf-8 -*-
from typing import List
from logger_config import logger
import os
from dotenv import load_dotenv

# Загрузка переменных окружения из .env файла
load_dotenv()

# Конфигурация базы данных
DB_USERNAME = os.getenv('DB_USERNAME', 'postgres')
DB_PASSWORD = os.getenv('DB_PASSWORD', 'umschoolpswd')
DB_NAME = os.getenv('DB_NAME', 'umschooldb')
DB_PORT = os.getenv('DB_PORT', '5432')

# Конфигурация Telegram бота
BOT_TOKEN = os.getenv('BOT_TOKEN')

# ID администраторов (через запятую в .env файле)
ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS', '').split(',') if id.strip()]

# URL для подключения к базе данных
DATABASE_URL = f'postgresql://{DB_USERNAME}:{DB_PASSWORD}@localhost:{DB_PORT}/{DB_NAME}'

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
    if not BOT_TOKEN:
        raise ValueError("BOT_TOKEN не найден в переменных окружения")
    return BOT_TOKEN

def get_admin_ids() -> List[int]:
    """Получить список ID администраторов"""
    return ADMIN_IDS

def get_channel_id() -> str:
    """Получить ID канала"""
    channel_id = os.getenv('CHANNEL_ID')
    if not channel_id:
        raise ValueError("CHANNEL_ID не найден в переменных окружения")
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
    