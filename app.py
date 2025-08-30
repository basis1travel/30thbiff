import streamlit as st
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials
import pandas as pd

# --- Password Protection ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]  # Don't store password.
        else:
            st.session_state["password_correct"] = False

    if "password_correct" not in st.session_state:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        return False
    elif not st.session_state["password_correct"]:
        st.text_input("Password", type="password", on_change=password_entered, key="password")
        st.error("😕 Password incorrect")
        return False
    else:
        return True

# --- Google Sheets Connection ---
def get_gspread_client():
    creds_dict = st.secrets["google_credentials"]["gcp"]
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

def get_spreadsheet(client):
    spreadsheet_key = st.secrets["google_credentials"]["spreadsheet_key"]
    spreadsheet = client.open_by_key(spreadsheet_key)
    return spreadsheet

# --- Data Handling Functions ---
def create_sheet_if_not_exists(spreadsheet, sheet_name, headers):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="20")
        worksheet.append_row(headers)
    return worksheet

def load_data(worksheet):
    df = get_as_dataframe(worksheet, usecols=None, header=0).astype(str)
    df = df.fillna("")
    return df

def save_data(worksheet, df):
    worksheet.clear()
    set_with_dataframe(worksheet, df, include_index=False, resize=True)

# --- Streamlit UI ---
st.set_page_config(page_title="부산 커플 여행 플래너", layout="wide")

if not check_password():
    st.stop()

# --- Secrets Debugging ---
st.subheader("⚙️ Secrets 디버깅 정보")
secrets_ok = True
if "google_credentials" not in st.secrets:
    st.error("❌ Secrets에 `[google_credentials]` 섹션이 없습니다.")
    secrets_ok = False
else:
    st.success("✅ Secrets에 `[google_credentials]` 섹션이 있습니다.")
    
    if "spreadsheet_key" not in st.secrets["google_credentials"]:
        st.error("❌ `[google_credentials]` 안에 `spreadsheet_key` 항목이 없습니다.")
        secrets_ok = False
    else:
        st.success("✅ `[google_credentials]` 안에 `spreadsheet_key` 항목이 있습니다.")

    if "gcp" not in st.secrets["google_credentials"]:
        st.error("❌ `[google_credentials]` 안에 `[google_credentials.gcp]` 하위 섹션이 없습니다.")
        secrets_ok = False
    else:
        st.success("✅ `[google_credentials]` 안에 `[google_credentials.gcp]` 하위 섹션이 있습니다.")
        gcp_keys = st.secrets["google_credentials"]["gcp"].keys()
        expected_keys = ["type", "project_id", "private_key_id", "private_key", "client_email", "client_id"]
        missing_keys = [key for key in expected_keys if key not in gcp_keys]
        if missing_keys:
            st.error(f"❌ `[gcp]` 섹션에 다음 항목들이 누락되었습니다: {', '.join(missing_keys)}")
            secrets_ok = False
        else:
            st.success("✅ `[gcp]` 섹션에 필요한 모든 항목이 존재합니다.")

if not secrets_ok:
    st.warning("위의 디버깅 정보를 확인하여 Streamlit Secrets 설정을 수정해주세요.")
    st.stop()
# --- End of Debugging ---


st.title("💘 30회 BIFF 4박 5일 커플 여행 플래너 (Google Sheets 연동)")

