from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from src.project.bot import app, save_user_token, get_user_token, generate_google_auth_url, \
    generate_todoist_auth_url, convert_relative_to_iso

client = TestClient(app)


@pytest.mark.asyncio
async def test_save_and_get_user_token():
    chat_id = 12345
    save_user_token(chat_id, "google_token", "test_google_token")
    save_user_token(chat_id, "todoist_token", "test_todoist_token")

    google_token = get_user_token(chat_id, "google_token")
    todoist_token = get_user_token(chat_id, "todoist_token")

    assert google_token == "test_google_token"
    assert todoist_token == "test_todoist_token"


@pytest.mark.asyncio
async def test_generate_google_auth_url():
    auth_url = generate_google_auth_url()
    assert auth_url.startswith("https://accounts.google.com/o/oauth2/v2/auth")
    assert "client_id=" in auth_url
    assert "redirect_uri=" in auth_url


@pytest.mark.asyncio
async def test_generate_todoist_auth_url():
    auth_url = generate_todoist_auth_url()
    assert auth_url.startswith("https://todoist.com/oauth/authorize")
    assert "client_id=" in auth_url
    assert "scope=" in auth_url
    assert "redirect_uri=" in auth_url


@pytest.mark.asyncio
async def test_google_callback():
    response = client.get("/callback/google?code=test_code")
    assert response.status_code == 200
    data = response.json()
    assert "Google authorisation completed!" in data["message"] or "Google authorisation error" in data["message"]


@pytest.mark.asyncio
async def test_todoist_callback():
    response = client.get("/callback/todoist?code=test_code")
    assert response.status_code == 200
    data = response.json()
    assert "Todoist authorisation completed!" in data["message"] or "Todoist authorisation error" in data["message"]


def test_convert_relative_to_iso_tomorrow():
    time_str = "завтра 16:30"
    result = convert_relative_to_iso(time_str)
    now = datetime.now() + timedelta(days=1)
    expected = now.replace(hour=16, minute=30, second=0, microsecond=0)
    assert result == expected.isoformat()
