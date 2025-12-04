import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, time

# --- 1. 기본 설정 ---
# 내 컴퓨터에서 실행할 때 필요한 키 파일 이름
LOCAL_JSON_FILE = "key.json" 
SHEET_NAME = "세미나실_대관" 

st.set_page_config(page_title="세미나실 대관시스템", page_icon="📅", layout="centered")

# --- 2. CSS: 디자인 및 다크모드 대응 ---
st.markdown("""
    <style>
    /* 상단 여백 (제목 위치) */
    .block-container { padding-top: 6rem; padding-bottom: 5rem; }
    
    /* 제목 중앙 정렬 */
    h1 { text-align: center; font-size: 1.8rem !important; margin-bottom: 10px; }
    
    /* 버튼 스타일 */
    .stButton button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    
    /* 현황 리스트 박스 (다크모드 대응: 흰 배경/검은 글씨 고정) */
    .status-box {
        background-color: #ffffff; 
        border-radius: 10px;
        padding: 15px;
        margin-bottom: 20px;
        border: 1px solid #ddd;
        font-size: 14px;
        color: #000000 !important;
    }
    .status-header { 
        font-weight: bold; 
        color: #ff4b4b !important; 
        margin-bottom: 10px; 
        font-size: 16px;
        border-bottom: 2px solid #eee;
        padding-bottom: 5px;
    }
    .status-item { 
        margin-bottom: 5px; 
        padding: 5px; 
        border-bottom: 1px solid #f0f0f0;
    }
    
    /* 공지사항 박스 */
    .notice-box {
        background-color: #fff3cd;
        color: #856404 !important;
        padding: 15px;
        border-radius: 5px;
        font-size: 13px;
        margin-bottom: 15px;
        line-height: 1.6;
    }

    /* 예약 성공 박스 */
    .success-box {
        background-color: #d4edda;
        color: #155724 !important;
        padding: 20px;
        border-radius: 10px;
        border: 1px solid #c3e6cb;
        margin-top: 10px;
        text-align: center;
    }
    
    /* 입력칸 패딩 */
    div[data-baseweb="input"] { padding: 5px; }
    </style>
    """, unsafe_allow_html=True)

# --- 3. 구글 시트 연결 (배포/로컬 호환) ---
@st.cache_resource
def get_client():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    
    try:
        # 1순위: Streamlit Cloud Secrets (배포 환경)
        if "gcp_service_account" in st.secrets:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        
        # 2순위: 로컬 json 파일 (내 컴퓨터)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(LOCAL_JSON_FILE, scope)
            
        client = gspread.authorize(creds)
        return client
    except Exception as e:
        return None

# --- 4. 데이터 캐싱 (API 보호) ---
@st.cache_data(ttl=15)
def load_data():
    client = get_client()
    if not client: return None, None
    
    try:
        sheet = client.open(SHEET_NAME)
        # 1. 일반 예약
        try:
            ws1 = sheet.worksheet("시트1")
            data1 = ws1.get_all_records()
        except: data1 = []
        
        # 2. 정기 대관
        try:
            ws2 = sheet.worksheet("정기대관_신청")
            data2 = ws2.get_all_values()
        except: data2 = []
            
        return data1, data2
    except:
        return None, None

# --- 5. 헬퍼 함수 ---
def to_min(v):
    """시간을 분 단위 정수로 변환"""
    try:
        if isinstance(v, int): return v * 60
        if isinstance(v, str):
            v = v.strip()
            if ':' in v: h, m = map(int, v.split(':')); return h * 60 + m
            if v.isdigit(): return int(v) * 60
    except: pass
    return 0

def get_day_korean(date_obj):
    return ["월", "화", "수", "목", "금", "토", "일"][date_obj.weekday()]

def mask_name(name):
    """이름 마스킹 (김중앙 -> 김**)"""
    name = str(name).strip()
    if len(name) > 1: return name[0] + "**"
    return name

