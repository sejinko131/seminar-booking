import streamlit as st
from datetime import datetime, timedelta, time as dt_time
from zoneinfo import ZoneInfo
from oauth2client.service_account import ServiceAccountCredentials

JSON_FILE = "key.json"
SHEET_NAME = "세미나실_대관"
KST = ZoneInfo("Asia/Seoul")
REGULAR_HEADERS = [
    "신청일", "단체명", "대표자", "연락처", "사용기간",
    "요일", "사용시간", "사용목적", "대표학번"
]


def now_kst():
    return datetime.now(KST)


def today_kst():
    return now_kst().date()


def get_day_korean(date_obj):
    return ["월", "화", "수", "목", "금", "토", "일"][date_obj.weekday()]


def mask_name(name):
    name = str(name).strip()
    return name[0] + "**" if len(name) > 1 else name


def to_min(v):
    try:
        if isinstance(v, int):
            return v * 60
        if hasattr(v, "hour") and hasattr(v, "minute"):
            return int(v.hour) * 60 + int(v.minute)
        if isinstance(v, str):
            v = v.strip()
            if ":" in v:
                h, m = map(int, v.split(":")[:2])
                return h * 60 + m
            if v.isdigit():
                return int(v) * 60
    except Exception:
        pass
    return 0


def min_to_time(minutes):
    minutes = int(minutes) % 1440
    return dt_time(minutes // 60, minutes % 60)


def parse_date(v):
    try:
        return datetime.strptime(
            str(v).replace(".", "-").replace("/", "-").strip(), "%Y-%m-%d"
        ).date()
    except Exception:
        return None


def parse_period(text):
    try:
        left, right = str(text).split("~", 1)
        return parse_date(left.strip()), parse_date(right.strip())
    except Exception:
        return None, None


def parse_time_range(text):
    try:
        left, right = str(text).split("~", 1)
        return to_min(left.strip()), to_min(right.strip())
    except Exception:
        return None, None


def normalize_days(text):
    parts = (
        str(text).replace("매주", "").replace("요일", "")
        .replace("/", ",").replace("·", ",").replace(" ", "").split(",")
    )
    return [p for p in parts if p in ["월", "화", "수", "목", "금", "토", "일"]]


def make_interval(base_date, start_min, end_min):
    start = datetime.combine(base_date, min_to_time(start_min), tzinfo=KST)
    end_date = base_date + timedelta(days=1 if end_min < start_min else 0)
    end = datetime.combine(end_date, min_to_time(end_min), tzinfo=KST)
    return start, end


def intervals_overlap(start1, end1, start2, end2):
    return start1 < end2 and end1 > start2


def duration_minutes(start_min, end_min):
    if end_min < start_min:
        return (1440 - start_min) + end_min
    return end_min - start_min


@st.cache_resource
def get_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
    ]
    try:
        if "gcp_service_account" in st.secrets:
            key_dict = dict(st.secrets["gcp_service_account"])
            creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
        else:
            creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_FILE, scope)
        import gspread
        return gspread.authorize(creds)
    except Exception:
        return None


def get_worksheets():
    client = get_client()
    if not client:
        return None, None
    sheet = client.open(SHEET_NAME)
    return sheet.worksheet("시트1"), sheet.worksheet("정기대관_신청")


def ensure_regular_header(ws):
    headers = ws.row_values(1)
    if not headers:
        ws.append_row(REGULAR_HEADERS)
        return
    if len(headers) < 9 or str(headers[8]).strip() != "대표학번":
        ws.update_cell(1, 9, "대표학번")


@st.cache_data(ttl=15)
def load_data_cached():
    try:
        ws1, ws2 = get_worksheets()
        if not ws1 or not ws2:
            return None, None
        return ws1.get_all_records(), ws2.get_all_values()
    except Exception:
        return None, None


def load_fresh_values():
    ws1, ws2 = get_worksheets()
    if not ws1 or not ws2:
        return None, None, [], []
    ensure_regular_header(ws2)
    return ws1, ws2, ws1.get_all_values(), ws2.get_all_values()


def _header_index(headers, names):
    normalized = [str(x).strip() for x in headers]
    for name in names:
        if name in normalized:
            return normalized.index(name)
    return None


