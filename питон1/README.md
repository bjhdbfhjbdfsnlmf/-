# Telegram Survey Bot

Бот для проведения опросов в Telegram.

## Установка

1. Клонируйте репозиторий:
```bash
git clone <repository-url>
cd <repository-directory>
```

2. Создайте виртуальное окружение и активируйте его:
```bash
python -m venv venv
source venv/bin/activate  # для Linux/Mac
venv\Scripts\activate     # для Windows
```

3. Установите зависимости:
```bash
pip install -r requirements.txt
```

4. Создайте файл `.env` на основе `.env.example`:
```bash
cp .env.example .env
```

5. Отредактируйте `.env` файл, указав необходимые значения:
- `DB_USERNAME` - имя пользователя базы данных
- `DB_PASSWORD` - пароль базы данных
- `DB_NAME` - имя базы данных
- `DB_PORT` - порт базы данных
- `BOT_TOKEN` - токен вашего Telegram бота
- `ADMIN_IDS` - ID администраторов через запятую
- `CHANNEL_ID` - ID канала для публикации

## Запуск

```bash
python main.py
```

## Функциональность

- Создание опросов с множественным выбором
- Прохождение опросов пользователями
- Просмотр личной статистики ответов
- Просмотр общей статистики (для администраторов)
- Управление опросами (создание, удаление)

## Требования

- Python 3.8+
- PostgreSQL
- Telegram Bot Token 