# --- 6. 예약 현황 조회 (리스트 뷰) ---
def show_status(records_normal, records_reg):
    st.markdown("#### 📅 세미나실 대관현황")
    status_html = "<div class='status-box'>"
    
    # [1] 일반 대관 현황
    status_html += "<div class='status-header'>▪️ 일반대관 (24시간 기준)</div>"
    
    if records_normal is not None:
        today = datetime.now().date()
        future_reservations = []
        
        for row in records_normal:
            r_d_str = str(row.get('날짜','')).replace('.','-').replace('/','-').strip()
            try: r_date = datetime.strptime(r_d_str, "%Y-%m-%d").date()
            except: continue
            
            if r_date >= today:
                name = str(row.get('대표자명', ''))
                start = str(row.get('시작시간', ''))
                end = str(row.get('종료시간', ''))
                display_name = mask_name(name) if name else "예약자"
                
                if start and end:
                    item_str = f"<b>{display_name}</b> / {r_date.strftime('%m/%d')}({get_day_korean(r_date)}) / {start} - {end}"
                    future_reservations.append({"date": r_date, "str": item_str})
        
        future_reservations.sort(key=lambda x: x['date'])
        
        if not future_reservations:
            status_html += "<div class='status-item' style='color:#999;'>예정된 예약이 없습니다.</div>"
        else:
            for item in future_reservations[:10]: 
                status_html += f"<div class='status-item'>{item['str']}</div>"
    else:
        status_html += "<div class='status-item' style='color:red;'>데이터 로딩 실패 (잠시 후 다시 시도)</div>"
    
    status_html += "<br>"

    # [2] 정기 대관 현황
    status_html += "<div class='status-header'>▪️ 정기대관 (학기 중)</div>"
    if records_reg and len(records_reg) > 1:
        has_reg = False
        for row in records_reg[1:]: 
            if len(row) < 7: continue
            team, days, times = row[1], row[5], row[6]
            status_html += f"<div class='status-item'><b>{team}</b> / 매주 {days} / {times}</div>"
            has_reg = True
        if not has_reg:
            status_html += "<div class='status-item' style='color:#999;'>승인된 정기 대관이 없습니다.</div>"
    else:
        status_html += "<div class='status-item' style='color:#999;'>승인된 정기 대관이 없습니다.</div>"
            
    status_html += "</div>"
    st.markdown(status_html, unsafe_allow_html=True)


# --- 7. 메인 UI ---
st.title("공공인재학부 세미나실 대관시스템")

with st.expander("📢 이용수칙 및 안내 (필독)", expanded=False):
    st.markdown("""
    <div class="notice-box">
    <b>📁 대관 안내</b><br>
    - <b>일반대관:</b> 대관 희망 날짜 7일 전부터 신청 가능합니다. 동일 인원 구성으로 하루 최대 3시간 이용 가능합니다.<br>
    - <b>정기대관:</b> 매월 1일부터 한 달 단위로 신청 가능합니다. 동일 인원 구성으로 일주일 최대 3시간 이용 가능하며, 스터디 목적으로만 이용 가능합니다.<br><br>
    <b>📁 이용 수칙</b><br>
    - 1인 대관은 불가능합니다. 다만, 00시~08시 및 방학 중에는 가능합니다.<br>
    - 반드시 세미나실 대관 후 이용해주시길 바랍니다.<br>
    - 사용 후 정리정돈 부탁드립니다.<br>
    - 부적절한 이용이 발견될 경우 세미나실 이용이 제한될 수 있습니다<br>
    - 공공인재학부생을 위한 공간으로, 타 학과(부)생은 이용이 불가능하니 양해 부탁드립니다.<br>
    </div>
    """, unsafe_allow_html=True)

# 데이터 로드
records_normal, records_reg = load_data()
show_status(records_normal, records_reg)

# 탭 메뉴
tab1, tab2 = st.tabs(["📅 일반 예약", "📝 정기 대관 신청"])

