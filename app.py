import streamlit as st
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials
import pandas as pd
from datetime import datetime, timedelta

# --- Google Sheets Connection ---

# Streamlit의 Secrets에서 Google Cloud 서비스 계정 키 정보를 가져옵니다.
def get_gspread_client():
    creds_dict = st.secrets["gcp_service_account"]
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

# 특정 이름의 스프레드시트와 워크시트를 엽니다.
def get_spreadsheet(client):
    spreadsheet_key = st.secrets["spreadsheet"]["key"]
    spreadsheet = client.open_by_key(spreadsheet_key)
    return spreadsheet

# --- Data Handling Functions ---

# 워크시트가 없으면 새로 만들고 헤더를 추가하는 함수
def create_sheet_if_not_exists(spreadsheet, sheet_name, headers):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols="20")
        worksheet.append_row(headers)
    return worksheet

# 워크시트에서 데이터를 DataFrame으로 로드하는 함수
def load_data(worksheet):
    # gspread-dataframe을 사용하여 로드하고, 헤더는 첫 번째 행으로 사용
    df = get_as_dataframe(worksheet, usecols=None, header=0)
    # NaN 값을 빈 문자열로 변환
    df = df.fillna("")
    return df

# DataFrame을 워크시트에 저장하는 함수
def save_data(worksheet, df):
    # 기존 내용 지우고 DataFrame으로 새로 쓰기
    worksheet.clear()
    set_with_dataframe(worksheet, df)

# --- Streamlit UI ---
st.set_page_config(page_title="부산 커플 여행 플래너", layout="wide")
st.title("💘 30회 BIFF 4박 5일 커플 여행 플래너 (Google Sheets 연동)")

try:
    # Google Sheets에 연결
    gspread_client = get_gspread_client()
    spreadsheet = get_spreadsheet(gspread_client)

    # 각 탭에 해당하는 워크시트 준비 (없으면 생성)
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

    # 데이터 로드
    df_overview = load_data(ws_overview)
    df_acc = load_data(ws_acc)
    df_act = load_data(ws_act)
    df_movies = load_data(ws_movies)
    df_events = load_data(ws_events)

    # --- UI Tabs ---
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["여행 개요", "📝 계획 버퍼", "🎬 영화 목록", "🗺️ 상세 일정", "✨ 이벤트/체험단"])

    with tab1:
        st.header("📌 여행 개요")
        
        # overview 데이터를 key-value 형태에서 다루기 쉽게 딕셔너리로 변환
        overview_data = dict(zip(df_overview['key'], df_overview['value']))

        title = st.text_input("여행 제목", value=overview_data.get("title", "제30회 부산국제영화제(BIFF) 커플 여행"))
        purpose = st.text_input("여행 목적", value=overview_data.get("purpose", "BIFF 영화 관람, 부산 관광 및 커플 여행"))
        
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.text_input("여행 시작일", value=overview_data.get("start_date", "2025-09-18"), disabled=True)
        with col2:
            end_date = st.text_input("여행 종료일", value=overview_data.get("end_date", "2025-09-23"), disabled=True)
        
        # 수정된 overview 데이터를 다시 DataFrame으로 변환 준비
        new_overview_data = {
            "title": title, "purpose": purpose, "start_date": start_date, "end_date": end_date
        }
        df_overview_new = pd.DataFrame(new_overview_data.items(), columns=['key', 'value'])


    with tab2:
        st.header("📝 계획 버퍼 (아이디어)")
        # ... (기존 가이드라인 UI는 그대로 유지)
        with st.expander("💡 여행 가이드라인 보기", expanded=True):
            st.subheader("📍 부산 지역별 중요도 (Tier List)")
            st.markdown("""
            - **1티어**: 광안리, 센텀
            - **2티어**: 부산역, 서면, 해운대
            - **3티어**: 남포동+자갈치, 미포, 청사포, 송정
            - **4어**: 송도, 기장 (부산 가깝거나, 역 근처 or 센텀가는 버스가 많은 곳)
            - **5티어**: 다대포, 영도(태종대), 금련산(범어사), 기장 (부산 멀고 접근성 떨어지는 곳)
            """)
        
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
        # 상세 일정은 복잡한 UI이므로 직접 연동보다는 안내 메시지 표시

    with tab5:
        st.header("✨ 체험단 및 이벤트 신청 정보")
        df_events_new = st.data_editor(
            df_events, num_rows="dynamic", use_container_width=True, key="events_editor",
            column_config={
                "상태": st.column_config.SelectboxColumn("상태", options=["준비", "신청 완료", "선정", "탈락"], required=True),
                "신청 방법": st.column_config.LinkColumn("신청 방법 (URL)")
            }
        )

    # --- Save Button ---
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
    st.error(e)