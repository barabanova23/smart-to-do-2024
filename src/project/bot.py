from datetime import datetime, timedelta
from src.project.api import googleapi, todoistapi
import telebot
import urllib.parse
import re
import requests
from fastapi import FastAPI, Request
import threading
import uvicorn
import json
import signal
from config import BOT_TOKEN, REDIRECT_URI, GOOGLE_CLIENT_ID, TODOIST_CLIENT_ID, GOOGLE_CLIENT_SECRET, TODOIST_CLIENT_SECRET, YANDEX_IAM_TOKEN

from const import (
    HTTP_OK,
    HTTP_NO_CONTENT,
    MODEL_URI,
    DEFAULT_COMPLETION_OPTIONS,
    SYSTEM_MESSAGE_GOOGLE,
    SYSTEM_MESSAGE_TODOIST,
    DELTA_TOMORROW,
    DELTA_AFTER_TOMORROW,
    WEEKDAY_R,
    DAYS_IN_WEEK,
    MONTH_R,
    DATE_R,
    MONTH_MAP,
    TIME_R
)


bot = telebot.TeleBot(BOT_TOKEN)
user_data = {}
app = FastAPI()


# ======== Вспомогательные функции для подключения ========
def save_user_token(chat_id, key, token):
    if chat_id not in user_data:
        user_data[chat_id] = {}
    user_data[chat_id][key] = token


def get_user_token(chat_id, key):
    return user_data.get(chat_id, {}).get(key)


