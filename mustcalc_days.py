import streamlit as st
import re
import datetime
from PyPDF2 import PdfReader

# ==========================================
# 1. 網頁基礎與 UI 設置
# ==========================================
st.set_page_config(page_title="澳科大逗留天數計算器 (26/27學年)", page_icon="🎓", layout="centered")
st.title("🎓 澳科大內地生逗留天數計算器 (2026/2027學年 二年級版)")
st.markdown("""
上傳從國家移民管理局下載的《出入境記錄查詢結果》PDF，系統將為你：
* 🔄 自動識別出入境狀態（**出境=進入澳門，入境=返回內地**）
* 🧠 智能補全長期留澳的空白日期
* 📅 精準匹配 **2026/2027 學年研究生校曆**，自動剔除週末、複習期、學校長假與澳門公眾假期（含補假），並提供**無效天數原因明細**
""")
st.caption("註：本工具適用於 2026/2027 學年研究生（二年級 90 天標準）。數據僅在瀏覽器本地運行，不保存任何個人隱私。")

# ==========================================
# 2. 澳科大 2026/2027 學年日曆與規則配置
# ==========================================
TARGET_DAYS = 90  # 二年級（第三、四學期）要求天數

# 有效學期時段（僅包含校曆「上課日期」與「考試日期」）
VALID_PERIODS = [
    (datetime.date(2026, 9, 1), datetime.date(2026, 12, 14)),   # 第一學期：上課日期
    (datetime.date(2026, 12, 28), datetime.date(2027, 1, 11)),  # 第一學期：考試日期
    (datetime.date(2027, 1, 13), datetime.date(2027, 5, 11)),   # 第二學期：上課日期
    (datetime.date(2027, 5, 18), datetime.date(2027, 5, 31)),   # 第二學期：考試日期
]

# 2026 - 2027 學年公眾假期、政府補假與大學休課日（附帶具體原因說明）
HOLIDAYS_WITH_REASON = [
    # --- 2026年 下半年 ---
    (datetime.date(2026, 9, 28), datetime.date(2026, 9, 28), "公眾假期補假 (中秋節翌日後首個工作日)"),
    (datetime.date(2026, 10, 1), datetime.date(2026, 10, 2), "公眾假期 (國慶節及國慶節翌日)"),
    (datetime.date(2026, 10, 19), datetime.date(2026, 10, 19), "公眾假期補假 (重陽節後首個工作日)"),
    (datetime.date(2026, 11, 2), datetime.date(2026, 11, 2), "公眾假期 (追思節)"),
    (datetime.date(2026, 12, 8), datetime.date(2026, 12, 8), "公眾假期 (聖母無原罪瞻禮)"),
    (datetime.date(2026, 12, 15), datetime.date(2026, 12, 19), "非教學/考試期 (第一學期複習期)"),
    (datetime.date(2026, 12, 20), datetime.date(2026, 12, 27), "大學休課/假期 (聖誕節假期)"),

    # --- 2027年 上半年 ---
    (datetime.date(2027, 1, 1), datetime.date(2027, 1, 1), "公眾假期 (元旦)"),
    (datetime.date(2027, 2, 1), datetime.date(2027, 2, 14), "大學休課/假期 (農曆新年假期及政府補假)"),
    (datetime.date(2027, 3, 26), datetime.date(2027, 3, 29), "公眾假期及補假 (耶穌受難日、復活節)"),
    (datetime.date(2027, 4, 5), datetime.date(2027, 4, 5), "公眾假期 (清明節)"),
    (datetime.date(2027, 5, 1), datetime.date(2027, 5, 3), "公眾假期及補假 (勞動節)"),
    (datetime.date(2027, 5, 12), datetime.date(2027, 5, 17), "非教學/考試期 (第二學期複習期，含5月13日佛誕節)"),
]

WEEKDAY_NAMES = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]

def evaluate_school_day(date_obj):
    """
    評估某一天是否有效，並返回 (是否有效: bool, 原因說明: str)
    """
    # 1. 檢查週末
    if date_obj.weekday() >= 5:
        return False, f"週末 ({WEEKDAY_NAMES[date_obj.weekday()]})"
    
    # 2. 檢查公眾假期、複習期與休課日
    for h_start, h_end, reason in HOLIDAYS_WITH_REASON:
        if h_start <= date_obj <= h_end:
            return False, reason
            
    # 3. 檢查是否處於有效上課或考試期內
    for p_start, p_end in VALID_PERIODS:
        if p_start <= date_obj <= p_end:
            return True, "有效教學/考試日"
            
    # 若不在上述有效區間內（例如 2027-01-12 兩學期之間的空檔日）
    return False, "非教學/考試期 (學期間歇/假期)"

# ==========================================
# 3. 網頁互動與核心運算邏輯
# ==========================================
uploaded_file = st.file_uploader("📂 請在此處拖曳或點擊上傳 PDF 文件", type="pdf")

