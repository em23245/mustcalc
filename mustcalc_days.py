import streamlit as st
import re
import datetime
from PyPDF2 import PdfReader

# ==========================================
# 1. 網頁基礎與 UI 設置
# ==========================================
st.set_page_config(page_title="澳科大逗留天數計算器", page_icon="🎓", layout="centered")
st.title("🎓 澳科大內地生逗留天數計算器)
st.markdown("""
上傳從國家移民管理局下載的《出入境記錄查詢結果》PDF，系統將為你：
* 🔄 自動識別出入境狀態（**出境=進入澳門，入境=返回內地**）
* 🧠 智能補全長期留澳的空白日期
* 📅 精準剔除週末、學校長假與法定公眾假期
""")
st.caption("註：本工具已內建 2025/2026 學年澳科大校曆（含聖誕、春節及五一等公眾假期）。數據僅在瀏覽器本地運行，不保存任何個人隱私。")

# ==========================================
# 2. 澳科大日曆與規則配置
# ==========================================
TARGET_DAYS = 119 # 博士首年要求天數

# 學期起止時間
SEMESTERS = [
    (datetime.date(2025, 9, 1), datetime.date(2026, 1, 10)),  # 第一學期
    (datetime.date(2026, 1, 12), datetime.date(2026, 5, 28))   # 第二學期
]

# 學校長假與公眾假期 (需扣除的日子)
HOLIDAYS = [
    # 學校長假
    (datetime.date(2025, 12, 15), datetime.date(2025, 12, 25)), # 聖誕假
    (datetime.date(2026, 2, 11), datetime.date(2026, 2, 24)),   # 農曆新年假
    # 單日/零星公眾假期 (2026年預估)
    (datetime.date(2026, 4, 3), datetime.date(2026, 4, 6)),     # 復活節與清明節連假
    (datetime.date(2026, 5, 1), datetime.date(2026, 5, 1)),     # 五一勞動節
    (datetime.date(2026, 5, 24), datetime.date(2026, 5, 25)),   # 佛誕節
]

def is_valid_school_day(date_obj):
    """判斷是否為學校規定的有效教學/考試日 (非週末、非假期)"""
    # 1. 剔除週末 (0=週一, 5=週六, 6=週日)
    if date_obj.weekday() >= 5: return False
    
    # 2. 剔除假期
    for h_start, h_end in HOLIDAYS:
        if h_start <= date_obj <= h_end: return False
        
    # 3. 必須在學期內
    in_semester = False
    for s_start, s_end in SEMESTERS:
        if s_start <= date_obj <= s_end:
            in_semester = True
            break
    return in_semester

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
            
            # 使用高級正則：同時抓取出入境動作與日期
            # 移民局文件邏輯：出境=離開內地(進澳門)，入境=回到內地(離開澳門)
            matches = re.findall(r'(出境|入境)[^\d]{0,40}(20\d{2}-\d{2}-\d{2})', text.replace('\n', ' '))
            
            # PDF 是最新記錄在最前，我們將其反轉，按照時間從舊到新（順敘）處理
            events = []
            for action, date_str in reversed(matches):
                d = datetime.datetime.strptime(date_str, "%Y-%m-%d").date()
                events.append((d, action))

            macau_days = set()
            current_location = "Mainland"
            last_date = None

            # 核心狀態機：計算連續逗留與填補空白
            for date, action in events:
                macau_days.add(date) # 只要有打卡記錄，當天一定算在澳門（至少待過）

                # 如果之前在澳門，現在有了新記錄，把中間斷層的日子全部補齊
                if current_location == "Macau" and last_date:
                    delta = (date - last_date).days
                    for i in range(1, delta):
                        macau_days.add(last_date + datetime.timedelta(days=i))

                if action == "出境": # 離開內地去澳門
                    current_location = "Macau"
                    last_date = date
                elif action == "入境": # 離開澳門回內地
                    current_location = "Mainland"
                    last_date = None

            # 處理邊界情況：如果 PDF 列印時，該同學仍在澳門還沒回來
            if current_location == "Macau" and last_date:
                today = datetime.date.today()
                if last_date < today:
                    for i in range(1, (today - last_date).days + 1):
                        macau_days.add(last_date + datetime.timedelta(days=i))

            # ==========================================
            # 4. 根據校曆過濾與預測
            # ==========================================
            valid_days_count = 0
            valid_dates_list = []
            for d in sorted(list(macau_days)):
                if is_valid_school_day(d):
                    valid_days_count += 1
                    valid_dates_list.append(d.strftime("%Y-%m-%d"))
            
            # 預測剩餘天數 (從今天到學期末)
            today = datetime.date.today()
            final_end_date = SEMESTERS[-1][1]
            future_valid_days = 0
            
            if today <= final_end_date:
                future_valid_days = sum(1 for i in range((final_end_date - today).days + 1) 
                                        if is_valid_school_day(today + datetime.timedelta(days=i)))
            
            total_projected = valid_days_count + future_valid_days
            shortfall = TARGET_DAYS - valid_days_count

            # ==========================================
            # 5. 渲染結果看板
            # ==========================================
            st.divider()
            st.subheader("📊 智能核算報告")
            
            col1, col2, col3 = st.columns(3)
            col1.metric("📌 實際在澳總天數", f"{len(macau_days)} 天")
            col2.metric("✨ 有效達標天數", f"{valid_days_count} 天")
            col3.metric("🎯 距離目標還差", f"{shortfall if shortfall > 0 else 0} 天")

            # 狀態提示
            if shortfall > 0:
                st.warning(f"⚠️ 距離 **{TARGET_DAYS}** 天的安全線還差 **{shortfall}** 天，請繼續保持通勤！")
            else:
                st.success(f"🎉 恭喜！你已經達標，超額完成了 {-shortfall} 天！")
            
            st.info(f"🔮 **考勤預測**：從今天起到學期結束（{final_end_date.strftime('%Y-%m-%d')}），扣除紅日子後，理論上還剩 **{future_valid_days}** 個有效工作日。")
            
            if total_projected >= TARGET_DAYS:
                st.success(f"✅ **學期末狀態預測**：安全。如果接下來全勤，你還擁有 **{total_projected - TARGET_DAYS}** 天的合法缺席額度。")
            else:
                st.error(f"❌ **學期末狀態預測**：危險！即使接下來天天都去，也還差 **{TARGET_DAYS - total_projected}** 天！")

            # 隱藏的詳情列表（點擊展開）
            with st.expander("📅 點擊查看計入的有效日期明細 (包含智能補全的連續長居日期)"):
                for i, d in enumerate(valid_dates_list, 1):
                    st.write(f"`{i:03d}.` {d}")

        except Exception as e:
            st.error(f"解析文件時出錯，請確保上傳的是正確的 PDF 文件。錯誤訊息: {e}")
