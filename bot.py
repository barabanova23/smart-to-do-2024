from datetime import datetime, timezone, timedelta
import googleapi
import telebot
import todoistapi
import urllib.parse
import re
import requests
from fastapi import FastAPI, Request
import threading
import uvicorn
import json
from config import BOT_TOKEN, GOOGLE_CLIENT_ID, TODOIST_CLIENT_ID, GOOGLE_CLIENT_SECRET, TODOIST_CLIENT_SECRET,\
    YANDEX_IAM_TOKEN

bot = telebot.TeleBot(BOT_TOKEN)
REDIRECT_URI = "http://127.0.0.1:8000/callback"

# Хранилище данных пользователя
user_data = {}

# FastAPI сервер
app = FastAPI()


# ======== Вспомогательные функции ========
def save_user_token(chat_id, key, token):
    """Сохраняет токен в глобальное хранилище."""
    if chat_id not in user_data:
        user_data[chat_id] = {}
    user_data[chat_id][key] = token


def get_user_token(chat_id, key):
    """Извлекает токен из хранилища."""
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


# ======== Telegram Bot Команды ========
@bot.message_handler(commands=['start'])
def start(message):
    """Приветственное сообщение."""
    welcome_message = (
        "Привет! Я WorkLifeBalanceBot. Я помогу тебе управлять твоими встречами и задачами.\n\n"
        "🔹 Напиши мне что-нибудь вроде:\n"
        "   - 'Поставь встречу с коллегами завтра в 15:00'\n"
        "   - 'Напомни позвонить врачу до пятницы'\n\n"
        "📌 Для настройки доступа к Google Calendar и Todoist используй команду /setup.\n"
        "ℹ️ Для справки по использованию напиши /help."
    )
    bot.send_message(message.chat.id, welcome_message)


@bot.message_handler(commands=['setup'])
def setup(message):
    """Отправляет ссылки для авторизации."""
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
        save_user_token(chat_id, "google_token", google_token)  # Сохраняем токен
        bot.send_message(chat_id, '''Токен Google успешно сохранён!\nВведите /add_event если хотите добавить событие\nВведите /list_events если хотите увидеть список всех запланированных событий\nВведите /delete_event если хотите удалить событие''')
    else:
        bot.send_message(chat_id, "Не удалось сохранить токен Google. Попробуйте снова.")

@bot.message_handler(func=lambda message: message.text.startswith("Todoist:"))
def handle_todoist_token(message):
    chat_id = message.chat.id
    todoist_token = message.text.split("Todoist:")[1].strip()

    if todoist_token:
        save_user_token(chat_id, "todoist_token", todoist_token)  # Сохраняем токен
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
            return {"message": "Google авторизация успешна!", "token": token}
        return {"message": "Ошибка авторизации Google"}
    return {"message": "Код авторизации отсутствует"}


@app.get("/callback/todoist")
async def todoist_callback(request: Request):
    """Обрабатывает колбэк от Todoist."""
    code = request.query_params.get("code")
    if code:
        token = exchange_todoist_code_for_token(code)
        if token:
            return {"message": "Todoist авторизация успешна!", "token": token}
        return {"message": "Ошибка авторизации Todoist"}
    return {"message": "Код авторизации отсутствует"}

# ======== FastAPI Todoist ========
@bot.message_handler(commands=['add_task'])
def add_task(message):
    """
    Основной обработчик для добавления задачи.
    """
    chat_id = message.chat.id
    todoist_token = get_user_token(chat_id, "todoist_token")
    if not todoist_token:
        bot.send_message(chat_id, "Вы не авторизованы в Todoist. Используйте /setup.")
        return

    projects = todoistapi.get_todoist_projects(todoist_token)
    if not projects or "error" in projects:
        bot.send_message(chat_id, "Не удалось получить список проектов.")
        return

    response = "Выберите проект:\n"
    for idx, project in enumerate(projects):
        response += f"{idx + 1}. {project['name']} (ID: {project['id']})\n"
    bot.send_message(chat_id, response)

    bot.register_next_step_handler(message, process_project_selection, projects)


def process_project_selection(message, projects):
    """
    Обработка выбора проекта.
    """
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
    """
    Обработка создания задачи.
    """
    chat_id = message.chat.id
    todoist_token = get_user_token(chat_id, "todoist_token")
    user_input = message.text.strip()

    try:
        # Используем Yandex LLM для извлечения деталей задачи
        print(user_input)
        task_details = extract_event_details(user_input, True)
        print(task_details)
        task_name = task_details["title"]
        due_string = task_details["start_time"]

        # Добавляем задачу в Todoist
        task = todoistapi.create_task_in_project(todoist_token, task_name, project_id, due_string)
        if "error" not in task:
            bot.send_message(chat_id, f"Задача '{task_name}' успешно добавлена в проект.")
        else:
            bot.send_message(chat_id, f"Ошибка при создании задачи: {task['error']}")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")

def get_todoist_tasks(token):
    """
    Получает список всех задач из Todoist.
    """
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()  # Возвращает список задач
    else:
        return {"error": response.text}  # Возвращает ошибку, если запрос не удался