# =========================================================
#  TAB 1: 일반 예약
# =========================================================
with tab1:
    if 'attendees' not in st.session_state:
        st.session_state.attendees = [{"name": "", "id": ""}, {"name": "", "id": ""}]
    def add_attendee(): st.session_state.attendees.append({"name": "", "id": ""})
    def remove_last(): 
        if len(st.session_state.attendees) > 1: st.session_state.attendees.pop()

    c1, c2 = st.columns(2)
    with c1:
        today = datetime.today()
        # 오늘부터 3주 뒤까지 예약 가능
        date = st.date_input("날짜", min_value=today, max_value=today+timedelta(weeks=3))
        date_str = date.strftime("%Y-%m-%d")
    with c2: st.write("")

    t1, t2 = st.columns(2)
    with t1: start_time = st.time_input("시작", value=time(14,0), step=600)
    with t2: end_time = st.time_input("종료", value=time(16,0), step=600)

    st.caption(f"예약자 명단 (첫 번째 사람이 대표자)")
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
        start_min = to_min(f"{start_time.hour}:{start_time.minute}")
        end_min = to_min(f"{end_time.hour}:{end_time.minute}")
        duration = end_min - start_min
        
        valid_users = [f"{p['name']} {p['id']}" for p in st.session_state.attendees if p['name'] and p['id']]
        
        if len(valid_users) < 1: st.error("❌ 최소 1명(대표자)은 입력해야 합니다.")
        elif duration > 180: st.error("❌ 하루 최대 3시간까지만 가능합니다.")
        elif duration < 10: st.error("❌ 최소 10분 이상 사용해야 합니다.")
        elif start_min >= end_min: st.error("❌ 종료 시간이 더 늦어야 합니다.")
        else:
            try:
                is_overlap = False
                
                # (A) 일반 예약 검사
                if records_normal is not None:
                    for row in records_normal:
                        r_d = str(row.get('날짜','')).replace('.','-').replace('/','-').strip()
                        if r_d == date_str:
                            e_s = to_min(row.get('시작시간'))
                            e_e = to_min(row.get('종료시간'))
                            if (start_min < e_e) and (end_min > e_s):
                                is_overlap = True; break
                
                # (B) 정기 대관 검사
                if not is_overlap and records_reg:
                    k_day = get_day_korean(date)
                    for rr in records_reg[1:]:
                        if len(rr)<7: continue
                        # [4]기간 [5]요일 [6]시간
                        if "~" in rr[4] and k_day in rr[5]:
                            ps, pe = rr[4].split("~")
                            if ps.strip() <= date_str <= pe.strip():
                                ts, te = rr[6].split("~")
                                rs, re = to_min(ts), to_min(te)
                                if (start_min < re) and (end_min > rs):
                                    is_overlap = True; break

                if is_overlap:
                    st.error("❌ 예약 불가: 이미 예약된 시간입니다.")
                else:
                    client = get_client()
                    if client:
                        sheet = client.open(SHEET_NAME).worksheet("시트1")
                        
                        rep_name = valid_users[0]['name']
                        rep_id = valid_users[0]['id']
                        others = [f"{p['name']}({p['id']})" for p in valid_users[1:]]
                        others_str = ", ".join(others) if len(others) > 0 else "없음"
                        
                        s_str = start_time.strftime("%H:%M")
                        e_str = end_time.strftime("%H:%M")
                        
                        sheet.append_row([date_str, s_str, e_str, rep_name, rep_id, others_str])
                        st.cache_data.clear()
                        
                        st.balloons()
                        st.markdown(f"""
                        <div class="success-box">
                            <h3>✅ 대관 신청 완료!</h3>
                            <p>{date_str} {s_str}~{e_str}<br>대표자: {rep_name}</p>
                        </div>
                        """, unsafe_allow_html=True)
                        st.rerun()
                    else:
                        st.error("서버 연결 오류")
                    
            except Exception as e: st.error(f"오류: {e}")

# =========================================================
#  TAB 2: 정기 대관
# =========================================================
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
        with tc1: rs = st.time_input("시작시간", time(18,0))
        with tc2: re = st.time_input("종료시간", time(21,0))
        purp = st.text_area("사용목적", height=80)
        
        if st.form_submit_button("신청서 제출"):
            if not tn or not days: st.error("필수 정보를 입력하세요.")
            else:
                try:
                    client = get_client()
                    if client:
                        sr = client.open(SHEET_NAME).worksheet("정기대관_신청")
                        now_s = datetime.now().strftime("%Y-%m-%d")
                        p_str = f"{sd} ~ {ed}"
                        d_str = ", ".join(days)
                        t_str = f"{rs.strftime('%H:%M')} ~ {re.strftime('%H:%M')}"
                        sr.append_row([now_s, tn, ln, ct, p_str, d_str, t_str, purp])
                        
                        st.cache_data.clear()
                        st.success("✅ 신청 접수 완료!")
                        st.rerun()
                    else: st.error("서버 연결 오류")
                except: st.error("오류 발생")