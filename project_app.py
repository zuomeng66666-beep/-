import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os
import io

# --- 1. 页面配置 ---
st.set_page_config(page_title="多项目协同管理工具", layout="wide")
st.title("🚀 团队多项目进度与风险管理看板")

# 文件名更新，建议使用新文件名避免与旧数据冲突
TASKS_FILE = "all_tasks_v2.csv"
RISKS_FILE = "all_risks_v2.csv"

# --- 2. 数据处理函数 ---
def load_data():
    # 加载任务
    if os.path.exists(TASKS_FILE):
        df = pd.read_csv(TASKS_FILE)
        # 兼容旧数据：如果没有项目名称列，补上默认项目
        if '项目名称' not in df.columns: df['项目名称'] = "默认项目"
        if '进度' not in df.columns: df['进度'] = 0
    else:
        df = pd.DataFrame(columns=["项目名称", "任务", "负责人", "状态", "开始", "结束", "进度"])
    
    # 加载风险
    if os.path.exists(RISKS_FILE):
        rdf = pd.read_csv(RISKS_FILE)
        if '项目名称' not in rdf.columns: rdf['项目名称'] = "默认项目"
    else:
        rdf = pd.DataFrame(columns=["项目名称", "风险点", "影响程度", "状态", "具体影响", "应对措施"])
    return df, rdf

def save_data():
    st.session_state.tasks.to_csv(TASKS_FILE, index=False)
    st.session_state.risks.to_csv(RISKS_FILE, index=False)

# 初始化数据
if 'tasks' not in st.session_state:
    st.session_state.tasks, st.session_state.risks = load_data()

# --- 3. 侧边栏：多项目管理 ---
st.sidebar.header("📁 项目空间管理")

# 3.1 创建新项目
with st.sidebar.expander("✨ 新建项目"):
    new_p_name = st.text_input("输入新项目名称")
    if st.button("确认创建"):
        if new_p_name:
            # 这里不需要立刻写入CSV，只需在添加第一个任务时关联即可
            st.success(f"项目 '{new_p_name}' 已创建，请在下方添加任务。")
        else:
            st.error("名称不能为空")

# 3.2 项目切换器
# 获取所有已存在的项目名称
existing_projs = st.session_state.tasks["项目名称"].unique().tolist()
if not existing_projs: existing_projs = ["默认项目"]
# 如果用户刚输入了新项目名但还没任务，也把它加进下拉列表里
if 'new_p_name' in locals() and new_p_name and new_p_name not in existing_projs:
    existing_projs.append(new_p_name)

current_p = st.sidebar.selectbox("当前选中的项目", existing_projs)

st.sidebar.divider()

# 3.3 侧边栏：在当前项目下添加任务
st.sidebar.header(f"➕ 新增任务 [{current_p}]")
with st.sidebar.form("new_task_form"):
    t_name = st.text_input("任务名称")
    t_owner = st.text_input("负责人")
    t_status = st.selectbox("状态", ["待办", "进行中", "已完成"])
    t_prog = st.slider("初始进度 (%)", 0, 100, 100 if t_status == "已完成" else 0)
    t_start = st.date_input("开始日期", datetime.now())
    t_end = st.date_input("结束日期", datetime.now() + timedelta(days=7))
    
    if st.form_submit_button("保存至该项目") and t_name:
        new_data = pd.DataFrame([{
            "项目名称": current_p, "任务": t_name, "负责人": t_owner, 
            "状态": t_status, "开始": str(t_start), "结束": str(t_end), "进度": t_prog
        }])
        st.session_state.tasks = pd.concat([st.session_state.tasks, new_data], ignore_index=True)
        save_data()
        st.rerun()

# 3.4 导出功能
st.sidebar.divider()
st.sidebar.subheader("💾 数据备份 (多项目)")
if st.sidebar.button("📊 生成Excel"):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        # 按项目分组导出
        all_projects = st.session_state.tasks["项目名称"].unique()
        for p_name in all_projects:
            p_df = st.session_state.tasks[st.session_state.tasks["项目名称"] == p_name]
            # Excel Sheet名称限31字符，去除特殊字符
            safe_name = str(p_name).replace("[","").replace("]","")[:30]
            p_df.to_excel(writer, index=False, sheet_name=safe_name)
        
        # 风险单独一页
        st.session_state.risks.to_excel(writer, index=False, sheet_name="风险追踪总表")
    
    st.sidebar.download_button(
        label="📥 点击下载 Excel",
        data=buffer.getvalue(),
        file_name=f"多项目进度汇总_{datetime.now().strftime('%m%d')}.xlsx",
        mime="application/vnd.ms-excel"
    )

# --- 4. 数据过滤逻辑 ---
tasks_all = st.session_state.tasks
tasks = tasks_all[tasks_all["项目名称"] == current_p]
risks_all = st.session_state.risks
risks = risks_all[risks_all["项目名称"] == current_p]

# --- 5. 关键绩效指标 (KPI) ---
st.subheader(f"📊 项目概览: {current_p}")
total = len(tasks)
done = len(tasks[tasks["状态"]=="已完成"])
doing = len(tasks[tasks["状态"]=="进行中"])
overdue = 0
if total > 0:
    overdue = len(tasks[(pd.to_datetime(tasks['结束']) < datetime.now()) & (tasks['状态'] != "已完成")])

