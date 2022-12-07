import logging
import os
import requests
from collections import defaultdict
from telegram import Poll
from telegram.ext import (MessageHandler,
                          CommandHandler,
                          PollHandler,
                          Filters,
                          Updater)
import telegram

user_quizes = defaultdict(dict)
issued_polls = defaultdict(dict)
user_busy = dict()
user_idle = dict()
polls_answers =  dict()

class QuizQuestion:
    def __init__(self, question, answers, correct_answer_position, db_id):
        self.question = question
        self.answers = answers
        self.correct_answer_position = correct_answer_position
        self.correct_answer = answers[correct_answer_position]
        self.db_id = db_id
        
class APIClient:
    
    @staticmethod
    def submit_user(_id, password="", topics=["all"]):
        _json = {"telegram_id": str(_id), 
                 "password": password, 
                 "topics": ",".join(topics) 
                }
        resp = requests.post(f"{BotConfig.API_URL}:{BotConfig.API_PORT}/users/", json=_json) 
        if resp.status_code == 400:
            return False
        elif resp.status_code == 200:
            return True
        else:
            raise ValueError(f"Unknown response from server: {resp.content}")
        return False
    
    @staticmethod
    def get_quizes(_id=None, password="", topics=["all"], amount=1):
        _json = {"telegram_id": str(_id), 
                 "password": password, 
                 "topics": ",".join(topics) 
                }
        if _id is None:
            url = f"{BotConfig.API_URL}:{BotConfig.API_PORT}/quiz/active/"
        else:
            url = f"{BotConfig.API_URL}:{BotConfig.API_PORT}/quiz/{_id}"
        
        resp = requests.get(url, json=_json) 
        if resp.status_code == 200:
            res = resp.json()[:amount] if _id is None else [resp.json()]
            return res
        else:
            raise ValueError(f"Unknown response from server: {resp.content}")
        return []
    
    def submit_user_response(chat_id: str, question_id: int, answer: str):
        url = f"{BotConfig.API_URL}:{BotConfig.API_PORT}/users_by_tid/{int(chat_id)}"
        resp = requests.get(url)
        print(url, resp)
        if resp.status_code == 200:
            _id = resp.json()["id"]
        else:
            logging.info(f"No User with telegram ID {chat_id}")
            return 
        _json = {"question_id": int(question_id),
                 "user_id": _id,
                 "response_time": "2022-12-07T08:19:54.375Z",
                 "answer": answer
                }
        url = f"{BotConfig.API_URL}:{BotConfig.API_PORT}/user_responses/"
        resp = requests.post(url, json=_json) 
        print(url, resp, _json)
        
    
    @staticmethod
    def api_quiz_to_poll(quizes: list, amount=1):
        poll = list()
        for i, quiz in enumerate(quizes):
            if i >= amount:
                break
            for q in quiz["questions"]:
                answers = [q["answer1"], q["answer2"], q["answer3"], q["answer4"]]
                correct_option = int(q["correct_answers"].split(",")[0]) - 1
                poll_item = (q["description"], answers, correct_option, q["id"])
                poll.append(poll_item)
        return poll
        

     
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
        #print(update)
        #print(context.bot_data)
    #print(f"CHAT ID {chat_id}")
    return chat_id, user_name
 
def get_answer(poll):
    ret = ""

    for answer in poll.options:
        if answer.voter_count == 1:
            ret = answer.text

    return ret

def is_answer_correct(poll):
    ret = False
    for i, answer in enumerate(poll.options):
        if answer.voter_count == 1 and poll.correct_option_id == i:
            ret = True
            break
    return ret

def send_text_message(update, context, message):
    chat_id, _ = get_chat_id_user(update, context)
    context.bot.send_message(chat_id=chat_id, text=message)
    
def send_quiz_question(update, context, quiz_question):
    chat_id, _ = get_chat_id_user(update, context)
    logging.info(f"Send poll to {chat_id}")
    message = context.bot.send_poll(
        chat_id=chat_id,
        question=quiz_question.question,
        options=quiz_question.answers,
        type=Poll.QUIZ,
        correct_option_id=quiz_question.correct_answer_position,
        open_period=300,
        is_anonymous=True,
        explanation_parse_mode=telegram.ParseMode.MARKDOWN_V2,
    )
    issued_polls[chat_id]["questions"] = [message.poll.id, "issued"]
    user_busy[chat_id] = True
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
    
def poll_response_handler(update, context):
    chat_id, _ = get_chat_id_user(update, context)
    logging.info(f"question : {update.poll.question}")
    logging.info(f"correct option : {update.poll.correct_option_id}")
    logging.info(f"option #1 : {update.poll.options[0]}")
    logging.info(f"option #2 : {update.poll.options[1]}")
    logging.info(f"option #3 : {update.poll.options[2]}")
    logging.info(f"option #4 : {update.poll.options[3]}")
    user_answer = get_answer(update.poll)
    if chat_id in user_quizes and user_quizes[chat_id]["answers"]:
        i = user_quizes[chat_id]["position"] - 1
        user_quizes[chat_id]["answers"][i] = user_answer
    correct_answer = update.poll.options[update.poll.correct_option_id]['text']

    polls_answers[update.poll.id] = {"user": user_answer, "correct": correct_answer}
    logging.info(f"correct option {is_answer_correct(update.poll)}")
    _text = BotConfig.MESSAGES["answer"][BotConfig.LANG] + f"{correct_answer}"
    send_text_message(update, context, _text)

    user_busy[chat_id] = False
    logging.info(f"Poll response porcessed for {chat_id}")
    if chat_id in user_idle and user_idle[chat_id] is False:
        start_poll(update, context)


