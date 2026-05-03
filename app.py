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

    .notice-box {
        background-color: #fff3cd;
        color: #856404 !important;
        padding: 15px;
        border-radius: 5px;
        font-size: 13px;
        margin-bottom: 15px;
        line-height: 1.6;
    }

    .regular-list-box {
        background-color: #f8f9fa;
        color: #212529 !important;
        padding: 15px;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        font-size: 14px;
        margin-bottom: 18px;
        line-height: 1.6;
    }

    .regular-list-title {
        font-weight: bold;
        font-size: 15px;
        margin-bottom: 8px;
        color: #0d6efd !important;
    }

    .regular-list-item {
        padding: 7px 0;
        border-bottom: 1px solid #e9ecef;
    }

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
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    try:
        if "gcp_service_account" in st.secrets:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)

        client = gspread.authorize(creds)
        return client

    except Exception:
        return None

# --- 4. 데이터 캐싱 ---
@st.cache_data(ttl=15)
def load_data():
    client = get_client()

    if not client:
        return None, None

    try:
        sheet = client.open(SHEET_NAME)

        try:
            ws1 = sheet.worksheet("시트1")
            data1 = ws1.get_all_records()
        except:
            data1 = []

        try:
            ws2 = sheet.worksheet("정기대관_신청")
            data2 = ws2.get_all_values()
        except:
            data2 = []

        return data1, data2

    except:
        return None, None

# --- 5. 헬퍼 함수 ---
def to_min(v):
    try:
        if isinstance(v, int):
            return v * 60

        if isinstance(v, str):
            v = v.strip()

            if ':' in v:
                h, m = map(int, v.split(':')[0:2])
                return h * 60 + m

            if v.isdigit():
                return int(v) * 60

    except:
        pass

    return 0


def get_day_korean(date_obj):
    return ["월", "화", "수", "목", "금", "토", "일"][date_obj.weekday()]


def mask_name(name):
    name = str(name).strip()

    if len(name) > 1:
        return name[0] + "**"

    return name


def parse_date_safe(date_str):
    try:
        return datetime.strptime(
            str(date_str).replace(".", "-").replace("/", "-").strip(),
            "%Y-%m-%d"
        ).date()
    except:
        return None


def parse_regular_row(row):
    """
    정기대관_신청 시트 형식:
    A 신청일시
    B 날짜
    C 시작시간
    D 종료시간
    E 대표자 이름
    F 학번
    G 이용 목적
    """
    try:
        if len(row) < 7:
            return None

        reg_date = parse_date_safe(row[1])

        if not reg_date:
            return None

        return {
            "date": reg_date,
            "start": str(row[2]).strip(),
            "end": str(row[3]).strip(),
            "name": str(row[4]).strip(),
            "student_id": str(row[5]).strip(),
            "purpose": str(row[6]).strip()
        }

    except:
        return None


def get_regular_records_in_period(records_reg, start_date, end_date):
    result = []

    if not records_reg or len(records_reg) <= 1:
        return result

    for row in records_reg[1:]:
        item = parse_regular_row(row)

        if not item:
            continue

        if start_date <= item["date"] <= end_date:
            result.append(item)

    result.sort(key=lambda x: (x["date"], to_min(x["start"])))

    return result


# --- 6. 정기대관 지난 월 내역 자동 삭제 ---
def clear_old_regular_records():
    cli = get_client()

    if not cli:
        return

    try:
        ws = cli.open(SHEET_NAME).worksheet("정기대관_신청")
        values = ws.get_all_values()

        if len(values) <= 1:
            return

        today = datetime.today().date()
        current_year = today.year
        current_month = today.month

        rows_to_delete = []

        for idx, row in enumerate(values[1:], start=2):
            item = parse_regular_row(row)

            if not item:
                continue

            reg_date = item["date"]

            if reg_date.year != current_year or reg_date.month != current_month:
                rows_to_delete.append(idx)

        for row_idx in reversed(rows_to_delete):
            ws.delete_rows(row_idx)

        if rows_to_delete:
            st.cache_data.clear()

    except:
        pass

