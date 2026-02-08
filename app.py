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
        color: #333; /* Добавил цвет текста по умолчанию */
    }
    .task-card b { color: #333; } /* Цвет для жирного текста */
    .task-card small { color: #666; } /* Цвет для мелкого текста */
    .action-btn { margin: 2px; }
    .project-name { color: #333 !important; } /* Явно задаем цвет для названия проекта */
    .task-title { color: #333 !important; } /* Явно задаем цвет для названия задачи */
</style>
""", unsafe_allow_html=True)

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

# Функция для выполнения запросов (INSERT/UPDATE/DELETE)
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
def load_data(user_id=None, project_id=None, status_filter=None, deadline_filter=None):
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
            p.id AS project_id,
            p.user_id
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        WHERE 1=1
    """
    params = []
    
    if user_id:
        query += " AND p.user_id = %s"
        params.append(user_id)
    
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

# Загрузка пользователей
@st.cache_data(ttl=300)
def load_users():
    cursor = conn.cursor()
    cursor.execute("""
        SELECT DISTINCT user_id 
        FROM projects 
        ORDER BY user_id
    """)
    users = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return users

# Загрузка проектов пользователя
@st.cache_data(ttl=300)
def load_projects(user_id=None):
    cursor = conn.cursor()
    if user_id:
        cursor.execute("SELECT id, name FROM projects WHERE user_id = %s ORDER BY name", (user_id,))
    else:
        cursor.execute("SELECT id, name FROM projects ORDER BY name")
    projects = [{"id": row[0], "name": row[1]} for row in cursor.fetchall()]
    cursor.close()
    return projects

# Получение проекта по ID
def get_project_by_id(project_id):
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, user_id FROM projects WHERE id = %s", (project_id,))
    row = cursor.fetchone()
    cursor.close()
    if row:
        return {"id": row[0], "name": row[1], "user_id": row[2]}
    return None

# Создание нового проекта
def create_project(name, user_id):
    query = """
        INSERT INTO projects (name, user_id, created_at)
        VALUES (%s, %s, NOW())
        RETURNING id
    """
    cursor = conn.cursor()
    try:
        cursor.execute(query, (name, user_id))
        project_id = cursor.fetchone()[0]
        conn.commit()
        return project_id
    except Exception as e:
        conn.rollback()
        st.error(f"Ошибка создания проекта: {e}")
        return None
    finally:
        cursor.close()

# Создание новой задачи
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

# Заголовок
st.title("🚀 Task Planner Pro Dashboard")
st.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

# Быстрые действия в шапке
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
        col1, col2 = st.columns(2)
        with col1:
            project_name = st.text_input("Название проекта*", placeholder="Например: Веб-сайт, Мобильное приложение")
        with col2:
            project_user_id = st.number_input("ID пользователя*", min_value=1, value=1, step=1)
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submitted = st.form_submit_button("✅ Создать проект", use_container_width=True)
        with col_btn2:
            cancelled = st.form_submit_button("❌ Отмена", use_container_width=True)
        
        if submitted:
            if not project_name.strip():
                st.error("❌ Название проекта обязательно")
            else:
                project_id = create_project(project_name.strip(), project_user_id)
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
            # Загрузка проектов для выбора
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
    
    # Выбор пользователя
    users = load_users()
    user_options = ['Все пользователи'] + [str(u) for u in users]
    selected_user = st.selectbox("Пользователь", user_options)
    user_id = int(selected_user) if selected_user != 'Все пользователи' else None
    
    # Выбор проекта
    projects = load_projects(user_id)
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
        user_id=user_id,
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
urgent_tasks = [t for t in tasks if t['deadline'] and today <= t['deadline'] <= today + timedelta(days=7)]
urgent_tasks.sort(key=lambda x: x['deadline'])

if urgent_tasks:
    for task in urgent_tasks[:10]:
        days_left = (task['deadline'] - today).days
        
        # Иконка и цвет
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
        
        # Статус с цветом
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
                # Быстрые действия
                if task['status'] != 'completed':
                    if st.button("✅ Завершить", key=f"complete_{task['id']}", use_container_width=True):
                        if update_task_status(task['id'], 'completed'):
                            st.success("✅ Задача завершена!")
                            st.cache_data.clear()
                            st.rerun()
                
                if st.button("✏️ Редактировать", key=f"edit_{task['id']}", use_container_width=True):
                    st.session_state.editing_task = task['id']
                    st.session_state.edit_task_data = task
                    st.rerun()
                
                if st.button("🗑️ Удалить", key=f"delete_{task['id']}", use_container_width=True):
                    if delete_task(task['id']):
                        st.success("✅ Задача удалена!")
                        st.cache_data.clear()
                        st.rerun()
            
            if task['description']:
                st.markdown(f"**Описание:** {task['description']}")
else:
    st.info("Нет задач с дедлайнами в ближайшие 7 дней")

# Форма редактирования задачи
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
            current_project = get_project_by_id(task['project_id']) if task['project_id'] else None
            project_names = [p['name'] for p in all_projects]
            
            # Находим индекс текущего проекта
            project_index = 0
            if current_project and current_project['name'] in project_names:
                project_index = project_names.index(current_project['name']) + 1
            
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
            
            status_options = {
                '⏳ В ожидании': 'pending',
                '🔄 В работе': 'in_progress',
                '✅ Завершено': 'completed'
            }
            current_status_name = next((k for k, v in status_options.items() if v == task['status']), '⏳ В ожидании')
            selected_status_name = st.selectbox("Статус*", list(status_options.keys()), index=list(status_options.keys()).index(current_status_name))
            edit_status = status_options[selected_status_name]
        
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            submitted = st.form_submit_button("✅ Сохранить изменения", use_container_width=True)
        with col_btn2:
            cancelled = st.form_submit_button("❌ Отмена", use_container_width=True)
        
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
                
                # Цвет дедлайна
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

# Таблица задач
st.divider()
st.subheader("📝 Список задач")

if tasks:
    for task in tasks:
        status_map = {
            'pending': '⏳ В ожидании',
            'in_progress': '🔄 В работе',
            'completed': '✅ Завершено',
            'overdue': '⚠️ Просрочено'
        }
        status_display = status_map.get(task['status'], task['status'])
        
        deadline_str = task['deadline'].strftime('%d.%m.%Y') if task['deadline'] else '—'
        
        with st.container():
            col1, col2, col3, col4, col5 = st.columns([3, 2, 1.5, 1.5, 1])
            with col1:
                st.markdown(f"**{task['title']}**")
                if task['description']:
                    st.caption(task['description'][:60] + "..." if len(task['description']) > 60 else task['description'])
            with col2:
                st.markdown(f"📁 {task['project_name'] or '—'}")
            with col3:
                st.markdown(status_display)
            with col4:
                st.markdown(f"🕗 {deadline_str}")
            with col5:
                if st.button("✏️", key=f"table_edit_{task['id']}", help="Редактировать"):
                    st.session_state.editing_task = task['id']
                    st.session_state.edit_task_data = task
                    st.rerun()
            
            st.divider()
else:
    st.info("Нет задач, удовлетворяющих фильтрам")

# Footer
st.divider()
st.caption("Task Planner Pro Dashboard • Данные обновляются каждые 30 секунд")
