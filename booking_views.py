import calendar
from datetime import date as date_cls, timedelta
from html import escape

import streamlit as st
import streamlit.components.v1 as components

from booking_core import (
    general_interval,
    get_day_korean,
    has_remaining_regular,
    mask_name,
    now_kst,
    parse_date,
    regular_records_from_values,
    regular_occurrences,
)

STATUS_REFRESH_SEC = 60
RESERVATION_PAGE_URL = "https://seminar-booking-yreuvhphdhqjdumy3dvwkm.streamlit.app"


def inject_css():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 3rem; padding-bottom: 5rem; }
        h1 { text-align:center; font-size:1.8rem !important; margin-bottom:10px; }
        .stButton button { width:100%; border-radius:8px; min-height:3em; font-weight:700; }
        .status-box { border:1px solid rgba(128,128,128,.35); border-radius:12px; padding:16px; margin-bottom:18px; }
        .status-header { font-weight:800; margin:4px 0 10px; padding-bottom:6px; border-bottom:1px solid rgba(128,128,128,.25); }
        .status-item { padding:5px 0; border-bottom:1px solid rgba(128,128,128,.12); }
        .notice-box { background:rgba(255,193,7,.14); border:1px solid rgba(255,193,7,.35); padding:15px; border-radius:8px; line-height:1.65; }
        .success-message { background:rgba(40,167,69,.15); border:1px solid rgba(40,167,69,.35); padding:20px; border-radius:10px; text-align:center; font-weight:700; }
        .manage-card { border:1px solid rgba(128,128,128,.35); border-radius:12px; padding:14px; margin:10px 0; }
        .week-wrap { border:1px solid rgba(128,128,128,.35); border-radius:14px; padding:14px; overflow-x:auto; }
        .week-title { text-align:center; font-weight:800; font-size:21px; margin-bottom:12px; }
        .week-grid { display:grid; grid-template-columns:80px repeat(7,minmax(118px,1fr)); min-width:910px; border-left:1px solid rgba(128,128,128,.3); border-top:1px solid rgba(128,128,128,.3); }
        .week-head,.week-time,.week-cell { border-right:1px solid rgba(128,128,128,.3); border-bottom:1px solid rgba(128,128,128,.3); }
        .week-head { font-weight:800; text-align:center; padding:9px 4px; background:rgba(128,128,128,.1); }
        .week-time { text-align:center; font-size:11px; padding:7px 3px; background:rgba(128,128,128,.06); }
        .week-cell { min-height:48px; padding:3px; }
        .week-event { font-size:10px; padding:3px 4px; border-radius:5px; margin-bottom:2px; }
        .week-event.normal { background:rgba(33,150,243,.18); }
        .week-event.regular { background:rgba(255,152,0,.18); }
        @media (max-width:720px) { .block-container{padding-top:1.5rem;padding-left:.8rem;padding-right:.8rem;} }
        </style>
        """,
        unsafe_allow_html=True,
    )


def show_status(records_normal, records_reg_values):
    st.markdown("#### 📅 세미나실 대관현황")
    now = now_kst()
    regular_records = regular_records_from_values(records_reg_values or [])

    html = "<div class='status-box'><div class='status-header'>▪️ 일반대관</div>"
    upcoming = []
    for row in records_normal or []:
        try:
            d = parse_date(row.get("날짜", ""))
            if not d:
                continue
            s = str(row.get("시작시간", "")).strip()
            e = str(row.get("종료시간", "")).strip()
            name = str(row.get("대표자명", "")).strip()
            start_dt, end_dt = general_interval(row)
            if end_dt and end_dt > now:
                upcoming.append((
                    start_dt,
                    f"<b>{escape(mask_name(name) if name else '예약자')}</b> / "
                    f"{d.strftime('%m/%d')}({get_day_korean(d)}) / {escape(s)} - {escape(e)}",
                ))
        except Exception:
            continue
    upcoming.sort(key=lambda x: x[0])
    if upcoming:
        for _, item in upcoming[:15]:
            html += f"<div class='status-item'>{item}</div>"
    else:
        html += "<div class='status-item'>예정된 예약이 없습니다.</div>"

    html += "<br><div class='status-header'>▪️ 정기대관</div>"
    regular_shown = False
    for rec in regular_records:
        if not has_remaining_regular(rec):
            continue
        html += (
            "<div class='status-item'>"
            f"<b>{escape(rec.get('단체명','') or '정기대관')}</b> / "
            f"매주 {escape(rec.get('요일',''))} / {escape(rec.get('사용시간',''))}"
            "</div>"
        )
        regular_shown = True
    if not regular_shown:
        html += "<div class='status-item'>등록된 정기대관이 없습니다.</div>"
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def week_start_monday(d):
    return d - timedelta(days=d.weekday())


def month_week_options(year, month):
    first = date_cls(year, month, 1)
    last = date_cls(year, month, calendar.monthrange(year, month)[1])
    cur = week_start_monday(first)
    out = []
    n = 1
    while cur <= last:
        out.append((f"{n}주차", cur))
        cur += timedelta(days=7)
        n += 1
    return out


def _split_general_event(row):
    start_dt, end_dt = general_interval(row)
    if not start_dt:
        return []
    if start_dt.date() == end_dt.date():
        return [(start_dt.date(), start_dt.hour * 60 + start_dt.minute, end_dt.hour * 60 + end_dt.minute)]
    return [
        (start_dt.date(), start_dt.hour * 60 + start_dt.minute, 1440),
        (end_dt.date(), 0, end_dt.hour * 60 + end_dt.minute),
    ]


def show_weekly_schedule(records_normal, records_reg_values):
    today = now_kst().date()
    c1, c2 = st.columns(2)
    with c1:
        month = st.selectbox(
            "월 선택",
            list(range(1, 13)),
            index=today.month - 1,
            format_func=lambda x: f"{x}월",
        )
    options = month_week_options(today.year, month)
    labels = [x[0] for x in options]
    current_start = week_start_monday(today)
    default_idx = next((i for i, (_, d) in enumerate(options) if d == current_start), 0)
    with c2:
        week_label = st.selectbox("주차 선택", labels, index=default_idx)
    week_start = dict(options)[week_label]
    week_end = week_start + timedelta(days=6)

    events = {week_start + timedelta(days=i): [] for i in range(7)}
    for row in records_normal or []:
        for d, s, e in _split_general_event(row):
            if d in events:
                events[d].append((s, e, "normal", f"{row.get('시작시간','')}~{row.get('종료시간','')}"))

    for rec in regular_records_from_values(records_reg_values or []):
        for _, sdt, edt in regular_occurrences(rec, week_start - timedelta(days=1), week_end):
            if sdt.date() in events:
                events[sdt.date()].append((
                    sdt.hour * 60 + sdt.minute,
                    1440 if edt.date() != sdt.date() else edt.hour * 60 + edt.minute,
                    "regular",
                    rec.get("사용시간", ""),
                ))
            if edt.date() != sdt.date() and edt.date() in events:
                events[edt.date()].append((
                    0,
                    edt.hour * 60 + edt.minute,
                    "regular",
                    rec.get("사용시간", ""),
                ))

    days = [week_start + timedelta(days=i) for i in range(7)]
    html = (
        f"<div class='week-wrap'><div class='week-title'>🗓️ {month}월 {escape(week_label)} 대관 시간표</div>"
        "<div class='week-grid'><div class='week-head'>시간</div>"
    )
    for d in days:
        html += f"<div class='week-head'>{get_day_korean(d)}요일<br>{d.strftime('%m/%d')}</div>"
    for hour in range(24):
        hs, he = hour * 60, (hour + 1) * 60
        html += f"<div class='week-time'>{hour:02d}:00<br>~<br>{(hour + 1) % 24:02d}:00</div>"
        for d in days:
            html += "<div class='week-cell'>"
            for s, e, kind, label in events[d]:
                if s < he and e > hs:
                    html += f"<div class='week-event {kind}'>{escape(label)}</div>"
            html += "</div>"
    html += "</div></div>"
    st.markdown(html, unsafe_allow_html=True)


def show_calendar_only(records_normal, records_reg_values):
    st.title("공공인재학부 세미나실 대관현황")
    st.caption("KST 기준 대관 내역을 월별·주차별로 확인합니다.")
    show_weekly_schedule(records_normal, records_reg_values)
    st.caption(
        f"마지막 갱신: {now_kst().strftime('%Y-%m-%d %H:%M:%S')} KST · "
        f"{STATUS_REFRESH_SEC}초마다 자동 새로고침"
    )
    components.html(
        f"<script>setTimeout(function(){{window.parent.location.reload();}}, {STATUS_REFRESH_SEC * 1000});</script>",
        height=0,
    )
    st.markdown(
        f"<div style='text-align:center;margin-top:20px'><a href='{RESERVATION_PAGE_URL}' target='_self'>📅 예약창으로 이동</a></div>",
        unsafe_allow_html=True,
    )
