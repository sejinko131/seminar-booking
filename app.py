import streamlit as st
import gspread
import pandas as pd
import time
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, time as dt_time

# --- 1. 기본 설정 ---
JSON_FILE = "key.json" 
SHEET_NAME = "세미나실_대관" 

st.set_page_config(page_title="세미나실 대관시스템", page_icon="📅", layout="centered")

# --- 2. CSS 스타일 ---
st.markdown("""
    <style>
    .block-container { padding-top: 6rem; padding-bottom: 5rem; }
    h1 { text-align: center; font-size: 1.8rem !important; margin-bottom: 10px; }
    .stButton button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    
    /* 달력 데이터프레임 스타일 */
    .dataframe { font-size: 12px !important; text-align: center !important; }
    
    .notice-box { background-color: #fff3cd; color: #856404 !important; padding: 15px; border-radius: 5px; font-size: 13px; margin-bottom: 15px; line-height: 1.6; }
    
    .success-message {
        background-color: #d4edda;
        color: #155724;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #c3e6cb;
        text-align: center;
        margin: 20px 0;
        font-weight: bold;
        font-size: 16px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    
    div[data-baseweb="input"] { padding: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 구글 시트 연결 ---
@st.cache_resource
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        if "gcp_service_account" in st.secrets:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

# --- 4. 데이터 캐싱 ---
@st.cache_data(ttl=15)
def load_data():
    client = get_client()
    if not client: return None, None
    try:
        sheet = client.open(SHEET_NAME)
        try: ws1 = sheet.worksheet("시트1"); data1 = ws1.get_all_records()
        except: data1 = []
        try: ws2 = sheet.worksheet("정기대관_신청"); data2 = ws2.get_all_values()
        except: data2 = []
        return data1, data2
    except: return None, None

# --- 5. 헬퍼 함수 ---
def to_min(v):
    try:
        if isinstance(v, int): return v * 60
        if isinstance(v, str):
            v = v.strip()
            if ':' in v: h, m = map(int, v.split(':')[0:2]); return h * 60 + m
            if v.isdigit(): return int(v) * 60
    except: pass
    return 0

def get_day_korean(date_obj): return ["월", "화", "수", "목", "금", "토", "일"][date_obj.weekday()]

# --- 6. 달력 데이터 생성 함수 ---
def get_weekly_schedule(records_normal, records_reg, week_offset=0):
    today = datetime.now().date()
    target_date = today + timedelta(weeks=week_offset)
    
    # 해당 주 월요일
    start_of_week = target_date - timedelta(days=target_date.weekday())
    week_dates = [start_of_week + timedelta(days=i) for i in range(7)]
    
    # 컬럼명
    week_cols = [f"{d.strftime('%m/%d')}({get_day_korean(d)})" for d in week_dates]
    
    # 시간대 (09:00 ~ 23:00)
    hours = range(9, 24)
    df = pd.DataFrame(index=[f"{h:02d}:00" for h in hours], columns=week_cols)
    df[:] = "" 

    # [1] 일반 예약
    if records_normal:
        for row in records_normal:
            try:
                r_d = datetime.strptime(str(row.get('날짜','')).replace('.','-').strip(), "%Y-%m-%d").date()
                if r_d in week_dates:
                    col_idx = week_dates.index(r_d)
                    col_name = week_cols[col_idx]
                    
                    s_min = to_min(row.get('시작시간'))
                    e_min = to_min(row.get('종료시간'))
                    
                    # 철야 처리
                    if e_min < s_min: e_min += 24 * 60

                    for h in hours:
                        h_start = h * 60
                        h_end = (h + 1) * 60
                        if (s_min < h_end) and (e_min > h_start):
                            df.at[f"{h:02d}:00", col_name] = "🟦"
            except: continue

    # [2] 정기 대관
    if records_reg and len(records_reg) > 1:
        for row in records_reg[1:]:
            try:
                if len(row) < 7: continue
                p_str, d_str, t_str = row[4], row[5], row[6]
                if "~" in p_str and "~" in t_str:
                    ps, pe = p_str.split("~")
                    p_start = datetime.strptime(ps.strip(), "%Y-%m-%d").date()
                    p_end = datetime.strptime(pe.strip(), "%Y-%m-%d").date()
                    
                    ts, te = t_str.split("~")
                    rs, re_time = to_min(ts), to_min(te)
                    if re_time < rs: re_time += 24*60

                    for i, w_date in enumerate(week_dates):
                        if p_start <= w_date <= p_end:
                            if get_day_korean(w_date) in d_str:
                                col_name = week_cols[i]
                                for h in hours:
                                    h_start = h * 60
                                    h_end = (h + 1) * 60
                                    if (rs < h_end) and (re_time > h_start):
                                        if df.at[f"{h:02d}:00", col_name] == "":
                                            df.at[f"{h:02d}:00", col_name] = "🟧"
            except: continue
            
    return df, f"{start_of_week.strftime('%Y.%m.%d')} ~ {(start_of_week+timedelta(days=6)).strftime('%Y.%m.%d')}"

# --- 7. 메인 UI ---
st.title("공공인재학부 세미나실 대관시스템")
with st.expander("📢 이용수칙 및 안내 (필독)", expanded=False):
    st.markdown("""<div class="notice-box"><b>📁 대관 안내</b><br>- 일반대관: 최대 3주 뒤까지 신청 가능 (1일 3시간)<br>- 정기대관: 매월 1일 신청 (스터디 목적)<br><br><b>📁 이용 수칙</b><br>- 1인 대관 불가 / 선착순 마감 / 타 학과생 불가</div>""", unsafe_allow_html=True)

# 데이터 로드
records_normal, records_reg = load_data()

# [대관 현황 - 달력]
st.markdown("#### 📅 세미나실 대관현황 (주간)")
if 'week_offset' not in st.session_state: st.session_state.week_offset = 0

wc1, wc2, wc3 = st.columns([1, 2, 1])
with wc1:
    if st.button("◀ 지난주"): st.session_state.week_offset -= 1; st.rerun()
with wc3:
    if st.button("다음주 ▶"):
        if st.session_state.week_offset < 3: st.session_state.week_offset += 1; st.rerun()
        else: st.toast("최대 3주 후까지만 조회 가능합니다.")

schedule_df, week_range_str = get_weekly_schedule(records_normal, records_reg, st.session_state.week_offset)
with wc2: st.markdown(f"<div style='text-align:center; font-weight:bold; padding-top:10px;'>{week_range_str}</div>", unsafe_allow_html=True)

st.caption("🟦: 일반 예약 / 🟧: 정기 대관")
def highlight_cells(val):
    if val == "🟦": return 'background-color: #a3d4ff; color: #a3d4ff' 
    elif val == "🟧": return 'background-color: #ffcc99; color: #ffcc99' 
    return ''
st.dataframe(schedule_df.style.map(highlight_cells), use_container_width=True, height=400)

# 성공 메시지
success_placeholder = st.empty()
if 'success_msg' in st.session_state and st.session_state['success_msg']:
    with success_placeholder.container():
        st.markdown("""
        <div class="success-message">
            ✅ 대관 완료되었습니다.<br>
            세미나실 비밀번호는 0015*입니다.<br>
            사용 후에는 정리정돈 및 문단속 부탁드립니다.
        </div>
        """, unsafe_allow_html=True)
        st.balloons()
    time.sleep(10)
    success_placeholder.empty()
    st.session_state['success_msg'] = False
    st.rerun()

tab1, tab2 = st.tabs(["📅 일반 예약", "📝 정기 대관 신청"])

# TAB 1: 일반 예약
with tab1:
    if 'attendees' not in st.session_state: st.session_state.attendees = [{"name": "", "id": ""}, {"name": "", "id": ""}]
    def add_attendee(): st.session_state.attendees.append({"name": "", "id": ""})
    def remove_last(): 
        if len(st.session_state.attendees) > 1: st.session_state.attendees.pop()

    c1, c2 = st.columns(2)
    with c1: 
        today = datetime.today()
        date = st.date_input("날짜", min_value=today, max_value=today+timedelta(weeks=3))
        date_str = date.strftime("%Y-%m-%d")
    with c2: st.write("")
    
    t1, t2 = st.columns(2)
    with t1: start_time = st.time_input("시작", value=dt_time(14,0), step=600)
    with t2: end_time = st.time_input("종료", value=dt_time(16,0), step=600)

    st.caption("예약자 명단 (첫 번째가 대표자)")
    for i, p in enumerate(st.session_state.attendees):
        ic1, ic2 = st.columns([6, 4])
        with ic1: st.session_state.attendees[i]["name"] = st.text_input(f"이름{i}", value=p["name"], placeholder="이름", key=f"n{i}", label_visibility="collapsed")
        with ic2: st.session_state.attendees[i]["id"] = st.text_input(f"학번{i}", value=p["id"], placeholder="학번", key=f"i{i}", label_visibility="collapsed")
    
    bc1, bc2 = st.columns(2)
    with bc1: st.button("➕ 인원 추가", on_click=add_attendee)
    with bc2: 
        if len(st.session_state.attendees) > 1: st.button("➖ 삭제", on_click=remove_last)
    
    st.write("---")
    if st.button("📅 예약 신청하기", type="primary"):
        s_min = to_min(f"{start_time.hour}:{start_time.minute}")
        e_min = to_min(f"{end_time.hour}:{end_time.minute}")
        
        # 철야 시간 계산 (종료 < 시작이면 다음날로 간주하여 시간 더함)
        if e_min < s_min: dur = (24 * 60 - s_min) + e_min
        else: dur = e_min - s_min
            
        valid_users = [p for p in st.session_state.attendees if p['name'] and p['id']]
        
        if len(valid_users) < 2: st.error("❌ 최소 2인 이상 입력해야 합니다. (1인 대관 불가)")
        elif dur > 180: st.error("❌ 하루 최대 3시간까지만 가능합니다.")
        elif dur < 10: st.error("❌ 최소 10분")
        else:
            cli = get_client()
            if not cli: st.error("❌ 서버 연결 실패")
            else:
                try:
                    # [★수정됨] rep_name, rep_id 정의 (try 블록 맨 위로 위치 변경)
                    rep_name = valid_users[0]['name'].strip()
                    rep_id = valid_users[0]['id'].strip()

                    # [1] 개인별 누적 사용량 전수 조사 (철야 포함)
                    block_msg = ""
                    if records_normal:
                        for applicant in valid_users:
                            app_name = applicant['name'].strip()
                            app_id = applicant['id'].strip()
                            my_usage_min = 0 
                            
                            for row in records_normal:
                                if str(row.get('날짜','')).replace('.','-').strip() == date_str:
                                    es = to_min(row.get('시작시간'))
                                    ee = to_min(row.get('종료시간'))
                                    
                                    # DB에 저장된 시간의 사용량 계산 (철야 고려)
                                    if ee < es: usage = (24*60 - es) + ee
                                    else: usage = ee - es
                                    
                                    # 포함 여부 확인
                                    is_included = False
                                    r_n = str(row.get('대표자명','')).strip()
                                    r_i = str(row.get('대표학번','')).strip()
                                    
                                    if r_n == app_name and r_i == app_id: # 대표자일 때
                                        is_included = True
                                    else: # 동반자일 때
                                        others = str(row.get('동반인원',''))
                                        target_str = f"{app_name}({app_id})"
                                        if others and others != "없음" and target_str in others:
                                            is_included = True
                                    
                                    if is_included:
                                        my_usage_min += usage
                            
                            if my_usage_min + dur > 180:
                                block_msg = f"❌ '{app_name}'님은 금일 이용 한도(3시간)를 초과하게 됩니다.\n(이미 {my_usage_min}분 사용 + 신청 {dur}분)"
                                break
                    
                    if block_msg:
                        st.error(block_msg)
                        st.stop()

                    # [2] 중복 시간 검사 (철야 포함)
                    overlap=False
                    req_start_dt = datetime.combine(date, start_time)
                    req_end_dt = datetime.combine(date + timedelta(days=1 if e_min < s_min else 0), end_time)

                    if records_normal:
                        for row in records_normal:
                            try:
                                r_d = datetime.strptime(str(row.get('날짜','')).replace('.','-').strip(), "%Y-%m-%d").date()
                                es = to_min(row.get('시작시간'))
                                ee = to_min(row.get('종료시간'))
                                
                                # 기존 예약 타임스탬프 (철야 고려)
                                exist_start_dt = datetime.combine(r_d, dt_time(hour=es//60, minute=es%60))
                                exist_end_dt = datetime.combine(r_d + timedelta(days=1 if ee < es else 0), dt_time(hour=ee//60, minute=ee%60))
                                
                                if (req_start_dt < exist_end_dt) and (req_end_dt > exist_start_dt):
                                    overlap=True; break
                            except: continue

                    if not overlap and records_reg:
                        kd = get_day_korean(date)
                        for rr in records_reg[1:]:
                            if len(rr)>6 and "~" in rr[4] and kd in rr[5]:
                                ps, pe = rr[4].split("~")
                                if ps.strip() <= date_str <= pe.strip():
                                    ts, te = rr[6].split("~")
                                    reg_s = to_min(ts.strip())
                                    reg_e = to_min(te.strip())
                                    reg_start_dt = datetime.combine(date, dt_time(hour=reg_s//60, minute=reg_s%60))
                                    reg_end_dt = datetime.combine(date + timedelta(days=1 if reg_e < reg_s else 0), dt_time(hour=reg_e//60, minute=reg_e%60))
                                    if (req_start_dt < reg_end_dt) and (req_end_dt > reg_start_dt):
                                        overlap=True; break
                    
                    if overlap: st.error("❌ 예약 불가: 이미 예약된 시간입니다.")
                    else:
                        sht = cli.open(SHEET_NAME).worksheet("시트1")
                        others = ", ".join([f"{p['name']}({p['id']})" for p in valid_users[1:]])
                        s_str, e_str = start_time.strftime("%H:%M"), end_time.strftime("%H:%M")
                        # 이제 rep_name, rep_id가 정의되어 있으므로 에러 없음
                        sht.append_row([date_str, s_str, e_str, rep_name, rep_id, others])
                        st.cache_data.clear()
                        st.session_state['success_msg'] = True
                        st.rerun()
                except Exception as e: st.error(f"오류: {e}")

# TAB 2: 정기 대관
with tab2:
    st.info("📢 관리자 승인 후 확정됩니다.")
    with st.form("reg_form"):
        tn = st.text_input("단체명")
        ln = st.text_input("대표자")
        ct = st.text_input("연락처")
        c1, c2 = st.columns(2)
        with c1: sd = st.date_input("시작일")
        with c2: ed = st.date_input("종료일")
        days = st.multiselect("요일", ["월","화","수","목","금","토","일"])
        tc1, tc2 = st.columns(2)
        with tc1: rs = st.time_input("시작시간", dt_time(18,0))
        with tc2: re = st.time_input("종료시간", dt_time(21,0))
        purp = st.text_area("사용목적", height=80)
        if st.form_submit_button("신청서 제출"):
            if not tn or not days: st.error("필수 정보 입력")
            else:
                try:
                    cli = get_client()
                    sr = cli.open(SHEET_NAME).worksheet("정기대관_신청")
                    now = datetime.now().strftime("%Y-%m-%d")
                    p_str = f"{sd} ~ {ed}"
                    d_str = ", ".join(days)
                    t_str = f"{rs.strftime('%H:%M')} ~ {re.strftime('%H:%M')}"
                    sr.append_row([now, tn, ln, ct, p_str, d_str, t_str, purp])
                    st.cache_data.clear()
                    st.success("✅ 신청 완료!")
                    st.rerun()
                except: st.error("오류")
