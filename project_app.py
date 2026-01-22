import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os
import io

# --- 1. 页面配置 ---
st.set_page_config(page_title="项目管理看板", layout="wide")
st.title("🚀 团队项目进度与风险管理工具")

TASKS_FILE = "tasks_v1.csv"
RISKS_FILE = "risks_v1.csv"

# --- 2. 数据处理函数 ---
def load_data():
    # 加载任务
    if os.path.exists(TASKS_FILE):
        df = pd.read_csv(TASKS_FILE)
        if '进度' not in df.columns: df['进度'] = 0
    else:
        df = pd.DataFrame(columns=["任务", "负责人", "状态", "开始", "结束", "进度"])
    
    # 加载风险
    if os.path.exists(RISKS_FILE):
        rdf = pd.read_csv(RISKS_FILE)
    else:
        rdf = pd.DataFrame(columns=["风险点", "影响程度", "状态", "应对措施"])
    return df, rdf

def save_data():
    st.session_state.tasks.to_csv(TASKS_FILE, index=False)
    st.session_state.risks.to_csv(RISKS_FILE, index=False)

# 初始化
if 'tasks' not in st.session_state:
    st.session_state.tasks, st.session_state.risks = load_data()

# --- 3. 侧边栏：添加任务 & 导出 ---
st.sidebar.header("➕ 新建任务")
with st.sidebar.form("new_task_form"):
    t_name = st.text_input("任务名称")
    t_owner = st.text_input("负责人")
    t_status = st.selectbox("状态", ["待办", "进行中", "已完成"])
    t_prog = st.slider("初始进度 (%)", 0, 100, 100 if t_status == "已完成" else 0)
    t_start = st.date_input("开始日期", datetime.now())
    t_end = st.date_input("结束日期", datetime.now() + timedelta(days=7))
    
    if st.form_submit_button("确认添加") and t_name:
        new_data = pd.DataFrame([{"任务": t_name, "负责人": t_owner, "状态": t_status, 
                                 "开始": str(t_start), "结束": str(t_end), "进度": t_prog}])
        st.session_state.tasks = pd.concat([st.session_state.tasks, new_data], ignore_index=True)
        save_data()
        st.rerun()

# 导出功能
st.sidebar.divider()
st.sidebar.subheader("💾 数据备份")
buffer = io.BytesIO()
with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
    st.session_state.tasks.to_excel(writer, index=False, sheet_name='任务清单')
st.sidebar.download_button(label="📥 导出 Excel", data=buffer.getvalue(), 
                           file_name="项目进度表.xlsx", mime="application/vnd.ms-excel")
st.sidebar.success("准备就绪！")

# --- 4. 关键绩效指标 (KPI) ---
tasks = st.session_state.tasks
total = len(tasks)
done = len(tasks[tasks["状态"]=="已完成"])
doing = len(tasks[tasks["状态"]=="进行中"])
overdue = 0
if total > 0:
    # 延期检查
    overdue = len(tasks[(pd.to_datetime(tasks['结束']) < datetime.now()) & (tasks['状态'] != "已完成")])

m1, m2, m3, m4 = st.columns(4)
m1.metric("总任务数", total)
m2.metric("已完成", f"{done}", f"{done/total:.0%}" if total > 0 else "0%")
m3.metric("进行中", doing)
m4.metric("延期警告", overdue, delta_color="inverse" if overdue > 0 else "normal")

# --- 5. 主界面标签页 ---
tab1, tab2, tab3 = st.tabs(["📋 敏捷看板", "📊 时间轴(甘特图)", "🛡️ 风险日志"])

