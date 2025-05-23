import time
import requests
from init_bot import bot
from logger_config import logger
import handlers
from db_adapter import create_tables_in_db
import telebot.custom_filters

def main():
    """Основная функция запуска бота"""
    try:
        logger.info("Инициализация базы данных...")
        create_tables_in_db()
        logger.info("База данных инициализирована")
        
        # Регистрируем обработчики команд
        handlers.register_handlers()
        
        # Добавляем фильтр состояний
        bot.add_custom_filter(telebot.custom_filters.StateFilter(bot))
        
        logger.info("Бот запущен")
        
        while True:
            try:
                # Запускаем бота с повторными попытками при ошибках подключения
                bot.infinity_polling(timeout=60, long_polling_timeout=60)
            except requests.exceptions.ConnectionError as e:
                logger.error(f"Ошибка подключения: {e}")
                logger.info("Повторная попытка через 5 секунд...")
                time.sleep(5)
            except requests.exceptions.ReadTimeout as e:
                logger.error(f"Таймаут чтения: {e}")
                logger.info("Повторная попытка через 5 секунд...")
                time.sleep(5)
            except Exception as e:
                logger.error(f"Неожиданная ошибка: {e}")
                logger.info("Повторная попытка через 10 секунд...")
                time.sleep(10)
    except Exception as e:
        logger.error(f"Критическая ошибка при запуске бота: {e}")
        raise

if __name__ == '__main__':
    main()