# --- 7. 현황판 ---
def show_status(records_normal, records_reg):
    st.markdown("#### 📅 세미나실 대관현황")

    status_html = "<div class='status-box'>"
    status_html += "<div class='status-header'>▪️ 일반대관 (24시간 기준)</div>"

    if records_normal is not None:
        today = datetime.now().date()
        future = []

        for row in records_normal:
            try:
                r_d = datetime.strptime(
                    str(row.get('날짜', '')).replace('.', '-').replace('/', '-').strip(),
                    "%Y-%m-%d"
                ).date()

                if r_d >= today:
                    name = str(row.get('대표자명', ''))
                    start = str(row.get('시작시간', ''))
                    end = str(row.get('종료시간', ''))
                    disp = mask_name(name) if name else "예약자"

                    s_min = to_min(start)
                    e_min = to_min(end)

                    if e_min < s_min:
                        end_dt = datetime.combine(
                            r_d + timedelta(days=1),
                            dt_time(hour=e_min // 60, minute=e_min % 60)
                        )
                        overnight = " (+1)"
                    else:
                        end_dt = datetime.combine(
                            r_d,
                            dt_time(hour=e_min // 60, minute=e_min % 60)
                        )
                        overnight = ""

                    if end_dt > datetime.now():
                        item = f"<b>{disp}</b> / {r_d.strftime('%m/%d')}({get_day_korean(r_d)}) / {start} - {end}{overnight}"
                        future.append({"key": (r_d, s_min), "s": item})

            except:
                continue

        future.sort(key=lambda x: x['key'])

        if not future:
            status_html += "<div class='status-item' style='color:#999;'>예정된 예약이 없습니다.</div>"
        else:
            for item in future[:15]:
                status_html += f"<div class='status-item'>{item['s']}</div>"

    else:
        status_html += "<div class='status-item' style='color:red;'>서버 연결 실패</div>"

    status_html += "<br><div class='status-header'>▪️ 정기대관 신청 내역 (이번 달)</div>"

    today = datetime.today().date()
    month_start = today.replace(day=1)

    if today.month == 12:
        next_month_start = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month_start = today.replace(month=today.month + 1, day=1)

    month_end = next_month_start - timedelta(days=1)

    regular_items = get_regular_records_in_period(records_reg, month_start, month_end)

    if not regular_items:
        status_html += "<div class='status-item' style='color:#999;'>이번 달 정기대관 신청 내역이 없습니다.</div>"
    else:
        for item in regular_items[:15]:
            disp = mask_name(item["name"]) if item["name"] else "신청자"
            status_html += (
                f"<div class='status-item'>"
                f"<b>{disp}</b> / "
                f"{item['date'].strftime('%m/%d')}({get_day_korean(item['date'])}) / "
                f"{item['start']} - {item['end']} / "
                f"{item['purpose']}"
                f"</div>"
            )

    status_html += "</div>"

    st.markdown(status_html, unsafe_allow_html=True)


def show_regular_records_box(records_reg, start_date, end_date):
    regular_items = get_regular_records_in_period(records_reg, start_date, end_date)

    html = "<div class='regular-list-box'>"
    html += f"<div class='regular-list-title'>📌 현재 신청된 정기대관 내역</div>"
    html += f"<div style='font-size:13px; margin-bottom:8px;'>조회 기간: {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')}</div>"

    if not regular_items:
        html += "<div style='color:#999;'>해당 기간에 등록된 정기대관 신청 내역이 없습니다.</div>"
    else:
        for item in regular_items:
            html += (
                f"<div class='regular-list-item'>"
                f"<b>{item['date'].strftime('%m/%d')}({get_day_korean(item['date'])})</b> / "
                f"{item['start']} - {item['end']} / "
                f"{mask_name(item['name'])} / "
                f"{item['purpose']}"
                f"</div>"
            )

    html += "</div>"

    st.markdown(html, unsafe_allow_html=True)

# --- 8. 정기대관 월 초기화 실행 ---
clear_old_regular_records()

# --- 9. 메인 UI 및 로직 ---
st.title("공공인재학부 세미나실 대관시스템")

with st.expander("📢 이용수칙 및 안내 (필독)", expanded=False):
    st.markdown("""
    <div class="notice-box">
        <b>📁 대관 안내</b><br>
        - 일반대관: 최대 3주 뒤까지 신청 가능 (1일 3시간)<br>
        - 정기대관: 현재 월 안에서 신청 가능<br><br>
        <b>📁 이용 수칙</b><br>
        - 1인 대관 불가 / 선착순 마감 / 타 학과생 불가
    </div>
    """, unsafe_allow_html=True)

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

# --- TAB 1: 일반 예약 ---
with tab1:
    if 'attendees' not in st.session_state:
        st.session_state.attendees = [
            {"name": "", "id": ""},
            {"name": "", "id": ""}
        ]

    def add_attendee():
        st.session_state.attendees.append({"name": "", "id": ""})

    def remove_last():
        if len(st.session_state.attendees) > 1:
            st.session_state.attendees.pop()

    c1, c2 = st.columns(2)

    with c1:
        today = datetime.today()
        date = st.date_input(
            "날짜",
            min_value=today,
            max_value=today + timedelta(weeks=3)
        )
        date_str = date.strftime("%Y-%m-%d")

    with c2:
        st.write("")

    t1, t2 = st.columns(2)

    with t1:
        start_time = st.time_input(
            "시작",
            value=dt_time(14, 0),
            step=600
        )

    with t2:
        end_time = st.time_input(
            "종료",
            value=dt_time(16, 0),
            step=600
        )

    st.caption("예약자 명단 (첫 번째가 대표자)")

    for i, p in enumerate(st.session_state.attendees):
        ic1, ic2 = st.columns([6, 4])

        with ic1:
            st.session_state.attendees[i]["name"] = st.text_input(
                f"이름{i}",
                value=p["name"],
                placeholder="이름",
                key=f"n{i}",
                label_visibility="collapsed"
            )

        with ic2:
            st.session_state.attendees[i]["id"] = st.text_input(
                f"학번{i}",
                value=p["id"],
                placeholder="학번",
                key=f"i{i}",
                label_visibility="collapsed"
            )

    bc1, bc2 = st.columns(2)

    with bc1:
        st.button("➕ 인원 추가", on_click=add_attendee)

    with bc2:
        if len(st.session_state.attendees) > 1:
            st.button("➖ 삭제", on_click=remove_last)

    st.write("---")

    if st.button("📅 예약 신청하기", type="primary"):
        s_min = to_min(f"{start_time.hour}:{start_time.minute}")
        e_min = to_min(f"{end_time.hour}:{end_time.minute}")

        if e_min < s_min:
            dur = (24 * 60 - s_min) + e_min
        else:
            dur = e_min - s_min

        valid_users = [
            p for p in st.session_state.attendees
            if p['name'] and p['id']
        ]

        if len(valid_users) < 2:
            st.error("❌ 최소 2인 이상 입력해야 합니다. (1인 대관 불가)")

        elif dur > 180:
            st.error("❌ 하루 최대 3시간까지만 가능합니다.")

        elif dur < 10:
            st.error("❌ 최소 10분 이상 신청해주세요.")

        else:
            cli = get_client()

            if not cli:
                st.error("❌ 서버 연결 실패")

            else:
                try:
                    rep_name = valid_users[0]['name'].strip()
                    rep_id = valid_users[0]['id'].strip()

                    block_msg = ""

                    if records_normal:
                        for applicant in valid_users:
                            app_name = applicant['name'].strip()
                            app_id = applicant['id'].strip()
                            my_usage_min = 0

                            for row in records_normal:
                                if str(row.get('날짜', '')).replace('.', '-').strip() == date_str:
                                    es = to_min(row.get('시작시간'))
                                    ee = to_min(row.get('종료시간'))

                                    if ee < es:
                                        usage = (24 * 60 - es) + ee
                                    else:
                                        usage = ee - es

                                    is_included = False

                                    r_n = str(row.get('대표자명', '')).strip()
                                    r_i = str(row.get('대표학번', '')).strip()

                                    if r_n == app_name and r_i == app_id:
                                        is_included = True

                                    else:
                                        others = str(row.get('동반인원', ''))
                                        target_str = f"{app_name}({app_id})"

                                        if others and others != "없음" and target_str in others:
                                            is_included = True

                                    if is_included:
                                        my_usage_min += usage

                            if my_usage_min + dur > 180:
                                block_msg = (
                                    f"❌ '{app_name}'님은 금일 이용 한도(3시간)를 초과하게 됩니다.\n"
                                    f"(이미 {my_usage_min}분 사용 + 신청 {dur}분)"
                                )
                                break

                    if block_msg:
                        st.error(block_msg)
                        st.stop()

                    overlap = False

                    req_start_dt = datetime.combine(date, start_time)
                    req_end_dt = datetime.combine(
                        date + timedelta(days=1 if e_min < s_min else 0),
                        end_time
                    )

                    if records_normal:
                        for row in records_normal:
                            try:
                                r_d = datetime.strptime(
                                    str(row.get('날짜', '')).replace('.', '-').strip(),
                                    "%Y-%m-%d"
                                ).date()

                                es = to_min(row.get('시작시간'))
                                ee = to_min(row.get('종료시간'))

                                exist_start_dt = datetime.combine(
                                    r_d,
                                    dt_time(hour=es // 60, minute=es % 60)
                                )

                                exist_end_dt = datetime.combine(
                                    r_d + timedelta(days=1 if ee < es else 0),
                                    dt_time(hour=ee // 60, minute=ee % 60)
                                )

                                if (req_start_dt < exist_end_dt) and (req_end_dt > exist_start_dt):
                                    overlap = True
                                    break

                            except:
                                continue

                    if not overlap and records_reg:
                        for rr in records_reg[1:]:
                            item = parse_regular_row(rr)

                            if not item:
                                continue

                            if item["date"] != date:
                                continue

                            reg_s = to_min(item["start"])
                            reg_e = to_min(item["end"])

                            reg_start_dt = datetime.combine(
                                date,
                                dt_time(hour=reg_s // 60, minute=reg_s % 60)
                            )

                            reg_end_dt = datetime.combine(
                                date + timedelta(days=1 if reg_e < reg_s else 0),
                                dt_time(hour=reg_e // 60, minute=reg_e % 60)
                            )

                            if (req_start_dt < reg_end_dt) and (req_end_dt > reg_start_dt):
                                overlap = True
                                break

                    if overlap:
                        st.error("❌ 예약 불가: 이미 예약된 시간입니다.")

                    else:
                        sht = cli.open(SHEET_NAME).worksheet("시트1")

                        others = ", ".join([
                            f"{p['name']}({p['id']})"
                            for p in valid_users[1:]
                        ])

                        s_str = start_time.strftime("%H:%M")
                        e_str = end_time.strftime("%H:%M")

                        sht.append_row([
                            date_str,
                            s_str,
                            e_str,
                            rep_name,
                            rep_id,
                            others
                        ])

                        st.cache_data.clear()
                        st.session_state['success_msg'] = True
                        st.rerun()

                except Exception as e:
                    st.error(f"오류: {e}")

# --- TAB 2: 정기 대관 ---
with tab2:
    today = datetime.today().date()
    month_start = today.replace(day=1)

    if today.month == 12:
        next_month_start = today.replace(
            year=today.year + 1,
            month=1,
            day=1
        )
    else:
        next_month_start = today.replace(
            month=today.month + 1,
            day=1
        )

    month_end = next_month_start - timedelta(days=1)

    st.markdown("""
    <div class="notice-box">
        <b>📢 정기대관 신청 안내</b><br><br>
        정기대관은 날짜, 시작시간, 종료시간, 이용 목적, 대표자 이름, 학번을 입력해주시면
        검토 후 대관 등록 예정입니다.<br><br>
        정기대관 내역은 매달 말 초기화될 예정이오니, 계속 이용을 원하시는 경우
        매월 초 다시 신청해주시면 감사하겠습니다.
    </div>
    """, unsafe_allow_html=True)

    st.caption(
        f"선택 가능 기간: {month_start.strftime('%Y-%m-%d')} ~ {month_end.strftime('%Y-%m-%d')}"
    )

    show_regular_records_box(records_reg, month_start, month_end)

    with st.form("reg_info_form"):
        reg_date = st.date_input(
            "날짜",
            value=today,
            min_value=month_start,
            max_value=month_end,
            help="현재 속해있는 월의 월초부터 월말까지만 선택 가능합니다.",
            key="reg_date"
        )

        rt1, rt2 = st.columns(2)

        with rt1:
            reg_start_time = st.time_input(
                "시작시간",
                value=dt_time(18, 0),
                step=600,
                key="reg_start_time"
            )

        with rt2:
            reg_end_time = st.time_input(
                "종료시간",
                value=dt_time(21, 0),
                step=600,
                key="reg_end_time"
            )

        reg_purpose = st.text_area(
            "이용 목적",
            height=80,
            placeholder="예: 스터디, 회의 등",
            key="reg_purpose"
        )

        rn1, rn2 = st.columns(2)

        with rn1:
            reg_rep_name = st.text_input(
                "대표자 이름",
                placeholder="대표자 이름",
                key="reg_rep_name"
            )

        with rn2:
            reg_rep_id = st.text_input(
                "학번",
                placeholder="학번",
                key="reg_rep_id"
            )

        reg_submitted = st.form_submit_button(
            "정기대관 신청하기",
            type="primary"
        )

    if reg_submitted:
        reg_s_min = reg_start_time.hour * 60 + reg_start_time.minute
        reg_e_min = reg_end_time.hour * 60 + reg_end_time.minute

        if reg_e_min < reg_s_min:
            reg_duration = (24 * 60 - reg_s_min) + reg_e_min
        else:
            reg_duration = reg_e_min - reg_s_min

        if not reg_rep_name.strip() or not reg_rep_id.strip() or not reg_purpose.strip():
            st.error("❌ 날짜, 시작시간, 종료시간, 이용 목적, 대표자 이름, 학번을 모두 입력해주세요.")

        elif reg_duration > 180:
            st.error("❌ 1인당 이용 시간은 최대 3시간을 넘길 수 없습니다.")

        elif reg_duration < 10:
            st.error("❌ 최소 10분 이상 신청해주세요.")

        else:
            try:
                cli = get_client()

                if not cli:
                    st.error("❌ 서버 연결 실패")

                else:
                    ws = cli.open(SHEET_NAME).worksheet("정기대관_신청")

                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    date_str = reg_date.strftime("%Y-%m-%d")
                    start_str = reg_start_time.strftime("%H:%M")
                    end_str = reg_end_time.strftime("%H:%M")
                    rep_name = reg_rep_name.strip()
                    rep_id = reg_rep_id.strip()
                    purpose = reg_purpose.strip()

                    existing_rows = ws.get_all_values()
                    total_minutes = 0

                    if len(existing_rows) > 1:
                        for row in existing_rows[1:]:
                            item = parse_regular_row(row)

                            if not item:
                                continue

                            if (
                                item["date"] == reg_date
                                and item["name"] == rep_name
                                and item["student_id"] == rep_id
                            ):
                                rs = to_min(item["start"])
                                re = to_min(item["end"])

                                if re < rs:
                                    total_minutes += (24 * 60 - rs) + re
                                else:
                                    total_minutes += re - rs

                    if records_normal:
                        for row in records_normal:
                            try:
                                row_date = str(row.get('날짜', '')).replace('.', '-').replace('/', '-').strip()

                                if row_date != date_str:
                                    continue

                                es = to_min(row.get('시작시간'))
                                ee = to_min(row.get('종료시간'))

                                if ee < es:
                                    usage = (24 * 60 - es) + ee
                                else:
                                    usage = ee - es

                                is_included = False

                                normal_rep_name = str(row.get('대표자명', '')).strip()
                                normal_rep_id = str(row.get('대표학번', '')).strip()

                                if normal_rep_name == rep_name and normal_rep_id == rep_id:
                                    is_included = True

                                else:
                                    others = str(row.get('동반인원', ''))
                                    target_str = f"{rep_name}({rep_id})"

                                    if others and others != "없음" and target_str in others:
                                        is_included = True

                                if is_included:
                                    total_minutes += usage

                            except:
                                continue

                    if total_minutes + reg_duration > 180:
                        st.error(
                            f"❌ '{rep_name}'님은 해당 날짜 이용 한도 3시간을 초과합니다. "
                            f"(기존 {total_minutes}분 + 신청 {reg_duration}분)"
                        )

                    else:
                        overlap = False

                        req_start_dt = datetime.combine(reg_date, reg_start_time)
                        req_end_dt = datetime.combine(
                            reg_date + timedelta(days=1 if reg_e_min < reg_s_min else 0),
                            reg_end_time
                        )

                        if records_normal:
                            for row in records_normal:
                                try:
                                    r_d = datetime.strptime(
                                        str(row.get('날짜', '')).replace('.', '-').replace('/', '-').strip(),
                                        "%Y-%m-%d"
                                    ).date()

                                    if r_d != reg_date:
                                        continue

                                    es = to_min(row.get('시작시간'))
                                    ee = to_min(row.get('종료시간'))

                                    exist_start_dt = datetime.combine(
                                        r_d,
                                        dt_time(hour=es // 60, minute=es % 60)
                                    )

                                    exist_end_dt = datetime.combine(
                                        r_d + timedelta(days=1 if ee < es else 0),
                                        dt_time(hour=ee // 60, minute=ee % 60)
                                    )

                                    if (req_start_dt < exist_end_dt) and (req_end_dt > exist_start_dt):
                                        overlap = True
                                        break

                                except:
                                    continue

                        if not overlap and len(existing_rows) > 1:
                            for row in existing_rows[1:]:
                                item = parse_regular_row(row)

                                if not item:
                                    continue

                                if item["date"] != reg_date:
                                    continue

                                rs = to_min(item["start"])
                                re = to_min(item["end"])

                                exist_start_dt = datetime.combine(
                                    reg_date,
                                    dt_time(hour=rs // 60, minute=rs % 60)
                                )

                                exist_end_dt = datetime.combine(
                                    reg_date + timedelta(days=1 if re < rs else 0),
                                    dt_time(hour=re // 60, minute=re % 60)
                                )

                                if (req_start_dt < exist_end_dt) and (req_end_dt > exist_start_dt):
                                    overlap = True
                                    break

                        if overlap:
                            st.error("❌ 신청 불가: 이미 예약 또는 신청된 시간입니다.")

                        else:
                            ws.append_row([
                                now,
                                date_str,
                                start_str,
                                end_str,
                                rep_name,
                                rep_id,
                                purpose
                            ])

                            st.cache_data.clear()
                            st.success("✅ 정기대관 신청이 완료되었습니다. 검토 후 대관 등록 예정입니다.")
                            st.rerun()

            except Exception as e:
                st.error(f"오류: {e}")
