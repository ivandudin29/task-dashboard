import streamlit as st
import psycopg2
import pandas as pd
from datetime import datetime, timedelta
import os

# Настройки страницы
st.set_page_config(
    page_title="Планировщик задач",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="collapsed"
)

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
@st.cache_data(ttl=60)
def load_data():
    query = """
        SELECT 
            t.id,
            t.title AS task_name,
            t.status,
            t.deadline,
            p.name AS project_name,
            t.description
        FROM tasks t
        LEFT JOIN projects p ON t.project_id = p.id
        ORDER BY t.deadline ASC NULLS LAST
    """
    return pd.read_sql_query(query, conn)

df = load_data()

# Заголовок
st.title("📊 Дашборд задач")
st.caption(f"Обновлено: {datetime.now().strftime('%H:%M:%S')}")

# Фильтры в сайдбаре
st.sidebar.header("Фильтры")
statuses = ['Все'] + df['status'].dropna().unique().tolist()
selected_status = st.sidebar.selectbox("Статус", statuses)
if selected_status != 'Все':
    df = df[df['status'] == selected_status]

# Канбан-доска
st.subheader("Канбан")
cols = st.columns(4)
status_order = ['новая', 'в работе', 'тестирование', 'завершена']

for idx, status in enumerate(status_order):
    with cols[idx]:
        st.markdown(f"### {status.title()}")
        tasks = df[df['status'] == status]
        for _, task in tasks.iterrows():
            deadline_str = task['deadline'].strftime('%d.%m') if pd.notnull(task['deadline']) else '—'
            st.markdown(f"""
                <div style="border:1px solid #ddd; border-radius:6px; padding:12px; margin-bottom:10px; background:#f9f9f9">
                    <b>{task['task_name']}</b><br>
                    <small>Проект: {task['project_name'] or '—'}</small><br>
                    <small>🕗 {deadline_str}</small>
                </div>
            """, unsafe_allow_html=True)

# Таблица задач с дедлайнами
st.subheader("Список задач")
df_display = df[['task_name', 'project_name', 'status', 'deadline', 'description']].copy()
df_display.columns = ['Задача', 'Проект', 'Статус', 'Дедлайн', 'Описание']
st.dataframe(
    df_display,
    column_config={
        "Дедлайн": st.column_config.DateColumn(format="DD.MM.YYYY"),
        "Статус": st.column_config.SelectboxColumn(options=status_order),
    },
    hide_index=True,
    use_container_width=True
)

# Ближайшие дедлайны
st.subheader("🔥 Ближайшие дедлайны (3 дня)")
tomorrow = datetime.now() + timedelta(days=3)
urgent = df[pd.notnull(df['deadline']) & (df['deadline'] <= tomorrow)].sort_values('deadline')
if not urgent.empty:
    for _, task in urgent.iterrows():
        st.warning(f"⏰ {task['deadline'].strftime('%d.%m %H:%M')} — {task['task_name']} ({task['project_name']})")
else:
    st.info("Нет задач с дедлайнами в ближайшие 3 дня")
