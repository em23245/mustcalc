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
* 📅 精準匹配 **2026/2027 學年研究生校曆**，自動剔除週末、複習期、學校長假與澳門公眾假期（含補假）
""")
st.caption("註：本工具適用於 2026/2027 學年研究生（二年級 90 天標準）。數據僅在瀏覽器本地運行，不保存任何個人隱私。")

# ==========================================
# 2. 澳科大 2026/2027 學年日曆與規則配置
# ==========================================
TARGET_DAYS = 90  # 二年級（第三、四學期）要求天數

# 有效學期時段（僅包含校曆「上課日期」與「考試日期」，已剔除複習期、聖誕假及學期間歇）
VALID_PERIODS = [
    (datetime.date(2026, 9, 1), datetime.date(2026, 12, 14)),   # 第一學期：上課日期
    (datetime.date(2026, 12, 28), datetime.date(2027, 1, 11)),  # 第一學期：考試日期
    (datetime.date(2027, 1, 13), datetime.date(2027, 5, 11)),   # 第二學期：上課日期
    (datetime.date(2027, 5, 18), datetime.date(2027, 5, 31)),   # 第二學期：考試日期
]

# 2026 - 2027 學年公眾假期、政府補假與大學休課日 (落在學期內的工作日)
HOLIDAYS = [
    # --- 2026年 下半年公眾假期及補假 ---
    (datetime.date(2026, 9, 28), datetime.date(2026, 9, 28)),   # 中秋節翌日後首個工作日補假
    (datetime.date(2026, 10, 1), datetime.date(2026, 10, 2)),   # 國慶節及國慶節翌日
    (datetime.date(2026, 10, 19), datetime.date(2026, 10, 19)), # 重陽節後首個工作日補假
    (datetime.date(2026, 11, 2), datetime.date(2026, 11, 2)),   # 追思節
    (datetime.date(2026, 12, 8), datetime.date(2026, 12, 8)),   # 聖母無原罪瞻禮
    (datetime.date(2026, 12, 15), datetime.date(2026, 12, 27)), # 第一學期複習期及聖誕節休課 (含回歸紀念日、冬至等)

    # --- 2027年 上半年公眾假期、補假及大學休課 ---
    (datetime.date(2027, 1, 1), datetime.date(2027, 1, 1)),     # 元旦
    (datetime.date(2027, 2, 1), datetime.date(2027, 2, 14)),    # 農曆新年休課 (含春節及政府補假)
    (datetime.date(2027, 3, 26), datetime.date(2027, 3, 29)),   # 耶穌受難日、復活節前日及補假
    (datetime.date(2027, 4, 5), datetime.date(2027, 4, 5)),     # 清明節
    (datetime.date(2027, 5, 1), datetime.date(2027, 5, 3)),     # 勞動節及勞動節後首個工作日補假
    (datetime.date(2027, 5, 12), datetime.date(2027, 5, 17)),   # 第二學期複習期 (含5月13日佛誕節)
]

def is_valid_school_day(date_obj):
    """判斷是否為學校規定的有效教學/考試日 (非週末、非假期、處於上課或考試期內)"""
    # 1. 剔除週末 (0=週一, ..., 5=週六, 6=週日)
    if date_obj.weekday() >= 5:
        return False
    
    # 2. 剔除公眾假期與休課日
    for h_start, h_end in HOLIDAYS:
        if h_start <= date_obj <= h_end:
            return False
            
    # 3. 必須處於有效上課或考試期內
    for p_start, p_end in VALID_PERIODS:
        if p_start <= date_obj <= p_end:
            return True
            
    return False

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
            # 4. 根據校曆過濾與預測
            # ==========================================
            academic_year_start = VALID_PERIODS[0][0]
            academic_year_end = VALID_PERIODS[-1][1]
            
            # 僅統計本學年期間的在澳天數與有效天數
            ay_macau_days = [d for d in sorted(list(macau_days)) if academic_year_start <= d <= academic_year_end]
            valid_dates_list = [d.strftime("%Y-%m-%d") for d in ay_macau_days if is_valid_school_day(d)]
            valid_days_count = len(valid_dates_list)
            
            # 預測剩餘天數 (從明天起算至學年結束，避免與今天已打卡記錄重複計算)
            today = datetime.date.today()
            calc_start = max(today + datetime.timedelta(days=1), academic_year_start)
            future_valid_days = 0
            
            if calc_start <= academic_year_end:
                future_valid_days = sum(
                    1 for i in range((academic_year_end - calc_start).days + 1)
                    if is_valid_school_day(calc_start + datetime.timedelta(days=i))
                )
            
            total_projected = valid_days_count + future_valid_days
            shortfall = TARGET_DAYS - valid_days_count

            # ==========================================
            # 5. 渲染結果看板
            # ==========================================
            st.divider()
            st.subheader("📊 2026/2027 學年智能核算報告")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📌 本學年在澳總天數", f"{len(ay_macau_days)} 天")
            col2.metric("✨ 有效達標天數", f"{valid_days_count} 天")
            col3.metric("🎯 距離目標還差", f"{shortfall if shortfall > 0 else 0} 天")

            if shortfall > 0:
                st.warning(f"⚠️ 距離二年級 **{TARGET_DAYS}** 天的安全線還差 **{shortfall}** 天，請繼續保持通勤！")
            else:
                st.success(f"🎉 恭喜！你已經達成二年級 90 天指標，超額完成了 {-shortfall} 天！")
            
            st.info(f"🔮 **考勤預測**：從明天起到本學年結束（{academic_year_end.strftime('%Y-%m-%d')}），扣除週末、複習週及所有公眾假期後，還剩 **{future_valid_days}** 個有效工作日。")
            
            if total_projected >= TARGET_DAYS:
                st.success(f"✅ **學期末狀態預測**：安全。如果接下來全勤，你還擁有 **{total_projected - TARGET_DAYS}** 天的合法缺席額度。")
            else:
                st.error(f"❌ **學期末狀態預測**：危險！即使接下來每個有效日都去，也還差 **{TARGET_DAYS - total_projected}** 天！")

            with st.expander("📅 點擊查看計入的有效日期明細 (含智能補全的連續長居日期)"):
                if valid_dates_list:
                    for i, d in enumerate(valid_dates_list, 1):
                        st.write(f"`{i:03d}.` {d}")
                else:
                    st.write("暫無本學年的有效逗留記錄。")

        except Exception as e:
            st.error(f"解析文件時出錯，請確保上傳的是正確的 PDF 文件。錯誤訊息: {e}")
