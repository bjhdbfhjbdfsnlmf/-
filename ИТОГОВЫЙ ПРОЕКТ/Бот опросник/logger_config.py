import logging
import sys
from datetime import datetime

# Настраиваем логирование
def setup_logger():
    logger = logging.getLogger('survey_bot')
    logger.setLevel(logging.DEBUG)

    # Создаем форматтер для логов
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

    # Хендлер для записи в файл
    file_handler = logging.FileHandler(f'bot_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8')
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    # Хендлер для вывода в консоль
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(formatter)

    # Добавляем хендлеры к логгеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

# Создаем глобальный логгер
logger = setup_logger()
