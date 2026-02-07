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
    .task-card { border:1px solid #ddd; border-radius:8px; padding:12px; margin-bottom:10px; background:#f9f9f9; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
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

# Загрузка данных напрямую через курсор (без pandas)
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

# Статистика
def get_statistics(tasks):
    total = len(tasks)
    pending = len([t for t in tasks if t['status'] == 'pending'])
    in_progress = len([t for t in tasks if t['status'] == 'in_progress'])
    completed = len([t for t in tasks if t['status'] == 'completed'])
    overdue = len([t for t in tasks if t['status'] == 'overdue' or (t['deadline'] and t['deadline'] < date.today() and t['status'] != 'completed')])
    
    today = date.today()
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

# Заголовок
st.title("🚀 Task Planner Pro Dashboard")
st.caption(f"Обновлено: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}")

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
    for task in urgent_tasks[:10]:  # Показываем первые 10
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
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown(f"**Проект:** {task['project_name'] or '—'}")
                st.markdown(f"**Статус:** {status_html}", unsafe_allow_html=True)
            
            with col2:
                deadline_str = task['deadline'].strftime('%d.%m.%Y') if task['deadline'] else '—'
                st.markdown(f'<p><b>Дедлайн:</b> <span class="{deadline_class}">{deadline_str}</span></p>', unsafe_allow_html=True)
                if days_left >= 0:
                    st.markdown(f"**Осталось:** {days_left} дн.")
            
            if task['description']:
                st.markdown(f"**Описание:** {task['description']}")
else:
    st.info("Нет задач с дедлайнами в ближайшие 7 дней")

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
            for task in status_tasks[:8]:  # Ограничиваем до 8 задач на колонку
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
                    <b>{task['title']}</b><br>
                    <small>📁 {task['project_name'] or 'Без проекта'}</small><br>
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
            col1, col2, col3, col4 = st.columns([3, 2, 2, 2])
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
            st.divider()
else:
    st.info("Нет задач, удовлетворяющих фильтрам")

# Footer
st.divider()
st.caption("Task Planner Pro Dashboard • Данные обновляются каждые 30 секунд")
