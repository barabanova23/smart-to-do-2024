from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from datetime import datetime, timezone, timedelta


def get_google_service(token):
    """Создает объект сервиса Google Calendar."""
    credentials = Credentials(token)
    service = build('calendar', 'v3', credentials=credentials)
    return service


def create_google_event(token, summary, start_time, end_time):
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
    service = get_google_service(token)
    now = datetime.utcnow().isoformat() + 'Z'
    events_result = service.events().list(
        calendarId='primary', timeMin=now,
        maxResults=10, singleEvents=True,
        orderBy='startTime'
    ).execute()
    events = events_result.get('items', [])
    return events


def delete_google_event(token, event_id):
    service = get_google_service(token)
    service.events().delete(calendarId='primary', eventId=event_id).execute()
    return True


def parse_datetime_to_iso(date_time_str, tz_offset_hours=0):
    dt = datetime.strptime(date_time_str, "%Y-%m-%dT%H:%M:%S")

    tz_offset = timedelta(hours=tz_offset_hours)
    tz_info = timezone(tz_offset)
    dt_with_tz = dt.replace(tzinfo=tz_info)

    return dt_with_tz.isoformat()