try:
    gspread_client = get_gspread_client()
    spreadsheet = get_spreadsheet(gspread_client)

    overview_headers = ["key", "value"]
    acc_headers = ["숙소명", "위치", "예상 비용", "장점", "예약링크", "상태"]
    act_headers = ["활동명", "장소", "예상 비용", "소요시간", "메모"]
    movies_headers = ["영화 제목", "감독", "상영 일시", "상영관", "예매 여부"]
    events_headers = ["플랫폼", "업체/내용", "신청 기간", "결과 발표일", "리뷰 마감일", "상태", "신청 방법"]
    
    ws_overview = create_sheet_if_not_exists(spreadsheet, "overview", overview_headers)
    ws_acc = create_sheet_if_not_exists(spreadsheet, "accommodation_candidates", acc_headers)
    ws_act = create_sheet_if_not_exists(spreadsheet, "activity_candidates", act_headers)
    ws_movies = create_sheet_if_not_exists(spreadsheet, "movies", movies_headers)
    ws_events = create_sheet_if_not_exists(spreadsheet, "events", events_headers)

    df_overview = load_data(ws_overview)
    df_acc = load_data(ws_acc)
    df_act = load_data(ws_act)
    df_movies = load_data(ws_movies)
    df_events = load_data(ws_events)

    tab1, tab2, tab3, tab4, tab5 = st.tabs(["여행 개요", "📝 계획 버퍼", "🎬 영화 목록", "🗺️ 상세 일정", "✨ 이벤트/체험단"])

    with tab1:
        st.header("📌 여행 개요")
        
        # Defensive coding: Check if required columns exist before processing
        if 'key' in df_overview.columns and 'value' in df_overview.columns:
            overview_data = dict(zip(df_overview['key'], df_overview['value']))
        else:
            overview_data = {} # Prevent error if sheet is empty

        title = st.text_input("여행 제목", value=overview_data.get("title", "제30회 부산국제영화제(BIFF) 커플 여행"))
        purpose = st.text_input("여행 목적", value=overview_data.get("purpose", "BIFF 영화 관람, 부산 관광 및 커플 여행"))
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.text_input("여행 시작일", value=overview_data.get("start_date", "2025-09-18"), disabled=True)
        with col2:
            end_date = st.text_input("여행 종료일", value=overview_data.get("end_date", "2025-09-23"), disabled=True)
        new_overview_data = {"title": title, "purpose": purpose, "start_date": start_date, "end_date": end_date}
        df_overview_new = pd.DataFrame(new_overview_data.items(), columns=['key', 'value'])

    with tab2:
        st.header("📝 계획 버퍼 (아이디어)")
        with st.expander("💡 여행 가이드라인 보기", expanded=True):
            st.subheader("📍 부산 지역별 중요도 (Tier List)")
            st.markdown("""
            - **1티어**: 광안리, 센텀
            - **2티어**: 부산역, 서면, 해운대
            - **3티어**: 남포동+자갈치, 미포, 청사포, 송정
            - **4티어**: 송도, 기장 (부산 가깝거나, 역 근처 or 센텀가는 버스가 많은 곳)
            - **5티어**: 다대포, 영도(태종대), 금련산(범어사), 기장 (부산 멀고 접근성 떨어지는 곳)
            
            *5티어로 갈수록 영화제와 함께 즐기려면 시간과 체력을 더 많이 써야 합니다.*
            """)
            st.subheader("🍽️ 맛집/명소 탐방 가이드")
            st.markdown("부산 지역 명물 맛집, 시장 로컬 맛집, 명소/구경거리 등을 아래 '하고 싶은 것들'에 후보로 추가하여 계획해보세요.")
        
        st.divider()
        st.subheader("🏨 숙소 예비 후보")
        df_acc_new = st.data_editor(df_acc, num_rows="dynamic", use_container_width=True, key="acc_editor")
        st.divider()
        st.subheader("📋 하고 싶은 것들 (엑티비티)")
        df_act_new = st.data_editor(df_act, num_rows="dynamic", use_container_width=True, key="act_editor")

    with tab3:
        st.header("🎬 관람 희망 영화 리스트")
        df_movies_new = st.data_editor(
            df_movies, num_rows="dynamic", use_container_width=True, key="movies_editor",
            column_config={"예매 여부": st.column_config.CheckboxColumn("예매 여부", default=False)}
        )

    with tab4:
        st.header("🗺️ 일자별 상세 계획")
        st.info("상세 일정은 Google Sheets에서 직접 편집하는 것이 더 편리할 수 있습니다.")

    with tab5:
        st.header("✨ 체험단 및 이벤트 신청 정보")
        df_events_new = st.data_editor(
            df_events, num_rows="dynamic", use_container_width=True, key="events_editor",
            column_config={
                "상태": st.column_config.SelectboxColumn("상태", options=["준비", "신청 완료", "선정", "탈락"], required=True),
                "신청 방법": st.column_config.LinkColumn("신청 방법 (URL)")
            }
        )

    st.sidebar.header("저장하기")
    if st.sidebar.button("💾 변경사항 Google Sheets에 저장하기"):
        try:
            save_data(ws_overview, df_overview_new)
            save_data(ws_acc, df_acc_new)
            save_data(ws_act, df_act_new)
            save_data(ws_movies, df_movies_new)
            save_data(ws_events, df_events_new)
            st.sidebar.success("✅ 모든 변경사항이 Google Sheets에 저장되었습니다!")
            st.experimental_rerun()
        except Exception as e:
            st.sidebar.error(f"저장 중 오류 발생: {e}")

except Exception as e:
    st.error(f"앱 로딩 중 오류가 발생했습니다. Google Sheets API 설정 및 Secrets 구성을 확인하세요.")
    st.error(f"오류 상세 내용: {e}")