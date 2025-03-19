import time
import requests
from init_bot import bot
from logger_config import logger
import handlers
import admin_handlers

def main():
    """Основная функция запуска бота"""
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

if __name__ == '__main__':
    main()