def start_dummy_poll(update, context):
    _question = BotConfig.QUIZES["dummy"][BotConfig.LANG]
    quiz_question = QuizQuestion(*_question)
    send_quiz_question(update, context, quiz_question)
    
def start_poll(update, context):
    chat_id, user_name = get_chat_id_user(update, context)
    user_idle[chat_id] = False
    if not chat_id in user_quizes:
        user_quizes[chat_id]["questions"] = []
        user_quizes[chat_id]["answers"] = []
        user_quizes[chat_id]["position"] = 0
    if (user_quizes[chat_id]["questions"] and 
        len(user_quizes[chat_id]["questions"]) <= user_quizes[chat_id]["position"]):
        user_busy[chat_id] = False
        user_idle[chat_id] = True
        for i ,q in enumerate(user_quizes[chat_id]["questions"]):
            answer = user_quizes[chat_id]["answers"][i]
            APIClient.submit_user_response(chat_id, q[-1], answer)
        user_quizes[chat_id]["questions"] = []
        user_quizes[chat_id]["position"] = 0
        user_quizes[chat_id]["answers"] = []
    else:
        if not user_quizes[chat_id]["questions"]:

            quizes = APIClient.get_quizes()
            if not quizes:
                _text = BotConfig.MESSAGES["nopolls"][BotConfig.LANG]
                send_text_message(update, context, _text)
                logging.info(f"No quizes")
                return 
            logging.info(f"Start quiz for {chat_id}")
            logging.info(f"Got quizes {len(quizes)}")
            polls = APIClient.api_quiz_to_poll(quizes)
            if len(polls) == 0:
                user_busy[chat_id] = False
                user_idle[chat_id] = True
                del user_quizes[chat_id]
                send_text_message(update, context, 
                                  BotConfig.MESSAGES["start"][BotConfig.LANG])
            user_quizes[chat_id]["questions"] = polls
            user_quizes[chat_id]["position"] = 0
            user_quizes[chat_id]["answers"] = ["" for _ in polls]
            logging.info(f"Starting polls {len(polls)} questions")
        user_busy[chat_id] = True
        user_idle[chat_id] = False
        question = user_quizes[chat_id]["questions"][user_quizes[chat_id]["position"]]
        quiz_question = QuizQuestion(*question)
        user_quizes[chat_id]["position"] += 1
        send_quiz_question(update, context, quiz_question)


def start_command_handler(update, context):
    chat_id, user_name = get_chat_id_user(update, context)
    APIClient.submit_user(chat_id)
    send_text_message(update, context, BotConfig.MESSAGES["start"][BotConfig.LANG])
    start_dummy_poll(update, context)
    
    
def main():
    if BotConfig.TELEGRAM_TOKEN == "":
        raise ValueError("Could not find TOKEN for the bot")
    updater = Updater(BotConfig.TELEGRAM_TOKEN, use_context=True)
    dp = updater.dispatcher
    dp.add_handler(CommandHandler("start", start_command_handler))
    dp.add_handler(CommandHandler("quiz", start_poll))
    dp.add_handler(MessageHandler(Filters.text, echo_handler))
    dp.add_handler(PollHandler(poll_response_handler, 
                               pass_chat_data=True, 
                               pass_user_data=True))
    if BotConfig.MODE != "polling":
        raise ValueError("Polling MODE is only available")
    updater.start_polling()
    
class BotConfig:
    PORT = int(os.environ.get("TELEGRAM_PORT", 3978))
    API_URL = os.environ.get("TELEGRAM_BOT_API_URL", "")
    API_PORT = int(os.environ.get("TELEGRAM_BOT_API_PORT", ""))
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
    MODE = os.environ.get("TELEGRAM_MODE", "polling")
    WEBHOOK_URL = os.environ.get("TELEGRAM_WEBHOOK_URL", "")

    LOG_LEVEL = os.environ.get("TELEGRAM_LOG_LEVEL", "INFO").upper()
    
    MESSAGES = {"start": {"en": "Lets start. Check you first",
                          "ru": "Давайте начнем. Простой тест для начала"},
                "answer": {"en": "Correct answer is:",
                           "ru": "Правильный ответ:"},
                "nopolls": {"en": "No active polls",
                            "ru": "Нет доступных опросов"}
               }
    QUIZES = {"dummy": {"en": ("What is liquid?",  ["wood", "ice", "water", "stone"], 2, None),
                        "ru": ("Что является жидкостью?",  ["дерево", "лед", "вода", "камень"], 2, None)}
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
