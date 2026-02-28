import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta
import os
import io

# --- 1. 页面配置 ---
st.set_page_config(page_title="多项目协同管理工具", layout="wide")
st.title("⌛团队多项目进度与风险管理看板")
TASKS_FILE = "all_tasks_v2.csv"
RISKS_FILE = "all_risks_v2.csv"
LOGS_FILE = "operation_logs_v2.csv"

# --- 2. 数据处理函数 ---
def load_data():
    if os.path.exists(TASKS_FILE):
        df = pd.read_csv(TASKS_FILE)
        if '项目名称' not in df.columns: df['项目名称'] = "默认项目"
        if '进度' not in df.columns: df['进度'] = 0
    else:
        df = pd.DataFrame(columns=["项目名称", "任务", "负责人", "状态", "开始", "结束", "进度"])
    
    if os.path.exists(RISKS_FILE):
        rdf = pd.read_csv(RISKS_FILE)
        if '项目名称' not in rdf.columns: rdf['项目名称'] = "默认项目"
    else:
        rdf = pd.DataFrame(columns=["项目名称", "风险点", "影响程度", "状态", "具体影响", "应对措施"])
        
    if os.path.exists(LOGS_FILE):
        ldf = pd.read_csv(LOGS_FILE)
    else:
        ldf = pd.DataFrame(columns=["时间", "项目名称", "任务", "操作内容"])
    
    # 初始化 session_state
    if 'logs' not in st.session_state:
        st.session_state.logs = ldf
    return df, rdf, ldf

def save_data():
    st.session_state.tasks.to_csv(TASKS_FILE, index=False)
    st.session_state.risks.to_csv(RISKS_FILE, index=False)
    st.session_state.logs.to_csv(LOGS_FILE, index=False)

def add_log(project, task, action):
    new_log = pd.DataFrame([{
        "时间": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "项目名称": project,
        "任务": task,
        "操作内容": action
    }])
    st.session_state.logs = pd.concat([st.session_state.logs, new_log], ignore_index=True)
    
if 'tasks' not in st.session_state:
    st.session_state.tasks, st.session_state.risks, st.session_state.logs = load_data()


# --- 3. 侧边栏：多项目管理 ---
st.sidebar.header("📁 项目空间管理")

# 创建新项目
with st.sidebar.expander("✨ 新建项目"):
    new_p_name = st.text_input("输入新项目名称")
    if st.button("确认创建"):
        if new_p_name:
            # 这里不需要立刻写入CSV，只需在添加第一个任务时关联即可
            st.success(f"项目 '{new_p_name}' 已创建，请在下方添加任务。")
        else:
            st.error("名称不能为空")

# 项目切换器
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
        add_log(current_p, t_name, "新建了该任务")
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
tab1, tab2, tab3, tab4 = st.tabs(["📋 敏捷看板", "📊 时间轴(甘特图)", "🛡️ 风险日志", "📜 操作日志"])

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
                    
                    # 1. 获取当前状态
                    new_status = st.selectbox("变更状态", ["待办", "进行中", "已完成"], 
                                             index=["待办", "进行中", "已完成"].index(status),
                                             key=f"st_{idx}")
                    
                    # 2. 进度逻辑处理
                    current_p = int(row['进度'])
                    new_p = current_p
                    
                    if new_status == "进行中":
                        # 如果是从“待办”切过来的，且进度还是0，提示用户滑动
                        new_p = st.slider("进度更新", 0, 100, current_p, key=f"pg_{idx}")
                        
                        # ✨ 核心改进：如果进度滑到了 100%，自动切换状态为“已完成”
                        if new_p == 100:
                            new_status = "已完成"
                            
                    elif new_status == "已完成":
                        # 如果手动切到“已完成”，进度强制 100
                        new_p = 100
                        
                    elif new_status == "待办":
                        # 如果手动切到“待办”，进度强制 0
                        new_p = 0
                    if status == "已完成" and new_p < 100:
                        new_status = "进行中"

                    # 4. 保存变更
                    if new_status != status or new_p != current_p:
                        st.session_state.tasks.at[idx, '状态'] = new_status
                        st.session_state.tasks.at[idx, '进度'] = new_p
                        save_data()
                        st.rerun()
        
                    if new_status != status or new_p != current_p:
                        log_msg = f"状态: {status}->{new_status} | 进度: {current_p}%->{new_p}%"
                        add_log(row['项目名称'], row['任务'], log_msg) # 记录日志
            
                        st.session_state.tasks.at[idx, '状态'] = new_status
                        st.session_state.tasks.at[idx, '进度'] = new_p
                        save_data()
                        st.rerun()

                    st.divider()
                    if st.button(f"🗑️ 删除任务", key=f"del_{idx}"):
                        add_log(row['项目名称'], row['任务'], "彻底删除了该任务") # 记录日志
                        st.session_state.tasks = st.session_state.tasks.drop(idx).reset_index(drop=True)
                        save_data()
                        st.warning(f"任务 '{row['任务']}' 已删除")
                        st.rerun()

