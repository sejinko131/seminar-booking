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
RESERVATION_PAGE_URL = "https://seminar-booking-yreuvhphdhqjdumy3dvwkm.streamlit.app"  # 하단 예약창 이동 링크

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


    .week-wrap {
        background: #ffffff;
        border: 1px solid #dddddd;
        border-radius: 14px;
        padding: 14px;
        margin-top: 10px;
        margin-bottom: 20px;
        overflow-x: auto;
    }

    .week-title {
        text-align: center;
        font-weight: 800;
        font-size: 22px;
        margin-bottom: 12px;
        color: #222222;
    }

    .week-guide {
        font-size: 13px;
        color: #444444;
        margin: 4px 0 12px 0;
    }

    .week-grid {
        display: grid;
        grid-template-columns: 88px repeat(7, minmax(132px, 1fr));
        min-width: 1060px;
        border-top: 1px solid #dddddd;
        border-left: 1px solid #dddddd;
    }

    .week-corner,
    .week-day-head,
    .week-time,
    .week-cell {
        border-right: 1px solid #dddddd;
        border-bottom: 1px solid #dddddd;
        box-sizing: border-box;
    }

    .week-corner,
    .week-day-head {
        background: #f5f5f5;
        color: #333333;
        font-weight: 800;
        text-align: center;
        padding: 10px 6px;
        position: sticky;
        top: 0;
        z-index: 2;
    }

    .week-time {
        background: #fafafa;
        color: #444444;
        font-size: 12px;
        font-weight: 700;
        padding: 8px 6px;
        text-align: center;
        min-height: 54px;
    }

    .week-cell {
        min-height: 54px;
        padding: 5px;
        background: #ffffff;
    }

    .week-cell.booked {
        background: #fbfdff;
    }

    .week-cell.today {
        box-shadow: inset 0 0 0 2px rgba(255, 75, 75, 0.18);
    }

    .week-event {
        font-size: 11px;
        line-height: 1.3;
        padding: 4px 5px;
        margin-bottom: 4px;
        border-radius: 6px;
        word-break: keep-all;
    }

    .week-event.normal {
        background: #e8f2ff;
        color: #174ea6;
        border: 1px solid #cfe2ff;
    }

    .week-event.regular {
        background: #fff4e5;
        color: #9a5b00;
        border: 1px solid #ffe0ad;
    }

    .reservation-link-box {
        background: #ffffff;
        border: 1px solid #dddddd;
        border-radius: 14px;
        padding: 18px;
        margin-top: 24px;
        text-align: center;
    }

    .reservation-link-box a {
        display: inline-block;
        padding: 12px 18px;
        border-radius: 10px;
        background: #ff4b4b;
        color: #ffffff !important;
        text-decoration: none;
        font-weight: 800;
    }

    .week-detail-wrap {
        background: #ffffff;
        border: 1px solid #dddddd;
        border-radius: 12px;
        padding: 14px;
        margin-bottom: 12px;
    }

    .week-detail-day {
        font-weight: 800;
        margin-top: 8px;
        margin-bottom: 6px;
        color: #222222;
    }

    .week-detail-item {
        font-size: 13px;
        padding: 5px 0;
        border-bottom: 1px solid #f0f0f0;
    }

    @media (max-width: 720px) {
        .week-title { font-size: 18px; }
        .week-grid { grid-template-columns: 74px repeat(7, minmax(118px, 1fr)); min-width: 900px; }
        .week-time { font-size: 11px; padding: 7px 4px; }
        .week-cell { padding: 4px; }
        .week-event { font-size: 10px; }
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



# --- 6-1. 주간 시간표형 현황 화면 ---
def format_minute(minute_value):
    """분 단위를 00:00 형식으로 변환합니다. 1440은 24:00으로 표시합니다."""
    try:
        minute_value = int(minute_value)
        if minute_value >= 1440:
            return "24:00"
        return f"{(minute_value // 60) % 24:02d}:{minute_value % 60:02d}"
    except Exception:
        return ""


def week_start_monday(base_date):
    return base_date - timedelta(days=base_date.weekday())


def add_week_event(events_by_date, event_date, kind, title, start_min, end_min, time_text, extra=""):
    if start_min is None or end_min is None:
        return

    try:
        start_min = max(0, min(1440, int(start_min)))
        end_min = max(0, min(1440, int(end_min)))
    except Exception:
        return

    if end_min <= start_min:
        return

    events_by_date.setdefault(event_date, []).append({
        "kind": kind,
        "title": str(title).strip(),
        "start_min": start_min,
        "end_min": end_min,
        "time_text": str(time_text).strip(),
        "extra": str(extra).strip(),
        "sort_min": start_min
    })


def split_event_into_days(base_date, start_min, end_min):
    """자정을 넘기는 예약은 당일/다음날 표시용으로 나눕니다."""
    if start_min is None or end_min is None:
        return []

    try:
        start_min = int(start_min)
        end_min = int(end_min)
    except Exception:
        return []

    if start_min < 0 or end_min < 0:
        return []

    if end_min > start_min:
        return [(base_date, start_min, min(end_min, 1440))]

    if end_min < start_min:
        return [
            (base_date, start_min, 1440),
            (base_date + timedelta(days=1), 0, end_min)
        ]

    return []


def collect_week_events(records_normal, records_reg, week_start, week_end):
    """일반대관과 정기대관을 주간 시간표용 이벤트로 합칩니다."""
    events_by_date = {}
    fetch_start = week_start - timedelta(days=1)  # 전날 심야 예약이 이번 주 00시로 넘어오는 경우 대비
    fetch_end = week_end

    # 일반대관: 시트1 컬럼 기준
    if records_normal:
        for row in records_normal:
            try:
                r_d = parse_date_local(row.get("날짜", ""))

                if not r_d or not (fetch_start <= r_d <= fetch_end):
                    continue

                start = str(row.get("시작시간", "")).strip()
                end = str(row.get("종료시간", "")).strip()
                name = str(row.get("대표자명", "")).strip()
                s_min = to_min(start)
                e_min = to_min(end)
                display_name = mask_name(name) if name else "예약자"
                original_time_text = f"{start} ~ {end}" + (" (+1)" if e_min < s_min else "")

                for event_date, day_start, day_end in split_event_into_days(r_d, s_min, e_min):
                    if week_start <= event_date <= week_end:
                        add_week_event(
                            events_by_date,
                            event_date,
                            "normal",
                            f"일반 · {display_name}",
                            day_start,
                            day_end,
                            original_time_text
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

                cur = max(fetch_start, period_start)
                end_date = min(fetch_end, period_end)

                while cur <= end_date:
                    if get_day_korean(cur) in days:
                        for event_date, day_start, day_end in split_event_into_days(cur, reg_s, reg_e):
                            if week_start <= event_date <= week_end:
                                add_week_event(
                                    events_by_date,
                                    event_date,
                                    "regular",
                                    f"정기 · {group_name}",
                                    day_start,
                                    day_end,
                                    time_text,
                                    purpose
                                )

                    cur += timedelta(days=1)

            except Exception:
                continue

    for d in events_by_date:
        events_by_date[d].sort(key=lambda x: (x["sort_min"], x["kind"], x["title"]))

    return events_by_date


def render_week_schedule_html(week_start, events_by_date):
    week_days = [week_start + timedelta(days=i) for i in range(7)]
    week_end = week_days[-1]
    today = datetime.today().date()

    html = "<div class='week-wrap'>"
    html += (
        f"<div class='week-title'>🗓️ {week_start.strftime('%Y-%m-%d')} ~ "
        f"{week_end.strftime('%Y-%m-%d')} 주간 대관 시간표</div>"
    )
    html += "<div class='week-guide'>"
    html += "<span class='event-kind normal'>일반대관</span> "
    html += "<span class='event-kind regular'>정기대관</span> "
    html += "00:00부터 24:00까지 1시간 단위로 표시됩니다. 예약이 걸쳐 있는 시간대에 내역이 표시됩니다."
    html += "</div>"
    html += "<div class='week-grid'>"
    html += "<div class='week-corner'>시간</div>"

    for d in week_days:
        day_label = f"{get_day_korean(d)}<br>{d.strftime('%m/%d')}"
        if d == today:
            day_label += "<br><span style='color:#ff4b4b;'>오늘</span>"
        html += f"<div class='week-day-head'>{day_label}</div>"

    for hour in range(24):
        hour_start = hour * 60
        hour_end = (hour + 1) * 60
        html += f"<div class='week-time'>{format_minute(hour_start)}<br>~<br>{format_minute(hour_end)}</div>"

        for d in week_days:
            cell_events = [
                event for event in events_by_date.get(d, [])
                if event["start_min"] < hour_end and event["end_min"] > hour_start
            ]
            classes = ["week-cell"]

            if cell_events:
                classes.append("booked")

            if d == today:
                classes.append("today")

            html += f"<div class='{ ' '.join(classes) }'>"

            for event in cell_events:
                event_class = "regular" if event["kind"] == "regular" else "normal"
                title = escape(event["title"])
                time_text = escape(event["time_text"])
                html += (
                    f"<div class='week-event {event_class}' title='{title} {time_text}'>"
                    f"<b>{time_text}</b><br>{title}"
                    f"</div>"
                )

            html += "</div>"

    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)


def show_week_detail_list(week_start, events_by_date):
    week_days = [week_start + timedelta(days=i) for i in range(7)]
    has_any = any(events_by_date.get(d) for d in week_days)

    st.markdown("#### 📌 이번 주 예약 상세")

    if not has_any:
        st.info("이번 주에 등록된 대관 내역이 없습니다.")
        return

    html = "<div class='week-detail-wrap'>"

    for d in week_days:
        events = events_by_date.get(d, [])
        if not events:
            continue

        html += f"<div class='week-detail-day'>{d.strftime('%Y-%m-%d')}({get_day_korean(d)})</div>"

        for event in events:
            kind_label = "정기대관" if event["kind"] == "regular" else "일반대관"
            time_text = escape(event["time_text"])
            title = escape(event["title"])
            extra = escape(event.get("extra", ""))
            extra_text = f" · {extra}" if extra else ""
            html += (
                f"<div class='week-detail-item'>"
                f"<b>{time_text}</b> · {kind_label} · {title}{extra_text}"
                f"</div>"
            )

    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def render_reservation_link():
    safe_url = escape(RESERVATION_PAGE_URL)
    st.markdown(
        f"""
        <div class='reservation-link-box'>
            <div style='font-weight:800; margin-bottom:10px;'>예약을 신청하려면 아래 버튼을 눌러주세요.</div>
            <a href='{safe_url}' target='_self'>📅 예약창으로 이동</a>
        </div>
        """,
        unsafe_allow_html=True
    )


def show_weekly_schedule_page(records_normal, records_reg):
    today = datetime.today().date()

    selected_date = st.date_input(
        "확인할 주 선택",
        value=today,
        help="선택한 날짜가 포함된 월요일~일요일 주간 시간표를 보여줍니다.",
        key="weekly_schedule_selected_date"
    )

    week_start = week_start_monday(selected_date)
    week_end = week_start + timedelta(days=6)
    events_by_date = collect_week_events(records_normal, records_reg, week_start, week_end)

    render_week_schedule_html(week_start, events_by_date)
    show_week_detail_list(week_start, events_by_date)

# --- 7. 메인 UI 및 로직 ---
mode = str(get_query_value("mode", "reserve")).lower().strip()
is_calendar_only = mode in ["calendar", "status", "view"]

records_normal, records_reg = load_data()

if is_calendar_only:
    st.title("공공인재학부 세미나실 대관현황")
    st.caption("구글시트에 등록된 일반대관/정기대관 내역을 주별·시간대별로 확인하는 전용 화면입니다.")
    show_weekly_schedule_page(records_normal, records_reg)
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
    render_reservation_link()
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