if uploaded_file is not None:
    with st.spinner("正在高速解析 PDF 數據與活動軌跡..."):
        try:
            # 讀取 PDF
            reader = PdfReader(uploaded_file)
            text = "".join([page.extract_text() + "\n" for page in reader.pages])
            
            # 抓取出入境動作與日期：出境=離開內地(進澳門)，入境=回到內地(離開澳門)
            matches = re.findall(r'(出境|入境)[^\d]{0,40}(20\d{2}-\d{2}-\d{2})', text.replace('\n', ' '))
            
            # 按時間從舊到新（順敘）排列
            events = []
            for action, date_str in reversed(matches):
                d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                events.append((d, action))

            macau_days = set()
            current_location = "Mainland"
            last_date = None

            # 核心狀態機：計算連續逗留與填補空白
            for date, action in events:
                macau_days.add(date)

                if current_location == "Macau" and last_date:
                    delta = (date - last_date).days
                    for i in range(1, delta):
                        macau_days.add(last_date + datetime.timedelta(days=i))

                if action == "出境":
                    current_location = "Macau"
                    last_date = date
                elif action == "入境":
                    current_location = "Mainland"
                    last_date = None

            # 處理邊界情況：如果查詢當天仍在澳門未返回內地，補齊至查詢當日（不超過學期末）
            if current_location == "Macau" and last_date:
                today = datetime.date.today()
                end_cap = min(today, VALID_PERIODS[-1][1])
                if last_date < end_cap:
                    for i in range(1, (end_cap - last_date).days + 1):
                        macau_days.add(last_date + datetime.timedelta(days=i))

            # ==========================================
            # 4. 根據校曆過濾有效與無效天數
            # ==========================================
            academic_year_start = VALID_PERIODS[0][0]
            academic_year_end = VALID_PERIODS[-1][1]
            
            ay_macau_days = [d for d in sorted(list(macau_days)) if academic_year_start <= d <= academic_year_end]
            outside_ay_days = [d for d in sorted(list(macau_days)) if d < academic_year_start or d > academic_year_end]
            
            valid_dates_list = []
            invalid_dates_list = []
            
            for d in ay_macau_days:
                is_valid, reason = evaluate_school_day(d)
                date_formatted = f"{d.strftime('%Y-%m-%d')} ({WEEKDAY_NAMES[d.weekday()]})"
                if is_valid:
                    valid_dates_list.append(date_formatted)
                else:
                    invalid_dates_list.append((date_formatted, reason))
                    
            valid_days_count = len(valid_dates_list)
            invalid_days_count = len(invalid_dates_list)
            
            # 預測剩餘天數 (從明天起算至學年結束)
            today = datetime.date.today()
            calc_start = max(today + datetime.timedelta(days=1), academic_year_start)
            future_valid_days = 0
            
            if calc_start <= academic_year_end:
                future_valid_days = sum(
                    1 for i in range((academic_year_end - calc_start).days + 1)
                    if evaluate_school_day(calc_start + datetime.timedelta(days=i))[0]
                )
            
            total_projected = valid_days_count + future_valid_days
            shortfall = TARGET_DAYS - valid_days_count

            # ==========================================
            # 5. 渲染結果看板
            # ==========================================
            st.divider()
            st.subheader("📊 2026/2027 學年智能核算報告")
            
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("📌 本學年在澳總天數", f"{len(ay_macau_days)} 天")
            col2.metric("✨ 有效達標天數", f"{valid_days_count} 天")
            col3.metric("🚫 無效剔除天數", f"{invalid_days_count} 天")
            col4.metric("🎯 距離目標還差", f"{shortfall if shortfall > 0 else 0} 天")

            if shortfall > 0:
                st.warning(f"⚠️ 距離二年級 **{TARGET_DAYS}** 天的安全線還差 **{shortfall}** 天，請繼續保持通勤！")
            else:
                st.success(f"🎉 恭喜！你已經達成二年級 90 天指標，超額完成了 {-shortfall} 天！")
            
            st.info(f"🔮 **考勤預測**：從明天起到本學年結束（{academic_year_end.strftime('%Y-%m-%d')}），扣除週末、複習週及所有公眾假期後，還剩 **{future_valid_days}** 個有效工作日。")
            
            if total_projected >= TARGET_DAYS:
                st.success(f"✅ **學期末狀態預測**：安全。如果接下來全勤，你還擁有 **{total_projected - TARGET_DAYS}** 天的合法缺席額度。")
            else:
                st.error(f"❌ **學期末狀態預測**：危險！即使接下來每個有效日都去，也還差 **{TARGET_DAYS - total_projected}** 天！")

            # 摺疊面板 1：有效日期明細
            with st.expander(f"✅ 點擊查看計入的有效日期明細 (共 {valid_days_count} 天)"):
                if valid_dates_list:
                    for i, d_str in enumerate(valid_dates_list, 1):
                        st.write(f"`{i:03d}.` {d_str}")
                else:
                    st.write("暫無本學年的有效逗留記錄。")

            # 摺疊面板 2：無效日期及原因解釋
            with st.expander(f"🚫 點擊查看未計入的無效日期及原因 (本學年共 {invalid_days_count} 天)"):
                st.caption("根據大學《關於內地生在澳逗留時間指引通告》，「學期」僅包含校曆內的「上課日期」與「考試日期」，且必須排除星期六、日及法定假期/學校休課日。")
                if invalid_dates_list:
                    for i, (d_str, reason) in enumerate(invalid_dates_list, 1):
                        st.write(f"`{i:03d}.` **{d_str}** —— {reason}")
                else:
                    st.write("太棒了！你在本學年期間的在澳記錄全部為有效工作日，沒有無效天數。")
                    
                if outside_ay_days:
                    st.divider()
                    st.write(f"ℹ️ **另註**：你的 PDF 中還包含 **{len(outside_ay_days)} 天** 屬於 2026/2027 學年之外的在澳記錄（如 2026年9月1日前 或 2027年5月31日後），已自動隔離不納入本學年計算。")

        except Exception as e:
            st.error(f"解析文件時出錯，請確保上傳的是正確的 PDF 文件。錯誤訊息: {e}")