m1, m2, m3, m4 = st.columns(4)
m1.metric("当前项目任务数", total)
m2.metric("已完成", f"{done}", f"{done/total:.0%}" if total > 0 else "0%")
m3.metric("进行中", doing)
m4.metric("延期警告", overdue, delta_color="inverse" if overdue > 0 else "normal")

# --- 6. 主界面标签页 ---
tab1, tab2, tab3 = st.tabs(["📋 敏捷看板", "📊 时间轴(甘特图)", "🛡️ 风险日志"])

with tab1:
    col_a, col_b, col_c = st.columns(3)
    status_cols = {"待办": col_a, "进行中": col_b, "已完成": col_c}
    
    for status, col in status_cols.items():
        with col:
            st.markdown(f"### {status}")
            # 注意：在看板中要使用 tasks 过滤后的内容
            filtered = tasks[tasks["状态"] == status]
            for idx, row in filtered.iterrows():
                with st.expander(f"📌 {row['任务']} ({row['进度']}%)"):
                    st.caption(f"负责人: {row['负责人']} | 截止: {row['结束']}")
                    
                    new_status = st.selectbox("变更状态", ["待办", "进行中", "已完成"], 
                                             index=["待办", "进行中", "已完成"].index(status),
                                             key=f"st_{idx}")
                    
                    new_p = row['进度']
                    if new_status == "进行中":
                        new_p = st.slider("进度更新", 0, 100, int(row['进度']), key=f"pg_{idx}")
                    elif new_status == "已完成":
                        new_p = 100
                    
                    if new_status != status or new_p != row['进度']:
                        st.session_state.tasks.at[idx, '状态'] = new_status
                        st.session_state.tasks.at[idx, '进度'] = new_p
                        save_data()
                        st.rerun()
                    
                    if st.button("🗑️ 删除任务", key=f"del_{idx}"):
                        st.session_state.tasks = st.session_state.tasks.drop(idx)
                        save_data()
                        st.rerun()

with tab2:
    st.subheader(f"⏳ {current_p} 进度分析")
    if not tasks.empty:
        df_gantt = tasks.copy()
        df_gantt['结束'] = pd.to_datetime(df_gantt['结束']).dt.date
        today = datetime.now().date()
        
        st.markdown("### ⚠️ 临近里程碑")
        uncompleted = df_gantt[df_gantt['状态'] != "已完成"]
        overdue_tasks = uncompleted[uncompleted['结束'] < today]
        upcoming_tasks = uncompleted[(uncompleted['结束'] >= today) & 
                                    (uncompleted['结束'] <= today + timedelta(days=3))]
        
        if overdue_tasks.empty and upcoming_tasks.empty:
            st.success("✅ 该项目目前没有紧急或延期的任务。")
        else:
            for _, row in overdue_tasks.iterrows():
                st.error(f"🚨 **已延期**: '{row['任务']}' (原定: {row['结束']}) - 负责人: {row['负责人']}")
            for _, row in upcoming_tasks.iterrows():
                days_left = (row['结束'] - today).days
                st.warning(f"⏰ **即将到期**: '{row['任务']}' ({'今天' if days_left==0 else str(days_left)+'天后'}) - 负责人: {row['负责人']}")

        st.divider()
        st.subheader("📊 项目时间线")
        df_gantt['开始'] = pd.to_datetime(tasks['开始'])
        df_gantt['结束'] = pd.to_datetime(tasks['结束'])
        fig = px.timeline(df_gantt, x_start="开始", x_end="结束", y="任务", color="状态", text="进度",
                         color_discrete_map={"待办": "#E5ECF6", "进行中": "#FFA15A", "已完成": "#636EFA"})
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("该项目下暂无任务，请在左侧边栏添加。")

with tab3:
    st.subheader(f"🛡️ {current_p} 风险管理")
    r_col1, r_col2 = st.columns([1, 2])
    with r_col1:
        with st.form("risk_f"):
            r_n = st.text_input("风险描述")
            r_l = st.select_slider("影响程度", ["低", "中", "高"])
            r_imp = st.text_area("具体影响描述")
            r_act = st.text_area("应对措施建议")
            if st.form_submit_button("记录风险") and r_n:
                new_r = pd.DataFrame([{
                    "项目名称": current_p, "风险点": r_n, "影响程度": r_l, 
                    "状态": "监控中", "具体影响": r_imp, "应对措施": r_act
                }])
                st.session_state.risks = pd.concat([st.session_state.risks, new_r], ignore_index=True)
                save_data()
                st.success("风险已记录！")
                st.rerun()
    with r_col2:
        st.dataframe(risks.drop(columns=["项目名称"]), use_container_width=True)

st.divider()
st.info(f"💡 提示：当前视图已根据项目 **'{current_p}'** 过滤。导出 Excel 时将包含所有项目的 Sheet。")
#执行运行命令：streamlit run project_app.py
#改进方向：
#1. 增加任务优先级字段，并在看板中支持按优先级排序显示。
#2. 
#3. 增加任务标签功能，支持多维度筛选和查看任务。
#4. 多人协同，接入 Google Sheets 或数据库。
