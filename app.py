import streamlit as st
import psycopg2
from datetime import datetime, timedelta, date
import os

# Настройки страницы
st.set_page_config(
    page_title="Task Planner Pro",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Стили
st.markdown("""
<style>
    .status-pending { background-color: #FFD700; color: #000; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .status-in_progress { background-color: #4169E1; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .status-completed { background-color: #32CD32; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .status-overdue { background-color: #DC143C; color: white; padding: 4px 8px; border-radius: 4px; font-weight: bold; }
    .deadline-urgent { color: #DC143C; font-weight: bold; }
    .deadline-warning { color: #FFA500; font-weight: bold; }
    .deadline-normal { color: #32CD32; }
    .task-card { 
        border: 1px solid #ddd; 
        border-radius: 8px; 
        padding: 12px; 
        margin-bottom: 10px; 
        background: #f9f9f9; 
        box-shadow: 0 2px 4px rgba(0,0,0,0.1); 
        color: #333;
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .task-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 8px rgba(0,0,0,0.15);
    }
    .task-card b { color: #333; }
    .task-card small { color: #666; }
    .action-btn { margin: 2px; }
    .project-name { color: #333 !important; }
    .task-title { color: #333 !important; }
    .project-group { 
        background: linear-gradient(135deg, #1E3A8A 0%, #3B82F6 100%); 
        padding: 12px 20px; 
        border-radius: 8px; 
        margin: 20px 0 15px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        color: white !important;
    }
    .project-group h4 { 
        color: white !important; 
        margin: 0;
        font-size: 1.2rem;
    }
    .collapsed { 
        background: linear-gradient(135deg, #3B82F6 0%, #60A5FA 100%);
        padding: 12px 20px; 
        border-radius: 8px; 
        margin: 20px 0 15px 0;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .collapsed h4 { 
        color: white !important; 
        margin: 0;
        font-size: 1.2rem;
    }
    .task-actions {
        display: flex;
        gap: 5px;
        margin-top: 8px;
        flex-wrap: wrap;
    }
    .task-actions button {
        padding: 4px 8px !important;
        font-size: 0.8rem !important;
        min-height: unset !important;
    }
    .task-content {
        padding: 15px;
    }
    .task-meta {
        display: flex;
        flex-wrap: wrap;
        gap: 10px;
        margin-top: 8px;
        font-size: 0.9rem;
    }
    .task-project {
        background-color: #e8f4fd;
        padding: 2px 8px;
        border-radius: 4px;
        color: #1E3A8A;
        font-weight: 500;
    }
    .task-description {
        margin-top: 8px;
        color: #666;
        font-size: 0.9rem;
        line-height: 1.4;
    }
</style>
""", unsafe_allow_html=True)

# Ваш Telegram ID
TELEGRAM_USER_ID = 209010651

# Подключение к БД
@st.cache_resource
def init_connection():
    return psycopg2.connect(
        host="dpg-d623k7m3jp1c73bhruk0-a",
        database="task_planner_3k47",
        user="task_planner_user",
        password="esbiIzvvhnGcZF1NOc4oRxUs8vyW24by",
        port=5432
    )

conn = init_connection()

# Функция для выполнения запросов
def execute_query(query, params=None):
    cursor = conn.cursor()
    try:
        cursor.execute(query, params or ())
        conn.commit()
        return True
    except Exception as e:
        conn.rollback()
        st.error(f"Ошибка базы данных: {e}")
        return False
    finally:
        cursor.close()

# Загрузка данных
@st.cache_data(ttl=30)
def load_data(project_id=None, status_filter=None, deadline_filter=None):
    cursor = conn.cursor()
    
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
            p.id AS project_id
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE p.user_id = %s
    """
    params = [TELEGRAM_USER_ID]
    
    if project_id:
        query += " AND t.project_id = %s"
        params.append(project_id)
    
    if status_filter and status_filter != 'all':
        query += " AND t.status = %s"
        params.append(status_filter)
    
    today = date.today()
    if deadline_filter == 'today':
        query += " AND t.deadline = %s"
        params.append(today)
    elif deadline_filter == 'tomorrow':
        query += " AND t.deadline = %s"
        params.append(today + timedelta(days=1))
    elif deadline_filter == 'next_3_days':
        query += " AND t.deadline BETWEEN %s AND %s"
        params.append(today)
        params.append(today + timedelta(days=3))
    elif deadline_filter == 'next_week':
        query += " AND t.deadline BETWEEN %s AND %s"
        params.append(today)
        params.append(today + timedelta(days=7))
    elif deadline_filter == 'overdue':
        query += " AND t.deadline < %s AND t.status != 'completed'"
        params.append(today)
    
    query += " ORDER BY t.deadline ASC NULLS LAST, t.status ASC"
    
    cursor.execute(query, params)
    columns = [desc[0] for desc in cursor.description]
    rows = cursor.fetchall()
    cursor.close()
    
    return [dict(zip(columns, row)) for row in rows]

# Загрузка проектов
@st.cache_data(ttl=300)
def load_projects():
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM projects WHERE user_id = %s ORDER BY name", (TELEGRAM_USER_ID,))
    projects = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
    cursor.close()
    return projects

# Обновление существующих данных
def migrate_web_data_to_telegram():
    """Перенос данных, созданных в вебе, в ваш Telegram аккаунт"""
    try:
        cursor = conn.cursor()
        
        # 1. Обновляем проекты с user_id = 1 на ваш Telegram ID
        cursor.execute("""
            UPDATE projects 
            SET user_id = %s 
            WHERE user_id = 1 OR user_id IS NULL
        """, (TELEGRAM_USER_ID,))
        
        projects_updated = cursor.rowcount
        
        # 2. Для задач, привязанных к проектам, которые были обновлены
        cursor.execute("""
            SELECT COUNT(*) 
            FROM tasks t
            JOIN projects p ON t.project_id = p.id
            WHERE p.user_id = %s
        """, (TELEGRAM_USER_ID,))
        
        tasks_count = cursor.fetchone()[0]
        
        conn.commit()
        
        return {
            'success': True,
            'projects_updated': projects_updated,
            'tasks_migrated': tasks_count
        }
        
    except Exception as e:
        conn.rollback()
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        cursor.close()

# Создание проекта
def create_project(name):
    query = """
        INSERT INTO projects (name, user_id, created_at)
        VALUES (%s, %s, NOW())
        RETURNING id
    """
    cursor = conn.cursor()
    try:
        cursor.execute(query, (name, TELEGRAM_USER_ID))
        project_id = cursor.fetchone()[0]
        conn.commit()
        return project_id
    except Exception as e:
        conn.rollback()
        st.error(f"Ошибка создания проекта: {e}")
        return None
    finally:
        cursor.close()

# Создание задачи
def create_task(title, description, deadline, status, project_id):
    query = """
        INSERT INTO tasks (title, description, deadline, status, project_id, created_at)
        VALUES (%s, %s, %s, %s, %s, NOW())
    """
    return execute_query(query, (title, description, deadline, status, project_id))

# Обновление статуса задачи
def update_task_status(task_id, status):
    if status == 'completed':
        query = "UPDATE tasks SET status = %s, completed_at = NOW() WHERE id = %s"
    else:
        query = "UPDATE tasks SET status = %s WHERE id = %s"
    return execute_query(query, (status, task_id))

# Обновление задачи
def update_task(task_id, title, description, deadline, status, project_id):
    query = """
        UPDATE tasks 
        SET title = %s, description = %s, deadline = %s, status = %s, project_id = %s
        WHERE id = %s
    """
    return execute_query(query, (title, description, deadline, status, project_id, task_id))

# Удаление задачи
def delete_task(task_id):
    query = "DELETE FROM tasks WHERE id = %s"
    return execute_query(query, (task_id,))

# Статистика
def get_statistics(tasks):
    total = len(tasks)
    pending = len([t for t in tasks if t['status'] == 'pending'])
    in_progress = len([t for t in tasks if t['status'] == 'in_progress'])
    completed = len([t for t in tasks if t['status'] == 'completed'])
    
    today = date.today()
    overdue = len([t for t in tasks if (t['deadline'] and t['deadline'] < today and t['status'] != 'completed')])
    
    due_today = len([t for t in tasks if t['deadline'] == today])
    due_tomorrow = len([t for t in tasks if t['deadline'] == today + timedelta(days=1)])
    
    return {
        'total': total,
        'pending': pending,
        'in_progress': in_progress,
        'completed': completed,
        'overdue': overdue,
        'due_today': due_today,
        'due_tomorrow': due_tomorrow
    }

# Инициализация session state
if 'show_add_task' not in st.session_state:
    st.session_state.show_add_task = False
if 'show_add_project' not in st.session_state:
    st.session_state.show_add_project = False
if 'editing_task' not in st.session_state:
    st.session_state.editing_task = None
if 'edit_task_data' not in st.session_state:
    st.session_state.edit_task_data = None
if 'data_migrated' not in st.session_state:
    st.session_state.data_migrated = False
# Инициализация состояния для свернутых проектов
if 'collapsed_projects' not in st.session_state:
    st.session_state.collapsed_projects = {}

# Заголовок
st.title("🚀 Task Planner Pro Dashboard")
st.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

# Форма редактирования задачи (ПОМЕЩЕНА ВВЕРХУ ДЛЯ УДОБСТВА)
if st.session_state.get('editing_task'):
    st.divider()
    st.subheader("✏️ Редактировать задачу")
    
    task = st.session_state.edit_task_data
    
    with st.form("edit_task_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            edit_title = st.text_input("Название задачи*", value=task['title'])
            edit_description = st.text_area("Описание", value=task['description'] or "", height=100)
        
        with col2:
            all_projects = load_projects()
            project_names = [p['name'] for p in all_projects]
            
            project_index = 0
            if task['project_name'] and task['project_name'] in project_names:
                project_index = project_names.index(task['project_name']) + 1
            
            selected_project_name = st.selectbox(
                "Проект*",
                ['Без проекта'] + project_names,
                index=project_index
            )
            selected_project = next((p for p in all_projects if p['name'] == selected_project_name), None)
            
            edit_deadline = st.date_input(
                "Дедлайн*",
                value=task['deadline'] if task['deadline'] else date.today() + timedelta(days=3),
                min_value=date.today() - timedelta(days=365)
            )
            
            # Все возможные статусы, включая "В работе"
            status_options = {
                '⏳ В ожидании': 'pending',
                '🔄 В работе': 'in_progress',
                '✅ Завершено': 'completed'
            }
            current_status_name = next((k for k, v in status_options.items() if v == task['status']), '⏳ В ожидании')
            selected_status_name = st.selectbox("Статус*", list(status_options.keys()), index=list(status_options.keys()).index(current_status_name))
            edit_status = status_options[selected_status_name]
        
        col_btn1, col_btn2, col_btn3 = st.columns(3)
        with col_btn1:
            submitted = st.form_submit_button("✅ Сохранить изменения", use_container_width=True)
        with col_btn2:
            cancelled = st.form_submit_button("❌ Отмена", use_container_width=True)
        with col_btn3:
            # Кнопка быстрого завершения
            if task['status'] != 'completed':
                if st.form_submit_button("✅ Завершить задачу", use_container_width=True):
                    if update_task_status(task['id'], 'completed'):
                        st.success(f"✅ Задача '{task['title']}' завершена!")
                        st.session_state.editing_task = None
                        st.session_state.edit_task_data = None
                        st.cache_data.clear()
                        st.rerun()
        
        if submitted:
            if not edit_title.strip():
                st.error("❌ Название задачи обязательно")
            else:
                project_id = selected_project['id'] if selected_project else None
                success = update_task(
                    task['id'],
                    edit_title.strip(),
                    edit_description.strip() if edit_description else None,
                    edit_deadline,
                    edit_status,
                    project_id
                )
                if success:
                    st.success(f"✅ Задача '{edit_title}' обновлена!")
                    st.session_state.editing_task = None
                    st.session_state.edit_task_data = None
                    st.cache_data.clear()
                    st.rerun()
        
        if cancelled:
            st.session_state.editing_task = None
            st.session_state.edit_task_data = None
            st.rerun()
    
    st.divider()

# Кнопка для миграции данных
if not st.session_state.data_migrated:
    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(f"👤 Используется ваш Telegram ID: {TELEGRAM_USER_ID}")
    with col2:
        if st.button("🔄 Перенести данные в мой аккаунт", use_container_width=True):
            with st.spinner("Перенос данных..."):
                result = migrate_web_data_to_telegram()
                if result['success']:
                    st.success(f"✅ Данные успешно перенесены! Обновлено проектов: {result['projects_updated']}, задач: {result['tasks_migrated']}")
                    st.session_state.data_migrated = True
                    st.cache_data.clear()
                    st.rerun()
                else:
                    st.error(f"❌ Ошибка при переносе данных: {result['error']}")

# Быстрые действия
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("➕ Добавить задачу", use_container_width=True):
        st.session_state.show_add_task = True
        st.rerun()
with col2:
    if st.button("📁 Добавить проект", use_container_width=True):
        st.session_state.show_add_project = True
        st.rerun()
with col3:
    if st.button("🔄 Обновить данные", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.divider()

# Форма добавления проекта
if st.session_state.get('show_add_project'):
    st.subheader("📁 Создать новый проект")
    
    with st.form("add_project_form"):
        project_name = st.text_input("Название проекта*", placeholder="Например: Веб-сайт, Мобильное приложение")
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submitted = st.form_submit_button("✅ Создать проект", use_container_width=True)
        with col_btn2:
            cancelled = st.form_submit_button("❌ Отмена", use_container_width=True)
        
        if submitted:
            if not project_name.strip():
                st.error("❌ Название проекта обязательно")
            else:
                project_id = create_project(project_name.strip())
                if project_id:
                    st.success(f"✅ Проект '{project_name}' создан! ID: {project_id}")
                    st.session_state.show_add_project = False
                    st.cache_data.clear()
                    st.rerun()
        
        if cancelled:
            st.session_state.show_add_project = False
            st.rerun()
    
    st.divider()

# Форма добавления задачи
if st.session_state.get('show_add_task'):
    st.subheader("➕ Создать новую задачу")
    
    with st.form("add_task_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            task_title = st.text_input("Название задачи*", placeholder="Например: Разработать макет главной страницы")
            task_description = st.text_area("Описание", placeholder="Подробное описание задачи...", height=100)
        
        with col2:
            all_projects = load_projects()
            project_names = [p['name'] for p in all_projects]
            selected_project_name = st.selectbox("Проект*", ['Без проекта'] + project_names)
            selected_project = next((p for p in all_projects if p['name'] == selected_project_name), None)
            
            task_deadline = st.date_input(
                "Дедлайн*",
                min_value=date.today(),
                value=date.today() + timedelta(days=3)
            )
            
            status_options = {
                '⏳ В ожидании': 'pending',
                '🔄 В работе': 'in_progress',
                '✅ Завершено': 'completed'
            }
            selected_status_name = st.selectbox("Статус*", list(status_options.keys()))
            task_status = status_options[selected_status_name]
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submitted = st.form_submit_button("✅ Создать задачу", use_container_width=True)
        with col_btn2:
            cancelled = st.form_submit_button("❌ Отмена", use_container_width=True)
        
        if submitted:
            if not task_title.strip():
                st.error("❌ Название задачи обязательно")
            else:
                project_id = selected_project['id'] if selected_project else None
                success = create_task(
                    task_title.strip(),
                    task_description.strip() if task_description else None,
                    task_deadline,
                    task_status,
                    project_id
                )
                if success:
                    st.success(f"✅ Задача '{task_title}' создана!")
                    st.session_state.show_add_task = False
                    st.cache_data.clear()
                    st.rerun()
        
        if cancelled:
            st.session_state.show_add_task = False
            st.rerun()
    
    st.divider()

# Сайдбар - фильтры
with st.sidebar:
    st.header("🎛️ Фильтры")
    
    # Информация о пользователе
    st.info(f"👤 Пользователь: {TELEGRAM_USER_ID}")
    
    # Выбор проекта
    projects = load_projects()
    project_options = ['Все проекты'] + [p['name'] for p in projects]
    selected_project = st.selectbox("Проект", project_options)
    project_id = next((p['id'] for p in projects if p['name'] == selected_project), None) if selected_project != 'Все проекты' else None
    
    # Фильтр по статусу
    status_options = {
        'Все статусы': 'all',
        '⏳ В ожидании': 'pending',
        '🔄 В работе': 'in_progress',
        '✅ Завершённые': 'completed',
        '⚠️ Просроченные': 'overdue'
    }
    selected_status = st.selectbox("Статус", list(status_options.keys()))
    status_filter = status_options[selected_status]
    
    # Фильтр по дедлайну
    st.subheader("📅 Дедлайн")
    deadline_options = {
        'Все': None,
        'Сегодня': 'today',
        'Завтра': 'tomorrow',
        'Ближайшие 3 дня': 'next_3_days',
        'Ближайшая неделя': 'next_week',
        'Просроченные': 'overdue'
    }
    selected_deadline = st.selectbox("Период", list(deadline_options.keys()))
    deadline_filter = deadline_options[selected_deadline]
    
    st.divider()
    
    # Загрузка данных с фильтрами
    tasks = load_data(
        project_id=project_id,
        status_filter=status_filter if status_filter != 'all' else None,
        deadline_filter=deadline_filter
    )
    
    st.info(f"📈 Показано задач: {len(tasks)}")

# Статистика
stats = get_statistics(tasks)

col1, col2, col3, col4, col5 = st.columns(5)
with col1:
    st.metric("Всего задач", stats['total'])
with col2:
    st.metric("⏳ В ожидании", stats['pending'])
with col3:
    st.metric("🔄 В работе", stats['in_progress'])
with col4:
    st.metric("✅ Завершено", stats['completed'])
with col5:
    st.metric("⚠️ Просрочено", stats['overdue'], delta_color="inverse")

# Ближайшие дедлайны
st.divider()
st.subheader("⏰ Ближайшие дедлайны")

today = date.today()
# ИСКЛЮЧАЕМ завершенные задачи из этого раздела
urgent_tasks = [t for t in tasks if t['deadline'] and t['status'] != 'completed' and today <= t['deadline'] <= today + timedelta(days=7)]
urgent_tasks.sort(key=lambda x: x['deadline'])

if urgent_tasks:
    for task in urgent_tasks[:10]:
        days_left = (task['deadline'] - today).days
        
        if days_left < 0:
            icon = "🔴"
            deadline_class = "deadline-urgent"
        elif days_left == 0:
            icon = "🟠"
            deadline_class = "deadline-urgent"
        elif days_left <= 2:
            icon = "🟡"
            deadline_class = "deadline-warning"
        else:
            icon = "🟢"
            deadline_class = "deadline-normal"
        
        status_map = {
            'pending': '<span class="status-pending">⏳ В ожидании</span>',
            'in_progress': '<span class="status-in_progress">🔄 В работе</span>',
            'completed': '<span class="status-completed">✅ Завершено</span>',
            'overdue': '<span class="status-overdue">⚠️ Просрочено</span>'
        }
        status_html = status_map.get(task['status'], task['status'])
        
        with st.expander(f"{icon} {task['title']}"):
            col1, col2, col3 = st.columns([2, 2, 1])
            
            with col1:
                st.markdown(f"**Проект:** {task['project_name'] or '—'}")
                st.markdown(f"**Статус:** {status_html}", unsafe_allow_html=True)
            
            with col2:
                deadline_str = task['deadline'].strftime('%d.%m.%Y') if task['deadline'] else '—'
                st.markdown(f'<p><b>Дедлайн:</b> <span class="{deadline_class}">{deadline_str}</span></p>', unsafe_allow_html=True)
                if days_left >= 0:
                    st.markdown(f"**Осталось:** {days_left} дн.")
            
            with col3:
                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if task['status'] != 'completed':
                        if st.button("✅", key=f"complete_{task['id']}", help="Завершить", use_container_width=True):
                            if update_task_status(task['id'], 'completed'):
                                st.success("✅ Задача завершена!")
                                st.cache_data.clear()
                                st.rerun()
                
                with col_b:
                    if st.button("🔄", key=f"inprogress_{task['id']}", help="В работу", use_container_width=True):
                        if update_task_status(task['id'], 'in_progress'):
                            st.success("🔄 Задача в работе!")
                            st.cache_data.clear()
                            st.rerun()
                
                with col_c:
                    if st.button("✏️", key=f"edit_deadline_{task['id']}", help="Редактировать", use_container_width=True):
                        st.session_state.editing_task = task['id']
                        st.session_state.edit_task_data = task
                        st.rerun()
            
            if task['description']:
                st.markdown(f"**Описание:** {task['description']}")
else:
    st.info("Нет активных задач с дедлайнами в ближайшие 7 дней (завершенные задачи скрыты)")

# Канбан-доска
st.divider()
st.subheader("📋 Канбан-доска")

status_order = ['pending', 'in_progress', 'completed', 'overdue']
status_names = {
    'pending': '⏳ В ожидании',
    'in_progress': '🔄 В работе',
    'completed': '✅ Завершено',
    'overdue': '⚠️ Просрочено'
}

cols = st.columns(len(status_order))

for idx, status in enumerate(status_order):
    with cols[idx]:
        st.markdown(f"### {status_names[status]}")
        
        status_tasks = [t for t in tasks if t['status'] == status]
        
        if not status_tasks:
            st.caption("_Нет задач_")
        else:
            for task in status_tasks[:8]:
                deadline_str = task['deadline'].strftime('%d.%m') if task['deadline'] else '—'
                
                if task['deadline']:
                    days_left = (task['deadline'] - today).days
                    if days_left < 0:
                        deadline_class = "deadline-urgent"
                    elif days_left <= 2:
                        deadline_class = "deadline-warning"
                    else:
                        deadline_class = "deadline-normal"
                else:
                    deadline_class = ""
                
                task_html = f"""
                <div class="task-card">
                    <b class="task-title">{task['title']}</b><br>
                    <small class="project-name">📁 {task['project_name'] or 'Без проекта'}</small><br>
                    <small>🕗 <span class="{deadline_class}">{deadline_str}</span></small>
                </div>
                """
                st.markdown(task_html, unsafe_allow_html=True)
            
            if len(status_tasks) > 8:
                st.caption(f"... и ещё {len(status_tasks) - 8} задач")

# Список задач в стиле "Дедлайны" с группировкой по проектам
st.divider()
st.subheader("📝 Список задач")

if tasks:
    # Группируем задачи по проектам
    grouped_tasks = {}
    for task in tasks:
        project_name = task['project_name'] or 'Без проекта'
        if project_name not in grouped_tasks:
            grouped_tasks[project_name] = []
        grouped_tasks[project_name].append(task)
    
    # Сортируем проекты по алфавиту
    sorted_projects = sorted(grouped_tasks.keys())
    
    for project_name in sorted_projects:
        project_tasks = grouped_tasks[project_name]
        
        # Определяем, свернут ли проект
        is_collapsed = st.session_state.collapsed_projects.get(project_name, False)
        
        # Заголовок проекта с кнопкой сворачивания
        col1, col2 = st.columns([5, 1])
        
        with col1:
            if is_collapsed:
                st.markdown(f'<div class="collapsed"><h4>📁 {project_name} ({len(project_tasks)} задач) 🔽</h4></div>', unsafe_allow_html=True)
            else:
                st.markdown(f'<div class="project-group"><h4>📁 {project_name} ({len(project_tasks)} задач) 🔼</h4></div>', unsafe_allow_html=True)
        
        with col2:
            button_text = "Свернуть" if not is_collapsed else "Развернуть"
            if st.button(button_text, key=f"toggle_{project_name}", use_container_width=True):
                st.session_state.collapsed_projects[project_name] = not is_collapsed
                st.rerun()
        
        # Отображаем задачи проекта, если не свернуто
        if not is_collapsed:
            for task in project_tasks:
                days_left = None
                if task['deadline']:
                    days_left = (task['deadline'] - today).days
                
                # Определяем иконку и цвет дедлайна
                if not task['deadline']:
                    icon = "⚪"
                    deadline_class = ""
                elif days_left < 0:
                    icon = "🔴"
                    deadline_class = "deadline-urgent"
                elif days_left == 0:
                    icon = "🟠"
                    deadline_class = "deadline-urgent"
                elif days_left <= 2:
                    icon = "🟡"
                    deadline_class = "deadline-warning"
                else:
                    icon = "🟢"
                    deadline_class = "deadline-normal"
                
                # Определяем статус задачи
                status_map = {
                    'pending': '<span class="status-pending">⏳ В ожидании</span>',
                    'in_progress': '<span class="status-in_progress">🔄 В работе</span>',
                    'completed': '<span class="status-completed">✅ Завершено</span>',
                    'overdue': '<span class="status-overdue">⚠️ Просрочено</span>'
                }
                status_html = status_map.get(task['status'], task['status'])
                
                deadline_str = task['deadline'].strftime('%d.%m.%Y') if task['deadline'] else '—'
                
                # Создаем карточку задачи в стиле "Дедлайнов"
                with st.expander(f"{icon} {task['title']}"):
                    # Верхняя часть карточки
                    col_a, col_b, col_c = st.columns([2, 2, 1])
                    
                    with col_a:
                        st.markdown(f"**📁 Проект:** {task['project_name'] or '—'}")
                        st.markdown(f"**📊 Статус:** {status_html}", unsafe_allow_html=True)
                    
                    with col_b:
                        st.markdown(f'<p><b>⏰ Дедлайн:</b> <span class="{deadline_class}">{deadline_str}</span></p>', unsafe_allow_html=True)
                        if days_left is not None and days_left >= 0:
                            st.markdown(f"**📅 Осталось:** {days_left} дн.")
                        elif days_left is not None:
                            st.markdown(f"**⚠️ Просрочено на:** {abs(days_left)} дн.")
                    
                    with col_c:
                        # Кнопки действий в строку
                        action_col1, action_col2, action_col3 = st.columns(3)
                        
                        with action_col1:
                            if task['status'] != 'completed':
                                if st.button("✅", key=f"list_complete_{task['id']}", help="Завершить", use_container_width=True):
                                    if update_task_status(task['id'], 'completed'):
                                        st.success("✅ Задача завершена!")
                                        st.cache_data.clear()
                                        st.rerun()
                        
                        with action_col2:
                            if task['status'] != 'in_progress' and task['status'] != 'completed':
                                if st.button("🔄", key=f"list_inprogress_{task['id']}", help="В работу", use_container_width=True):
                                    if update_task_status(task['id'], 'in_progress'):
                                        st.success("🔄 Задача в работе!")
                                        st.cache_data.clear()
                                        st.rerun()
                        
                        with action_col3:
                            if st.button("✏️", key=f"list_edit_{task['id']}", help="Редактировать", use_container_width=True):
                                st.session_state.editing_task = task['id']
                                st.session_state.edit_task_data = task
                                st.rerun()
                    
                    # Описание задачи
                    if task['description']:
                        st.markdown("---")
                        st.markdown(f"**📝 Описание:** {task['description']}")
                    
                    # Дополнительные кнопки действий
                    col_x, col_y, col_z = st.columns(3)
                    with col_x:
                        if st.button("📋 Подробнее", key=f"details_{task['id']}", use_container_width=True):
                            # Здесь можно добавить дополнительную информацию
                            st.info(f"Задача создана: {task['created_at'].strftime('%d.%m.%Y') if task['created_at'] else '—'}")
                    
                    with col_y:
                        if task['status'] == 'completed' and task['completed_at']:
                            st.info(f"✅ Завершена: {task['completed_at'].strftime('%d.%m.%Y') if task['completed_at'] else '—'}")
                    
                    with col_z:
                        if st.button("🗑️ Удалить", key=f"delete_{task['id']}", use_container_width=True):
                            if delete_task(task['id']):
                                st.success("🗑️ Задача удалена!")
                                st.cache_data.clear()
                                st.rerun()
else:
    st.info("Нет задач, удовлетворяющих фильтрам")

# Кнопки управления внизу
st.divider()
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("⬆️ Наверх", use_container_width=True):
        st.rerun()
with col2:
    if st.button("🔄 Сбросить фильтры", use_container_width=True):
        st.session_state.collapsed_projects = {}
        st.cache_data.clear()
        st.rerun()
with col3:
    if st.button("📋 Развернуть все проекты", use_container_width=True):
        for project_name in st.session_state.collapsed_projects:
            st.session_state.collapsed_projects[project_name] = False
        st.rerun()

# Footer
st.divider()
st.caption(f"Task Planner Pro Dashboard • Пользователь: {TELEGRAM_USER_ID} • Данные обновляются каждые 30 секунд")
