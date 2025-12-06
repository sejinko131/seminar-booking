import streamlit as st
import gspread
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
    
    .status-box { background-color: #ffffff; border-radius: 10px; padding: 15px; margin-bottom: 20px; border: 1px solid #ddd; font-size: 14px; color: #000000 !important; }
    .status-header { font-weight: bold; color: #ff4b4b !important; margin-bottom: 10px; font-size: 16px; border-bottom: 2px solid #eee; padding-bottom: 5px; }
    .status-item { margin-bottom: 5px; padding: 5px; border-bottom: 1px solid #f0f0f0; }
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

# --- 3. 구글 시트 연결 (TOML 방식 - 가장 안정적) ---
@st.cache_resource
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    try:
        # [배포 환경] Secrets의 [gcp_service_account] 섹션을 딕셔너리로 바로 가져옴
        if "gcp_service_account" in st.secrets:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        # [로컬 환경] 내 컴퓨터 파일 사용
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
            if ':' in v: h, m = map(int, v.split(':')); return h * 60 + m
            if v.isdigit(): return int(v) * 60
    except: pass
    return 0

def get_day_korean(date_obj): return ["월", "화", "수", "목", "금", "토", "일"][date_obj.weekday()]
def mask_name(name): return (str(name).strip()[0] + "**") if len(str(name).strip()) > 1 else str(name)

# --- 6. 현황판 ---
def show_status(records_normal, records_reg):
    st.markdown("#### 📅 세미나실 대관현황")
    status_html = "<div class='status-box'>"
    status_html += "<div class='status-header'>▪️ 일반대관 (24시간 기준)</div>"
    
    if records_normal is not None:
        today = datetime.now().date()
        future = []
        for row in records_normal:
            try:
                r_d = datetime.strptime(str(row.get('날짜','')).replace('.','-').replace('/','-').strip(), "%Y-%m-%d").date()
                if r_d >= today:
                    name = str(row.get('대표자명', ''))
                    start = str(row.get('시작시간', ''))
                    end = str(row.get('종료시간', ''))
                    disp = mask_name(name) if name else "예약자"
                    if start and end:
                        item = f"<b>{disp}</b> / {r_d.strftime('%m/%d')}({get_day_korean(r_d)}) / {start} - {end}"
                        future.append({"d": r_d, "s": item})
            except: continue
        future.sort(key=lambda x: x['d'])
        if not future: status_html += "<div class='status-item' style='color:#999;'>예정된 예약이 없습니다.</div>"
        else:
            for item in future[:10]: status_html += f"<div class='status-item'>{item['s']}</div>"
    else: status_html += "<div class='status-item' style='color:red;'>서버 연결 실패</div>"
    
    status_html += "<br><div class='status-header'>▪️ 정기대관 (학기 중)</div>"
    has_reg = False
    if records_reg and len(records_reg) > 1:
        for row in records_reg[1:]:
            if len(row) > 6:
                status_html += f"<div class='status-item'><b>{row[1]}</b> / 매주 {row[5]} / {row[6]}</div>"
                has_reg = True
    if not has_reg: status_html += "<div class='status-item' style='color:#999;'>승인된 정기 대관이 없습니다.</div>"
    
    status_html += "</div>"
    st.markdown(status_html, unsafe_allow_html=True)

# --- 7. 메인 UI 및 로직 ---
st.title("공공인재학부 세미나실 대관시스템")
with st.expander("📢 이용수칙 및 안내 (필독)", expanded=False):
    st.markdown("""<div class="notice-box"><b>📁 대관 안내</b><br>- 일반대관: 최대 3주 뒤까지 신청 가능 (1일 3시간)<br>- 정기대관: 매월 1일 신청 (스터디 목적)<br><br><b>📁 이용 수칙</b><br>- 1인 대관 불가 / 선착순 마감 / 타 학과생 불가</div>""", unsafe_allow_html=True)

# 데이터 로드 및 현황판 표시
records_normal, records_reg = load_data()
show_status(records_normal, records_reg)

# ★ [핵심] 예약 성공 메시지 표시 영역
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
        dur = e_min - s_min
        valid = [p for p in st.session_state.attendees if p['name'] and p['id']]
        
        if len(valid)<1: st.error("❌ 최소 1명 입력 필수")
        elif dur > 180: st.error("❌ 최대 3시간")
        elif dur < 10: st.error("❌ 최소 10분")
        elif s_min >= e_min: st.error("❌ 종료시간 오류")
        else:
            cli = get_client()
            if not cli: st.error("❌ 서버 연결 실패")
            else:
                try:
                    overlap=False
                    if records_normal:
                        for row in records_normal:
                            if str(row.get('날짜','')).replace('.','-').strip() == date_str:
                                es, ee = to_min(row.get('시작시간')), to_min(row.get('종료시간'))
                                if (s_min < ee) and (e_min > es): overlap=True; break
                    if not overlap and records_reg:
                        kd = get_day_korean(date)
                        for rr in records_reg[1:]:
                            if len(rr)>6 and "~" in rr[4] and kd in rr[5]:
                                ps, pe = rr[4].split("~")
                                if ps.strip() <= date_str <= pe.strip():
                                    ts, te = rr[6].split("~")
                                    if (s_min < to_min(te.strip())) and (e_min > to_min(ts.strip())): overlap=True; break
                    
                    if overlap: st.error("❌ 예약 불가: 이미 예약된 시간입니다.")
                    else:
                        sht = cli.open(SHEET_NAME).worksheet("시트1")
                        rep_n, rep_i = valid[0]['name'], valid[0]['id']
                        others = ", ".join([f"{p['name']}({p['id']})" for p in valid[1:]]) if len(valid)>1 else "없음"
                        s_str, e_str = start_time.strftime("%H:%M"), end_time.strftime("%H:%M")
                        sht.append_row([date_str, s_str, e_str, rep_n, rep_i, others])
                        
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
