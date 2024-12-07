import requests
import re

def create_task_in_project(token, task_content, project_id, due_string=None):
    """
    Создаёт задачу в указанном проекте Todoist.
    """
    url = "https://api.todoist.com/rest/v2/tasks"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    data = {
        "content": task_content,
        "project_id": project_id
    }
    if due_string:
        data["due_string"] = due_string  # Например, "завтра" или "через 2 часа"
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200 or response.status_code == 204:
        return response.json()  # Информация о задаче
    else:
        return {"error": response.text}


def get_todoist_projects(token):
    """
    Получает список проектов пользователя из Todoist.
    """
    url = "https://api.todoist.com/rest/v2/projects"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)

    if response.status_code == 200:
        return response.json()  # Возвращает список проектов
    else:
        return {"error": response.text}  # Возвращает ошибку, если запрос не удался