@bot.message_handler(commands=['list_tasks'])
def list_tasks(message):
    """
    Обработчик команды /list_tasks для вывода списка задач.
    """
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
        response += f"{idx + 1}. {task['content']} (ID: {task['id']})\n"
    bot.send_message(chat_id, response)


def delete_todoist_task(token, task_id):
    """
    Удаляет задачу в Todoist по её ID.
    """
    url = f"https://api.todoist.com/rest/v2/tasks/{task_id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.delete(url, headers=headers)

    if response.status_code == 204:
        return True  # Удаление успешно
    else:
        return {"error": response.text}  # Возвращает ошибку, если запрос не удался

@bot.message_handler(commands=['delete_task'])
def delete_task(message):
    """
    Обработчик команды /delete_task для удаления задачи.
    """
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
        response += f"{idx + 1}. {task['content']} (ID: {task['id']})\n"
    bot.send_message(chat_id, response)

    bot.register_next_step_handler(message, process_task_deletion, tasks)


def process_task_deletion(message, tasks):
    """
    Обработка удаления выбранной задачи.
    """
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



# ======== FastAPI Google ========
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
                response += f"- {event['summary']} ({start})\n"
            bot.send_message(chat_id, response)
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при получении событий: {str(e)}")


@bot.message_handler(commands=['delete_event'])
def delete_event_start(message):
    """
    Начало процесса удаления события. Показывает список событий.
    """
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

        # Генерация списка событий для пользователя
        event_list = "Ваши ближайшие события:\n"
        for idx, event in enumerate(events, start=1):
            start = event['start'].get('dateTime', event['start'].get('date'))
            event_list += f"{idx}. {event['summary']} ({start})\n"

        bot.send_message(chat_id, event_list)
        bot.send_message(chat_id, "Напишите номер из списка, чтобы удалить событие по номеру.")
        bot.register_next_step_handler(message, process_event_deletion, events)

    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при получении событий: {str(e)}")


def process_event_deletion(message, events):
    """
    Обрабатывает запрос на удаление события по номеру.
    """
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


YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

# Константы
FOLDER_ID = "b1gqhf0knkfj54l8590v"  # Ваш идентификатор каталога

def form_payload(request_text, google_todoist):
    """
    Формируем тело запроса к Yandex LLM API.
    """
    print(google_todoist)
    if google_todoist:
        return json.dumps({
            "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite/latest",
            "completionOptions": {
                "stream": False,
                "temperature": 0.2,
                "maxTokens": 2000
            },
            "messages": [
                {
                    "role": "system",
                    "text": "Ты - ассистент, который помогает планировать события. "
                            "Анализируй запросы пользователя и возвращай следующую информацию: "
                            "1. Название события, 2. Время начала события, 3. Время окончания события (если указано). "
                            "Формат ответа: 'Событие: <название>. Начало: <дата (день) и время>. Конец: <дата (день) и время>'."
                },
                {
                    "role": "user",
                    "text": request_text
                }
            ]
        })
    return json.dumps({
        "modelUri": f"gpt://{FOLDER_ID}/yandexgpt-lite/latest",
        "completionOptions": {
            "stream": False,
            "temperature": 0.2,
            "maxTokens": 2000
        },
        "messages": [
            {
                "role": "system",
                "text": "Ты - ассистент, который помогает планировать задачи. "
                        "Анализируй запросы пользователя и возвращай следующую информацию: "
                        "1. Название задачи, 2. Дата и время задачи (если указано), 3. Время окончания задачи (если указано). "
                        "Формат ответа: 'Задача: <название>. Начало: <дата (день) и время>. Конец: <дата (день) и время>'."
            },
            {
                "role": "user",
                "text": request_text
            }
        ]
    })

def extract_event_details(request_text, google_todoist):
    """
    Отправляет запрос к Yandex LLM API для анализа текста.
    """
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json"
    }
    payload = form_payload(request_text, google_todoist)
    response = requests.post(YANDEX_API_URL, headers=headers, data=payload)

    if response.status_code == 200:
        result = response.json()
        text = result['result']['alternatives'][0]['message']['text']
        print(text)

        # Парсим текст ответа для извлечения данных
        return parse_event_text(text)
    else:
        raise Exception(f"Ошибка при вызове Yandex LLM API: {response.status_code} {response.text}")

def parse_event_text(text):
    """
    Парсинг текста от Yandex LLM для извлечения данных о событии.
    """
    # Пример текста: "Событие: маникюр. Начало: 2024-12-05T12:00. Конец: 2024-12-05T13:00."
    print(text)
    title_match = re.search(r"Событие: (.+?)\.", text)
    start_time_match = re.search(r"Начало: (.+?)\К", text)
    end_time_match = re.search(r"Конец: ([\d\-T:\+]+)", text)
    print(start_time_match)
    # Извлекаем данные
    title = title_match.group(1) if title_match else "Неизвестное событие"
    start_time = start_time_match.group(1) if start_time_match else None
    end_time = end_time_match.group(1) if end_time_match else None
    # Если дата не в ISO 8601, преобразуем
    if start_time and not re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", start_time):
        start_time = convert_relative_to_iso(start_time)
    if end_time and not re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}", end_time):
        end_time = convert_relative_to_iso(end_time)
    return {"title": title, "start_time": start_time, "end_time": end_time}

