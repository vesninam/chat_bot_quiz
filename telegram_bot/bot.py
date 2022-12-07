import logging
import os
from telegram import Poll
from telegram.ext import (MessageHandler,
                          CommandHandler,
                          PollHandler,
                          Filters,
                          Updater)
import telegram

class QuizQuestion:
    def __init__(self, question, answers, correct_answer_position):
        self.question = question
        self.answers = answers
        self.correct_answer_position = correct_answer_position
        self.correct_answer = answers[correct_answer_position]

     
def get_chat_id_user(update, context):
    chat_id = -1
    user_name = ""
    if update.message is not None:
        chat_id = update.message.chat.id
        user_name = update.message.chat.username
    elif update.callback_query is not None:
        chat_id = update.callback_query.message.chat.id
        user_name = update.callback_query.message.chat.username
    elif update.poll is not None:
        chat_id = context.bot_data[update.poll.id]
        print(update)
    return chat_id, user_name
 
def get_answer(update):
    answers = update.poll.options

    ret = ""

    for answer in answers:
        if answer.voter_count == 1:
            ret = answer.text

    return ret

def is_answer_correct(update):
    answers = update.poll.options
    ret = False
    for i, answer in enumerate(answers):
        if answer.voter_count == 1 and update.poll.correct_option_id == i:
            ret = True
            break
    return ret

def send_text_message(update, context, message):
    chat_id, _ = get_chat_id_user(update, context)
    context.bot.send_message(chat_id=chat_id, text=message)
    
def send_quiz_question(update, context, quiz_question):
    message = context.bot.send_poll(
        chat_id=get_chat_id_user(update, context)[0],
        question=quiz_question.question,
        options=quiz_question.answers,
        type=Poll.QUIZ,
        correct_option_id=quiz_question.correct_answer_position,
        open_period=5,
        is_anonymous=True,
        explanation_parse_mode=telegram.ParseMode.MARKDOWN_V2,
    )
    print(message.poll.id,  message.chat.id)
    # Save some info about the poll the bot_data for later use in receive_quiz_answer
    context.bot_data.update({message.poll.id: message.chat.id})

def echo_handler(update, context):
    logging.info(f"update : {update}")
    chat_id, _ = get_chat_id_user(update, context)
    logging.info(f"update from chat_id : {chat_id}")

    if update.message is not None:
        user_input = update.message.text
        logging.info(f"user_input : {user_input}")
        send_text_message(update, context, f"You said: {user_input}")
    
def poll_handler(update, context):
    logging.info(f"question : {update.poll.question}")
    logging.info(f"correct option : {update.poll.correct_option_id}")
    logging.info(f"option #1 : {update.poll.options[0]}")
    logging.info(f"option #2 : {update.poll.options[1]}")
    logging.info(f"option #3 : {update.poll.options[2]}")

    user_answer = get_answer(update)
    logging.info(f"correct option {is_answer_correct(update)}")

    send_text_message(update, context, f"Correct answer is {user_answer}")

def start_dummy_poll(update, context):
    _question = BotConfig.QUIZES["dummy"][BotConfig.LANG]
    quiz_question = QuizQuestion(*_question)
    send_quiz_question(update, context, quiz_question)

def start_command_handler(update, context):
    send_text_message(update, context, BotConfig.MESSAGES["start"][BotConfig.LANG])
    start_dummy_poll(update, context)
    
    
def main():
    if BotConfig.TELEGRAM_TOKEN == "":
        raise ValueError("Could not find TOKEN for the bot")
    updater = Updater(BotConfig.TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start_command_handler))
    dp.add_handler(MessageHandler(Filters.text, echo_handler))
    dp.add_handler(PollHandler(poll_handler, pass_chat_data=True, pass_user_data=True))
    if BotConfig.MODE != "polling":
        raise ValueError("Polling MODE is only available")
    updater.start_polling()
    
class BotConfig:
    PORT = int(os.environ.get("TELEGRAM_PORT", 3978))
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
    MODE = os.environ.get("TELEGRAM_MODE", "polling")
    WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")

    LOG_LEVEL = os.environ.get("TELEGRAM_LOG_LEVEL", "INFO").upper()
    
    MESSAGES = {"start": {"en": "Lets start. Check you first",
                          "ru": "Давайте начнем. Простой тест для начала"}
               }
    QUIZES = {"dummy": {"en": ("What is liquid?",  ["wood", "ice", "water"], 2),
                        "ru": ("Что является жидкостью?",  ["дерево", "лед", "вода"], 2)}
             }

    LANG = "ru"
    @staticmethod
    def init_logging():
        logging.basicConfig(
            format="%(asctime)s - %(levelname)s - %(message)s",
            level=BotConfig.LOG_LEVEL,
        )
        
        
if __name__ == "__main__":
    print("Bot starting...")
    BotConfig.init_logging()

    main()