with tab1:
    col_a, col_b, col_c = st.columns(3)
    status_cols = {"待办": col_a, "进行中": col_b, "已完成": col_c}
    
    for status, col in status_cols.items():
        with col:
            st.markdown(f"### {status}")
            filtered = tasks[tasks["状态"] == status]
            for idx, row in filtered.iterrows():
                with st.expander(f"📌 {row['任务']} ({row['进度']}%)"):
                    st.caption(f"负责人: {row['负责人']} | 截止: {row['结束']}")
                    
                    # 动态修改状态
                    new_status = st.selectbox("变更状态", ["待办", "进行中", "已完成"], 
                                             index=["待办", "进行中", "已完成"].index(status),
                                             key=f"st_{idx}")
                    
                    # 只有进行中显示滑动条
                    new_p = row['进度']
                    if new_status == "进行中":
                        new_p = st.slider("进度更新", 0, 100, int(row['进度']), key=f"pg_{idx}")
                    elif new_status == "已完成":
                        new_p = 100
                    
                    # 保存变更
                    if new_status != status or new_p != row['进度']:
                        st.session_state.tasks.at[idx, '状态'] = new_status
                        st.session_state.tasks.at[idx, '进度'] = new_p
                        save_data()
                        st.rerun()
                    
                    # 删除按钮
                    if st.button("🗑️ 删除任务", key=f"del_{idx}"):
                        st.session_state.tasks = st.session_state.tasks.drop(idx)
                        save_data()
                        st.rerun()

with tab2:
    st.subheader("⏳ 项目进度分析")
    
    if not st.session_state.tasks.empty:
        # --- 数据预处理 ---
        df_gantt = st.session_state.tasks.copy()
        df_gantt['结束'] = pd.to_datetime(df_gantt['结束']).dt.date # 转为纯日期
        today = datetime.now().date()
        

        st.markdown("### ⚠️ 临近里程碑")
        uncompleted = df_gantt[df_gantt['状态'] != "已完成"]
        overdue_tasks = uncompleted[uncompleted['结束'] < today]
        upcoming_tasks = uncompleted[(uncompleted['结束'] >= today) & 
                                    (uncompleted['结束'] <= today + timedelta(days=3))]
        
        # --- 渲染报警信息 ---
        if overdue_tasks.empty and upcoming_tasks.empty:
            st.success("✅ 目前没有紧急或延期的任务。")
        else:
            # 显示已延期 
            for _, row in overdue_tasks.iterrows():
                st.error(f"🚨 **已延期**: '{row['任务']}' (原定: {row['结束']}) - 负责人: {row['负责人']}")
            
            # 显示即将到期 
            for _, row in upcoming_tasks.iterrows():
                days_left = (row['结束'] - today).days
                if days_left == 0:
                    st.warning(f"⏰ **今天截止**: '{row['任务']}' - 负责人: {row['负责人']}")
                else:
                    st.warning(f"⏰ **即将截止**: '{row['任务']}' 还有 {days_left} 天 - 负责人: {row['负责人']}")

        st.divider()

        # --- 甘特图展示 ---
        st.subheader("📊 项目时间线")
        fig = px.timeline(df_gantt, x_start="开始", x_end="结束", y="任务", color="状态", text="进度",
                         color_discrete_map={"待办": "#E5ECF6", "进行中": "#FFA15A", "已完成": "#636EFA"})
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
        
    else:
        st.info("暂无数据，请在左侧添加任务。")


with tab3:
    st.subheader("风险追踪")
    r_col1, r_col2 = st.columns([1, 2])
    with r_col1:
        with st.form("risk_f"):
            r_n = st.text_input("风险描述")
            r_l = st.select_slider("影响程度", ["低", "中", "高"])
            r_action = st.text_area("风险具体影响")
            r_action = st.text_area("应对措施")
            if st.form_submit_button("提交") and r_n:
                new_r = pd.DataFrame([{"风险点": r_n, "影响程度": r_l, "状态": "监控中", "具体影响": r_action, "应对措施": r_action}])
                st.session_state.risks = pd.concat([st.session_state.risks, new_r], ignore_index=True)
                st.success("风险已记录！")
                save_data()
                st.rerun()
    with r_col2:
        st.dataframe(st.session_state.risks, use_container_width=True)

st.info("提示：此为初始版本网站，欢迎反馈建议以改进功能！")
#执行运行命令：streamlit run project_app.py