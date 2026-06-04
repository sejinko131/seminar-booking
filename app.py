import streamlit as st
import streamlit.components.v1 as components
import gspread
import time
import calendar
from html import escape
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta, time as dt_time

# --- 1. 기본 설정 ---
JSON_FILE = "key.json"
SHEET_NAME = "세미나실_대관"
STATUS_REFRESH_SEC = 60  # 현황 전용 화면 자동 새로고침 주기

st.set_page_config(page_title="세미나실 대관시스템", page_icon="📅", layout="wide")

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

    .calendar-wrap {
        background: #ffffff;
        border: 1px solid #dddddd;
        border-radius: 14px;
        padding: 14px;
        margin-top: 10px;
        margin-bottom: 20px;
    }

    .calendar-title {
        text-align: center;
        font-weight: 800;
        font-size: 22px;
        margin-bottom: 12px;
        color: #222222;
    }

    .calendar-grid {
        display: grid;
        grid-template-columns: repeat(7, minmax(0, 1fr));
        gap: 6px;
    }

    .calendar-head {
        text-align: center;
        font-weight: 700;
        padding: 8px 0;
        border-radius: 8px;
        background: #f5f5f5;
        color: #444444;
        font-size: 13px;
    }

    .cal-cell {
        min-height: 112px;
        border: 1px solid #e5e5e5;
        border-radius: 10px;
        padding: 8px;
        background: #ffffff;
        overflow: hidden;
    }

    .cal-cell.muted {
        background: #fafafa;
        color: #aaaaaa;
    }

    .cal-cell.today {
        border: 2px solid #ff4b4b;
    }

    .cal-cell.selected {
        box-shadow: 0 0 0 3px rgba(255, 75, 75, 0.18) inset;
    }

    .cal-day-number {
        font-weight: 800;
        font-size: 14px;
        margin-bottom: 5px;
        color: #222222;
    }

    .cal-event {
        font-size: 11px;
        line-height: 1.25;
        padding: 4px 5px;
        margin-top: 4px;
        border-radius: 6px;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
    }

    .cal-event.normal {
        background: #e8f2ff;
        color: #174ea6;
        border: 1px solid #cfe2ff;
    }

    .cal-event.regular {
        background: #fff4e5;
        color: #9a5b00;
        border: 1px solid #ffe0ad;
    }

    .cal-more {
        font-size: 11px;
        color: #666666;
        margin-top: 4px;
    }

    .event-card {
        background: #ffffff;
        border: 1px solid #dddddd;
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 10px;
        color: #222222;
    }

    .event-kind {
        display: inline-block;
        font-size: 12px;
        font-weight: 700;
        padding: 3px 8px;
        border-radius: 999px;
        margin-right: 8px;
    }

    .event-kind.normal {
        background: #e8f2ff;
        color: #174ea6;
    }

    .event-kind.regular {
        background: #fff4e5;
        color: #9a5b00;
    }

    .legend-box {
        font-size: 13px;
        color: #444444;
        margin: 4px 0 12px 0;
    }

    @media (max-width: 720px) {
        .block-container { padding-top: 2rem; padding-left: 0.8rem; padding-right: 0.8rem; }
        .calendar-grid { gap: 3px; }
        .calendar-head { font-size: 11px; padding: 6px 0; }
        .cal-cell { min-height: 86px; padding: 5px; border-radius: 7px; }
        .cal-day-number { font-size: 12px; }
        .cal-event { font-size: 10px; padding: 3px 4px; }
        h1 { font-size: 1.45rem !important; }
    }

    </style>
    """, unsafe_allow_html=True)


# --- 2-1. URL/화면 헬퍼 ---
def get_query_value(key, default=""):
    """Streamlit 버전에 상관없이 URL 쿼리 파라미터 값을 안전하게 읽습니다."""
    try:
        value = st.query_params.get(key, default)
    except Exception:
        value = st.experimental_get_query_params().get(key, [default])

    if isinstance(value, list):
        return value[0] if value else default

    return value if value is not None else default

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

            if ":" in v:
                h, m = map(int, v.split(":")[0:2])
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


def parse_date_local(v):
    try:
        return datetime.strptime(
            str(v).replace(".", "-").replace("/", "-").strip(),
            "%Y-%m-%d"
        ).date()
    except:
        return None


def parse_period_local(period_text):
    try:
        if "~" not in str(period_text):
            return None, None

        ps, pe = str(period_text).split("~", 1)

        return parse_date_local(ps.strip()), parse_date_local(pe.strip())

    except:
        return None, None


def parse_time_range_local(time_text):
    try:
        if "~" not in str(time_text):
            return None, None

        ts, te = str(time_text).split("~", 1)

        return to_min(ts.strip()), to_min(te.strip())

    except:
        return None, None


def normalize_days_text(days_text):
    result = []

    raw = (
        str(days_text)
        .replace("매주", "")
        .replace("요일", "")
        .replace("/", ",")
        .replace("·", ",")
        .replace(" ", "")
        .split(",")
    )

    for d in raw:
        d = d.strip()

        if d in ["월", "화", "수", "목", "금", "토", "일"]:
            result.append(d)

    return result


def make_dt_range(base_date, start_min, end_min):
    start_dt = datetime.combine(
        base_date,
        dt_time(hour=start_min // 60, minute=start_min % 60)
    )

    end_dt = datetime.combine(
        base_date + timedelta(days=1 if end_min < start_min else 0),
        dt_time(hour=end_min // 60, minute=end_min % 60)
    )

    return start_dt, end_dt


def has_remaining_regular_occurrence(period_start, period_end, days, time_text):
    now = datetime.now()
    today = now.date()

    start_min, end_min = parse_time_range_local(time_text)

    if start_min is None or end_min is None:
        return False

    cur = max(today, period_start)

    while cur <= period_end:
        if get_day_korean(cur) in days:
            start_dt, end_dt = make_dt_range(cur, start_min, end_min)

            if end_dt > now:
                return True

        cur += timedelta(days=1)

    return False


def get_dates_by_days(start_date, end_date, selected_days):
    result = []
    cur = start_date

    while cur <= end_date:
        if get_day_korean(cur) in selected_days:
            result.append(cur)

        cur += timedelta(days=1)

    return result


def is_time_overlap(start1, end1, start2, end2):
    return start1 < end2 and end1 > start2

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
                r_d = parse_date_local(row.get("날짜", ""))

                if not r_d:
                    continue

                if r_d >= today:
                    name = str(row.get("대표자명", ""))
                    start = str(row.get("시작시간", ""))
                    end = str(row.get("종료시간", ""))
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
                        item = (
                            f"<b>{disp}</b> / "
                            f"{r_d.strftime('%m/%d')}({get_day_korean(r_d)}) / "
                            f"{start} - {end}{overnight}"
                        )
                        future.append({"key": (r_d, s_min), "s": item})

            except:
                continue

        future.sort(key=lambda x: x["key"])

        if not future:
            status_html += "<div class='status-item' style='color:#999;'>예정된 예약이 없습니다.</div>"
        else:
            for item in future[:15]:
                status_html += f"<div class='status-item'>{item['s']}</div>"

    else:
        status_html += "<div class='status-item' style='color:red;'>서버 연결 실패</div>"

    status_html += "<br><div class='status-header'>▪️ 정기대관</div>"

    has_reg = False

    if records_reg and len(records_reg) > 1:
        today = datetime.today().date()

        for row in records_reg[1:]:
            try:
                # 신청일 / 단체명 / 대표자 / 연락처 / 사용기간 / 요일 / 사용시간 / 사용목적
                if len(row) < 8:
                    continue

                group_name = str(row[1]).strip()
                period_text = str(row[4]).strip()
                days_text = str(row[5]).strip()
                time_text = str(row[6]).strip()

                period_start, period_end = parse_period_local(period_text)
                days = normalize_days_text(days_text)

                if not period_start or not period_end:
                    continue

                if not days:
                    continue

                # 사용기간이 끝난 정기대관은 메인화면에서 숨김
                if period_end < today:
                    continue

                # 오늘 이후 실제 사용 가능한 요일/시간이 남아있는 경우만 표시
                if not has_remaining_regular_occurrence(period_start, period_end, days, time_text):
                    continue

                status_html += (
                    f"<div class='status-item'>"
                    f"<b>{group_name}</b> / "
                    f"매주 {days_text} / "
                    f"{time_text}"
                    f"</div>"
                )
                has_reg = True

            except:
                continue

    if not has_reg:
        status_html += "<div class='status-item' style='color:#999;'>등록된 정기대관이 없습니다.</div>"

    status_html += "</div>"

    st.markdown(status_html, unsafe_allow_html=True)



# --- 6-1. 달력형 현황 화면 ---
def format_minute(minute_value):
    try:
        minute_value = int(minute_value)
        return f"{(minute_value // 60) % 24:02d}:{minute_value % 60:02d}"
    except Exception:
        return ""


def month_add(base_date, offset):
    year = base_date.year + (base_date.month - 1 + offset) // 12
    month = (base_date.month - 1 + offset) % 12 + 1
    return base_date.replace(year=year, month=month, day=1)


def build_month_options(center_date=None, months_before=1, months_after=4):
    if center_date is None:
        center_date = datetime.today().date().replace(day=1)

    options = []

    for offset in range(-months_before, months_after + 1):
        d = month_add(center_date, offset)
        options.append({
            "label": f"{d.year}년 {d.month:02d}월",
            "year": d.year,
            "month": d.month,
            "date": d
        })

    return options


def add_event(events_by_date, event_date, kind, title, time_text, sort_min, extra=""):
    events_by_date.setdefault(event_date, []).append({
        "kind": kind,
        "title": str(title).strip(),
        "time_text": str(time_text).strip(),
        "sort_min": sort_min,
        "extra": str(extra).strip()
    })


def collect_calendar_events(records_normal, records_reg, range_start, range_end):
    """일반대관과 정기대관을 날짜별 이벤트로 합칩니다."""
    events_by_date = {}

    # 일반대관: 시트1 컬럼 기준
    if records_normal:
        for row in records_normal:
            try:
                r_d = parse_date_local(row.get("날짜", ""))

                if not r_d or not (range_start <= r_d <= range_end):
                    continue

                start = str(row.get("시작시간", "")).strip()
                end = str(row.get("종료시간", "")).strip()
                name = str(row.get("대표자명", "")).strip()
                s_min = to_min(start)
                e_min = to_min(end)
                overnight = " (+1)" if e_min < s_min else ""
                display_name = mask_name(name) if name else "예약자"

                add_event(
                    events_by_date,
                    r_d,
                    "normal",
                    f"일반대관 · {display_name}",
                    f"{start} ~ {end}{overnight}",
                    s_min
                )

            except Exception:
                continue

    # 정기대관: 정기대관_신청 컬럼 기준
    if records_reg and len(records_reg) > 1:
        for row in records_reg[1:]:
            try:
                # 신청일 / 단체명 / 대표자 / 연락처 / 사용기간 / 요일 / 사용시간 / 사용목적
                if len(row) < 8:
                    continue

                group_name = str(row[1]).strip() or "정기대관"
                period_text = str(row[4]).strip()
                days_text = str(row[5]).strip()
                time_text = str(row[6]).strip()
                purpose = str(row[7]).strip()

                period_start, period_end = parse_period_local(period_text)
                days = normalize_days_text(days_text)
                reg_s, reg_e = parse_time_range_local(time_text)

                if not period_start or not period_end or not days:
                    continue

                if reg_s is None or reg_e is None:
                    continue

                cur = max(range_start, period_start)
                end_date = min(range_end, period_end)

                while cur <= end_date:
                    if get_day_korean(cur) in days:
                        add_event(
                            events_by_date,
                            cur,
                            "regular",
                            f"정기대관 · {group_name}",
                            time_text,
                            reg_s,
                            purpose
                        )

                    cur += timedelta(days=1)

            except Exception:
                continue

    for d in events_by_date:
        events_by_date[d].sort(key=lambda x: (x["sort_min"], x["kind"], x["title"]))

    return events_by_date


def render_calendar_html(year, month, selected_date, events_by_date):
    cal = calendar.Calendar(firstweekday=0)  # 월요일 시작
    weeks = cal.monthdatescalendar(year, month)
    today = datetime.today().date()
    month_label = f"{year}년 {month:02d}월"

    html = "<div class='calendar-wrap'>"
    html += f"<div class='calendar-title'>📅 {month_label} 대관 달력</div>"
    html += "<div class='legend-box'>"
    html += "<span class='event-kind normal'>일반대관</span> "
    html += "<span class='event-kind regular'>정기대관</span> "
    html += "달력의 시간은 이미 예약된 시간입니다."
    html += "</div>"
    html += "<div class='calendar-grid'>"

    for day_name in ["월", "화", "수", "목", "금", "토", "일"]:
        html += f"<div class='calendar-head'>{day_name}</div>"

    for week in weeks:
        for d in week:
            classes = ["cal-cell"]

            if d.month != month:
                classes.append("muted")

            if d == today:
                classes.append("today")

            if selected_date and d == selected_date:
                classes.append("selected")

            events = events_by_date.get(d, [])
            html += f"<div class='{ ' '.join(classes) }'>"
            html += f"<div class='cal-day-number'>{d.day}</div>"

            for event in events[:3]:
                event_class = "regular" if event["kind"] == "regular" else "normal"
                time_text = escape(event["time_text"])
                title = escape(event["title"])
                html += f"<div class='cal-event {event_class}' title='{title} {time_text}'>{time_text}</div>"

            if len(events) > 3:
                html += f"<div class='cal-more'>+{len(events) - 3}건 더 있음</div>"

            html += "</div>"

    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)


def show_selected_day_events(selected_date, events_by_date):
    st.markdown(f"#### 🕒 {selected_date.strftime('%Y-%m-%d')}({get_day_korean(selected_date)}) 예약 시간")
    events = events_by_date.get(selected_date, [])

    if not events:
        st.info("해당 날짜에 등록된 대관 내역이 없습니다.")
        return

    for event in events:
        kind_class = "regular" if event["kind"] == "regular" else "normal"
        kind_label = "정기대관" if event["kind"] == "regular" else "일반대관"
        extra_html = ""

        if event.get("extra"):
            extra_html = f"<div style='margin-top:6px; font-size:13px; color:#666;'>사용목적: {escape(event['extra'])}</div>"

        st.markdown(
            f"""
            <div class='event-card'>
                <span class='event-kind {kind_class}'>{kind_label}</span>
                <b>{escape(event['time_text'])}</b><br>
                <span>{escape(event['title'])}</span>
                {extra_html}
            </div>
            """,
            unsafe_allow_html=True
        )


def show_calendar_page(records_normal, records_reg):
    today = datetime.today().date()
    options = build_month_options(today.replace(day=1), months_before=1, months_after=4)

    query_year = get_query_value("year", "")
    query_month = get_query_value("month", "")
    default_index = 1  # 현재 월

    for idx, opt in enumerate(options):
        if str(opt["year"]) == str(query_year) and str(opt["month"]) == str(query_month):
            default_index = idx
            break

    c1, c2 = st.columns([1, 1])

    with c1:
        selected_label = st.selectbox(
            "월 선택",
            [opt["label"] for opt in options],
            index=default_index,
            key="calendar_month_select"
        )

    selected_option = next(opt for opt in options if opt["label"] == selected_label)
    year = selected_option["year"]
    month = selected_option["month"]
    month_start = selected_option["date"]
    month_end = month_add(month_start, 1) - timedelta(days=1)

    selected_default = today if (today.year == year and today.month == month) else month_start

    with c2:
        selected_date = st.date_input(
            "날짜 선택",
            value=selected_default,
            min_value=month_start,
            max_value=month_end,
            key=f"calendar_selected_date_{year}_{month}"
        )

    events_by_date = collect_calendar_events(records_normal, records_reg, month_start, month_end)
    render_calendar_html(year, month, selected_date, events_by_date)
    show_selected_day_events(selected_date, events_by_date)

# --- 7. 메인 UI 및 로직 ---
mode = str(get_query_value("mode", "reserve")).lower().strip()
is_calendar_only = mode in ["calendar", "status", "view"]

records_normal, records_reg = load_data()

if is_calendar_only:
    st.title("공공인재학부 세미나실 대관현황")
    st.caption("구글시트에 등록된 일반대관/정기대관 내역을 달력으로 확인하는 전용 화면입니다.")
    show_calendar_page(records_normal, records_reg)
    st.caption(
        f"마지막 갱신: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} · "
        f"{STATUS_REFRESH_SEC}초마다 자동 새로고침됩니다."
    )
    components.html(
        f"""
        <script>
        setTimeout(function() {{
            window.parent.location.reload();
        }}, {STATUS_REFRESH_SEC * 1000});
        </script>
        """,
        height=0
    )
    st.stop()

st.title("공공인재학부 세미나실 대관시스템")

with st.expander("📢 이용수칙 및 안내 (필독)", expanded=False):
    st.markdown("""
    <div class="notice-box">
        <b>📁 대관 안내</b><br>
        - 일반대관: 최대 3주 뒤까지 신청 가능 (1일 3시간)<br>
        - 정기대관: 해당 월 기준으로 신청 가능<br><br>
        <b>📁 이용 수칙</b><br>
        - 1인 대관 불가 / 선착순 마감 / 타 학과생 불가
    </div>
    """, unsafe_allow_html=True)

show_status(records_normal, records_reg)


success_placeholder = st.empty()

if "success_msg" in st.session_state and st.session_state["success_msg"]:
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
    st.session_state["success_msg"] = False
    st.rerun()

tab1, tab2 = st.tabs(["📅 일반 예약", "📝 정기 대관 신청"])

# TAB 1: 일반 예약
with tab1:
    if "attendees" not in st.session_state:
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
        today = datetime.today().date()
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
        start_time = st.time_input("시작", value=dt_time(14, 0), step=600)

    with t2:
        end_time = st.time_input("종료", value=dt_time(16, 0), step=600)

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
            if p["name"] and p["id"]
        ]

        if len(valid_users) < 2:
            st.error("❌ 최소 2인 이상 입력해야 합니다. (1인 대관 불가)")

        elif dur > 180:
            st.error("❌ 하루 최대 3시간까지만 가능합니다.")

        elif dur < 10:
            st.error("❌ 최소 10분")

        else:
            cli = get_client()

            if not cli:
                st.error("❌ 서버 연결 실패")

            else:
                try:
                    rep_name = valid_users[0]["name"].strip()
                    rep_id = valid_users[0]["id"].strip()

                    # 1일 총량제 검사
                    block_msg = ""

                    if records_normal:
                        for applicant in valid_users:
                            app_name = applicant["name"].strip()
                            app_id = applicant["id"].strip()
                            my_usage_min = 0

                            for row in records_normal:
                                if str(row.get("날짜", "")).replace(".", "-").strip() == date_str:
                                    es = to_min(row.get("시작시간"))
                                    ee = to_min(row.get("종료시간"))

                                    if ee < es:
                                        usage = (24 * 60 - es) + ee
                                    else:
                                        usage = ee - es

                                    is_included = False
                                    r_n = str(row.get("대표자명", "")).strip()
                                    r_i = str(row.get("대표학번", "")).strip()

                                    if r_n == app_name and r_i == app_id:
                                        is_included = True

                                    else:
                                        others = str(row.get("동반인원", ""))
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

                    # 일반대관 중복검사
                    overlap = False
                    req_start_dt = datetime.combine(date, start_time)
                    req_end_dt = datetime.combine(
                        date + timedelta(days=1 if e_min < s_min else 0),
                        end_time
                    )

                    if records_normal:
                        for row in records_normal:
                            try:
                                r_d = parse_date_local(row.get("날짜", ""))

                                if not r_d:
                                    continue

                                es = to_min(row.get("시작시간"))
                                ee = to_min(row.get("종료시간"))

                                exist_start_dt, exist_end_dt = make_dt_range(r_d, es, ee)

                                if is_time_overlap(req_start_dt, req_end_dt, exist_start_dt, exist_end_dt):
                                    overlap = True
                                    break

                            except:
                                continue

                    # 일반대관 신청 시간이 기존 정기대관과 겹치는지 검사
                    if not overlap and records_reg:
                        kd = get_day_korean(date)

                        for rr in records_reg[1:]:
                            try:
                                if len(rr) < 7:
                                    continue

                                period_start, period_end = parse_period_local(rr[4])
                                days = normalize_days_text(rr[5])
                                reg_s, reg_e = parse_time_range_local(rr[6])

                                if not period_start or not period_end:
                                    continue

                                if not days:
                                    continue

                                if reg_s is None or reg_e is None:
                                    continue

                                if not (period_start <= date <= period_end):
                                    continue

                                if kd not in days:
                                    continue

                                reg_start_dt, reg_end_dt = make_dt_range(date, reg_s, reg_e)

                                if is_time_overlap(req_start_dt, req_end_dt, reg_start_dt, reg_end_dt):
                                    overlap = True
                                    break

                            except:
                                continue

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
                        st.session_state["success_msg"] = True
                        st.rerun()

                except Exception as e:
                    st.error(f"오류: {e}")

# TAB 2: 정기 대관
with tab2:
    today = datetime.today().date()
    month_start = today.replace(day=1)

    if today.month == 12:
        next_month_start = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month_start = today.replace(month=today.month + 1, day=1)

    month_end = next_month_start - timedelta(days=1)

    st.markdown("""
    <div class="notice-box">
        <b>📢 정기대관 신청 안내</b><br><br>
        정기대관은 이번 달 안에서 신청 가능하며, 선택한 요일마다 매주 반복되는 형태로 등록됩니다.<br>
        단체명, 대표자, 연락처, 요일, 시작시간, 종료시간, 사용목적을 입력해주시면 검토 후 대관 등록 예정입니다.<br><br>
        매달 말 초기화될 예정이오니, 계속 이용을 원하시는 경우,
        매월 초 다시 신청해주시면 감사하겠습니다.
    </div>
    """, unsafe_allow_html=True)

    st.caption(
        f"신청 가능 기간: {month_start.strftime('%Y-%m-%d')} ~ {month_end.strftime('%Y-%m-%d')}"
    )

    with st.form("regular_form"):
        group_name = st.text_input("단체명", placeholder="예: 공공인재학부 스터디")
        rep_name = st.text_input("대표자", placeholder="대표자 이름")
        contact = st.text_input("연락처", placeholder="예: 010-0000-0000")

        reg_days = st.multiselect(
            "요일",
            ["월", "화", "수", "목", "금", "토", "일"],
            placeholder="매주 반복될 요일을 선택하세요"
        )

        c1, c2 = st.columns(2)

        with c1:
            reg_start_time = st.time_input(
                "시작시간",
                value=dt_time(18, 0),
                step=600
            )

        with c2:
            reg_end_time = st.time_input(
                "종료시간",
                value=dt_time(21, 0),
                step=600
            )

        purpose = st.text_area(
            "사용목적",
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

        if not group_name.strip():
            st.error("❌ 단체명을 입력해주세요.")

        elif not rep_name.strip():
            st.error("❌ 대표자를 입력해주세요.")

        elif not contact.strip():
            st.error("❌ 연락처를 입력해주세요.")

        elif not reg_days:
            st.error("❌ 요일을 1개 이상 선택해주세요.")

        elif not purpose.strip():
            st.error("❌ 사용목적을 입력해주세요.")

        elif reg_duration > 180:
            st.error("❌ 1회 이용 시간은 최대 3시간을 넘길 수 없습니다.")

        elif reg_duration < 10:
            st.error("❌ 최소 10분 이상 신청해주세요.")

        else:
            selected_dates = get_dates_by_days(month_start, month_end, reg_days)

            selected_dates_for_check = [
                d for d in selected_dates
                if d >= today
            ]

            if not selected_dates_for_check:
                st.error("❌ 선택한 요일 중 이번 달에 남아있는 신청 가능 날짜가 없습니다.")
                st.stop()

            overlap = False
            overlap_msg = ""

            # 1. 정기대관 신청이 기존 일반대관과 겹치는지 검사
            if records_normal:
                for target_date in selected_dates_for_check:
                    req_start_dt, req_end_dt = make_dt_range(
                        target_date,
                        reg_s_min,
                        reg_e_min
                    )

                    for row in records_normal:
                        try:
                            normal_date = parse_date_local(row.get("날짜", ""))

                            if normal_date != target_date:
                                continue

                            normal_s_min = to_min(row.get("시작시간"))
                            normal_e_min = to_min(row.get("종료시간"))

                            normal_start_dt, normal_end_dt = make_dt_range(
                                normal_date,
                                normal_s_min,
                                normal_e_min
                            )

                            if is_time_overlap(req_start_dt, req_end_dt, normal_start_dt, normal_end_dt):
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

            # 2. 정기대관 신청이 기존 정기대관과 겹치는지 검사
            if not overlap and records_reg and len(records_reg) > 1:
                for row in records_reg[1:]:
                    try:
                        if len(row) < 7:
                            continue

                        old_period_text = str(row[4]).strip()
                        old_days_text = str(row[5]).strip()
                        old_time_text = str(row[6]).strip()

                        old_start_date, old_end_date = parse_period_local(old_period_text)
                        old_days = normalize_days_text(old_days_text)
                        old_s_min, old_e_min = parse_time_range_local(old_time_text)

                        if not old_start_date or not old_end_date:
                            continue

                        if not old_days:
                            continue

                        if old_s_min is None or old_e_min is None:
                            continue

                        for target_date in selected_dates_for_check:
                            if not (old_start_date <= target_date <= old_end_date):
                                continue

                            if get_day_korean(target_date) not in old_days:
                                continue

                            req_start_dt, req_end_dt = make_dt_range(
                                target_date,
                                reg_s_min,
                                reg_e_min
                            )

                            old_start_dt, old_end_dt = make_dt_range(
                                target_date,
                                old_s_min,
                                old_e_min
                            )

                            if is_time_overlap(req_start_dt, req_end_dt, old_start_dt, old_end_dt):
                                overlap = True
                                overlap_msg = (
                                    f"❌ 신청 불가: {target_date.strftime('%m/%d')}({get_day_korean(target_date)}) "
                                    f"{reg_start_time.strftime('%H:%M')}~{reg_end_time.strftime('%H:%M')} 시간이 "
                                    f"이미 정기대관과 겹칩니다."
                                )
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

                        request_date = datetime.now().strftime("%Y-%m-%d")
                        period_str = f"{month_start.strftime('%Y-%m-%d')} ~ {month_end.strftime('%Y-%m-%d')}"
                        days_str = ", ".join(reg_days)
                        time_str = (
                            f"{reg_start_time.strftime('%H:%M')} ~ "
                            f"{reg_end_time.strftime('%H:%M')}"
                        )

                        # 신청일 / 단체명 / 대표자 / 연락처 / 사용기간 / 요일 / 사용시간 / 사용목적
                        ws.append_row([
                            request_date,
                            group_name.strip(),
                            rep_name.strip(),
                            contact.strip(),
                            period_str,
                            days_str,
                            time_str,
                            purpose.strip()
                        ])

                        st.cache_data.clear()
                        st.success("✅ 정기대관 신청이 완료되었습니다. 검토 후 대관 등록 예정입니다.")
                        st.rerun()

                except Exception as e:
                    st.error(f"오류: {e}")
