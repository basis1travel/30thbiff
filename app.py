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
    # Read data, interpreting all columns as strings initially
    df = get_as_dataframe(worksheet, usecols=None, header=0, dtype=str)
    # Replace any lingering pandas/numpy specific null values with empty strings
    df.replace({pd.NA: "", float('nan'): "", 'nan': ''}, inplace=True)
    # Ensure all data is string type and fill any remaining nulls
    df = df.astype(str).fillna("")
    return df

def save_data(worksheet, df):
    worksheet.clear()
    set_with_dataframe(worksheet, df, include_index=False, resize=True)

# --- Streamlit UI ---
st.set_page_config(page_title="부산 커플 여행 플래너", layout="wide")

if not check_password():
    st.stop()




st.title("💘 30회 BIFF 4박 5일 커플 여행 플래너 (Google Sheets 연동)")

try:
    gspread_client = get_gspread_client()
    spreadsheet = get_spreadsheet(gspread_client)

    overview_headers = ["key", "value"]
    acc_headers = ["숙소명", "위치", "예상 비용", "장점", "예약링크", "상태"]
    act_headers = ["활동명", "장소", "예상 비용", "소요시간", "메모"]
    movies_headers = ["영화 제목", "감독", "상영 일시", "상영관", "예매 여부"]
    events_headers = [
        "No.", "상호", "예약계획", "방문일자", "방문요일", "예약시간", "방문시간", 
        "Schedule", "플랫폼", "종류", "술", "콜/프", "포스팅마감일자", "웹페이지", 
        "지원내역", "예약가능일시", "방문전특이사항", "월", "화", "수", "목", "금", 
        "토", "일", "주소", "위치설명", "권역", "세부권역", "주문메뉴", "지원비용", 
        "추가비용", "방문후특이사항", "뿡이별점", "뿡이코멘트", "쁜찬별점", "쁜찬코멘트"
    ]
    
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

    # Load 2024 data for the new tab
    ws_2024 = create_sheet_if_not_exists(spreadsheet, "biff_2024", [])
    df_2024 = load_data(ws_2024)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["여행 개요", "📝 계획 버퍼", "🎬 영화 목록", "🗺️ 작년 여행 돌아보기", "🗓️ 상세 일정", "✨ 체험단"])

    with tab1:
        st.header("📌 여행 개요")
        if 'key' in df_overview.columns and 'value' in df_overview.columns:
            overview_data = dict(zip(df_overview['key'], df_overview['value']))
        else:
            overview_data = {}
        title = st.text_input("여행 제목", value=overview_data.get("title", "제30회 부산국제영화제(BIFF) 커플 여행"))
        purpose = st.text_input("여행 목적", value=overview_data.get("purpose", "BIFF 영화 관람, 부산 관광 및 커플 여행"))
        col1, col2 = st.columns(2)
        with col1:
            start_date = st.text_input("여행 시작일", value=overview_data.get("start_date", "2025-09-18"), disabled=True)
        with col2:
            end_date = st.text_input("여행 종료일", value=overview_data.get("end_date", "2025-09-23"), disabled=True)
        
        if st.button("💾 여행 개요 저장하기", key="save_overview"):
            new_overview_data = {"title": title, "purpose": purpose, "start_date": start_date, "end_date": end_date}
            df_overview_new = pd.DataFrame(new_overview_data.items(), columns=['key', 'value'])
            save_data(ws_overview, df_overview_new)
            st.success("✅ 여행 개요가 저장되었습니다!")
            st.experimental_rerun()

    with tab2:
        st.header("📝 계획 버퍼 (아이디어)")
        with st.expander("💡 여행 가이드라인 보기", expanded=True):
            st.subheader("📍 부산 지역별 중요도 (Tier List)")
            st.markdown("""
            - **1티어**: 광안리, 센텀
            - **2티어**: 부산역, 서면, 해운대
            - **3어**: 남포동+자갈치, 미포, 청사포, 송정
            - **4티어**: 송도, 기장 (부산 가깝거나, 역 근처 or 센텀가는 버스가 많은 곳)
            - **5티어**: 다대포, 영도(태종대), 금련산(범어사), 기장 (부산 멀고 접근성 떨어지는 곳)
            
            *5티어로 갈수록 영화제와 함께 즐기려면 시간과 체력을 더 많이 써야 합니다.*
            """)
            st.subheader("🍽️ 맛집/명소 탐방 가이드")
            st.markdown("부산 지역 명물 맛집, 시장 로컬 맛집, 명소/구경거리 등을 아래 '하고 싶은 것들'에 후보로 추가하여 계획해보세요.")
        
        st.divider()
        st.subheader("🏨 숙소 예비 후보")
        df_acc_new = st.data_editor(df_acc, num_rows="dynamic", use_container_width=True, key="acc_editor")
        if st.button("💾 숙소 후보 저장하기", key="save_acc"):
            save_data(ws_acc, df_acc_new)
            st.success("✅ 숙소 예비 후보 목록이 저장되었습니다!")
            st.experimental_rerun()

        st.divider()
        st.subheader("📋 하고 싶은 것들 (엑티비티)")
        df_act_new = st.data_editor(df_act, num_rows="dynamic", use_container_width=True, key="act_editor")
        if st.button("💾 하고 싶은 것들 저장하기", key="save_act"):
            save_data(ws_act, df_act_new)
            st.success("✅ 하고 싶은 것들 목록이 저장되었습니다!")
            st.experimental_rerun()

    with tab3:
        st.header("🎬 관람 희망 영화 리스트")
        df_movies_new = st.data_editor(
            df_movies, num_rows="dynamic", use_container_width=True, key="movies_editor",
            column_config={"예매 여부": st.column_config.CheckboxColumn("예매 여부", default=False)}
        )
        if st.button("💾 영화 목록 저장하기", key="save_movies"):
            save_data(ws_movies, df_movies_new)
            st.success("✅ 영화 목록이 저장되었습니다!")
            st.experimental_rerun()

    with tab4:
        st.header("🗺️ 작년 여행 돌아보기 (2024)")

        if df_2024.empty or '상호' not in df_2024.columns:
            st.warning("작년 여행 데이터가 'biff_2024' 시트에 없거나 형식이 맞지 않습니다.")
        else:
            # Data Preprocessing
            df_2024_filtered = df_2024[df_2024['상호'].notna() & (df_2024['상호'] != '')].copy()
            df_2024_filtered['지원비용'] = pd.to_numeric(df_2024_filtered['지원비용'], errors='coerce').fillna(0)
            df_2024_filtered['추가비용'] = pd.to_numeric(df_2024_filtered['추가비용'], errors='coerce').fillna(0)
            df_2024_filtered['총비용'] = df_2024_filtered['지원비용'] + df_2024_filtered['추가비용']
            
            # --- 1. Highlights ---
            st.subheader("👑 작년 여행 하이라이트")
            total_places = len(df_2024_filtered)
            total_spent = df_2024_filtered['총비용'].sum()
            
            col1, col2 = st.columns(2)
            col1.metric("총 방문 장소", f"{total_places} 곳")
            col2.metric("총 지출 (추정)", f"{int(total_spent):,} 원")

            st.divider()

            # --- 2. Interactive Map ---
            st.subheader("🗺️ 인터랙티브 방문 지도")
            map_data = df_2024_filtered[df_2024_filtered['주소'].notna() & (df_2024_filtered['주소'] != '')]
            
            if not map_data.empty and '주소' in map_data.columns:
                # Create a perfectly clean, single-column DataFrame for st.map
                address_df = map_data[['주소']].reset_index(drop=True)
                st.map(address_df, zoom=11)
            else:
                st.info("지도에 표시할 주소 데이터가 없습니다.")

            st.divider()

            # --- 3. Daily Timeline ---
            st.subheader("🗓️ 일자별 타임라인")
            df_2024_filtered['방문일자'] = pd.to_datetime(df_2024_filtered['방문일자'], errors='coerce')
            valid_dates_df = df_2024_filtered.dropna(subset=['방문일자'])
            
            for date in sorted(valid_dates_df['방문일자'].dt.date.unique()):
                with st.expander(f"**{date.strftime('%Y년 %m월 %d일')}**"):
                    day_df = valid_dates_df[valid_dates_df['방문일자'].dt.date == date]
                    for _, row in day_df.iterrows():
                        st.markdown(f"- **{row.get('방문시간', '')} - {row.get('상호', '')}** ({row.get('종류', '')})")
                        if row.get('주문메뉴', ''):
                            st.markdown(f"  - *주문:* {row.get('주문메뉴')}")
                        if row.get('총비용', 0) > 0:
                            st.markdown(f"  - *비용:* {int(row.get('총비용')):,} 원")


    with tab5:
        st.header("🗓️ 상세 일정")
        st.info("상세 일정은 Google Sheets에서 직접 편집하는 것이 더 편리할 수 있습니다.")

    with tab6:
        st.header("✨ 체험단 정보")
        df_events_new = st.data_editor(
            df_events, num_rows="dynamic", use_container_width=True, key="events_editor",
            column_config={
                "웹페이지": st.column_config.LinkColumn("웹페이지")
            }
        )
        if st.button("💾 체험단 정보 저장하기", key="save_events"):
            save_data(ws_events, df_events_new)
            st.success("✅ 체험단 정보가 저장되었습니다!")
            st.experimental_rerun()

except Exception as e:
    st.error(f"앱 로딩 중 오류가 발생했습니다. Google Sheets API 설정 및 Secrets 구성을 확인하세요.")
    st.error(f"오류 상세 내용: {e}")