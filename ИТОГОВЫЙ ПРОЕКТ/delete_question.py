import telebot.types

from init_bot import bot

from db_adapter import(
get_random_question,
get_choices_by_question_id,
)

@bot.message_handler()
def start_delete_question(message: telebot.types.Message):
    pass

@bot.message_handler()
def process_user_answer(message: telebot.types.Message):
    pass