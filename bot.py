import telebot
import urllib.parse
import requests

BOT_TOKEN = "7740852398:AAF-D1841q9RI8GzYiXCPRhmE8ttxVB1c_Q"

bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start'])
def start(message):
    welcome_message = (
        "Привет! Я WorkLifeBalanceBot. Я помогу тебе управлять твоими встречами и задачами.\n\n"
        "🔹 Напиши мне что-нибудь вроде:\n"
        "   - 'Поставь встречу с коллегами завтра в 15:00'\n"
        "   - 'Напомни позвонить врачу до пятницы'\n\n"
        "📌 Для настройки доступа к Google Calendar и Todoist используй команду /setup.\n"
        "ℹ️ Для справки по использованию напиши /help."
    )
    bot.send_message(message.chat.id, welcome_message)

GOOGLE_CLIENT_ID = "748744852574-45frt4u5ns45rq09a9cn3nbiok7tkd60"
TODOIST_CLIENT_ID = "4024b907332d49d687f0556c336681e7"
GOOGLE_CLIENT_SECRET = "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"
TODOIST_CLIENT_SECRET = "e8d27c11d3094ef39be6b2e5a68357dc"
REDIRECT_URI = "http://127.0.0.1:5000"

user_data = {}

# ===== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ =====
def save_user_token(chat_id, key, token):
    """Сохраняет токен в глобальное хранилище."""
    if chat_id not in user_data:
        user_data[chat_id] = {}
    user_data[chat_id][key] = token


def get_user_token(chat_id, key):
    """Извлекает токен из хранилища."""
    return user_data.get(chat_id, {}).get(key)


def generate_google_auth_url():
    """Генерирует ссылку авторизации для Google."""
    base_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": GOOGLE_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "response_type": "code",
        "scope": "https://www.googleapis.com/auth/calendar",
        "access_type": "offline",
        "prompt": "consent",
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def generate_todoist_auth_url():
    """Генерирует ссылку авторизации для Todoist."""
    base_url = "https://todoist.com/oauth/authorize"
    params = {
        "client_id": TODOIST_CLIENT_ID,
        "scope": "data:read_write",
        "redirect_uri": REDIRECT_URI,
    }
    return f"{base_url}?{urllib.parse.urlencode(params)}"


def exchange_google_code_for_token(code):
    """Обменивает код Google на токен."""
    url = "https://oauth2.googleapis.com/token"
    data = {
        "code": code,
        "client_id": GOOGLE_CLIENT_ID,
        "client_secret": GOOGLE_CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
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
        "redirect_uri": REDIRECT_URI,
    }
    response = requests.post(url, data=data)
    return response.json().get("access_token")


# ===== ОБРАБОТЧИКИ КОМАНД =====

@bot.message_handler(commands=['setup'])
def setup(message):
    """Обрабатывает команду /setup."""
    google_auth_url = generate_google_auth_url()
    todoist_auth_url = generate_todoist_auth_url()

    setup_message = (
        "Для настройки сервисов выполните следующие шаги:\n\n"
        "1️⃣ Авторизуйтесь в Google: [Авторизация Google]({google_url})\n"
        "2️⃣ Авторизуйтесь в Todoist: [Авторизация Todoist]({todoist_url})\n\n"
        "После завершения авторизации вы получите коды. "
        "Отправьте их мне в формате:\n"
        "- `Google: ваш_код`\n"
        "- `Todoist: ваш_код`."
    )

    bot.send_message(
        message.chat.id,
        setup_message.format(google_url=google_auth_url, todoist_url=todoist_auth_url),
        parse_mode="Markdown",
    )


@bot.message_handler(func=lambda message: True)
def handle_code(message):
    """Обрабатывает текстовые сообщения для получения кодов."""
    if message.text.startswith("Google:"):
        google_code = message.text.split("Google:")[1].strip()
        google_token = exchange_google_code_for_token(google_code)
        if google_token:
            save_user_token(message.chat.id, "google_token", google_token)
            bot.send_message(message.chat.id, "Google авторизация завершена.")
        else:
            bot.send_message(message.chat.id, "Не удалось завершить авторизацию Google.")
    elif message.text.startswith("Todoist:"):
        todoist_code = message.text.split("Todoist:")[1].strip()
        todoist_token = exchange_todoist_code_for_token(todoist_code)
        if todoist_token:
            save_user_token(message.chat.id, "todoist_token", todoist_token)
            bot.send_message(message.chat.id, "Todoist авторизация завершена.")
        else:
            bot.send_message(message.chat.id, "Не удалось завершить авторизацию Todoist.")
    else:
        bot.send_message(message.chat.id, "Неизвестный код. Попробуйте снова.")


@bot.message_handler(commands=['check_tokens'])
def check_tokens(message):
    """Проверяет сохраненные токены пользователя."""
    google_token = get_user_token(message.chat.id, "google_token")
    todoist_token = get_user_token(message.chat.id, "todoist_token")

    if google_token or todoist_token:
        response = "Ваши токены:\n"
        if google_token:
            response += f"🔹 Google: {google_token}\n"
        if todoist_token:
            response += f"🔹 Todoist: {todoist_token}\n"
    else:
        response = "Токены не найдены. Пожалуйста, авторизуйтесь через /setup."

    bot.send_message(message.chat.id, response)

from fastapi import FastAPI, Request

app = FastAPI()

@app.get("/callback")
async def callback(request: Request):
    code = request.query_params.get("code")
    if code:
        token = exchange_google_code_for_token(code)
        return {"message": "Авторизация успешна!"}
    return {"message": "Ошибка авторизации"}, 400


# ===== ЗАПУСК  =====
if __name__ == "__main__":
    print("Бот запущен...")
    bot.polling(none_stop=True)
