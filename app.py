import streamlit as st
import psycopg2
from datetime import datetime, timedelta, date
import time
from typing import List, Dict, Optional, Tuple
from contextlib import contextmanager
import json
import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import pickle

# Настройки страницы
st.set_page_config(
    page_title="Task Planner Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Константы
TELEGRAM_USER_ID = 209010651
DAYS_TO_KEEP_COMPLETED = 7  # Автоматическое удаление через 7 дней

# Google Calendar API настройки
SCOPES = ['https://www.googleapis.com/auth/calendar']
CALENDAR_ID = 'primary'  # Основной календарь пользователя
TOKEN_FILE = f'token_{TELEGRAM_USER_ID}.pickle'
CREDENTIALS_FILE = 'credentials.json'

# Стили - оптимизированные
st.markdown("""
<style>
    /* Базовые стили */
    .status-pending { background-color: #FFD700; color: #000; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .status-in_progress { background-color: #4169E1; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .status-completed { background-color: #32CD32; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .status-overdue { background-color: #DC143C; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    
    /* Цвета дедлайнов */
    .deadline-urgent { color: #DC143C; font-weight: bold; }
    .deadline-warning { color: #FFA500; font-weight: bold; }
    .deadline-normal { color: #32CD32; }
    
    /* Карточки */
    .task-card { 
        border: 1px solid #e0e0e0; 
        border-radius: 8px; 
        padding: 12px; 
        margin-bottom: 10px; 
        background: #ffffff; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.05); 
        transition: transform 0.2s ease, box-shadow 0.2s ease;
        color: #333;
    }
    .task-card:hover { 
        transform: translateY(-2px); 
        box-shadow: 0 4px 8px rgba(0,0,0,0.1); 
    }
    
    /* Группы проектов */
    .project-group { 
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); 
        padding: 12px 20px; 
        border-radius: 8px; 
        margin: 15px 0 10px 0;
        color: white !important;
    }
    .project-group h4 { 
        color: white !important; 
        margin: 0;
        font-size: 1.2rem;
        font-weight: 600;
    }
    
    /* Кнопки */
    .stButton button {
        transition: all 0.3s ease;
        border-radius: 6px !important;
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    
    /* Быстрые действия */
    .quick-action-btn {
        background: #f0f2f6 !important;
        border: 1px solid #ddd !important;
        color: #333 !important;
    }
    
    /* Инпуты */
    .stTextInput > div > input, .stTextArea > div > textarea {
        border-radius: 6px !important;
    }
    
    /* Списки */
    .stSelectbox > div > div {
        border-radius: 6px !important;
    }
    
    /* Календарь */
    .calendar-sync { 
        background: linear-gradient(135deg, #0F9D58 0%, #34A853 100%);
        color: white !important;
        border: none !important;
    }
    .calendar-not-connected { 
        background: linear-gradient(135deg, #DB4437 0%, #EA4335 100%);
        color: white !important;
        border: none !important;
    }
</style>
""", unsafe_allow_html=True)

# ========== GOOGLE CALENDAR INTEGRATION ==========

class GoogleCalendarManager:
    """Менеджер для работы с Google Calendar API"""
    
    def __init__(self):
        self.service = None
        self.credentials = None
        
    def authenticate(self) -> bool:
        """Аутентификация через OAuth 2.0"""
        try:
            if os.path.exists(TOKEN_FILE):
                with open(TOKEN_FILE, 'rb') as token:
                    self.credentials = pickle.load(token)
            
            # Если нет валидных учетных данных
            if not self.credentials or not self.credentials.valid:
                if self.credentials and self.credentials.expired and self.credentials.refresh_token:
                    self.credentials.refresh(Request())
                else:
                    if not os.path.exists(CREDENTIALS_FILE):
                        st.error(f"Файл {CREDENTIALS_FILE} не найден. Загрузите его для настройки Google Calendar.")
                        return False
                    
                    flow = InstalledAppFlow.from_client_secrets_file(
                        CREDENTIALS_FILE, SCOPES)
                    self.credentials = flow.run_local_server(port=0)
                
                # Сохраняем учетные данные
                with open(TOKEN_FILE, 'wb') as token:
                    pickle.dump(self.credentials, token)
            
            # Создаем сервис
            self.service = build('calendar', 'v3', credentials=self.credentials)
            return True
            
        except Exception as e:
            st.error(f"Ошибка аутентификации: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """Проверка аутентификации"""
        return self.service is not None
    
    def create_event(self, task_data: Dict) -> Optional[str]:
        """Создание события в календаре"""
        try:
            if not self.service:
                if not self.authenticate():
                    return None
            
            # Формируем описание
            description = f"Задача: {task_data['title']}\n"
            if task_data.get('description'):
                description += f"Описание: {task_data['description']}\n"
            if task_data.get('project_name'):
                description += f"Проект: {task_data['project_name']}\n"
            description += f"Статус: {task_data['status']}\n"
            description += f"ID задачи: {task_data['id']}"
            
            # Время события (целый день)
            start_date = task_data['deadline'].strftime('%Y-%m-%d')
            end_date = (task_data['deadline'] + timedelta(days=1)).strftime('%Y-%m-%d')
            
            event = {
                'summary': f"📋 {task_data['title']}",
                'description': description,
                'start': {
                    'date': start_date,
                    'timeZone': 'Europe/Moscow',
                },
                'end': {
                    'date': end_date,
                    'timeZone': 'Europe/Moscow',
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 60 * 24},  # За день
                        {'method': 'popup', 'minutes': 60 * 2},   # За 2 часа
                    ],
                },
                'extendedProperties': {
                    'private': {
                        'taskId': str(task_data['id']),
                        'userId': str(TELEGRAM_USER_ID)
                    }
                }
            }
            
            # Создаем событие
            event_result = self.service.events().insert(
                calendarId=CALENDAR_ID,
                body=event
            ).execute()
            
            return event_result.get('id')
            
        except HttpError as e:
            st.error(f"Ошибка Google Calendar: {e}")
            return None
        except Exception as e:
            st.error(f"Ошибка создания события: {e}")
            return None
    
    def update_event(self, event_id: str, task_data: Dict) -> bool:
        """Обновление события в календаре"""
        try:
            if not self.service:
                if not self.authenticate():
                    return False
            
            # Получаем существующее событие
            event = self.service.events().get(
                calendarId=CALENDAR_ID,
                eventId=event_id
            ).execute()
            
            # Обновляем данные
            event['summary'] = f"📋 {task_data['title']}"
            
            # Обновляем описание
            description = f"Задача: {task_data['title']}\n"
            if task_data.get('description'):
                description += f"Описание: {task_data['description']}\n"
            if task_data.get('project_name'):
                description += f"Проект: {task_data['project_name']}\n"
            description += f"Статус: {task_data['status']}\n"
            description += f"ID задачи: {task_data['id']}"
            event['description'] = description
            
            # Обновляем дату, если она изменилась
            if task_data['deadline']:
                start_date = task_data['deadline'].strftime('%Y-%m-%d')
                end_date = (task_data['deadline'] + timedelta(days=1)).strftime('%Y-%m-%d')
                event['start']['date'] = start_date
                event['end']['date'] = end_date
            
            # Обновляем напоминания для просроченных задач
            if task_data['status'] == 'overdue':
                event['summary'] = f"⚠️ ПРОСРОЧЕНО: {task_data['title']}"
                event['colorId'] = '11'  # Красный цвет
            
            elif task_data['status'] == 'completed':
                event['summary'] = f"✅ ВЫПОЛНЕНО: {task_data['title']}"
                event['colorId'] = '10'  # Зеленый цвет
            
            elif task_data['status'] == 'in_progress':
                event['colorId'] = '5'  # Желтый цвет
            
            # Обновляем событие
            self.service.events().update(
                calendarId=CALENDAR_ID,
                eventId=event_id,
                body=event
            ).execute()
            
            return True
            
        except Exception as e:
            st.error(f"Ошибка обновления события: {e}")
            return False
    
    def delete_event(self, event_id: str) -> bool:
        """Удаление события из календаря"""
        try:
            if not self.service:
                if not self.authenticate():
                    return False
            
            self.service.events().delete(
                calendarId=CALENDAR_ID,
                eventId=event_id
            ).execute()
            
            return True
            
        except Exception as e:
            # Если событие уже удалено, игнорируем ошибку
            if "notFound" in str(e):
                return True
            st.error(f"Ошибка удаления события: {e}")
            return False
    
    def get_upcoming_events(self, max_results: int = 10) -> List[Dict]:
        """Получение предстоящих событий"""
        try:
            if not self.service:
                if not self.authenticate():
                    return []
            
            now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
            
            events_result = self.service.events().list(
                calendarId=CALENDAR_ID,
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            formatted_events = []
            for event in events:
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                formatted_events.append({
                    'id': event.get('id'),
                    'summary': event.get('summary', 'Без названия'),
                    'description': event.get('description', ''),
                    'start': start,
                    'end': end,
                    'htmlLink': event.get('htmlLink'),
                    'status': event.get('status')
                })
            
            return formatted_events
            
        except Exception as e:
            st.error(f"Ошибка получения событий: {e}")
            return []
    
    def search_events_by_task_id(self, task_id: int) -> Optional[Dict]:
        """Поиск события по ID задачи"""
        try:
            if not self.service:
                if not self.authenticate():
                    return None
            
            # Ищем события с нужным taskId в extendedProperties
            events_result = self.service.events().list(
                calendarId=CALENDAR_ID,
                maxResults=100,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            for event in events:
                extended_props = event.get('extendedProperties', {}).get('private', {})
                if extended_props.get('taskId') == str(task_id):
                    return event
            
            return None
            
        except Exception as e:
            st.error(f"Ошибка поиска события: {e}")
            return None

# Создаем глобальный экземпляр менеджера календаря
calendar_manager = GoogleCalendarManager()

# ========== ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ БД ==========

class DatabaseManager:
    """Менеджер для работы с базой данных"""
    
    def __init__(self):
        self.max_retries = 3
        self.retry_delay = 2
        
    @contextmanager
    def get_connection(self):
        """Контекстный менеджер для подключения к БД"""
        conn = None
        try:
            conn = self._connect_with_retry()
            yield conn
        except Exception as e:
            st.error(f"Ошибка подключения к БД: {e}")
            raise
        finally:
            if conn:
                conn.close()
    
    def _connect_with_retry(self):
        """Подключение с повторными попытками"""
        for attempt in range(self.max_retries):
            try:
                conn = psycopg2.connect(
                    host="dpg-d623k7m3jp1c73bhruk0-a",
                    database="task_planner_3k47",
                    user="task_planner_user",
                    password="esbiIzvvhnGcZF1NOc4oRxUs8vyW24by",
                    port=5432,
                    connect_timeout=5
                )
                conn.autocommit = False
                return conn
            except Exception as e:
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
                else:
                    raise e
    
    def execute_query(self, query: str, params: tuple = None, fetch: bool = False):
        """Выполнение запроса с обработкой ошибок"""
        with self.get_connection() as conn:
            with conn.cursor() as cursor:
                try:
                    cursor.execute(query, params or ())
                    if fetch:
                        if query.strip().upper().startswith("SELECT"):
                            columns = [desc[0] for desc in cursor.description]
                            rows = cursor.fetchall()
                            return [dict(zip(columns, row)) for row in rows]
                        return cursor.fetchone()
                    else:
                        conn.commit()
                        return True
                except Exception as e:
                    conn.rollback()
                    st.error(f"Ошибка запроса: {e}")
                    return False

db = DatabaseManager()

# ========== ОПТИМИЗИРОВАННЫЕ ФУНКЦИИ ДАННЫХ ==========

@st.cache_data(ttl=30, show_spinner=False)
def load_projects() -> List[Dict]:
    """Загрузка проектов"""
    query = "SELECT id, name FROM projects WHERE user_id = %s ORDER BY name"
    return db.execute_query(query, (TELEGRAM_USER_ID,), fetch=True) or []

@st.cache_data(ttl=30, show_spinner=False)
def load_tasks(project_id: Optional[int] = None, 
               status_filter: Optional[str] = None,
               deadline_filter: Optional[str] = None) -> List[Dict]:
    """Загрузка задач с фильтрами"""
    
    query = """
        SELECT 
            t.id,
            t.title,
            t.description,
            t.deadline,
            t.status,
            t.created_at,
            t.completed_at,
            p.name AS project_name,
            p.id AS project_id,
            t.calendar_event_id
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE p.user_id = %s
    """
    params = [TELEGRAM_USER_ID]
    conditions = []
    
    if project_id:
        conditions.append("t.project_id = %s")
        params.append(project_id)
    
    if status_filter and status_filter != 'all':
        conditions.append("t.status = %s")
        params.append(status_filter)
    
    today = date.today()
    if deadline_filter == 'today':
        conditions.append("t.deadline = %s")
        params.append(today)
    elif deadline_filter == 'tomorrow':
        conditions.append("t.deadline = %s")
        params.append(today + timedelta(days=1))
    elif deadline_filter == 'next_3_days':
        conditions.append("t.deadline BETWEEN %s AND %s")
        params.append(today)
        params.append(today + timedelta(days=3))
    elif deadline_filter == 'next_week':
        conditions.append("t.deadline BETWEEN %s AND %s")
        params.append(today)
        params.append(today + timedelta(days=7))
    elif deadline_filter == 'overdue':
        conditions.append("t.deadline < %s AND t.status != 'completed'")
        params.append(today)
    
    if conditions:
        query += " AND " + " AND ".join(conditions)
    
    query += " ORDER BY t.deadline ASC NULLS LAST, t.created_at DESC"
    
    return db.execute_query(query, tuple(params), fetch=True) or []

def clean_old_tasks():
    """Очистка старых выполненных задач"""
    cutoff_date = date.today() - timedelta(days=DAYS_TO_KEEP_COMPLETED)
    
    # Сначала получаем задачи для удаления событий из календаря
    query_select = """
        SELECT id, calendar_event_id FROM tasks 
        WHERE status = 'completed' 
        AND completed_at < %s
        AND project_id IN (SELECT id FROM projects WHERE user_id = %s)
        AND calendar_event_id IS NOT NULL
    """
    tasks_to_clean = db.execute_query(
        query_select, 
        (cutoff_date, TELEGRAM_USER_ID), 
        fetch=True
    )
    
    # Удаляем события из календаря
    for task in tasks_to_clean:
        calendar_manager.delete_event(task['calendar_event_id'])
    
    # Удаляем задачи из БД
    query_delete = """
        DELETE FROM tasks 
        WHERE status = 'completed' 
        AND completed_at < %s
        AND project_id IN (SELECT id FROM projects WHERE user_id = %s)
    """
    return db.execute_query(query_delete, (cutoff_date, TELEGRAM_USER_ID))

def create_task(title: str, description: str, deadline: date, 
                status: str, project_id: Optional[int], sync_calendar: bool = True) -> Tuple[bool, Optional[str]]:
    """Создание новой задачи с синхронизацией в календарь"""
    
    # Создаем задачу в БД
    query = """
        INSERT INTO tasks (title, description, deadline, status, project_id, created_at) 
        VALUES (%s, %s, %s, %s, %s, NOW())
        RETURNING id
    """
    result = db.execute_query(query, (title, description, deadline, status, project_id), fetch=True)
    
    if not result:
        return False, None
    
    task_id = result[0]['id']
    
    # Создаем событие в календаре, если требуется
    calendar_event_id = None
    if sync_calendar and deadline:
        # Получаем данные задачи для календаря
        project_query = "SELECT name FROM projects WHERE id = %s"
        project_result = db.execute_query(project_query, (project_id,), fetch=True)
        project_name = project_result[0]['name'] if project_result else None
        
        task_data = {
            'id': task_id,
            'title': title,
            'description': description,
            'deadline': deadline,
            'status': status,
            'project_name': project_name
        }
        
        calendar_event_id = calendar_manager.create_event(task_data)
        
        # Обновляем задачу с ID события календаря
        if calendar_event_id:
            db.execute_query(
                "UPDATE tasks SET calendar_event_id = %s WHERE id = %s",
                (calendar_event_id, task_id)
            )
    
    return True, calendar_event_id

def update_task(task_id: int, sync_calendar: bool = True, **kwargs) -> bool:
    """Обновление задачи с синхронизацией в календарь"""
    
    # Получаем текущие данные задачи
    query_select = """
        SELECT t.*, p.name as project_name 
        FROM tasks t 
        LEFT JOIN projects p ON t.project_id = p.id 
        WHERE t.id = %s
    """
    current_task = db.execute_query(query_select, (task_id,), fetch=True)
    
    if not current_task:
        return False
    
    current_task = current_task[0]
    
    # Обновляем задачу в БД
    fields = []
    params = []
    
    for key, value in kwargs.items():
        if value is not None:
            fields.append(f"{key} = %s")
            params.append(value)
    
    if not fields:
        return False
    
    params.append(task_id)
    query = f"UPDATE tasks SET {', '.join(fields)} WHERE id = %s"
    success = db.execute_query(query, tuple(params))
    
    if not success:
        return False
    
    # Обновляем событие в календаре, если требуется
    if sync_calendar and current_task.get('calendar_event_id'):
        # Получаем обновленные данные задачи
        updated_task = {**current_task, **kwargs}
        
        # Обновляем событие
        calendar_manager.update_event(
            current_task['calendar_event_id'],
            updated_task
        )
    
    return True

def update_task_status(task_id: int, status: str, sync_calendar: bool = True) -> bool:
    """Обновление статуса задачи с синхронизацией в календарь"""
    
    # Получаем данные задачи для календаря
    query_select = """
        SELECT t.*, p.name as project_name 
        FROM tasks t 
        LEFT JOIN projects p ON t.project_id = p.id 
        WHERE t.id = %s
    """
    task_data = db.execute_query(query_select, (task_id,), fetch=True)
    
    if not task_data:
        return False
    
    task_data = task_data[0]
    
    # Обновляем статус в БД
    if status == 'completed':
        success = db.execute_query(
            "UPDATE tasks SET status = %s, completed_at = NOW() WHERE id = %s",
            (status, task_id)
        )
    else:
        success = db.execute_query(
            "UPDATE tasks SET status = %s WHERE id = %s",
            (status, task_id)
        )
    
    if not success:
        return False
    
    # Обновляем событие в календаре, если требуется
    if sync_calendar and task_data.get('calendar_event_id'):
        calendar_manager.update_event(
            task_data['calendar_event_id'],
            {**task_data, 'status': status}
        )
    
    return True

def delete_task(task_id: int, sync_calendar: bool = True) -> bool:
    """Удаление задачи с удалением из календаря"""
    
    # Получаем ID события календаря
    query_select = "SELECT calendar_event_id FROM tasks WHERE id = %s"
    result = db.execute_query(query_select, (task_id,), fetch=True)
    
    calendar_event_id = None
    if result:
        calendar_event_id = result[0].get('calendar_event_id')
    
    # Удаляем задачу из БД
    success = db.execute_query("DELETE FROM tasks WHERE id = %s", (task_id,))
    
    if not success:
        return False
    
    # Удаляем событие из календаря, если требуется
    if sync_calendar and calendar_event_id:
        calendar_manager.delete_event(calendar_event_id)
    
    return True

def create_project(name: str) -> Optional[int]:
    """Создание нового проекта"""
    query = """
        INSERT INTO projects (name, user_id, created_at)
        VALUES (%s, %s, NOW())
        RETURNING id
    """
    result = db.execute_query(query, (name, TELEGRAM_USER_ID), fetch=True)
    return result[0]['id'] if result else None

def migrate_web_data() -> Dict:
    """Миграция данных веб-пользователя в Telegram"""
    try:
        # Обновляем проекты
        db.execute_query(
            "UPDATE projects SET user_id = %s WHERE user_id = 1 OR user_id IS NULL",
            (TELEGRAM_USER_ID,)
        )
        
        # Получаем статистику
        result = db.execute_query(
            "SELECT COUNT(*) as count FROM tasks t JOIN projects p ON t.project_id = p.id WHERE p.user_id = %s",
            (TELEGRAM_USER_ID,), fetch=True
        )
        
        return {
            'success': True,
            'tasks_migrated': result[0]['count'] if result else 0
        }
    except Exception as e:
        return {'success': False, 'error': str(e)}

def sync_all_tasks_to_calendar() -> Dict:
    """Синхронизация всех задач с Google Calendar"""
    try:
        # Получаем все задачи без событий в календаре
        query = """
            SELECT t.*, p.name as project_name 
            FROM tasks t 
            LEFT JOIN projects p ON t.project_id = p.id 
            WHERE p.user_id = %s 
            AND t.deadline IS NOT NULL 
            AND t.calendar_event_id IS NULL
        """
        tasks = db.execute_query(query, (TELEGRAM_USER_ID,), fetch=True)
        
        synced_count = 0
        errors = []
        
        for task in tasks:
            try:
                event_id = calendar_manager.create_event(task)
                if event_id:
                    db.execute_query(
                        "UPDATE tasks SET calendar_event_id = %s WHERE id = %s",
                        (event_id, task['id'])
                    )
                    synced_count += 1
                else:
                    errors.append(f"Задача '{task['title']}'")
            except Exception as e:
                errors.append(f"Задача '{task['title']}': {str(e)}")
        
        return {
            'success': True,
            'synced': synced_count,
            'total': len(tasks),
            'errors': errors
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

def disconnect_calendar() -> bool:
    """Отключение от Google Calendar"""
    try:
        # Удаляем токен
        if os.path.exists(TOKEN_FILE):
            os.remove(TOKEN_FILE)
        
        # Обнуляем события в БД
        db.execute_query(
            "UPDATE tasks SET calendar_event_id = NULL WHERE id IN (SELECT t.id FROM tasks t JOIN projects p ON t.project_id = p.id WHERE p.user_id = %s)",
            (TELEGRAM_USER_ID,)
        )
        
        # Сбрасываем менеджер календаря
        global calendar_manager
        calendar_manager = GoogleCalendarManager()
        
        return True
        
    except Exception as e:
        st.error(f"Ошибка отключения календаря: {e}")
        return False

# ========== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==========

def get_statistics(tasks: List[Dict]) -> Dict:
    """Получение статистики по задачам"""
    today = date.today()
    
    stats = {
        'total': len(tasks),
        'pending': 0,
        'in_progress': 0,
        'completed': 0,
        'overdue': 0,
        'due_today': 0,
        'due_tomorrow': 0,
        'synced_with_calendar': 0
    }
    
    for task in tasks:
        stats[task['status']] += 1
        
        if task.get('calendar_event_id'):
            stats['synced_with_calendar'] += 1
        
        if task['deadline']:
            days_left = (task['deadline'] - today).days
            
            if days_left < 0 and task['status'] != 'completed':
                stats['overdue'] += 1
            elif days_left == 0:
                stats['due_today'] += 1
            elif days_left == 1:
                stats['due_tomorrow'] += 1
    
    return stats

def get_deadline_icon(days_left: Optional[int]) -> str:
    """Получение иконки для дедлайна"""
    if days_left is None:
        return "⚪"
    elif days_left < 0:
        return "🔴"
    elif days_left == 0:
        return "🟠"
    elif days_left <= 2:
        return "🟡"
    else:
        return "🟢"

def get_deadline_class(days_left: Optional[int]) -> str:
    """Получение CSS класса для дедлайна"""
    if days_left is None:
        return ""
    elif days_left < 0 or days_left == 0:
        return "deadline-urgent"
    elif days_left <= 2:
        return "deadline-warning"
    else:
        return "deadline-normal"

# ========== ИНИЦИАЛИЗАЦИЯ SESSION STATE ==========

for key in ['show_add_task', 'show_add_project', 'editing_task', 
            'edit_task_data', 'data_migrated', 'collapsed_projects',
            'show_calendar_sync', 'show_calendar_events']:
    if key not in st.session_state:
        if key == 'collapsed_projects':
            st.session_state[key] = {}
        elif key in ['data_migrated', 'show_calendar_sync', 'show_calendar_events']:
            st.session_state[key] = False
        else:
            st.session_state[key] = None

# ========== ОСНОВНОЙ ИНТЕРФЕЙС ==========

# Заголовок
st.title("🚀 Task Planner Pro Dashboard")
st.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

# Статус Google Calendar
col1, col2 = st.columns([3, 1])
with col1:
    is_calendar_connected = calendar_manager.is_authenticated()
    status_text = "✅ Подключен к Google Calendar" if is_calendar_connected else "❌ Google Calendar не подключен"
    status_color = "calendar-sync" if is_calendar_connected else "calendar-not-connected"
    
    if st.button(f"📅 {status_text}", use_container_width=True, type="secondary", key="calendar_status"):
        if is_calendar_connected:
            st.session_state.show_calendar_events = not st.session_state.show_calendar_events
        else:
            st.session_state.show_calendar_sync = True
        st.rerun()

with col2:
    if st.button("🔄 Обновить все", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

# Панель синхронизации с календарем
if st.session_state.show_calendar_sync:
    st.divider()
    st.subheader("📅 Настройка Google Calendar")
    
    if not os.path.exists(CREDENTIALS_FILE):
        st.warning("""
        ### 📋 Для подключения Google Calendar:
        
        1. Перейдите в [Google Cloud Console](https://console.cloud.google.com/)
        2. Создайте новый проект или выберите существующий
        3. Включите Google Calendar API
        4. Создайте учетные данные OAuth 2.0 (тип приложения: Desktop app)
        5. Скачайте файл `credentials.json`
        6. Загрузите его ниже
        """)
        
        uploaded_file = st.file_uploader("Загрузите credentials.json", type=['json'])
        if uploaded_file:
            with open(CREDENTIALS_FILE, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            st.success("✅ Файл загружен! Теперь подключитесь к календарю.")
            st.rerun()
    
    else:
        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("🔗 Подключить Google Calendar", use_container_width=True):
                with st.spinner("Подключение к Google Calendar..."):
                    if calendar_manager.authenticate():
                        st.success("✅ Успешно подключено к Google Calendar!")
                        st.session_state.show_calendar_sync = False
                        st.rerun()
        
        with col_b:
            if st.button("❌ Отмена", use_container_width=True, type="secondary"):
                st.session_state.show_calendar_sync = False
                st.rerun()

# Просмотр событий календаря
if st.session_state.show_calendar_events and is_calendar_connected:
    st.divider()
    st.subheader("📅 События в Google Calendar")
    
    with st.spinner("Загрузка событий..."):
        events = calendar_manager.get_upcoming_events(20)
    
    if events:
        for event in events:
            with st.expander(f"📅 {event['summary']}", expanded=False):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**Начало:** {event['start']}")
                    st.write(f"**Конец:** {event['end']}")
                    if event.get('description'):
                        st.text_area("Описание", event['description'], height=100, disabled=True)
                
                with col2:
                    if event.get('htmlLink'):
                        st.link_button("📆 Открыть в календаре", event['htmlLink'])
    else:
        st.info("📭 Нет предстоящих событий в календаре")
    
    if st.button("❌ Закрыть события календаря", use_container_width=True):
        st.session_state.show_calendar_events = False
        st.rerun()

# Быстрые действия
st.divider()
st.subheader("⚡ Быстрые действия")

col1, col2, col3, col4 = st.columns(4)

with col1:
    if st.button("➕ Добавить задачу", use_container_width=True):
        st.session_state.show_add_task = True
        st.rerun()

with col2:
    if st.button("📁 Добавить проект", use_container_width=True):
        st.session_state.show_add_project = True
        st.rerun()

with col3:
    if is_calendar_connected:
        if st.button("🔄 Синхронизировать все", use_container_width=True):
            with st.spinner("Синхронизация с Google Calendar..."):
                result = sync_all_tasks_to_calendar()
                if result['success']:
                    st.success(f"✅ Синхронизировано {result['synced']} из {result['total']} задач")
                    if result['errors']:
                        st.warning(f"Ошибки: {', '.join(result['errors'][:3])}")
                    st.cache_data.clear()
                    st.rerun()

with col4:
    if st.button("📋 Развернуть всё", use_container_width=True):
        st.session_state.collapsed_projects = {}
        st.rerun()

# Быстрая очистка старых задач
if st.button("🧹 Очистить старые задачи", type="secondary"):
    with st.spinner("Очистка старых задач..."):
        if clean_old_tasks():
            st.success("✅ Старые задачи очищены!")
            st.cache_data.clear()
            st.rerun()

# Управление календарем (если подключен)
if is_calendar_connected:
    st.divider()
    col_disconnect, col_sync = st.columns(2)
    
    with col_disconnect:
        if st.button("🚫 Отключить календарь", use_container_width=True, type="secondary"):
            if st.checkbox("Подтвердите отключение календаря"):
                if disconnect_calendar():
                    st.success("✅ Календарь отключен!")
                    st.session_state.show_calendar_events = False
                    st.cache_data.clear()
                    st.rerun()
    
    with col_sync:
        # Синхронизация отдельных задач
        st.info("ℹ️ События автоматически создаются для новых задач с дедлайнами")

# Миграция данных (если нужно)
if not st.session_state.data_migrated:
    if st.button("🔄 Перенести мои данные", type="primary"):
        with st.spinner("Перенос данных..."):
            result = migrate_web_data()
            if result['success']:
                st.success(f"✅ Данные перенесены! Задач: {result['tasks_migrated']}")
                st.session_state.data_migrated = True
                st.cache_data.clear()
                st.rerun()
            else:
                st.error(f"❌ Ошибка: {result['error']}")

# ========== ФОРМЫ ДОБАВЛЕНИЯ ==========

# Форма добавления проекта
if st.session_state.show_add_project:
    st.divider()
    st.subheader("📁 Создать новый проект")
    
    with st.form("add_project_form"):
        project_name = st.text_input(
            "Название проекта*",
            placeholder="Введите название проекта",
            help="Например: Веб-сайт, Мобильное приложение"
        )
        
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button(
                "✅ Создать проект",
                use_container_width=True,
                type="primary"
            )
        with col2:
            cancelled = st.form_submit_button(
                "❌ Отмена",
                use_container_width=True,
                type="secondary"
            )
        
        if submitted and project_name.strip():
            project_id = create_project(project_name.strip())
            if project_id:
                st.success(f"✅ Проект '{project_name}' создан!")
                st.session_state.show_add_project = False
                st.cache_data.clear()
                st.rerun()
        
        if cancelled:
            st.session_state.show_add_project = False
            st.rerun()

# Форма добавления/редактирования задачи
def render_task_form(task_data: Optional[Dict] = None):
    """Рендер формы для добавления/редактирования задачи"""
    is_edit = task_data is not None
    
    with st.form(f"{'edit' if is_edit else 'add'}_task_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            title = st.text_input(
                "Название задачи*",
                value=task_data['title'] if is_edit else "",
                placeholder="Краткое название задачи"
            )
            
            description = st.text_area(
                "Описание",
                value=task_data.get('description', '') if is_edit else "",
                placeholder="Подробное описание задачи...",
                height=120
            )
        
        with col2:
            # Выбор проекта
            projects = load_projects()
            project_options = ['Без проекта'] + [p['name'] for p in projects]
            
            if is_edit:
                default_index = 0
                if task_data.get('project_name'):
                    try:
                        default_index = project_options.index(task_data['project_name'])
                    except ValueError:
                        pass
            else:
                default_index = 0
            
            selected_project_name = st.selectbox(
                "Проект",
                project_options,
                index=default_index
            )
            
            selected_project = next(
                (p for p in projects if p['name'] == selected_project_name),
                None
            )
            
            # Дата дедлайна
            deadline_default = (
                task_data['deadline'] 
                if is_edit and task_data.get('deadline')
                else date.today() + timedelta(days=3)
            )
            
            deadline = st.date_input(
                "Дедлайн*",
                value=deadline_default,
                min_value=date.today() - timedelta(days=365)
            )
            
            # Статус
            status_options = {
                '⏳ В ожидании': 'pending',
                '🔄 В работе': 'in_progress',
                '✅ Завершено': 'completed'
            }
            
            if is_edit:
                current_status_name = next(
                    (k for k, v in status_options.items() if v == task_data['status']),
                    '⏳ В ожидании'
                )
                status_index = list(status_options.keys()).index(current_status_name)
            else:
                status_index = 0
            
            selected_status_name = st.selectbox(
                "Статус*",
                list(status_options.keys()),
                index=status_index
            )
            
            status = status_options[selected_status_name]
            
            # Синхронизация с календарем (только для задач с дедлайном)
            if is_calendar_connected:
                sync_calendar = st.checkbox(
                    "📅 Добавить в Google Calendar",
                    value=bool(deadline) and not (is_edit and task_data.get('calendar_event_id')),
                    help="Создать событие в Google Calendar с дедлайном задачи",
                    disabled=not deadline
                )
                if not deadline:
                    st.caption("_Укажите дедлайн для синхронизации с календарем_")
        
        # Кнопки действий
        col_btn1, col_btn2 = st.columns(2)
        
        with col_btn1:
            submit_text = "✅ Сохранить изменения" if is_edit else "✅ Создать задачу"
            submitted = st.form_submit_button(submit_text, use_container_width=True, type="primary")
        
        with col_btn2:
            cancelled = st.form_submit_button("❌ Отмена", use_container_width=True, type="secondary")
        
        if submitted:
            if not title.strip():
                st.error("❌ Название задачи обязательно")
            else:
                project_id = selected_project['id'] if selected_project else None
                
                if is_edit:
                    success = update_task(
                        task_data['id'],
                        sync_calendar=is_calendar_connected and sync_calendar,
                        title=title.strip(),
                        description=description.strip() or None,
                        deadline=deadline,
                        status=status,
                        project_id=project_id
                    )
                    if success:
                        st.success(f"✅ Задача '{title}' обновлена!")
                        st.session_state.editing_task = None
                        st.session_state.edit_task_data = None
                else:
                    success, event_id = create_task(
                        title.strip(),
                        description.strip() or None,
                        deadline,
                        status,
                        project_id,
                        sync_calendar=is_calendar_connected and sync_calendar
                    )
                    if success:
                        message = f"✅ Задача '{title}' создана!"
                        if event_id:
                            message += " 📅 Добавлено в календарь"
                        st.success(message)
                        st.session_state.show_add_task = False
                
                if success:
                    st.cache_data.clear()
                    st.rerun()
        
        if cancelled:
            if is_edit:
                st.session_state.editing_task = None
                st.session_state.edit_task_data = None
            else:
                st.session_state.show_add_task = False
            st.rerun()

# Показать форму редактирования
if st.session_state.editing_task:
    st.divider()
    st.subheader("✏️ Редактировать задачу")
    render_task_form(st.session_state.edit_task_data)

# Показать форму добавления
if st.session_state.show_add_task:
    st.divider()
    st.subheader("➕ Создать новую задачу")
    render_task_form()

# ========== САЙДБАР С ФИЛЬТРАМИ ==========

with st.sidebar:
    st.header("🎛️ Фильтры и настройки")
    
    st.info(f"👤 Пользователь: {TELEGRAM_USER_ID}")
    
    if is_calendar_connected:
        st.success("📅 Google Calendar: подключен")
    else:
        st.warning("📅 Google Calendar: не подключен")
        if st.button("⚙️ Настроить интеграцию"):
            st.session_state.show_calendar_sync = True
            st.rerun()
    
    st.divider()
    
    # Фильтры
    projects = load_projects()
    project_options = ['Все проекты'] + [p['name'] for p in projects]
    selected_project = st.selectbox("Проект", project_options)
    
    status_options = {
        'Все статусы': 'all',
        '⏳ В ожидании': 'pending',
        '🔄 В работе': 'in_progress',
        '✅ Завершённые': 'completed',
        '⚠️ Просроченные': 'overdue'
    }
    selected_status = st.selectbox("Статус", list(status_options.keys()))
    
    deadline_options = {
        'Все сроки': None,
        'Сегодня': 'today',
        'Завтра': 'tomorrow',
        'Ближайшие 3 дня': 'next_3_days',
        'Ближайшая неделя': 'next_week',
        'Просроченные': 'overdue'
    }
    selected_deadline = st.selectbox("Дедлайн", list(deadline_options.keys()))
    
    # Дополнительные фильтры для календаря
    if is_calendar_connected:
        calendar_filter = st.selectbox(
            "Синхронизация с календарем",
            ['Все', 'Синхронизированные', 'Не синхронизированные']
        )
    
    st.divider()
    
    # Загрузка данных с фильтрами
    project_id = next(
        (p['id'] for p in projects if p['name'] == selected_project),
        None
    ) if selected_project != 'Все проекты' else None
    
    tasks = load_tasks(
        project_id=project_id,
        status_filter=status_options[selected_status] if status_options[selected_status] != 'all' else None,
        deadline_filter=deadline_options[selected_deadline]
    )
    
    # Применяем фильтр календаря
    if is_calendar_connected and 'calendar_filter' in locals():
        if calendar_filter == 'Синхронизированные':
            tasks = [t for t in tasks if t.get('calendar_event_id')]
        elif calendar_filter == 'Не синхронизированные':
            tasks = [t for t in tasks if not t.get('calendar_event_id')]
    
    st.metric("📊 Показано задач", len(tasks))

# ========== СТАТИСТИКА ==========

st.divider()
st.subheader("📈 Статистика")

stats = get_statistics(tasks)

cols = st.columns(6)
metrics = [
    ("Всего задач", stats['total']),
    ("⏳ В ожидании", stats['pending']),
    ("🔄 В работе", stats['in_progress']),
    ("✅ Завершено", stats['completed']),
    ("⚠️ Просрочено", stats['overdue']),
]

if is_calendar_connected:
    metrics.append(("📅 В календаре", stats['synced_with_calendar']))

for col, (label, value) in zip(cols, metrics):
    with col:
        st.metric(label, value)

# ========== БЛИЖАЙШИЕ ДЕДЛАЙНЫ ==========

st.divider()
st.subheader("⏰ Ближайшие дедлайны")

today = date.today()
upcoming_tasks = sorted(
    [t for t in tasks if t['deadline'] and t['status'] != 'completed' and t['deadline'] >= today],
    key=lambda x: x['deadline']
)[:8]

if upcoming_tasks:
    for task in upcoming_tasks:
        days_left = (task['deadline'] - today).days
        icon = get_deadline_icon(days_left)
        deadline_class = get_deadline_class(days_left)
        
        # Создаем компактный вид
        with st.expander(f"{icon} **{task['title']}** | 📁 {task['project_name'] or 'Без проекта'}", expanded=False):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                deadline_str = task['deadline'].strftime('%d.%m.%Y')
                st.markdown(f'**Дедлайн:** <span class="{deadline_class}">{deadline_str}</span>', unsafe_allow_html=True)
                if days_left >= 0:
                    st.markdown(f"**Осталось:** {days_left} дн.")
                
                if task.get('description'):
                    st.markdown(f"**Описание:** {task['description']}")
                
                # Статус синхронизации с календарем
                if is_calendar_connected:
                    if task.get('calendar_event_id'):
                        st.success("📅 Синхронизировано с календарем")
                    else:
                        st.warning("⚠️ Не в календаре")
            
            with col2:
                # Быстрые кнопки действий
                if task['status'] != 'completed':
                    if st.button("✅", key=f"quick_complete_{task['id']}", help="Завершить"):
                        if update_task_status(task['id'], 'completed'):
                            st.success("✅ Готово!")
                            st.cache_data.clear()
                            st.rerun()
                
                if st.button("✏️", key=f"quick_edit_{task['id']}", help="Редактировать"):
                    st.session_state.editing_task = task['id']
                    st.session_state.edit_task_data = task
                    st.rerun()
                
                if st.button("🗑️", key=f"quick_delete_{task['id']}", help="Удалить", type="secondary"):
                    if delete_task(task['id']):
                        st.success("🗑️ Удалено!")
                        st.cache_data.clear()
                        st.rerun()
                
                # Кнопка синхронизации с календарем
                if is_calendar_connected and not task.get('calendar_event_id'):
                    if st.button("📅", key=f"sync_calendar_{task['id']}", help="Добавить в календарь"):
                        event_id = calendar_manager.create_event(task)
                        if event_id:
                            db.execute_query(
                                "UPDATE tasks SET calendar_event_id = %s WHERE id = %s",
                                (event_id, task['id'])
                            )
                            st.success("📅 Добавлено в календарь!")
                            st.cache_data.clear()
                            st.rerun()
else:
    st.info("🎉 Нет активных задач с дедлайнами!")

# ========== КАНБАН-ДОСКА ==========

st.divider()
st.subheader("📋 Канбан-доска")

status_order = ['pending', 'in_progress', 'completed']
status_names = {
    'pending': '⏳ В ожидании',
    'in_progress': '🔄 В работе',
    'completed': '✅ Завершено'
}

cols = st.columns(len(status_order))

for idx, status in enumerate(status_order):
    with cols[idx]:
        st.markdown(f"### {status_names[status]}")
        
        status_tasks = [t for t in tasks if t['status'] == status]
        
        if not status_tasks:
            st.caption("_Нет задач_")
        else:
            for task in status_tasks[:6]:
                deadline_str = task['deadline'].strftime('%d.%m') if task['deadline'] else '—'
                project_name = task['project_name'] or '—'
                calendar_icon = "📅 " if task.get('calendar_event_id') else ""
                
                st.markdown(f"""
                <div class="task-card">
                    <b>{calendar_icon}{task['title']}</b><br>
                    <small>📁 {project_name}</small><br>
                    <small>🕗 {deadline_str}</small>
                </div>
                """, unsafe_allow_html=True)
            
            if len(status_tasks) > 6:
                st.caption(f"... и ещё {len(status_tasks) - 6} задач")

# ========== ПОЛНЫЙ СПИСОК ЗАДАЧ ==========

st.divider()
st.subheader("📝 Полный список задач")

if tasks:
    # Группировка по проектам
    grouped_tasks = {}
    for task in tasks:
        project_name = task['project_name'] or 'Без проекта'
        grouped_tasks.setdefault(project_name, []).append(task)
    
    # Сортировка проектов по количеству задач
    sorted_projects = sorted(
        grouped_tasks.keys(),
        key=lambda x: len(grouped_tasks[x]),
        reverse=True
    )
    
    for project_name in sorted_projects:
        project_tasks = grouped_tasks[project_name]
        
        # Заголовок проекта с количеством задач
        with st.container():
            col1, col2 = st.columns([5, 1])
            
            with col1:
                task_count = len(project_tasks)
                completed_count = len([t for t in project_tasks if t['status'] == 'completed'])
                synced_count = len([t for t in project_tasks if t.get('calendar_event_id')])
                progress = (completed_count / task_count * 100) if task_count > 0 else 0
                
                st.markdown(
                    f'<div class="project-group">'
                    f'<h4>📁 {project_name} ({task_count} задач)</h4>'
                    f'<small>✅ Завершено: {completed_count} ({progress:.0f}%)</small>'
                    f'{"<br><small>📅 Синхронизировано: " + str(synced_count) + "</small>" if is_calendar_connected else ""}'
                    f'</div>',
                    unsafe_allow_html=True
                )
            
            with col2:
                # Кнопка свернуть/развернуть
                is_collapsed = st.session_state.collapsed_projects.get(project_name, False)
                button_text = "▼" if is_collapsed else "▲"
                
                if st.button(button_text, key=f"toggle_{project_name}", use_container_width=True):
                    st.session_state.collapsed_projects[project_name] = not is_collapsed
                    st.rerun()
        
        # Показываем задачи, если проект не свернут
        if not st.session_state.collapsed_projects.get(project_name, False):
            for task in project_tasks:
                days_left = None
                if task['deadline']:
                    days_left = (task['deadline'] - today).days
                
                icon = get_deadline_icon(days_left)
                deadline_class = get_deadline_class(days_left)
                
                # Компактное отображение задачи
                col_a, col_b, col_c = st.columns([3, 2, 1])
                
                with col_a:
                    calendar_indicator = "📅 " if task.get('calendar_event_id') else ""
                    st.markdown(f"**{calendar_indicator}{icon} {task['title']}**")
                    if task.get('description'):
                        st.caption(task['description'][:100] + ("..." if len(task['description']) > 100 else ""))
                
                with col_b:
                    if task['deadline']:
                        deadline_str = task['deadline'].strftime('%d.%m.%Y')
                        st.markdown(f'<span class="{deadline_class}">🕗 {deadline_str}</span>', unsafe_allow_html=True)
                    
                    status_display = {
                        'pending': '⏳ В ожидании',
                        'in_progress': '🔄 В работе',
                        'completed': '✅ Завершено'
                    }.get(task['status'], task['status'])
                    st.caption(f"📊 {status_display}")
                
                with col_c:
                    # Быстрые действия для задачи
                    col1, col2, col3 = st.columns(3) if is_calendar_connected else st.columns(2)
                    
                    if is_calendar_connected:
                        with col1:
                            if not task.get('calendar_event_id') and task['deadline']:
                                if st.button("📅", key=f"sync_{task['id']}", help="В календарь", use_container_width=True):
                                    event_id = calendar_manager.create_event(task)
                                    if event_id:
                                        db.execute_query(
                                            "UPDATE tasks SET calendar_event_id = %s WHERE id = %s",
                                            (event_id, task['id'])
                                        )
                                        st.success("📅 Добавлено!")
                                        st.cache_data.clear()
                                        st.rerun()
                    
                    col_index = 0
                    if is_calendar_connected:
                        col_index = 1
                    
                    with st.container():
                        col_left, col_right = st.columns(2)
                        
                        with col_left:
                            if task['status'] != 'completed':
                                if st.button("✅", key=f"complete_{task['id']}", help="Завершить", use_container_width=True):
                                    if update_task_status(task['id'], 'completed'):
                                        st.success("✅ Готово!")
                                        st.cache_data.clear()
                                        st.rerun()
                        
                        with col_right:
                            if st.button("✏️", key=f"edit_{task['id']}", help="Редактировать", use_container_width=True):
                                st.session_state.editing_task = task['id']
                                st.session_state.edit_task_data = task
                                st.rerun()
                
                st.divider()
else:
    st.info("📭 Нет задач, удовлетворяющих фильтрам")

# ========== ФУТЕР ==========

st.divider()
col1, col2 = st.columns(2)

with col1:
    st.caption(f"Task Planner Pro • Пользователь: {TELEGRAM_USER_ID}")

with col2:
    calendar_status = "📅 Подключен" if is_calendar_connected else "📅 Не подключен"
    st.caption(f"{calendar_status} • Автоочистка: {DAYS_TO_KEEP_COMPLETED} дней • Обновление: каждые 30 секунд")