def convert_relative_to_iso(time_str):
    now = datetime.now()
    print("Преобразуем строку:", time_str)

    # Обработка ключевых слов
    if "завтра" in time_str:
        target_date = now + timedelta(days=1)
    elif "послезавтра" in time_str:
        target_date = now + timedelta(days=2)
    elif "сегодня" in time_str:
        target_date = now
    elif re.search(r"(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)", time_str):
        weekdays = {
            "понедельник": 0, "вторник": 1, "среда": 2, "четверг": 3,
            "пятница": 4, "суббота": 5, "воскресенье": 6
        }
        weekday_name = re.search(r"(понедельник|вторник|среда|четверг|пятница|суббота|воскресенье)", time_str).group(1)
        target_weekday = weekdays[weekday_name]
        current_weekday = now.weekday()

        # Рассчитываем, сколько дней вперед до нужного дня недели
        days_ahead = (target_weekday - current_weekday + 7) % 7
        if days_ahead == 0:  # Если указанный день - это сегодня
            days_ahead = 7
        target_date = now + timedelta(days=days_ahead)
    elif re.search(r"\d{1,2} (января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)", time_str):
        # Обработка формата "14 декабря"
        month_map = {
            "января": 1, "февраля": 2, "марта": 3, "апреля": 4, "мая": 5, "июня": 6,
            "июля": 7, "августа": 8, "сентября": 9, "октября": 10, "ноября": 11, "декабря": 12
        }
        day, month_name = re.search(r"(\d{1,2}) (января|февраля|марта|апреля|мая|июня|июля|августа|сентября|октября|ноября|декабря)", time_str).groups()
        month = month_map[month_name]
        target_date = now.replace(day=int(day), month=month, hour=0, minute=0, second=0, microsecond=0)
    elif re.match(r"\d{1,2}\.\d{1,2}\.\d{4}", time_str):
        # Обработка формата "14.12.2024"
        data = time_str.split(",")
        if len(data) == 1:
            data = time_str.split(" ")
        day, month, year = map(int, data[0].split("."))
        hour, minute = map(int, data[1].split(":"))
        dt = datetime(year, month, day, hour, minute)
        return dt.isoformat()
    else:
        raise ValueError(f"Не удалось распознать дату: {time_str}")

    # Извлекаем время из строки, если указано
    time_match = re.search(r"\d{1,2}:\d{2}", time_str)
    if time_match:
        target_time = time_match.group()
        target_datetime = datetime.strptime(f"{target_date.date()} {target_time}", "%Y-%m-%d %H:%M")
    else:
        target_datetime = target_date.replace(hour=0, minute=0)

    return target_datetime.isoformat()


try:
    user_request = "в понедельник у меня встреча с другом в 19.30"
    result = extract_event_details(user_request, True)
    print("Ответ от Yandex LLM API:", result)
except Exception as e:
    print("Ошибка:", e)


@bot.message_handler(commands=['add_event'])
def add_event(message):
    chat_id = message.chat.id
    google_token = get_user_token(chat_id, "google_token")

    if not google_token:
        bot.send_message(chat_id, "Вы не авторизованы в Google. Используйте /setup.")
        return

    bot.send_message(chat_id, "Пожалуйста, введите информацию о событии:")
    bot.register_next_step_handler(message, process_event_details_nlp)


def process_event_details_nlp(message):
    chat_id = message.chat.id
    google_token = get_user_token(chat_id, "google_token")
    user_input = message.text.strip()

    try:
        # Вызов Yandex LLM для анализа текста
        event_data = extract_event_details(user_input, True)
        print(event_data)

        # Проверяем, удалось ли распознать событие
        if not event_data.get("title") or not event_data.get("start_time"):
            bot.send_message(chat_id,
                             "Не удалось распознать событие. Пожалуйста, введите информацию о событии еще раз.")
            bot.register_next_step_handler(message, process_event_details_nlp)
            return

        # Получаем название, время начала и окончания
        summary = event_data.get("title")
        start_time_str = event_data.get("start_time")  # Ожидается формат 'YYYY-MM-DD HH:MM'
        end_time_str = event_data.get("end_time") or start_time_str  # Если нет времени окончания, используем время начала

        # Преобразуем время в формат ISO 8601
        start_time = googleapi.parse_datetime_to_iso(start_time_str)
        end_time = googleapi.parse_datetime_to_iso(end_time_str)

        # Создаем событие в Google Calendar
        event = googleapi.create_google_event(google_token, summary, start_time, end_time)
        bot.send_message(chat_id, f"Событие '{event['summary']}' успешно добавлено в Google Calendar.")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка: {str(e)}")


# ======== Запуск сервера и бота ========
def start_fastapi():
    uvicorn.run(app, host="127.0.0.1", port=8000)


def start_telegram_bot():
    bot.polling(none_stop=True)


if __name__ == "__main__":
    threading.Thread(target=start_fastapi).start()
    threading.Thread(target=start_telegram_bot).start()
