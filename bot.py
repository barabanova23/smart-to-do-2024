import googleapi
import telebot
import todoistapi
import urllib.parse
import requests
from fastapi import FastAPI, Request
import threading
import uvicorn
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
        bot.send_message(chat_id, '''Токен Google успешно сохранён!
             Введите /add_event если хотите добавить событие
             Введите /list_events если хотите увидеть список всех запланированных событий
             Введите /delete_event если хотите удалить событие''')
    else:
        bot.send_message(chat_id, "Не удалось сохранить токен Google. Попробуйте снова.")

@bot.message_handler(func=lambda message: message.text.startswith("Todoist:"))
def handle_todoist_token(message):
    chat_id = message.chat.id
    todoist_token = message.text.split("Todoist:")[1].strip()

    if todoist_token:
        save_user_token(chat_id, "todoist_token", todoist_token)  # Сохраняем токен
        bot.send_message(chat_id, "Токен Todoist успешно сохранён!")
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
    chat_id = message.chat.id
    todoist_token = get_user_token(chat_id, "todoist_token")
    if not todoist_token:
        bot.send_message(chat_id, "Вы не авторизованы в Todoist. Используйте /setup.")
        return

    projects = todoistapi.get_todoist_projects(todoist_token)
    if not projects:
        bot.send_message(chat_id, "Не удалось получить список проектов.")
        return

    response = "Выберите проект:\n"
    for idx, project in enumerate(projects):
        response += f"{idx + 1}. {project['name']} (ID: {project['id']})\n"
    bot.send_message(chat_id, response)

    bot.register_next_step_handler(message, process_project_selection, projects)

def process_project_selection(message, projects):
    chat_id = message.chat.id
    try:
        selected_index = int(message.text.strip()) - 1
        if 0 <= selected_index < len(projects):
            selected_project_id = projects[selected_index]["id"]
            bot.send_message(chat_id, "Введите задачу для добавления:")
            bot.register_next_step_handler(message, process_task_creation, selected_project_id)
        else:
            bot.send_message(chat_id, "Неверный выбор. Попробуйте снова.")
    except ValueError:
        bot.send_message(chat_id, "Неверный ввод. Укажите номер проекта.")

def process_task_creation(message, project_id):
    chat_id = message.chat.id
    todoist_token = get_user_token(chat_id, "todoist_token")

    try:
        task_info = message.text.split(";")
        task_content = task_info[0].strip()
        due_string = task_info[1].strip() if len(task_info) > 1 else None

        task = todoistapi.create_task_in_project(todoist_token, task_content, project_id, due_string)
        if "error" not in task:
            bot.send_message(chat_id, f"Задача '{task_content}' успешно добавлена в Todoist.")
        else:
            bot.send_message(chat_id, f"Ошибка при создании задачи: {task['error']}")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")



# ======== FastAPI Google ========

# def process_event_creation(message):
#     chat_id = message.chat.id
#     google_token = get_user_token(chat_id, "google_token")
#
#     try:
#         parts = message.text.split(";")
#         if len(parts) != 3:
#             bot.send_message(
#                 chat_id,
#                 "Ошибка: Убедитесь, что вы ввели данные в формате 'Название события; Дата начала; Дата окончания'."
#             )
#             return
#
#         # Парсинг и преобразование данных
#         summary = parts[0].strip()
#         start_time = googleapi.parse_datetime_to_iso(parts[1].strip())
#         end_time = googleapi.parse_datetime_to_iso(parts[2].strip())
#
#         # Создание события в Google Calendar
#         event = googleapi.create_google_event(google_token, summary, start_time, end_time)
#         bot.send_message(chat_id, f"Событие '{event['summary']}' успешно добавлено в Google Calendar.")
#     except ValueError as ve:
#         bot.send_message(chat_id, f"Ошибка: {str(ve)}")
#     except Exception as e:
#         bot.send_message(chat_id, f"Ошибка при создании события: {str(e)}")


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
        bot.send_message(chat_id, "Напишите, например: 'Удали событие 2', чтобы удалить событие по номеру.")
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
        if not text.startswith("удали событие"):
            bot.send_message(chat_id, "Неверный формат. Напишите, например: 'Удали событие 2'.")
            return

        # Получение номера события из текста
        parts = text.split()
        if len(parts) != 3 or not parts[2].isdigit():
            bot.send_message(chat_id,
                             "Неверный формат. Убедитесь, что вы указали номер события, например: 'Удали событие 2'.")
            return

        event_index = int(parts[2]) - 1
        if event_index < 0 or event_index >= len(events):
            bot.send_message(chat_id, "Неверный номер события. Пожалуйста, выберите номер из списка.")
            return

        # Получение ID события и удаление
        event_id = events[event_index]['id']
        googleapi.delete_google_event(google_token, event_id)

        bot.send_message(chat_id, f"Событие '{events[event_index]['summary']}' успешно удалено.")
    except Exception as e:
        bot.send_message(chat_id, f"Ошибка при удалении события: {str(e)}")


YANDEX_API_URL = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"

def extract_event_details(text):
    """
    Sends text to Yandex LLM API to extract event information.
    """
    headers = {
        "Authorization": f"Bearer {YANDEX_IAM_TOKEN}",
        "Content-Type": "application/json",
    }
    data = {
        "prompt": text,
        "model": "general",
        "temperature": 0.5,
        "maxTokens": 150,
        "topP": 1,
        "stop": ["\n"]
    }
    response = requests.post(YANDEX_API_URL, headers=headers, json=data)

    if response.status_code == 200:
        return response.json()
    else:
        raise Exception(f"Ошибка при вызове Yandex LLM API: {response.text}")



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
        event_data = extract_event_details(user_input)

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
