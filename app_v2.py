import streamlit as st
from datetime import timedelta

from booking_core import (
    active_general_for_user,
    active_regular_for_user,
    attendees_from_general,
    check_daily_usage,
    duration_minutes,
    find_general_conflict,
    find_matching_general_row,
    find_matching_regular_row,
    find_regular_conflict,
    find_schedule_conflict,
    general_records_from_values,
    get_day_korean,
    load_data_cached,
    load_fresh_values,
    make_interval,
    min_to_time,
    normalize_days,
    now_kst,
    parse_date,
    parse_period,
    parse_time_range,
    regular_records_from_values,
    today_kst,
    to_min,
)
from booking_views import inject_css, show_calendar_only, show_status


st.set_page_config(page_title="세미나실 대관시스템", page_icon="📅", layout="wide")
inject_css()


def get_query_value(key, default=""):
    try:
        value = st.query_params.get(key, default)
    except Exception:
        value = st.experimental_get_query_params().get(key, [default])
    if isinstance(value, list):
        return value[0] if value else default
    return value if value is not None else default


def validate_general_candidate(target_date, start_time, end_time, attendees,
                               general_records, regular_records, exclude_row=None):
    s_min = to_min(start_time)
    e_min = to_min(end_time)
    dur = duration_minutes(s_min, e_min)

    if len(attendees) < 2:
        return "최소 2인 이상 입력해야 합니다. (1인 대관 불가)"
    if dur > 180:
        return "하루 최대 3시간까지만 가능합니다."
    if dur < 10:
        return "최소 10분 이상 신청해야 합니다."

    today = today_kst()
    if target_date > today + timedelta(weeks=3):
        return "일반대관은 최대 3주 뒤까지만 신청할 수 있습니다."

    start_dt, end_dt = make_interval(target_date, s_min, e_min)
    if end_dt <= now_kst():
        return "이미 종료된 시간으로는 예약하거나 변경할 수 없습니다."

    conflict = find_general_conflict(start_dt, end_dt, general_records, exclude_row)
    if conflict:
        return "이미 등록된 일반예약과 시간이 겹칩니다."

    conflict = find_regular_conflict(start_dt, end_dt, regular_records)
    if conflict:
        return "정기대관과 시간이 겹칩니다."

    usage_msg = check_daily_usage(
        general_records, target_date, attendees, dur, exclude_row=exclude_row
    )
    if usage_msg:
        return usage_msg
    return ""


def refresh_management_results(name, student_id):
    try:
        _, _, general_values, regular_values = load_fresh_values()
        general_records = general_records_from_values(general_values)
        regular_records = regular_records_from_values(regular_values)
        st.session_state["manage_general_matches"] = active_general_for_user(
            general_records, name, student_id
        )
        st.session_state["manage_regular_matches"] = active_regular_for_user(
            regular_records, name, student_id
        )
        st.session_state["manage_lookup_name"] = name
        st.session_state["manage_lookup_id"] = student_id
        st.session_state["manage_loaded"] = True
        return True
    except Exception as e:
        st.error(f"조회 중 오류가 발생했습니다: {e}")
        return False


def set_flash(message, kind="success"):
    st.session_state["manage_flash"] = (kind, message)


records_normal_cached, records_reg_cached = load_data_cached()
mode = str(get_query_value("mode", "reserve")).lower().strip()

if mode in ["calendar", "status", "view"]:
    show_calendar_only(records_normal_cached or [], records_reg_cached or [])
    st.stop()

st.title("공공인재학부 세미나실 대관시스템")

with st.expander("📢 이용수칙 및 안내 (필독)", expanded=False):
    st.markdown(
        """
        <div class="notice-box">
        <b>📁 대관 안내</b><br>
        - 일반대관: 최대 3주 뒤까지 신청 가능 (1일 총 3시간)<br>
        - 정기대관: 해당 월 기준으로 신청 가능<br>
        - 모든 시간 판정은 한국시간(KST) 기준입니다.<br><br>
        <b>📁 이용 수칙</b><br>
        - 1인 대관 불가 / 선착순 마감 / 타 학과생 불가
        </div>
        """,
        unsafe_allow_html=True,
    )

