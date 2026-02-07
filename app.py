import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime, timedelta, date
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
    .metric-card { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); border-radius: 10px; padding: 20px; color: white; }
    .deadline-urgent { color: #DC143C; font-weight: bold; }
    .deadline-warning { color: #FFA500; font-weight: bold; }
    .deadline-normal { color: #32CD32; }
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

# Загрузка данных
@st.cache_data(ttl=30)
def load_data(user_id=None):
    query = """
        SELECT 
            t.id,
            t.title AS task_name,
            t.description,
            t.deadline,
            t.status,
            t.created_at,
            t.completed_at,
            t.updated_at,
            p.id AS project_id,
            p.name AS project_name,
            p.user_id
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
    """
    
    if user_id:
        query += f" WHERE p.user_id = {user_id}"
    
    query += " ORDER BY t.deadline ASC NULLS LAST"
    
    return pd.read_sql_query(query, conn)

# Загрузка всех пользователей
@st.cache_data(ttl=300)
def load_users():
    query = """
        SELECT DISTINCT user_id, COUNT(*) as project_count
        FROM projects
        GROUP BY user_id
        ORDER BY user_id
    """
    return pd.read_sql_query(query, conn)

# Функция для получения статистики
@st.cache_data(ttl=30)
def get_statistics(df):
    total = len(df)
    pending = len(df[df['status'] == 'pending'])
    in_progress = len(df[df['status'] == 'in_progress'])
    completed = len(df[df['status'] == 'completed'])
    overdue = len(df[(df['status'] == 'overdue') | ((df['deadline'] < pd.Timestamp.now()) & (df['status'] != 'completed'))])
    
    today = pd.Timestamp.now().date()
    due_today = len(df[df['deadline'] == today])
    due_tomorrow = len(df[df['deadline'] == today + timedelta(days=1)])
    
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

# Загрузка данных
users_df = load_users()
df = load_data()

# Сайдбар - фильтры
with st.sidebar:
    st.header("🎛️ Фильтры")
    
    # Выбор пользователя
    user_options = ['Все пользователи'] + users_df['user_id'].astype(str).tolist()
    selected_user = st.selectbox("Пользователь", user_options)
    
    if selected_user != 'Все пользователи':
        df = load_data(int(selected_user))
    else:
        df = load_data()
    
    # Фильтр по проекту
    project_options = ['Все проекты'] + df['project_name'].dropna().unique().tolist()
    selected_project = st.selectbox("Проект", project_options)
    
    if selected_project != 'Все проекты':
        df = df[df['project_name'] == selected_project]
    
    # Фильтр по статусу
    status_options = {
        'Все статусы': ['pending', 'in_progress', 'completed', 'overdue'],
        '⏳ В ожидании': ['pending'],
        '🔄 В работе': ['in_progress'],
        '✅ Завершённые': ['completed'],
        '⚠️ Просроченные': ['overdue']
    }
    selected_status_filter = st.selectbox("Статус", list(status_options.keys()))
    df = df[df['status'].isin(status_options[selected_status_filter])]
    
    # Фильтр по дедлайну
    st.subheader("📅 Дедлайн")
    deadline_filter = st.selectbox("Период", [
        'Все',
        'Сегодня',
        'Завтра',
        'Ближайшие 3 дня',
        'Ближайшая неделя',
        'Просроченные'
    ])
    
    today = pd.Timestamp.now().date()
    
    if deadline_filter == 'Сегодня':
        df = df[df['deadline'] == today]
    elif deadline_filter == 'Завтра':
        df = df[df['deadline'] == today + timedelta(days=1)]
    elif deadline_filter == 'Ближайшие 3 дня':
        df = df[(df['deadline'] >= today) & (df['deadline'] <= today + timedelta(days=3))]
    elif deadline_filter == 'Ближайшая неделя':
        df = df[(df['deadline'] >= today) & (df['deadline'] <= today + timedelta(days=7))]
    elif deadline_filter == 'Просроченные':
        df = df[df['deadline'] < today]
    
    st.divider()
    st.info(f"📈 Показано задач: {len(df)}")

# Статистика
stats = get_statistics(df)

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

# Графики
col1, col2 = st.columns(2)

with col1:
    # График по статусам
    st.subheader("📊 Распределение по статусам")
    status_counts = df['status'].value_counts().reset_index()
    status_counts.columns = ['status', 'count']
    status_map = {
        'pending': '⏳ В ожидании',
        'in_progress': '🔄 В работе',
        'completed': '✅ Завершено',
        'overdue': '⚠️ Просрочено'
    }
    status_counts['status'] = status_counts['status'].map(status_map)
    
    fig = px.pie(
        status_counts,
        values='count',
        names='status',
        color='status',
        color_discrete_map={
            '⏳ В ожидании': '#FFD700',
            '🔄 В работе': '#4169E1',
            '✅ Завершено': '#32CD32',
            '⚠️ Просрочено': '#DC143C'
        }
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    st.plotly_chart(fig, use_container_width=True)

with col2:
    # График по проектам
    st.subheader("📁 Задач по проектам")
    project_counts = df.groupby('project_name').size().reset_index(name='count')
    project_counts = project_counts.sort_values('count', ascending=True)
    
    fig = px.bar(
        project_counts,
        x='count',
        y='project_name',
        orientation='h',
        color='count',
        color_continuous_scale='Blues'
    )
    fig.update_layout(showlegend=False, yaxis_title="Проект", xaxis_title="Количество задач")
    st.plotly_chart(fig, use_container_width=True)

# Ближайшие дедлайны
st.divider()
st.subheader("⏰ Ближайшие дедлайны")

today = pd.Timestamp.now().date()
next_7_days = today + timedelta(days=7)

urgent_tasks = df[(df['deadline'] >= today) & (df['deadline'] <= next_7_days)].sort_values('deadline')

if not urgent_tasks.empty:
    for _, task in urgent_tasks.iterrows():
        days_left = (task['deadline'] - today).days
        
        # Определяем цвет и иконку
        if days_left < 0:
            icon = "🔴"
            color_class = "deadline-urgent"
        elif days_left == 0:
            icon = "🟠"
            color_class = "deadline-urgent"
        elif days_left <= 2:
            icon = "🟡"
            color_class = "deadline-warning"
        else:
            icon = "🟢"
            color_class = "deadline-normal"
        
        # Статус с цветом
        status_map = {
            'pending': '<span class="status-pending">⏳ В ожидании</span>',
            'in_progress': '<span class="status-in_progress">🔄 В работе</span>',
            'completed': '<span class="status-completed">✅ Завершено</span>',
            'overdue': '<span class="status-overdue">⚠️ Просрочено</span>'
        }
        status_html = status_map.get(task['status'], task['status'])
        
        with st.expander(f"{icon} {task['task_name']}"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"**Проект:** {task['project_name'] or '—'}")
                st.markdown(f"**Статус:** {status_html}", unsafe_allow_html=True)
            
            with col2:
                deadline_str = task['deadline'].strftime('%d.%m.%Y') if pd.notnull(task['deadline']) else '—'
                st.markdown(f'<p><b>Дедлайн:</b> <span class="{color_class}">{deadline_str}</span></p>', unsafe_allow_html=True)
                
                if days_left >= 0:
                    st.markdown(f"**Осталось:** {days_left} дн.")
            
            with col3:
                if pd.notnull(task['description']):
                    st.markdown(f"**Описание:** {task['description']}")
            
            st.caption(f"Создано: {task['created_at'].strftime('%d.%m.%Y %H:%M') if pd.notnull(task['created_at']) else '—'}")
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
        
        tasks = df[df['status'] == status].sort_values('deadline')
        
        if len(tasks) == 0:
            st.caption("_Нет задач_")
        else:
            for _, task in tasks.iterrows():
                deadline_str = task['deadline'].strftime('%d.%m') if pd.notnull(task['deadline']) else '—'
                
                # Цвет дедлайна
                if pd.notnull(task['deadline']):
                    days_left = (task['deadline'] - today).days
                    if days_left < 0:
                        deadline_color = "deadline-urgent"
                    elif days_left <= 2:
                        deadline_color = "deadline-warning"
                    else:
                        deadline_color = "deadline-normal"
                else:
                    deadline_color = ""
                
                task_card = f"""
                <div style="border:1px solid #ddd; border-radius:8px; padding:12px; margin-bottom:10px; background:#f9f9f9; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <b>{task['task_name']}</b><br>
                    <small>📁 {task['project_name'] or 'Без проекта'}</small><br>
                    <small>🕗 <span class="{deadline_color}">{deadline_str}</span></small>
                </div>
                """
                st.markdown(task_card, unsafe_allow_html=True)

# Таблица всех задач
st.divider()
st.subheader("📝 Все задачи")

if not df.empty:
    df_display = df[['task_name', 'project_name', 'status', 'deadline', 'description']].copy()
    df_display.columns = ['Задача', 'Проект', 'Статус', 'Дедлайн', 'Описание']
    
    # Преобразуем статусы в читаемый формат
    status_display = {
        'pending': '⏳ В ожидании',
        'in_progress': '🔄 В работе',
        'completed': '✅ Завершено',
        'overdue': '⚠️ Просрочено'
    }
    df_display['Статус'] = df_display['Статус'].map(status_display)
    
    st.dataframe(
        df_display,
        column_config={
            "Дедлайн": st.column_config.DateColumn(format="DD.MM.YYYY"),
        },
        hide_index=True,
        use_container_width=True
    )
else:
    st.info("Нет задач, удовлетворяющих фильтрам")

# Footer
st.divider()
st.caption("Task Planner Pro Dashboard • Данные обновляются каждые 30 секунд")
