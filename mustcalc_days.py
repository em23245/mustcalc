import streamlit as st
import re
import datetime
from PyPDF2 import PdfReader

# 1. 网页基础设置
st.set_page_config(page_title="澳科大逗留天数计算器", page_icon="🎓", layout="centered")
st.title("🎓 澳科大内地生逗留天数计算器")
st.markdown("上传从国家移民管理局下载的《出入境记录查询结果》PDF，系统将自动扣除周末与学校假期，精准核算你的有效逗留天数！")
st.caption("注：本工具已内置 2025/2026 学年澳科大日历（含圣诞假及春节假）。数据仅在浏览器本地运行，不保存任何个人隐私。")

# 2. 澳科大日历配置 (直接沿用我们之前的逻辑)
TARGET_DAYS = 119 
SEMESTERS = [
    (datetime.date(2025, 9, 1), datetime.date(2026, 1, 10)),
    (datetime.date(2026, 1, 12), datetime.date(2026, 5, 28))  
]
HOLIDAYS = [
    (datetime.date(2025, 12, 15), datetime.date(2025, 12, 25)), 
    (datetime.date(2026, 2, 11), datetime.date(2026, 2, 24))    
]

def is_valid_school_day(date_obj):
    if date_obj.weekday() >= 5: return False
    for h_start, h_end in HOLIDAYS:
        if h_start <= date_obj <= h_end: return False
    in_semester = False
    for s_start, s_end in SEMESTERS:
        if s_start <= date_obj <= s_end:
            in_semester = True
            break
    return in_semester

# 3. 网页交互界面：文件上传框
uploaded_file = st.file_uploader("📂 请在此处拖拽或点击上传 PDF 文件", type="pdf")

if uploaded_file is not None:
    with st.spinner("正在高速解析 PDF 数据..."):
        try:
            # 解析 PDF
            reader = PdfReader(uploaded_file)
            text = "".join([page.extract_text() + "\n" for page in reader.pages])
            
            raw_dates = re.findall(r'20\d{2}-\d{2}-\d{2}', text)
            unique_dates = sorted(list(set(raw_dates)))

            valid_days_count = 0
            valid_dates_list = []

            for date_str in unique_dates:
                d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                if is_valid_school_day(d):
                    valid_days_count += 1
                    valid_dates_list.append(date_str)
            
            # 预测剩余天数
            today = datetime.date.today()
            final_end_date = SEMESTERS[-1][1]
            future_valid_days = sum(1 for i in range((final_end_date - today).days + 1) 
                                    if is_valid_school_day(today + datetime.timedelta(days=i)))
            
            total_projected = valid_days_count + future_valid_days
            shortfall = TARGET_DAYS - valid_days_count

            # 4. 渲染结果看板
            st.divider()
            st.subheader("📊 智能核算报告")
            
            # 制作三个漂亮的数据卡片
            col1, col2, col3 = st.columns(3)
            col1.metric("PDF 提取总天数", f"{len(unique_dates)} 天")
            col2.metric("✨ 有效达标天数", f"{valid_days_count} 天")
            col3.metric("🎯 距离目标还差", f"{shortfall if shortfall > 0 else 0} 天")

            # 状态提示
            if shortfall > 0:
                st.warning(f"⚠️ 距离 {TARGET_DAYS} 天的安全线还差 **{shortfall}** 天，请继续努力！")
            else:
                st.success(f"🎉 恭喜！你已经达标，超额完成了 {-shortfall} 天！")
            
            st.info(f"🔮 **考勤预测**：从今天起到学期结束（5月28日），理论上还剩 **{future_valid_days}** 个有效工作日。")
            
            if total_projected >= TARGET_DAYS:
                st.success(f"✅ **状态安全**：如果接下来全勤，你还有 **{total_projected - TARGET_DAYS}** 天的合法请假额度。")
            else:
                st.error(f"❌ **状态危险**：即使接下来天天都去，也还差 **{TARGET_DAYS - total_projected}** 天！")

            # 隐藏的详情列表（点击展开）
            with st.expander("📅 点击查看计入的有效日期明细"):
                for i, d in enumerate(valid_dates_list, 1):
                    st.write(f"`{i:03d}.` {d}")

        except Exception as e:
            st.error(f"解析文件时出错，请确保上传的是正确的 PDF 文件。错误代码: {e}")