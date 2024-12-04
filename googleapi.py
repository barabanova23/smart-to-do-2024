from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

def get_google_service(token):
    """
    Создает объект сервиса Google Calendar.
    """
    credentials = Credentials(token)
    service = build('calendar', 'v3', credentials=credentials)
    return service

def create_google_event(token, summary, start_time, end_time):
    """
    Создает событие в Google Calendar.
    """
    service = get_google_service(token)
    event = {
        'summary': summary,
        'start': {
            'dateTime': start_time,
        },
        'end': {
            'dateTime': end_time,
        },
    }
    event_result = service.events().insert(calendarId='primary', body=event).execute()
    return event_result

def list_google_events(token):
    """
    Получает список ближайших событий из Google Calendar.
    """
    service = get_google_service(token)
    now = datetime.utcnow().isoformat() + 'Z'  # Текущее время в формате ISO 8601
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=10, singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return events

def delete_google_event(token, event_id):
    """
    Удаляет событие из Google Calendar по ID.
    """
    service = get_google_service(token)
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return True


from datetime import datetime

def parse_datetime_to_iso(date_time_str):
    """
    Преобразует дату и время из формата 'YYYY-MM-DD HH:MM' в ISO 8601 с временной зоной '+03:00'.
    """
    try:
        # Парсим строку в объект datetime
        dt = datetime.strptime(date_time_str, "%Y-%m-%d %H:%M")
        # Добавляем часовой пояс и возвращаем ISO 8601 формат
        return dt.strftime("%Y-%m-%dT%H:%M:%S+03:00")
    except ValueError:
        raise ValueError("Некорректный формат даты. Используйте 'YYYY-MM-DD HH:MM'.")