def general_records_from_values(values):
    if not values:
        return []
    headers = values[0]
    idx_date = _header_index(headers, ["날짜"])
    idx_start = _header_index(headers, ["시작시간", "시작"])
    idx_end = _header_index(headers, ["종료시간", "종료"])
    idx_name = _header_index(headers, ["대표자명", "대표자"])
    idx_id = _header_index(headers, ["대표학번", "학번"])
    idx_others = _header_index(headers, ["동반인원", "동반자"])

    result = []
    for row_no, row in enumerate(values[1:], start=2):
        def cell(idx):
            return str(row[idx]).strip() if idx is not None and idx < len(row) else ""
        result.append({
            "_row": row_no,
            "날짜": cell(idx_date),
            "시작시간": cell(idx_start),
            "종료시간": cell(idx_end),
            "대표자명": cell(idx_name),
            "대표학번": cell(idx_id),
            "동반인원": cell(idx_others),
        })
    return result


def regular_records_from_values(values):
    if not values:
        return []
    headers = [str(x).strip() for x in values[0]]

    def find(*names):
        for n in names:
            if n in headers:
                return headers.index(n)
        return None

    indices = {
        "신청일": find("신청일"),
        "단체명": find("단체명"),
        "대표자": find("대표자", "대표자명"),
        "연락처": find("연락처"),
        "사용기간": find("사용기간"),
        "요일": find("요일"),
        "사용시간": find("사용시간"),
        "사용목적": find("사용목적"),
        "대표학번": find("대표학번", "학번"),
    }
    # 기존 8열 구조 호환
    fallback = {
        "신청일": 0, "단체명": 1, "대표자": 2, "연락처": 3,
        "사용기간": 4, "요일": 5, "사용시간": 6, "사용목적": 7,
        "대표학번": 8,
    }
    result = []
    for row_no, row in enumerate(values[1:], start=2):
        rec = {"_row": row_no}
        for key in fallback:
            idx = indices.get(key)
            if idx is None:
                idx = fallback[key]
            rec[key] = str(row[idx]).strip() if idx < len(row) else ""
        result.append(rec)
    return result


def general_interval(rec):
    d = parse_date(rec.get("날짜"))
    if not d:
        return None, None
    return make_interval(d, to_min(rec.get("시작시간")), to_min(rec.get("종료시간")))


def regular_occurrences(rec, window_start=None, window_end=None, remaining_only=False):
    period_start, period_end = parse_period(rec.get("사용기간", ""))
    days = normalize_days(rec.get("요일", ""))
    s_min, e_min = parse_time_range(rec.get("사용시간", ""))
    if not period_start or not period_end or not days or s_min is None or e_min is None:
        return []

    start_date = max(period_start, window_start) if window_start else period_start
    end_date = min(period_end, window_end) if window_end else period_end
    if end_date < start_date:
        return []

    now = now_kst()
    result = []
    cur = start_date
    while cur <= end_date:
        if get_day_korean(cur) in days:
            start_dt, end_dt = make_interval(cur, s_min, e_min)
            if not remaining_only or end_dt > now:
                result.append((cur, start_dt, end_dt))
        cur += timedelta(days=1)
    return result


def has_remaining_regular(rec):
    return bool(regular_occurrences(rec, remaining_only=True))


def active_general_for_user(records, name, student_id):
    now = now_kst()
    found = []
    for rec in records:
        if rec.get("대표자명", "").strip() != name.strip():
            continue
        if rec.get("대표학번", "").strip() != student_id.strip():
            continue
        _, end_dt = general_interval(rec)
        if end_dt and end_dt > now:
            found.append(rec)
    found.sort(key=lambda r: general_interval(r)[0] or now)
    return found


def active_regular_for_user(records, name, student_id):
    found = []
    for rec in records:
        if rec.get("대표자", "").strip() != name.strip():
            continue
        if rec.get("대표학번", "").strip() != student_id.strip():
            continue
        if has_remaining_regular(rec):
            found.append(rec)
    return found


def find_general_conflict(start_dt, end_dt, general_records, exclude_row=None):
    for rec in general_records:
        if exclude_row and rec.get("_row") == exclude_row:
            continue
        old_start, old_end = general_interval(rec)
        if old_start and intervals_overlap(start_dt, end_dt, old_start, old_end):
            return rec
    return None


