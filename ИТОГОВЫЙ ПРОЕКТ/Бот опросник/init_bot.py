from telebot import TeleBot
from config import get_bot_token

bot = TeleBot(get_bot_token())

# Словарь для хранения состояний пользователей
user_states = {}