import telebot
import urllib.parse
import requests
from fastapi import FastAPI, Request
import threading
import uvicorn

# Telegram Bot Token
BOT_TOKEN = "7740852398:AAF-D1841q9RI8GzYiXCPRhmE8ttxVB1c_Q"

bot = telebot.TeleBot(BOT_TOKEN)

# Google и Todoist API ключи
GOOGLE_CLIENT_ID = "748744852574-45frt4u5ns45rq09a9cn3nbiok7tkd60"
TODOIST_CLIENT_ID = "4024b907332d49d687f0556c336681e7"
GOOGLE_CLIENT_SECRET = "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"
TODOIST_CLIENT_SECRET = "e8d27c11d3094ef39be6b2e5a68357dc"

# Redirect URI (обязательно должно совпадать с настройками приложений)
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


# ======== Запуск сервера и бота ========
def start_fastapi():
    uvicorn.run(app, host="127.0.0.1", port=8000)


def start_telegram_bot():
    bot.polling(none_stop=True)


if __name__ == "__main__":
    threading.Thread(target=start_fastapi).start()
    threading.Thread(target=start_telegram_bot).start()