def find_regular_conflict(start_dt, end_dt, regular_records, exclude_row=None):
    d1 = start_dt.date() - timedelta(days=1)
    d2 = end_dt.date()
    for rec in regular_records:
        if exclude_row and rec.get("_row") == exclude_row:
            continue
        for _, old_start, old_end in regular_occurrences(rec, d1, d2):
            if intervals_overlap(start_dt, end_dt, old_start, old_end):
                return rec
    return None


def user_in_general_record(rec, name, student_id):
    name = name.strip()
    student_id = student_id.strip()
    if rec.get("대표자명", "").strip() == name and rec.get("대표학번", "").strip() == student_id:
        return True
    token = f"{name}({student_id})"
    return token in rec.get("동반인원", "")


def check_daily_usage(general_records, target_date, attendees, new_duration, exclude_row=None):
    for person in attendees:
        name = person["name"].strip()
        student_id = person["id"].strip()
        used = 0
        for rec in general_records:
            if exclude_row and rec.get("_row") == exclude_row:
                continue
            if parse_date(rec.get("날짜")) != target_date:
                continue
            if user_in_general_record(rec, name, student_id):
                used += duration_minutes(to_min(rec.get("시작시간")), to_min(rec.get("종료시간")))
        if used + new_duration > 180:
            return f"'{name}'님은 금일 이용 한도(3시간)를 초과하게 됩니다. (이미 {used}분 + 신청 {new_duration}분)"
    return ""


def attendees_from_general(rec):
    people = [{"name": rec.get("대표자명", "").strip(), "id": rec.get("대표학번", "").strip()}]
    text = rec.get("동반인원", "").strip()
    if not text or text == "없음":
        return people
    for part in text.split(","):
        part = part.strip()
        if "(" in part and part.endswith(")"):
            name, sid = part.rsplit("(", 1)
            people.append({"name": name.strip(), "id": sid[:-1].strip()})
    return people


def schedule_occurrences(period_start, period_end, days, start_min, end_min, remaining_only=True):
    now = now_kst()
    out = []
    cur = period_start
    while cur <= period_end:
        if get_day_korean(cur) in days:
            s, e = make_interval(cur, start_min, end_min)
            if not remaining_only or e > now:
                out.append((cur, s, e))
        cur += timedelta(days=1)
    return out


def find_schedule_conflict(period_start, period_end, days, start_min, end_min,
                           general_records, regular_records, exclude_regular_row=None):
    occurrences = schedule_occurrences(period_start, period_end, days, start_min, end_min, True)
    if not occurrences:
        return "신청 가능한 현재/미래 이용 회차가 없습니다."

    for target_date, start_dt, end_dt in occurrences:
        conflict_general = find_general_conflict(start_dt, end_dt, general_records)
        if conflict_general:
            return f"{target_date.strftime('%m/%d')}({get_day_korean(target_date)}) 시간이 기존 일반예약과 겹칩니다."
        conflict_regular = find_regular_conflict(start_dt, end_dt, regular_records, exclude_regular_row)
        if conflict_regular:
            return f"{target_date.strftime('%m/%d')}({get_day_korean(target_date)}) 시간이 기존 정기대관과 겹칩니다."
    return ""


def general_signature(rec):
    return (
        str(rec.get("날짜", "")).strip(),
        str(rec.get("시작시간", "")).strip(),
        str(rec.get("종료시간", "")).strip(),
        str(rec.get("대표자명", "")).strip(),
        str(rec.get("대표학번", "")).strip(),
        str(rec.get("동반인원", "")).strip(),
    )


def regular_signature(rec):
    return (
        str(rec.get("신청일", "")).strip(),
        str(rec.get("단체명", "")).strip(),
        str(rec.get("대표자", "")).strip(),
        str(rec.get("연락처", "")).strip(),
        str(rec.get("사용기간", "")).strip(),
        str(rec.get("요일", "")).strip(),
        str(rec.get("사용시간", "")).strip(),
        str(rec.get("사용목적", "")).strip(),
        str(rec.get("대표학번", "")).strip(),
    )


def find_matching_general_row(records, target):
    sig = general_signature(target)
    for rec in records:
        if general_signature(rec) == sig:
            return rec
    return None


def find_matching_regular_row(records, target):
    sig = regular_signature(target)
    for rec in records:
        if regular_signature(rec) == sig:
            return rec
    return None