show_status(records_normal_cached or [], records_reg_cached or [])

if st.session_state.pop("general_success", False):
    st.success("✅ 대관이 완료되었습니다. 세미나실 비밀번호는 0015*입니다. 사용 후 정리정돈 및 문단속 부탁드립니다.")
    st.balloons()

if st.session_state.pop("regular_success", False):
    st.success("✅ 정기대관 신청이 완료되었습니다. 검토 후 대관 등록 예정입니다.")

if "manage_flash" in st.session_state:
    kind, message = st.session_state.pop("manage_flash")
    if kind == "error":
        st.error(message)
    elif kind == "warning":
        st.warning(message)
    else:
        st.success(message)


tab1, tab2, tab3 = st.tabs(["📅 일반예약", "📝 정기 대관 신청", "🛠️ 대관 관리"])

# ------------------------------------------------------------------
# 1. 일반예약
# ------------------------------------------------------------------
with tab1:
    if "attendees" not in st.session_state:
        st.session_state.attendees = [{"name": "", "id": ""}, {"name": "", "id": ""}]

    def add_attendee():
        st.session_state.attendees.append({"name": "", "id": ""})

    def remove_attendee():
        if len(st.session_state.attendees) > 2:
            st.session_state.attendees.pop()

    today = today_kst()
    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        reserve_date = st.date_input(
            "날짜", value=today, min_value=today, max_value=today + timedelta(weeks=3),
            key="general_date"
        )
    with c2:
        start_time = st.time_input("시작", value=min_to_time(14 * 60), step=600, key="general_start")
    with c3:
        end_time = st.time_input("종료", value=min_to_time(16 * 60), step=600, key="general_end")

    st.caption("예약자 명단 (첫 번째가 대표자)")
    for i, person in enumerate(st.session_state.attendees):
        ncol, icol = st.columns([6, 4])
        with ncol:
            value = st.text_input(
                f"이름{i}", value=person.get("name", ""), placeholder="이름",
                key=f"general_name_{i}", label_visibility="collapsed"
            )
            st.session_state.attendees[i]["name"] = value
        with icol:
            value = st.text_input(
                f"학번{i}", value=person.get("id", ""), placeholder="학번",
                key=f"general_id_{i}", label_visibility="collapsed"
            )
            st.session_state.attendees[i]["id"] = value

    b1, b2 = st.columns(2)
    with b1:
        st.button("➕ 인원 추가", on_click=add_attendee, key="general_add")
    with b2:
        if len(st.session_state.attendees) > 2:
            st.button("➖ 마지막 인원 삭제", on_click=remove_attendee, key="general_remove")

    st.write("---")
    if st.button("📅 예약 신청하기", type="primary", key="general_submit"):
        valid_users = [
            {"name": p["name"].strip(), "id": p["id"].strip()}
            for p in st.session_state.attendees
            if p.get("name", "").strip() and p.get("id", "").strip()
        ]

        try:
            ws1, _, general_values, regular_values = load_fresh_values()
            if not ws1:
                st.error("❌ 서버 연결 실패")
            else:
                general_records = general_records_from_values(general_values)
                regular_records = regular_records_from_values(regular_values)
                msg = validate_general_candidate(
                    reserve_date, start_time, end_time, valid_users,
                    general_records, regular_records
                )
                if msg:
                    st.error(f"❌ {msg}")
                else:
                    rep = valid_users[0]
                    s_str = start_time.strftime("%H:%M")
                    e_str = end_time.strftime("%H:%M")
                    date_str = reserve_date.strftime("%Y-%m-%d")
                    duplicate = next((
                        r for r in general_records
                        if parse_date(r.get("날짜")) == reserve_date
                        and to_min(r.get("시작시간")) == to_min(start_time)
                        and to_min(r.get("종료시간")) == to_min(end_time)
                        and r.get("대표학번", "").strip() == rep["id"]
                    ), None)
                    if duplicate:
                        st.warning("⚠️ 동일한 예약이 이미 처리되어 추가 저장하지 않았습니다.")
                    else:
                        others = ", ".join(
                            f"{p['name']}({p['id']})" for p in valid_users[1:]
                        )
                        ws1.append_row([date_str, s_str, e_str, rep["name"], rep["id"], others])
                        st.cache_data.clear()
                        st.session_state["general_success"] = True
                        st.rerun()
        except Exception as e:
            st.error(f"오류: {e}")