with tab2:
    if not tasks.empty:
        # --- 1. 数据预处理 ---
        df_analysis = tasks.copy()
        df_analysis['开始'] = pd.to_datetime(df_analysis['开始']).dt.date
        df_analysis['结束'] = pd.to_datetime(df_analysis['结束']).dt.date
        today = datetime.now().date()
        
        # --- 2. 顶部仪表盘 (KPI) ---
        avg_progress = df_analysis['进度'].mean()
        total_tasks = len(df_analysis)
        completed_tasks = len(df_analysis[df_analysis['状态'] == '已完成'])
        
        # 计算项目剩余天数 (取所有任务中最晚的截止日期)
        project_end_date = df_analysis['结束'].max()
        days_remaining = (project_end_date - today).days
        
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("项目整体进度", f"{avg_progress:.1f}%")
        c2.metric("任务完成率", f"{(completed_tasks/total_tasks):.0%}")
        c3.metric("总负责人总数", len(df_analysis['负责人'].unique()))
        c4.metric("距离项目终点", f"{days_remaining} 天" if days_remaining >= 0 else "已逾期")

        st.divider()

        # --- 3. 可视化分析图表 ---
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("##### 📦 项目任务状态分布")
            # 统计状态数量
            status_counts = df_analysis['状态'].value_counts().reset_index()
            #  Pandas reset_index 后列名为 ['状态', 'count']
            fig_pie = px.pie(status_counts, 
                             names='状态',   # 原来的 'index' 改为 '状态'
                             values='count', # 原来的 '状态' 改为 'count'
                             color='状态',
                             color_discrete_map={"待办": "#E5ECF6", "进行中": "#FFA15A", "已完成": "#636EFA"},
                             hole=0.4)
            fig_pie.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_chart2:
            st.markdown("##### 👤 成员工作负荷 (任务数)")
            member_counts = df_analysis['负责人'].value_counts().reset_index()
            #  Pandas reset_index 后列名为 ['负责人', 'count']
            fig_bar = px.bar(member_counts, 
                             x='负责人',  # 原来的 'index' 改为 '负责人'
                             y='count',    # 原来的 '负责人' 改为 'count'
                             labels={'负责人': '成员', 'count': '任务量'},
                             color='count', 
                             color_continuous_scale='Blues')
            fig_bar.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=300)
            st.plotly_chart(fig_bar, use_container_width=True)

        st.divider()

        # --- 4. 里程碑预警 ---
        st.markdown("##### ⚠️ 临近里程碑 & 风险预警")
        uncompleted = df_analysis[df_analysis['状态'] != "已完成"]
        overdue_tasks = uncompleted[uncompleted['结束'] < today]
        upcoming_tasks = uncompleted[(uncompleted['结束'] >= today) & 
                                    (uncompleted['结束'] <= today + timedelta(days=3))]
        
        if overdue_tasks.empty and upcoming_tasks.empty:
            st.success("✅ 该项目目前所有任务均在计划内，暂无紧急风险。")
        else:
            alert_col1, alert_col2 = st.columns(2)
            with alert_col1:
                for _, row in overdue_tasks.iterrows():
                    st.error(f"🚨 **已延期**: {row['任务']} (负责人: {row['负责人']})")
            with alert_col2:
                for _, row in upcoming_tasks.iterrows():
                    days_left = (row['结束'] - today).days
                    st.warning(f"⏰ **即将到期**: {row['任务']} (还有 {days_left} 天)")

        st.divider()

        # --- 5. 项目时间线 (甘特图) ---
        st.markdown("##### 📊 项目详细时间轴 (甘特图)")
        # 转换回 datetime 格式以适配 plotly timeline
        df_analysis['开始'] = pd.to_datetime(df_analysis['开始'])
        df_analysis['结束'] = pd.to_datetime(df_analysis['结束'])
        
        fig_gantt = px.timeline(df_analysis, x_start="开始", x_end="结束", y="任务", 
                               color="状态", text="进度",
                               color_discrete_map={"待办": "#E5ECF6", "进行中": "#FFA15A", "已完成": "#636EFA"})
        fig_gantt.update_yaxes(autorange="reversed")
        fig_gantt.update_layout(height=400, margin=dict(t=0, b=0, l=0, r=0))
        st.plotly_chart(fig_gantt, use_container_width=True)
        
    else:
        # --- 6. 空白状态引导 ---
        st.info("💡 这是一个全新的项目，还没有任务数据。")
        st.markdown("""
        **如何开始？**
        1. 在左侧边栏填写 **任务名称**。
        2. 分配 **负责人** 并设置 **起止日期**。
        3. 点击 **保存至该项目**。
        完成后，这里将自动生成进度报表。
        """)


with tab3:
    st.subheader(f"🛡️风险管理")
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
with tab4:
    st.subheader("项目操作历史流")
    # 只显示当前项目的日志，并按时间倒序排列
    current_logs = st.session_state.logs[st.session_state.logs["项目名称"] == current_p]
    st.dataframe(current_logs.sort_values(by="时间", ascending=False), use_container_width=True)
    
    if st.button("清理过期日志 (保留最近50条)"):
        st.session_state.logs = st.session_state.logs.tail(50)
        save_data()
        st.rerun()
        
st.divider()
st.info(f"💡 提示：当前视图已根据当前项目过滤。导出 Excel 时将包含所有项目的 Sheet。")
#执行运行命令：streamlit run project_app.py
#改进方向：
#1. 增加任务优先级字段，并在看板中支持按优先级排序显示。
#2. 增加任务标签功能，支持多维度筛选和查看任务。
#3.多人协同，接入 Google Sheets 或数据库。
