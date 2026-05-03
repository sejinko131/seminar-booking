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
    
    /* 리스트형 현황판 스타일 복구 */
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
def mask_name(name): return (str(name).strip()[0] + "**") if len(str(name).strip()) > 1 else str(name)

# --- 6. 현황판 (리스트 형태 복구 + 스마트 숨김) ---
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
                    
                    s_min = to_min(start)
                    e_min = to_min(end)
                    
                    # 철야 표시
                    if e_min < s_min:
                        end_dt = datetime.combine(r_d + timedelta(days=1), dt_time(hour=e_min//60, minute=e_min%60))
                        overnight = " (+1)"
                    else:
                        end_dt = datetime.combine(r_d, dt_time(hour=e_min//60, minute=e_min%60))
                        overnight = ""
                    
                    # 현재 시간보다 종료 시간이 미래인 것만 표시 (지난 예약 숨김)
                    if end_dt > datetime.now():
                        item = f"<b>{disp}</b> / {r_d.strftime('%m/%d')}({get_day_korean(r_d)}) / {start} - {end}{overnight}"
                        future.append({"key": (r_d, s_min), "s": item})
            except: continue
            
        # 날짜 -> 시간 순 정렬
        future.sort(key=lambda x: x['key'])
        
        if not future:
            status_html += "<div class='status-item' style='color:#999;'>예정된 예약이 없습니다.</div>"
        else:
            for item in future[:15]: # 최대 15개까지만 표시
                status_html += f"<div class='status-item'>{item['s']}</div>"
    else:
        status_html += "<div class='status-item' style='color:red;'>서버 연결 실패</div>"
    
    status_html += "<br><div class='status-header'>▪️ 정기대관 (학기 중)</div>"
    has_reg = False
    if records_reg and len(records_reg) > 1:
        for row in records_reg[1:]:
            if len(row) > 6:
                # 정기대관 정보 표시
                status_html += f"<div class='status-item'><b>{row[1]}</b> / 매주 {row[5]} / {row[6]}</div>"
                has_reg = True
    if not has_reg:
        status_html += "<div class='status-item' style='color:#999;'>승인된 정기 대관이 없습니다.</div>"
    
    status_html += "</div>"
    st.markdown(status_html, unsafe_allow_html=True)

# --- 7. 메인 UI 및 로직 ---
st.title("공공인재학부 세미나실 대관시스템")
with st.expander("📢 이용수칙 및 안내 (필독)", expanded=False):
    st.markdown("""<div class="notice-box"><b>📁 대관 안내</b><br>- 일반대관: 최대 3주 뒤까지 신청 가능 (1일 3시간)<br>- 정기대관: 매월 1일 신청 (스터디 목적)<br><br><b>📁 이용 수칙</b><br>- 1인 대관 불가 / 선착순 마감 / 타 학과생 불가</div>""", unsafe_allow_html=True)

records_normal, records_reg = load_data()
show_status(records_normal, records_reg)

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
        
        if e_min < s_min: dur = (24 * 60 - s_min) + e_min
        else: dur = e_min - s_min
            
        valid_users = [p for p in st.session_state.attendees if p['name'] and p['id']]
        
        # 1. 기본 유효성 검사 (최소 2인)
        if len(valid_users) < 2: st.error("❌ 최소 2인 이상 입력해야 합니다. (1인 대관 불가)")
        elif dur > 180: st.error("❌ 하루 최대 3시간까지만 가능합니다.")
        elif dur < 10: st.error("❌ 최소 10분")
        else:
            cli = get_client()
            if not cli: st.error("❌ 서버 연결 실패")
            else:
                try:
                    rep_name = valid_users[0]['name'].strip()
                    rep_id = valid_users[0]['id'].strip()
                    
                    # 2. 1일 총량제 검사 (구성원 전수 조사)
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
                                    
                                    if ee < es: usage = (24*60 - es) + ee
                                    else: usage = ee - es
                                    
                                    # 포함 확인
                                    is_included = False
                                    r_n = str(row.get('대표자명','')).strip()
                                    r_i = str(row.get('대표학번','')).strip()
                                    
                                    if r_n == app_name and r_i == app_id:
                                        is_included = True
                                    else:
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

                    # 3. 중복 시간 검사 (철야 포함)
                    overlap=False
                    req_start_dt = datetime.combine(date, start_time)
                    req_end_dt = datetime.combine(date + timedelta(days=1 if e_min < s_min else 0), end_time)

                    if records_normal:
                        for row in records_normal:
                            try:
                                r_d = datetime.strptime(str(row.get('날짜','')).replace('.','-').strip(), "%Y-%m-%d").date()
                                es = to_min(row.get('시작시간'))
                                ee = to_min(row.get('종료시간'))
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
                        sht.append_row([date_str, s_str, e_str, rep_name, rep_id, others])
                        st.cache_data.clear()
                        st.session_state['success_msg'] = True
                        st.rerun()
                except Exception as e: st.error(f"오류: {e}")

# TAB 2: 정기 대관
with tab2:
    today = datetime.today().date()
    month_start = today.replace(day=1)

    if today.month == 12:
        next_month_start = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month_start = today.replace(month=today.month + 1, day=1)

    month_end = next_month_start - timedelta(days=1)

    def parse_date_local(v):
        try:
            return datetime.strptime(
                str(v).replace(".", "-").replace("/", "-").strip(),
                "%Y-%m-%d"
            ).date()
        except:
            return None

    def time_overlap(s1, e1, s2, e2):
        return s1 < e2 and e1 > s2

    def make_dt_range(base_date, start_min, end_min):
        start_dt = datetime.combine(
            base_date,
            dt_time(hour=start_min // 60, minute=start_min % 60)
        )

        end_date = base_date + timedelta(days=1 if end_min < start_min else 0)

        end_dt = datetime.combine(
            end_date,
            dt_time(hour=end_min // 60, minute=end_min % 60)
        )

        return start_dt, end_dt

    def get_dates_by_days(start_date, end_date, selected_days):
        result = []
        cur = start_date

        while cur <= end_date:
            if get_day_korean(cur) in selected_days:
                result.append(cur)
            cur += timedelta(days=1)

        return result

    def parse_period(period_text):
        try:
            if "~" not in str(period_text):
                return None, None

            ps, pe = str(period_text).split("~")
            ps = parse_date_local(ps.strip())
            pe = parse_date_local(pe.strip())

            return ps, pe
        except:
            return None, None

    def parse_time_range(time_text):
        try:
            if "~" not in str(time_text):
                return None, None

            ts, te = str(time_text).split("~")
            return to_min(ts.strip()), to_min(te.strip())
        except:
            return None, None

    st.markdown("""
    <div class="notice-box">
        <b>📢 정기대관 신청 안내</b><br><br>
        정기대관은 이번 달 안에서 신청 가능하며, 요일은 매주 반복되는 형태로 등록됩니다.<br>
        이름, 학번, 요일, 시작시간, 종료시간, 신청목적을 입력해주시면 검토 후 대관 등록 예정입니다.<br><br>
        매달 말 초기화될 예정이오니, 계속 이용을 원하시는 경우,
        매월 초 다시 신청해주시면 감사하겠습니다.
    </div>
    """, unsafe_allow_html=True)

    st.caption(f"신청 가능 기간: {month_start.strftime('%Y-%m-%d')} ~ {month_end.strftime('%Y-%m-%d')}")

    # 현재 시트에 등록된 정기대관 표시
    st.markdown("#### 📌 현재 등록된 정기대관")

    existing_reg_html = "<div class='status-box'>"
    has_existing_reg = False

    if records_reg and len(records_reg) > 1:
        for row in records_reg[1:]:
            try:
                if len(row) > 6 and "~" in row[4]:
                    ps, pe = parse_period(row[4])

                    if not ps or not pe:
                        continue

                    # 이번 달 기간과 겹치는 정기대관만 표시
                    if ps <= month_end and pe >= month_start:
                        name = str(row[1]).strip()
                        days_text = str(row[5]).strip()
                        time_text = str(row[6]).strip()
                        purpose = str(row[7]).strip() if len(row) > 7 else ""

                        existing_reg_html += (
                            f"<div class='status-item'>"
                            f"<b>{name}</b> / 매주 {days_text} / {time_text}"
                            f"{' / ' + purpose if purpose else ''}"
                            f"</div>"
                        )
                        has_existing_reg = True
            except:
                continue

    if not has_existing_reg:
        existing_reg_html += "<div class='status-item' style='color:#999;'>현재 등록된 정기대관이 없습니다.</div>"

    existing_reg_html += "</div>"
    st.markdown(existing_reg_html, unsafe_allow_html=True)

    with st.form("regular_form"):
        reg_name = st.text_input("이름 또는 단체명", placeholder="예: 홍길동 / 공공인재학부 스터디")
        reg_student_id = st.text_input("학번", placeholder="예: 20240000")

        reg_days = st.multiselect(
            "요일 선택",
            ["월", "화", "수", "목", "금", "토", "일"],
            placeholder="매주 반복될 요일을 선택하세요"
        )

        rt1, rt2 = st.columns(2)

        with rt1:
            reg_start_time = st.time_input(
                "시작시간",
                value=dt_time(18, 0),
                step=600
            )

        with rt2:
            reg_end_time = st.time_input(
                "종료시간",
                value=dt_time(21, 0),
                step=600
            )

        reg_purpose = st.text_area(
            "신청목적",
            height=80,
            placeholder="예: 스터디, 회의 등"
        )

        submitted = st.form_submit_button("정기대관 신청하기", type="primary")

    if submitted:
        reg_s_min = reg_start_time.hour * 60 + reg_start_time.minute
        reg_e_min = reg_end_time.hour * 60 + reg_end_time.minute

        if reg_e_min < reg_s_min:
            reg_duration = (24 * 60 - reg_s_min) + reg_e_min
        else:
            reg_duration = reg_e_min - reg_s_min

        if not reg_name.strip():
            st.error("❌ 이름 또는 단체명을 입력해주세요.")

        elif not reg_student_id.strip():
            st.error("❌ 학번을 입력해주세요.")

        elif not reg_days:
            st.error("❌ 요일을 1개 이상 선택해주세요.")

        elif not reg_purpose.strip():
            st.error("❌ 신청목적을 입력해주세요.")

        elif reg_duration > 180:
            st.error("❌ 1회 이용 시간은 최대 3시간을 넘길 수 없습니다.")

        elif reg_duration < 10:
            st.error("❌ 최소 10분 이상 신청해주세요.")

        else:
            selected_dates = get_dates_by_days(month_start, month_end, reg_days)

            if not selected_dates:
                st.error("❌ 선택한 요일에 해당하는 날짜가 이번 달에 없습니다.")
                st.stop()

            overlap = False
            overlap_msg = ""

            # 1. 일반대관과 정기대관 신청이 겹치는지 확인
            if records_normal:
                for target_date in selected_dates:
                    req_start_dt, req_end_dt = make_dt_range(
                        target_date,
                        reg_s_min,
                        reg_e_min
                    )

                    for row in records_normal:
                        try:
                            normal_date = parse_date_local(row.get("날짜", ""))

                            if not normal_date:
                                continue

                            ns = to_min(row.get("시작시간"))
                            ne = to_min(row.get("종료시간"))

                            normal_start_dt, normal_end_dt = make_dt_range(
                                normal_date,
                                ns,
                                ne
                            )

                            if time_overlap(req_start_dt, req_end_dt, normal_start_dt, normal_end_dt):
                                overlap = True
                                overlap_msg = (
                                    f"❌ 신청 불가: {target_date.strftime('%m/%d')}({get_day_korean(target_date)}) "
                                    f"{reg_start_time.strftime('%H:%M')}~{reg_end_time.strftime('%H:%M')} 시간이 "
                                    f"이미 일반대관과 겹칩니다."
                                )
                                break

                        except:
                            continue

                    if overlap:
                        break

            # 2. 기존 정기대관과 새 정기대관 신청이 겹치는지 확인
            if not overlap and records_reg and len(records_reg) > 1:
                for row in records_reg[1:]:
                    try:
                        if len(row) <= 6:
                            continue

                        old_period = str(row[4]).strip()
                        old_days_text = str(row[5]).strip()
                        old_time_text = str(row[6]).strip()

                        old_start_date, old_end_date = parse_period(old_period)
                        old_s_min, old_e_min = parse_time_range(old_time_text)

                        if not old_start_date or not old_end_date:
                            continue

                        if old_s_min is None or old_e_min is None:
                            continue

                        old_days = [
                            d.strip()
                            for d in old_days_text.replace("/", ",").split(",")
                            if d.strip()
                        ]

                        period_start = max(month_start, old_start_date)
                        period_end = min(month_end, old_end_date)

                        if period_start > period_end:
                            continue

                        old_dates = get_dates_by_days(period_start, period_end, old_days)

                        for target_date in selected_dates:
                            req_start_dt, req_end_dt = make_dt_range(
                                target_date,
                                reg_s_min,
                                reg_e_min
                            )

                            for old_date in old_dates:
                                old_start_dt, old_end_dt = make_dt_range(
                                    old_date,
                                    old_s_min,
                                    old_e_min
                                )

                                if time_overlap(req_start_dt, req_end_dt, old_start_dt, old_end_dt):
                                    overlap = True
                                    overlap_msg = (
                                        f"❌ 신청 불가: {target_date.strftime('%m/%d')}({get_day_korean(target_date)}) "
                                        f"{reg_start_time.strftime('%H:%M')}~{reg_end_time.strftime('%H:%M')} 시간이 "
                                        f"이미 정기대관과 겹칩니다."
                                    )
                                    break

                            if overlap:
                                break

                        if overlap:
                            break

                    except:
                        continue

            if overlap:
                st.error(overlap_msg)

            else:
                try:
                    cli = get_client()

                    if not cli:
                        st.error("❌ 서버 연결 실패")

                    else:
                        ws = cli.open(SHEET_NAME).worksheet("정기대관_신청")

                        now = datetime.now().strftime("%Y-%m-%d")
                        period_str = f"{month_start.strftime('%Y-%m-%d')} ~ {month_end.strftime('%Y-%m-%d')}"
                        days_str = ", ".join(reg_days)
                        time_str = f"{reg_start_time.strftime('%H:%M')} ~ {reg_end_time.strftime('%H:%M')}"

                        ws.append_row([
                            now,
                            reg_name.strip(),
                            reg_name.strip(),
                            reg_student_id.strip(),
                            period_str,
                            days_str,
                            time_str,
                            reg_purpose.strip()
                        ])

                        st.cache_data.clear()
                        st.success("✅ 정기대관 신청이 완료되었습니다. 검토 후 대관 등록 예정입니다.")
                        st.rerun()

                except Exception as e:
                    st.error(f"오류: {e}")
