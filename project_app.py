import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os

# --- 页面设置 ---
st.set_page_config(page_title="项目管理看板", layout="wide")
st.title("🚀 团队项目进度与风险管理看板")

# 文件路径
TASKS_FILE = "tasks_data_final.csv"
RISKS_FILE = "risks_data_final.csv"

# --- 数据加载逻辑  ---
def load_data():
    # 处理任务数据
    if os.path.exists(TASKS_FILE):
        df = pd.read_csv(TASKS_FILE)
        # 如果文件里缺了“进度”这一列，强制补齐
        if '进度' not in df.columns:
            df['进度'] = 0
        # 如果文件里缺了“任务”列，重新初始化
        if '任务' not in df.columns:
            df = pd.DataFrame(columns=["任务", "负责人", "状态", "开始", "结束", "进度"])
    else:
        # 默认初始数据
        df = pd.DataFrame([
            {"任务": "文献调研", "负责人": "1号", "状态": "已完成", "开始": "2026-1-21", "结束": "2026-2-23" ,"进度": 50},
            {"任务": "代码框架搭建", "负责人": "2号", "状态": "进行中", "开始": "2026-1-21", "结束": "2026-1-30","进度": 20},
            {"任务": "论文撰写", "负责人": "3号", "状态": "待办", "开始": "2026-1-21", "结束": "2026-2-10","进度": 10},
        ])
    
    # 处理风险数据
    if os.path.exists(RISKS_FILE):
        rdf = pd.read_csv(RISKS_FILE)
    else:
        rdf = pd.DataFrame(columns=["风险点", "影响程度", "状态", "应对措施"])
    
    return df, rdf

# 初始化 session_state
if 'tasks' not in st.session_state or 'risks' not in st.session_state:
    tasks_df, risks_df = load_data()
    st.session_state.tasks = tasks_df
    st.session_state.risks = risks_df

def save_data():
    st.session_state.tasks.to_csv(TASKS_FILE, index=False)
    st.session_state.risks.to_csv(RISKS_FILE, index=False)

# --- 侧边栏：添加新任务 ---
st.sidebar.header("➕ 添加新任务")
with st.sidebar.form("task_form"):
    new_task = st.text_input("任务名称")
    owner = st.text_input("负责人")
    status = st.selectbox("初始状态", ["待办", "进行中", "已完成"])

    init_progress = st.slider("初始进度 (%)", 0, 100, 0) 
    
    start_date = st.date_input("开始日期", datetime.now())
    end_date = st.date_input("结束日期", datetime.now() + timedelta(days=7))
    submit_task = st.form_submit_button("添加任务")
    
    if submit_task and new_task:
        final_p = 100 if status == "已完成" else init_progress
        new_row = {
            "任务": new_task, 
            "负责人": owner, 
            "状态": status, 
            "开始": str(start_date), 
            "结束": str(end_date), 
            "进度": final_p  # 确保这里有进度
        }
        st.session_state.tasks = pd.concat([st.session_state.tasks, pd.DataFrame([new_row])], ignore_index=True)
        save_data()
        st.rerun()


# --- 核心看板逻辑 ---
st.header("📋 敏捷开发看板")
cols = st.columns(3)
status_list = ["待办", "进行中", "已完成"]

for i, status_type in enumerate(status_list):
    with cols[i]:
        st.subheader(f"【{status_type}】")
        # 筛选对应状态的任务
        filtered_tasks = st.session_state.tasks[st.session_state.tasks["状态"] == status_type]
        
        for idx, row in filtered_tasks.iterrows():
            # 使用索引 idx 保证 key 的唯一性
            with st.expander(f"📌 {row['任务']} ({row['进度']}%)"):
                st.write(f"负责人: {row['负责人']}")
                
                # 状态修改
                new_s = st.selectbox("修改状态", status_list, 
                                     index=status_list.index(status_type), 
                                     key=f"status_{idx}")
                
                # 进度修改
                current_p = int(row['进度'])
                new_p = current_p
                if new_s == "进行中":
                    new_p = st.slider("完成进度 (%)", 0, 100, current_p, key=f"prog_{idx}")
                elif new_s == "已完成":
                    new_p = 100
                elif new_s == "待办":
                    new_p = 0
                
                # 检测到变动则保存
                if new_s != status_type or new_p != current_p:
                    st.session_state.tasks.at[idx, '状态'] = new_s
                    st.session_state.tasks.at[idx, '进度'] = new_p
                    save_data()
                    st.rerun()

st.divider()

# --- 甘特图可视化 ---
st.header("⏳ 项目时间线 (甘特图)")
if not st.session_state.tasks.empty:
    df_gantt = st.session_state.tasks.copy()
    df_gantt['开始'] = pd.to_datetime(df_gantt['开始'])
    df_gantt['结束'] = pd.to_datetime(df_gantt['结束'])
    
    fig = px.timeline(
        df_gantt, 
        x_start="开始", 
        x_end="结束", 
        y="任务", 
        color="状态",
        text="进度", 
        hover_data=["负责人", "进度"],
        color_discrete_map={"待办": "#E5ECF6", "进行中": "#FFA15A", "已完成": "#636EFA"}
    )
    fig.update_traces(texttemplate='%{text}%', textposition='inside')
    fig.update_yaxes(autorange="reversed") 
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("暂无任务数据，请在左侧添加。")

# 里程碑预警
today = datetime.now()
st.subheader("⚠️ 临近里程碑")
upcoming = df_gantt[(df_gantt['结束'] >= today) & (df_gantt['状态'] != "已完成")]
if not upcoming.empty:
    for _, row in upcoming.iterrows():
        days_left = (row['结束'] - today).days
        if days_left <= 3:
            st.warning(f"⏰ 任务 '{row['任务']}' 将在 {days_left} 天后截止！负责人: {row['负责人']}")
else:
    st.success("目前没有紧急的截止日期。")

st.divider()

# --- 风险管理 ---
st.header("🛡️ 风险管理日志")
c1, c2 = st.columns([1, 2])
with c1:
    with st.form("risk_form"):
        r_name = st.text_input("风险描述")
        r_impact = st.select_slider("影响程度", options=["低", "中", "高"])
        r_action = st.text_area("应对措施")
        if st.form_submit_button("记录风险") and r_name:
            new_r = pd.DataFrame([{"风险点": r_name, "影响程度": r_impact, "状态": "监控中", "应对措施": r_action}])
            st.session_state.risks = pd.concat([st.session_state.risks, new_r], ignore_index=True)
            st.success("风险已记录！")
            save_data()
            st.rerun()
with c2:
    st.dataframe(st.session_state.risks, use_container_width=True)

st.info("提示：此为初始版本网站，欢迎反馈建议以改进功能！")
#执行运行命令：streamlit run project_app.py