# ------------------------------------------------------------------
# 2. 정기대관 신청
# ------------------------------------------------------------------
with tab2:
    today = today_kst()
    month_start = today.replace(day=1)
    if today.month == 12:
        next_month = today.replace(year=today.year + 1, month=1, day=1)
    else:
        next_month = today.replace(month=today.month + 1, day=1)
    month_end = next_month - timedelta(days=1)

    st.markdown(
        """
        <div class="notice-box">
        <b>📢 정기대관 신청 안내</b><br><br>
        정기대관은 이번 달 안에서 신청 가능하며 선택한 요일마다 매주 반복됩니다.<br>
        대표자 학번은 추후 대관 관리에서 본인 예약을 조회·수정·취소할 때 사용됩니다.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(f"신청 가능 기간: {month_start} ~ {month_end}")

    with st.form("regular_form"):
        group_name = st.text_input("단체명", placeholder="예: 공공인재학부 스터디")
        rc1, rc2 = st.columns(2)
        with rc1:
            reg_name = st.text_input("대표자", placeholder="대표자 이름")
        with rc2:
            reg_id = st.text_input("대표자 학번", placeholder="학번")
        contact = st.text_input("연락처", placeholder="예: 010-0000-0000")
        reg_days = st.multiselect("요일", ["월", "화", "수", "목", "금", "토", "일"])
        tc1, tc2 = st.columns(2)
        with tc1:
            reg_start = st.time_input("시작시간", value=min_to_time(18 * 60), step=600)
        with tc2:
            reg_end = st.time_input("종료시간", value=min_to_time(21 * 60), step=600)
        purpose = st.text_area("사용목적", height=80, placeholder="예: 스터디, 회의 등")
        regular_submit = st.form_submit_button("정기대관 신청하기", type="primary")

    if regular_submit:
        s_min, e_min = to_min(reg_start), to_min(reg_end)
        dur = duration_minutes(s_min, e_min)
        if not group_name.strip():
            st.error("❌ 단체명을 입력해주세요.")
        elif not reg_name.strip():
            st.error("❌ 대표자를 입력해주세요.")
        elif not reg_id.strip():
            st.error("❌ 대표자 학번을 입력해주세요.")
        elif not contact.strip():
            st.error("❌ 연락처를 입력해주세요.")
        elif not reg_days:
            st.error("❌ 요일을 1개 이상 선택해주세요.")
        elif not purpose.strip():
            st.error("❌ 사용목적을 입력해주세요.")
        elif dur > 180:
            st.error("❌ 1회 이용 시간은 최대 3시간입니다.")
        elif dur < 10:
            st.error("❌ 최소 10분 이상 신청해주세요.")
        else:
            try:
                _, ws2, general_values, regular_values = load_fresh_values()
                general_records = general_records_from_values(general_values)
                regular_records = regular_records_from_values(regular_values)
                msg = find_schedule_conflict(
                    month_start, month_end, reg_days, s_min, e_min,
                    general_records, regular_records
                )
                if msg:
                    st.error(f"❌ 신청 불가: {msg}")
                else:
                    request_date = now_kst().strftime("%Y-%m-%d")
                    period_str = f"{month_start:%Y-%m-%d} ~ {month_end:%Y-%m-%d}"
                    days_str = ", ".join(reg_days)
                    time_str = f"{reg_start:%H:%M} ~ {reg_end:%H:%M}"
                    ws2.append_row([
                        request_date,
                        group_name.strip(),
                        reg_name.strip(),
                        contact.strip(),
                        period_str,
                        days_str,
                        time_str,
                        purpose.strip(),
                        reg_id.strip(),
                    ])
                    st.cache_data.clear()
                    st.session_state["regular_success"] = True
                    st.rerun()
            except Exception as e:
                st.error(f"오류: {e}")


# ------------------------------------------------------------------
# 3. 대관 관리
# ------------------------------------------------------------------
with tab3:
    st.markdown("### 🛠️ 대관 관리")
    st.caption("대표자로 신청한 이름과 학번을 입력하세요. KST 기준 현재 진행 중이거나 아직 종료되지 않은 예약만 조회됩니다.")

    q1, q2, q3 = st.columns([2, 2, 1])
    with q1:
        manage_name = st.text_input(
            "대표자 이름",
            value=st.session_state.get("manage_lookup_name", ""),
            key="manage_name_input",
        )
    with q2:
        manage_id = st.text_input(
            "대표자 학번",
            value=st.session_state.get("manage_lookup_id", ""),
            key="manage_id_input",
        )
    with q3:
        st.write("")
        st.write("")
        lookup_clicked = st.button("🔎 조회", type="primary", key="manage_lookup")

    if lookup_clicked:
        if not manage_name.strip() or not manage_id.strip():
            st.error("이름과 학번을 모두 입력해주세요.")
        else:
            refresh_management_results(manage_name.strip(), manage_id.strip())

    if st.session_state.get("manage_loaded"):
        qname = st.session_state.get("manage_lookup_name", "")
        qid = st.session_state.get("manage_lookup_id", "")
        general_matches = st.session_state.get("manage_general_matches", [])
        regular_matches = st.session_state.get("manage_regular_matches", [])

        if not general_matches and not regular_matches:
            st.info("조회된 현재/향후 대관 내역이 없습니다.")
        else:
            st.markdown(f"#### {qname}님의 대관 내역")

        if general_matches:
            st.markdown("##### 📅 일반예약")

        for idx, rec in enumerate(general_matches):
            current_date = parse_date(rec.get("날짜"))
            if not current_date:
                continue
            current_s = to_min(rec.get("시작시간"))
            current_e = to_min(rec.get("종료시간"))
            title = f"{current_date:%Y-%m-%d}({get_day_korean(current_date)}) · {rec.get('시작시간')} ~ {rec.get('종료시간')}"

            with st.expander(title, expanded=False):
                st.caption(f"동반인원: {rec.get('동반인원','') or '없음'}")
                with st.form(f"general_edit_{idx}_{rec.get('_row')}"):
                    ec1, ec2, ec3 = st.columns([1.2, 1, 1])
                    with ec1:
                        min_date = min(today_kst(), current_date)
                        new_date = st.date_input(
                            "대관 일자",
                            value=current_date,
                            min_value=min_date,
                            max_value=today_kst() + timedelta(weeks=3),
                            key=f"g_edit_date_{idx}_{rec.get('_row')}",
                        )
                    with ec2:
                        new_start = st.time_input(
                            "시작시간", value=min_to_time(current_s), step=600,
                            key=f"g_edit_start_{idx}_{rec.get('_row')}"
                        )
                    with ec3:
                        new_end = st.time_input(
                            "종료시간", value=min_to_time(current_e), step=600,
                            key=f"g_edit_end_{idx}_{rec.get('_row')}"
                        )
                    save_general = st.form_submit_button("💾 변경 저장", type="primary")

                if save_general:
                    try:
                        ws1, _, gv, rv = load_fresh_values()
                        fresh_general = general_records_from_values(gv)
                        fresh_regular = regular_records_from_values(rv)
                        actual = find_matching_general_row(fresh_general, rec)
                        if not actual or actual.get("대표자명") != qname or actual.get("대표학번") != qid:
                            set_flash("예약 정보가 이미 변경되었거나 찾을 수 없습니다. 다시 조회해주세요.", "error")
                        else:
                            attendees = attendees_from_general(actual)
                            msg = validate_general_candidate(
                                new_date, new_start, new_end, attendees,
                                fresh_general, fresh_regular,
                                exclude_row=actual.get("_row")
                            )
                            if msg:
                                set_flash(f"변경 불가: {msg}", "error")
                            else:
                                row_no = actual["_row"]
                                ws1.update(
                                    f"A{row_no}:F{row_no}",
                                    [[
                                        new_date.strftime("%Y-%m-%d"),
                                        new_start.strftime("%H:%M"),
                                        new_end.strftime("%H:%M"),
                                        actual.get("대표자명", ""),
                                        actual.get("대표학번", ""),
                                        actual.get("동반인원", ""),
                                    ]],
                                )
                                st.cache_data.clear()
                                refresh_management_results(qname, qid)
                                set_flash("일반예약이 변경되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"변경 중 오류: {e}")

                confirm_key = f"g_cancel_confirm_{idx}_{rec.get('_row')}"
                confirm = st.checkbox("이 예약을 취소하겠습니다.", key=confirm_key)
                if st.button("🗑️ 예약 취소", key=f"g_cancel_{idx}_{rec.get('_row')}", disabled=not confirm):
                    try:
                        ws1, _, gv, _ = load_fresh_values()
                        actual = find_matching_general_row(general_records_from_values(gv), rec)
                        if not actual or actual.get("대표자명") != qname or actual.get("대표학번") != qid:
                            set_flash("예약 정보가 이미 변경되었거나 찾을 수 없습니다. 다시 조회해주세요.", "error")
                        else:
                            ws1.delete_rows(actual["_row"])
                            st.cache_data.clear()
                            refresh_management_results(qname, qid)
                            set_flash("일반예약이 취소되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"취소 중 오류: {e}")

        if regular_matches:
            st.markdown("##### 📝 정기대관")

        for idx, rec in enumerate(regular_matches):
            p_start, p_end = parse_period(rec.get("사용기간", ""))
            s_min, e_min = parse_time_range(rec.get("사용시간", ""))
            days = normalize_days(rec.get("요일", ""))
            if not p_start or not p_end or s_min is None or e_min is None:
                continue

            title = f"{rec.get('단체명','정기대관')} · 매주 {rec.get('요일','')} · {rec.get('사용시간','')}"
            with st.expander(title, expanded=False):
                st.caption(f"현재 사용기간: {rec.get('사용기간','')} / 사용목적: {rec.get('사용목적','')}")
                with st.form(f"regular_edit_{idx}_{rec.get('_row')}"):
                    pc1, pc2 = st.columns(2)
                    with pc1:
                        new_period_start = st.date_input(
                            "사용 시작일", value=p_start,
                            key=f"r_edit_ps_{idx}_{rec.get('_row')}"
                        )
                    with pc2:
                        new_period_end = st.date_input(
                            "사용 종료일", value=p_end,
                            key=f"r_edit_pe_{idx}_{rec.get('_row')}"
                        )
                    new_days = st.multiselect(
                        "요일", ["월", "화", "수", "목", "금", "토", "일"],
                        default=days,
                        key=f"r_edit_days_{idx}_{rec.get('_row')}"
                    )
                    rtc1, rtc2 = st.columns(2)
                    with rtc1:
                        new_reg_start = st.time_input(
                            "시작시간", value=min_to_time(s_min), step=600,
                            key=f"r_edit_start_{idx}_{rec.get('_row')}"
                        )
                    with rtc2:
                        new_reg_end = st.time_input(
                            "종료시간", value=min_to_time(e_min), step=600,
                            key=f"r_edit_end_{idx}_{rec.get('_row')}"
                        )
                    save_regular = st.form_submit_button("💾 정기대관 변경 저장", type="primary")

                if save_regular:
                    ns, ne = to_min(new_reg_start), to_min(new_reg_end)
                    dur = duration_minutes(ns, ne)
                    error = ""
                    if new_period_start > new_period_end:
                        error = "사용 시작일은 종료일보다 늦을 수 없습니다."
                    elif new_period_start.year != new_period_end.year or new_period_start.month != new_period_end.month:
                        error = "정기대관 사용기간은 같은 달 안에서 설정해주세요."
                    elif not new_days:
                        error = "요일을 1개 이상 선택해주세요."
                    elif dur > 180:
                        error = "1회 이용 시간은 최대 3시간입니다."
                    elif dur < 10:
                        error = "최소 10분 이상 이용해야 합니다."

                    try:
                        if error:
                            set_flash(f"변경 불가: {error}", "error")
                        else:
                            _, ws2, gv, rv = load_fresh_values()
                            fresh_general = general_records_from_values(gv)
                            fresh_regular = regular_records_from_values(rv)
                            actual = find_matching_regular_row(fresh_regular, rec)
                            if not actual or actual.get("대표자") != qname or actual.get("대표학번") != qid:
                                set_flash("정기대관 정보가 이미 변경되었거나 찾을 수 없습니다. 다시 조회해주세요.", "error")
                            else:
                                msg = find_schedule_conflict(
                                    new_period_start, new_period_end, new_days, ns, ne,
                                    fresh_general, fresh_regular,
                                    exclude_regular_row=actual.get("_row")
                                )
                                if msg:
                                    set_flash(f"변경 불가: {msg}", "error")
                                else:
                                    row_no = actual["_row"]
                                    ws2.update(
                                        f"A{row_no}:I{row_no}",
                                        [[
                                            actual.get("신청일", ""),
                                            actual.get("단체명", ""),
                                            actual.get("대표자", ""),
                                            actual.get("연락처", ""),
                                            f"{new_period_start:%Y-%m-%d} ~ {new_period_end:%Y-%m-%d}",
                                            ", ".join(new_days),
                                            f"{new_reg_start:%H:%M} ~ {new_reg_end:%H:%M}",
                                            actual.get("사용목적", ""),
                                            actual.get("대표학번", ""),
                                        ]],
                                    )
                                    st.cache_data.clear()
                                    refresh_management_results(qname, qid)
                                    set_flash("정기대관이 변경되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"정기대관 변경 중 오류: {e}")

                confirm = st.checkbox(
                    "이 정기대관 전체를 취소하겠습니다.",
                    key=f"r_cancel_confirm_{idx}_{rec.get('_row')}"
                )
                if st.button(
                    "🗑️ 정기대관 전체 취소",
                    key=f"r_cancel_{idx}_{rec.get('_row')}",
                    disabled=not confirm,
                ):
                    try:
                        _, ws2, _, rv = load_fresh_values()
                        actual = find_matching_regular_row(regular_records_from_values(rv), rec)
                        if not actual or actual.get("대표자") != qname or actual.get("대표학번") != qid:
                            set_flash("정기대관 정보가 이미 변경되었거나 찾을 수 없습니다. 다시 조회해주세요.", "error")
                        else:
                            ws2.delete_rows(actual["_row"])
                            st.cache_data.clear()
                            refresh_management_results(qname, qid)
                            set_flash("정기대관이 취소되었습니다.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"정기대관 취소 중 오류: {e}")

        st.caption("※ 기존 정기대관 중 대표학번이 저장되지 않은 과거 신청은 관리 조회에 나타나지 않습니다.")