def generate_google_auth_url():
    """Генерирует ссылку авторизации Google."""
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI + "/google",
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def generate_todoist_auth_url():
    """Генерирует ссылку авторизации Todoist."""
    base_url = "https://todoist.com/oauth/authorize"
    params = {
        "client_id": TODOIST_CLIENT_ID,
        "scope": "data:read_write",
        "redirect_uri": REDIRECT_URI + "/todoist",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def exchange_google_code_for_token(code):
    """Обменивает код Google на токен."""
    url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI + "/google",
        "grant_type": "authorization_code",
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")


def exchange_todoist_code_for_token(code):
    """Обменивает код Todoist на токен."""
    url = "https://todoist.com/oauth/access_token"
    data = {
        "code": code,
        "client_id": TODOIST_CLIENT_ID,
        "client_secret": TODOIST_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI + "/todoist",
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")


# ======== Telegram Bot Настройка аккаунта ========
@bot.message_handler(commands=['start'])
def start(message):
    welcome_message = (
        "Привет! Я WorkLifeBalanceBot. Я помогу тебе управлять твоими встречами и задачами.\n\n"
        "🔹 Напиши мне что-нибудь вроде:\n"
        "   - 'Поставь встречу с коллегами завтра в 15:00'\n"
        "   - 'Напомни позвонить врачу до 28 декабря'\n\n"
        "📌 Для настройки доступа к Google Calendar и Todoist используй команду /setup.\n"
        "ℹ️ Для справки по использованию напиши /help."
    )
    bot.send_message(message.chat.id, welcome_message)


@bot.message_handler(commands=['help'])
def help_command(message):
    help_message = (
        "🔹 Доступные команды:\n\n"
        "/start — Приветственное сообщение и информация о боте.\n"
        "/setup — Настройка доступа к Google Calendar и Todoist.\n"
        "/add_event — Добавить событие в Google Calendar.\n"
        "/list_events — Показать список запланированных событий.\n"
        "/delete_event — Удалить событие из Google Calendar.\n"
        "/add_task — Добавить задачу в Todoist.\n"
        "/list_tasks — Показать список задач из Todoist.\n"
        "/delete_task — Удалить задачу из Todoist.\n\n"
        "💡 Пример использования:\n"
        "- 'Встречаюсь с коллегами завтра в 15:00' — Событие 'встреча с коллегами' успешно добавлено в Google Calendar.\n"
        "- 'Напомни про свидание завтра в семь вечера' — Задача 'свидание' успешно добавлена в проект.\n\n"
        "Для корректной работы авторизуйтесь с помощью команды /setup."
    )
    bot.send_message(message.chat.id, help_message)


@bot.message_handler(commands=['setup'])
def setup(message):
    google_auth_url = generate_google_auth_url()
    todoist_auth_url = generate_todoist_auth_url()
    setup_message = (
        "Для настройки сервисов выполните следующие шаги:\n\n"
        f"1️⃣ Авторизуйтесь в Google: [Авторизация Google]({google_auth_url})\n"
        f"2️⃣ Авторизуйтесь в Todoist: [Авторизация Todoist]({todoist_auth_url})\n\n"
        "После завершения авторизации вы получите коды. "
        "Отправьте их мне в формате:\n"
        "- `Google: ваш_код`\n"
        "- `Todoist: ваш_код`."
    )
    bot.send_message(message.chat.id, setup_message, parse_mode="Markdown")


@bot.message_handler(func=lambda message: message.text.startswith("Google:"))
def handle_google_token(message):
    chat_id = message.chat.id
    google_token = message.text.split("Google:")[1].strip()

    if google_token:
        save_user_token(chat_id, "google_token", google_token)
        bot.send_message(chat_id, "Токен Google успешно сохранён!\nВведите /add_event если хотите добавить событие\nВведите /list_events если хотите увидеть список всех запланированных событий\nВведите /delete_event если хотите удалить событие")
    else:
        bot.send_message(chat_id, "Не удалось сохранить токен Google. Попробуйте снова.")


@bot.message_handler(func=lambda message: message.text.startswith("Todoist:"))
def handle_todoist_token(message):
    chat_id = message.chat.id
    todoist_token = message.text.split("Todoist:")[1].strip()

    if todoist_token:
        save_user_token(chat_id, "todoist_token", todoist_token)
        bot.send_message(chat_id, "Токен Todoist успешно сохранён!\nВведите /add_task если хотите добавить событие\nВведите /list_tasks если хотите увидеть список всех запланированных событий\nВведите /delete_task если хотите удалить событие")
    else:
        bot.send_message(chat_id, "Не удалось сохранить токен Todoist. Попробуйте снова.")


# ======== FastAPI Колбэки ========
@app.get("/callback/google")
async def google_callback(request: Request):
    """Обрабатывает колбэк от Google."""
    code = request.query_params.get("code")
    if code:
        token = exchange_google_code_for_token(code)
        if token:
            return {"message": "Google authorisation completed!", "token": token}
        return {"message": "Google authorisation error"}
    return {"message": "Authorisation code missing"}


@app.get("/callback/todoist")
async def todoist_callback(request: Request):
    """Обрабатывает колбэк от Todoist."""
    code = request.query_params.get("code")
    if code:
        token = exchange_todoist_code_for_token(code)
        if token:
            return {"message": "Todoist authorisation completed!", "token": token}
        return {"message": "Todoist authorisation error"}
    return {"message": "Authorisation code missing"}


# ======== TODOIST ========
@bot.message_handler(commands=['add_task'])
def add_task(message):
    chat_id = message.chat.id
    todoist_token = get_user_token(chat_id, "todoist_token")
    if not todoist_token:
        bot.send_message(chat_id, "Вы не авторизованы в Todoist. Используйте /setup.")
        return

    projects = todoistapi.get_todoist_projects(todoist_token)
    if not projects or "error" in projects:
        bot.send_message(chat_id, "Не удалось получить список проектов.")
        return

    response = "Выберите проект (пришлите номер проекта):\n"
    for idx, project in enumerate(projects):
        response += f"{idx + 1}. {project['name']} (ID: {project['id']})\n"
    bot.send_message(chat_id, response)

    bot.register_next_step_handler(message, process_project_selection, projects)


def process_project_selection(message, projects):
    """ Обработка выбора проекта в Todoist. """
    chat_id = message.chat.id
    try:
        selected_index = int(message.text.strip()) - 1
        if 0 <= selected_index < len(projects):
            selected_project_id = projects[selected_index]["id"]
            bot.send_message(chat_id, "Введите описание задачи:")
            bot.register_next_step_handler(message, process_task_creation, selected_project_id)
        else:
            bot.send_message(chat_id, "Неверный выбор. Попробуйте снова.")
    except ValueError:
        bot.send_message(chat_id, "Неверный ввод. Укажите номер проекта.")


def process_task_creation(message, project_id):
    """ Обработка текста задачи."""
    chat_id = message.chat.id
    todoist_token = get_user_token(chat_id, "todoist_token")
    user_input = message.text.strip()

    try:
        task_details = extract_event_details(user_input, False)
        task_name = task_details["title"]
        due_string = task_details["start_time"]

        task = todoistapi.create_task_in_project(todoist_token, task_name, project_id, due_string)
        if "error" not in task:
            bot.send_message(chat_id, f"Задача '{task_name}' успешно добавлена в проект.")
        else:
            bot.send_message(chat_id, f"Ошибка при создании задачи: {task['error']}")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")


def get_todoist_tasks(token):
    """Получает список всех задач."""
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == HTTP_OK:
        return response.json()
    else:
        return {"error": response.text}


@bot.message_handler(commands=['list_tasks'])
def list_tasks(message):
    """Обработчик команды /list_tasks."""
    chat_id = message.chat.id
    todoist_token = get_user_token(chat_id, "todoist_token")

    if not todoist_token:
        bot.send_message(chat_id, "Вы не авторизованы в Todoist. Используйте /setup.")
        return

    tasks = get_todoist_tasks(todoist_token)
    if "error" in tasks:
        bot.send_message(chat_id, f"Ошибка при получении задач: {tasks['error']}")
        return

    if not tasks:
        bot.send_message(chat_id, "У вас нет активных задач.")
        return
    response = "Список ваших задач:\n"
    for idx, task in enumerate(tasks):
        print(task)
        due_date = task.get('due', {}).get('string')
        print(due_date)
        if due_date:
            parsed_date = datetime.fromisoformat(due_date)
            formatted_date = parsed_date.strftime("%d %B %Y year %H:%M")
            response += f"{idx + 1}. {task['content']} (дата: {formatted_date})\n"
        else:
            response += f"{idx + 1}. {task['content']}\n"
    bot.send_message(chat_id, response)


def delete_todoist_task(token, task_id):
    """Удаление задачи."""
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.delete(url, headers=headers)

    if response.status_code == HTTP_NO_CONTENT:
        return True
    else:
        return {"error": response.text}


def process_task_deletion(message, tasks):
    """Обработка удаления выбранной задачи."""
    chat_id = message.chat.id
    todoist_token = get_user_token(chat_id, "todoist_token")

    try:
        selected_index = int(message.text.strip()) - 1
        if 0 <= selected_index < len(tasks):
            task_id = tasks[selected_index]["id"]
            success = delete_todoist_task(todoist_token, task_id)
            if success is True:
                bot.send_message(chat_id, "Задача успешно удалена.")
            else:
                bot.send_message(chat_id, f"Ошибка при удалении задачи: {success['error']}")
        else:
            bot.send_message(chat_id, "Неверный выбор. Попробуйте снова.")
    except ValueError:
        bot.send_message(chat_id, "Неверный ввод. Укажите номер задачи.")


@bot.message_handler(commands=['delete_task'])
def delete_task(message):
    """Обработчик команды /delete_task."""
    chat_id = message.chat.id
    todoist_token = get_user_token(chat_id, "todoist_token")

    if not todoist_token:
        bot.send_message(chat_id, "Вы не авторизованы в Todoist. Используйте /setup.")
        return

    tasks = get_todoist_tasks(todoist_token)
    if "error" in tasks:
        bot.send_message(chat_id, f"Ошибка при получении задач: {tasks['error']}")
        return

    if not tasks:
        bot.send_message(chat_id, "У вас нет активных задач.")
        return

    response = "Выберите задачу для удаления:\n"
    for idx, task in enumerate(tasks):
        due_date = task.get('due', {}).get('string')
        if due_date:
            parsed_date = datetime.fromisoformat(due_date)
            formatted_date = parsed_date.strftime("%d %B %Y года %H:%M")
            response += f"{idx + 1}. {task['content']} (дата: {formatted_date})\n"
        else:
            response += f"{idx + 1}. {task['content']}\n"
    bot.send_message(chat_id, response)

    bot.register_next_step_handler(message, process_task_deletion, tasks)


# ======== GOOGLE ========
@bot.message_handler(commands=['add_event'])
def add_event(message):
    chat_id = message.chat.id
    google_token = get_user_token(chat_id, "google_token")

    if not google_token:
        bot.send_message(chat_id, "Вы не авторизованы в Google. Используйте /setup.")
        return

    bot.send_message(chat_id, "Пожалуйста, введите информацию о событии:")
    bot.register_next_step_handler(message, process_event_details_nlp)


@bot.message_handler(commands=['list_events'])
def list_events(message):
    chat_id = message.chat.id
    google_token = get_user_token(chat_id, "google_token")
    if not google_token:
        bot.send_message(chat_id, "Вы не авторизованы в Google. Используйте /setup.")
        return
    try:
        events = googleapi.list_google_events(google_token)
        if not events:
            bot.send_message(chat_id, "У вас нет ближайших событий.")
        else:
            response = "Ваши ближайшие события:\n"
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                parsed_date = datetime.fromisoformat(start)
                formatted_date = parsed_date.strftime("%d %B %Y года %H:%M")
                response += f"- {event['summary']} ({formatted_date})\n"
            bot.send_message(chat_id, response)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при получении событий: {str(e)}")


@bot.message_handler(commands=['delete_event'])
def delete_event_start(message):
    """Удаление события. Список событий для удаления."""
    chat_id = message.chat.id
    google_token = get_user_token(chat_id, "google_token")

    if not google_token:
        bot.send_message(chat_id, "Вы не авторизованы в Google. Используйте /setup.")
        return

    try:
        events = googleapi.list_google_events(google_token)
        if not events:
            bot.send_message(chat_id, "У вас нет ближайших событий для удаления.")
            return

        event_list = "Ваши ближайшие события:\n"
        for idx, event in enumerate(events, start=1):
            start = event['start'].get('dateTime', event['start'].get('date'))
            parsed_date = datetime.fromisoformat(start)
            formatted_date = parsed_date.strftime("%d %B %Y года %H:%M")
            event_list += f"{idx}. {event['summary']} ({formatted_date})\n"

        bot.send_message(chat_id, event_list)
        bot.send_message(chat_id, "Напишите номер из списка, чтобы удалить событие по номеру.")
        bot.register_next_step_handler(message, process_event_deletion, events)

    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при получении событий: {str(e)}")


def process_event_deletion(message, events):
    """Обрабатывает запрос удаления события."""
    chat_id = message.chat.id
    google_token = get_user_token(chat_id, "google_token")

    try:
        text = message.text.lower()
        parts = text.split()
        if len(parts) != 1 or not parts[0].isdigit():
            bot.send_message(chat_id,
                             "Неверный формат. Убедитесь, что вы указали номер события, например: '2'.")
            return

        event_index = int(parts[0]) - 1
        if event_index < 0 or event_index >= len(events):
            bot.send_message(chat_id, "Неверный номер события. Пожалуйста, выберите номер из списка.")
            return

        event_id = events[event_index]['id']
        googleapi.delete_google_event(google_token, event_id)

        bot.send_message(chat_id, f"Событие '{events[event_index]['summary']}' успешно удалено.")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при удалении события: {str(e)}")


# ======== YANDEX LLM ========
YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"


def form_payload(request_text, google_todoist):
    """Формируем тело запроса к Yandex LLM API."""
    if google_todoist:
        return json.dumps({
            "modelUri": MODEL_URI,
            "completionOptions": DEFAULT_COMPLETION_OPTIONS,
            "messages": [
                {
                    "role": "system",
                    "text": SYSTEM_MESSAGE_GOOGLE
                },
                {
                    "role": "user",
                    "text": request_text
                }
            ]
        })
    return json.dumps({
        "modelUri": MODEL_URI,
        "completionOptions": DEFAULT_COMPLETION_OPTIONS,
        "messages": [
            {
                "role": "system",
                "text": SYSTEM_MESSAGE_TODOIST
            },
            {
                "role": "user",
                "text": request_text
            }
        ]
    })


def extract_event_details(request_text, google_todoist):
    """Отправляет запрос к Yandex LLM API для анализа текста."""
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = form_payload(request_text, google_todoist)
    response = requests.post(YANDEX_API_URL, headers=headers, data=payload)

    if response.status_code == 200:
        result = response.json()
        text = result['result']['alternatives'][0]['message']['text']

        return parse_event_text(text)
    else:
        raise Exception(f"Ошибка при вызове Yandex LLM API: {response.status_code} {response.text}")


def parse_event_text(text):
    """Парсинг текста от Yandex LLM."""
    print(text)
    title_match = re.search(r"(?:Событие:|Задача:) (.+?)\.", text)
    start_time_match = re.search(r"Начало: (.+?)\К", text)
    end_time_match = re.search(r"Конец: (.*)", text)

    title = title_match.group(1) if title_match else "Неизвестное событие"
    start_time = start_time_match.group(1) if start_time_match else None
    end_time = end_time_match.group(1) if end_time_match else None

    if start_time and not re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", start_time):
        start_time = convert_relative_to_iso(start_time)
    if end_time and not re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", end_time):
        end_time = convert_relative_to_iso(end_time)
    return {"title": title, "start_time": start_time, "end_time": end_time}


def convert_relative_to_iso(time_str):
    now = datetime.now()
    print(f"Original time string: {time_str}")

    if "не указан" in time_str:
        return None

    if "послезавтра" in time_str:
        target_date = now + timedelta(days=DELTA_AFTER_TOMORROW)
    elif "завтра" in time_str:
        target_date = now + timedelta(days=DELTA_TOMORROW)
    elif "сегодня" in time_str:
        target_date = now
    elif re.search(WEEKDAY_R, time_str):
        weekdays = {
            "понедельник": 0, "вторник": 1, "среда": 2, "четверг": 3,
            "пятница": 4, "суббота": 5, "воскресенье": 6
        }
        weekday_name = re.search(WEEKDAY_R, time_str).group(1)
        target_weekday = weekdays[weekday_name]
        current_weekday = now.weekday()

        days_ahead = (target_weekday - current_weekday + DAYS_IN_WEEK) % DAYS_IN_WEEK
        if days_ahead == 0:
            days_ahead = DAYS_IN_WEEK
        target_date = now + timedelta(days=days_ahead)
    elif re.search(MONTH_R, time_str):
        match = re.search(MONTH_R, time_str)
        day, month_name = match.groups()
        month = MONTH_MAP[month_name]
        year_match = re.search(r"\d{4} года", time_str)
        if year_match:
            year = int(year_match.group().split()[0])
        else:
            if not (month == 12 and 23 <= int(day) <= 31):
                year = now.year + 1
            else:
                year = now.year

        target_date = datetime(year, month, int(day), 0, 0, 0)
    elif re.match(DATE_R, time_str):
        try:
            data = time_str.split(",") if "," in time_str else time_str.split(" ")
            day, month, year = map(int, data[0].split("."))
            if len(data) > 1 and re.match(TIME_R, data[1].strip()):
                hour, minute = map(int, data[1].strip().split(":"))
            else:
                hour, minute = 0, 0
            dt = datetime(year, month, day, hour, minute)
            return dt.replace(microsecond=0).isoformat()
        except ValueError as e:
            raise ValueError(f"Ошибка обработки времени: {time_str}. Причина: {e}")
    else:
        raise ValueError(f"Не удалось распознать дату: {time_str}")
    time_match = re.search(TIME_R, time_str)
    if time_match:
        target_time = time_match.group()
        target_datetime = datetime.strptime(f"{target_date.date()} {target_time}", "%Y-%m-%d %H:%M")
    else:
        target_datetime = target_date.replace(hour=0, minute=0)

    print(f"Processed datetime: {target_datetime.replace(microsecond=0).isoformat()}")
    return target_datetime.replace(microsecond=0).isoformat()



def process_event_details_nlp(message):
    chat_id = message.chat.id
    google_token = get_user_token(chat_id, "google_token")
    user_input = message.text.strip()

    try:
        event_data = extract_event_details(user_input, True)

        if not event_data.get("title") or not event_data.get("start_time"):
            bot.send_message(chat_id,
                             "Не удалось распознать событие. Пожалуйста, введите информацию о событии еще раз.")
            bot.register_next_step_handler(message, process_event_details_nlp)
            return

        summary = event_data.get("title")
        start_time_str = event_data.get("start_time")
        end_time_str = event_data.get("end_time") or start_time_str

        start_time = googleapi.parse_datetime_to_iso(start_time_str)
        end_time = googleapi.parse_datetime_to_iso(end_time_str)

        event = googleapi.create_google_event(google_token, summary, start_time, end_time)
        bot.send_message(chat_id, f"Событие '{event['summary']}' успешно добавлено в Google Calendar.")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {str(e)}")


# ======== Запуск сервера и бота ========
def start_fastapi():
    uvicorn.run(app, host="0.0.0.0", port=8000)


def start_telegram_bot():
    bot.polling(none_stop=True)


if __name__ == "__main__":
    threading.Thread(target=start_fastapi).start()
    threading.Thread(target=start_telegram_bot).start()


def handle_exit(signum, frame):
    bot.stop_polling()
    print("Завершение работы приложения...")
    exit(0)


signal.signal(signal.SIGINT, handle_exit)
signal.signal(signal.SIGTERM, handle_exit)
