import streamlit as st
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from google.oauth2.service_account import Credentials
import pandas as pd
from geopy.geocoders import Nominatim
import time
import pydeck as pdk
import re
import requests
from bs4 import BeautifulSoup

# --- Password Protection ---
def check_password():
    """Returns `True` if the user had the correct password."""
    def password_entered():
        """Checks whether a password entered by the user is correct."""
        if st.session_state["password"] == st.secrets["APP_PASSWORD"]:
            st.session_state["password_correct"] = True
            del st.session_state["password"]
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

# --- Google Sheets Connection & Data Handling ---
@st.cache_resource
def get_gspread_client():
    creds_dict = st.secrets["google_credentials"]["gcp"]
    scopes = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client

@st.cache_resource
def get_spreadsheet(_client):
    spreadsheet_key = st.secrets["google_credentials"]["spreadsheet_key"]
    spreadsheet = _client.open_by_key(spreadsheet_key)
    return spreadsheet

def create_sheet_if_not_exists(spreadsheet, sheet_name, headers):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows="100", cols=len(headers) if headers else 20)
        if headers:
            worksheet.append_row(headers)
    return worksheet

@st.cache_data(ttl=600) # Cache data for 10 minutes
def load_data(_worksheet):
    return get_as_dataframe(_worksheet, usecols=None, header=0, dtype=str).fillna("")

def save_data(worksheet, df):
    worksheet.clear()
    set_with_dataframe(worksheet, df, include_index=False, resize=True)
    # Clear relevant caches after saving data
    st.cache_data.clear()


# --- Geocoding Function ---
@st.cache_data
def geocode_address(address, name):
    """
    Geocodes an address string to latitude and longitude.
    Falls back to name if address geocoding fails.
    """
    # 1st try: Address
    if address and not pd.isna(address) and str(address).strip():
        try:
            clean_address = address.split('(')[0].strip()
            query = f"부산 {clean_address}"
            geolocator = Nominatim(user_agent="biff_planner_app")
            location = geolocator.geocode(query, timeout=10)
            time.sleep(1)
            if location:
                return location.latitude, location.longitude
        except Exception:
            pass # Fallback to name

    # 2nd try: Name
    if name and not pd.isna(name) and str(name).strip():
        try:
            clean_name = name.split('(')[0].strip()
            query = f"부산 {clean_name}"
            geolocator = Nominatim(user_agent="biff_planner_app")
            location = geolocator.geocode(query, timeout=10)
            time.sleep(1)
            if location:
                return location.latitude, location.longitude
        except Exception:
            return None, None
            
    return None, None


# --- BIFF Movie Crawling Function ---
@st.cache_data
def fetch_movie_info(url):
    # ... (crawl_biff.py의 함수를 그대로 가져옴)
    try:
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')

        title_tag = soup.select_one(".film_info_title .tit_h1")
        if title_tag and title_tag.find('small'):
            title_tag.find('small').decompose()
        title_kor = title_tag.text.strip() if title_tag else ""

        base_info = {
            "한국어 제목": title_kor,
            "영어 제목": soup.select_one(".film_info_title .film_tit_en").text.strip() if soup.select_one(".film_info_title .film_tit_en") else "",
            "감독": soup.select_one(".film_director .dir_name").text.strip() if soup.select_one(".film_director .dir_name") else "",
            "Program Note": soup.select_one(".film_synopsis .desc").text.strip() if soup.select_one(".film_synopsis .desc") else ""
        }
        
        spec_list = soup.select(".film_info.film_tit ul > li")
        base_info["국가"] = spec_list[0].text.replace("국가", "").strip() if len(spec_list) > 0 else ""
        base_info["제작 연도"] = spec_list[1].text.replace("제작연도", "").strip() if len(spec_list) > 1 else ""
        base_info["러닝타임"] = spec_list[2].text.replace("러닝타임", "").strip() if len(spec_list) > 2 else ""
        base_info["상영포맷"] = spec_list[3].text.replace("상영포맷", "").strip() if len(spec_list) > 3 else ""
        base_info["컬러"] = spec_list[4].text.replace("컬러", "").strip() if len(spec_list) > 4 else ""
        
        hashtags = [tag.text.strip() for tag in soup.select(".film_tit .keywords")]
        for i in range(3):
            base_info[f"해시태그{i+1}"] = hashtags[i] if i < len(hashtags) else ""

        final_data_list = []
        schedule_tags = soup.select(".pgv_schedule .pgv_sch_list")
        for schedule in schedule_tags:
            schedule_info = base_info.copy()
            schedule_info.update({
                "예매코드": re.sub(r'\D', '', schedule.select_one(".code").text),
                "날짜": schedule.select_one(".date").text.replace("날짜", "").strip(),
                "시간": schedule.select_one(".time").text.replace("시간", "").strip(),
                "상영관": schedule.select_one(".theater").text.replace("상영관", "").strip(),
                "기타": " ".join([tag.text.strip() for tag in schedule.select(".sch_grade > span") if tag.text.strip()]),
                "영화페이지": url
            })
            final_data_list.append(schedule_info)
        
        return final_data_list if final_data_list else [base_info]
    except Exception:
        return None

# --- Streamlit UI ---
st.set_page_config(page_title="부산 커플 여행 플래너", layout="wide")

if not check_password():
    st.stop()

st.title("💘 30회 BIFF 4박 5일 커플 여행 플래너 (Google Sheets 연동)")

try:
    gspread_client = get_gspread_client()
    spreadsheet = get_spreadsheet(gspread_client)

    # Define headers and get worksheets
    overview_headers = ["key", "value"]
    acc_headers = ["숙소명", "위치", "예상 비용", "장점", "예약링크", "상태"]
    act_headers = ["활동명", "장소", "예상 비용", "소요시간", "메모"]
    movies_headers = ["한국어 제목", "영어 제목", "감독", "국가", "제작 연도", "러닝타임", "상영포맷", "컬러", "해시태그1", "해시태그2", "해시태그3", "예매코드", "날짜", "시간", "상영관", "기타", "예매우선순위", "예매성공여부", "영화페이지", "영화참고자료", "Program Note"]
    events_headers = [
        "No.", "상호", "예약계획", "방문일자", "방문요일", "예약시간", "방문시간", "Schedule", "플랫폼", "종류", "술", "콜/프", 
        "포스팅마감일자", "웹페이지", "지원내역", "예약가능일시", "방문전특이사항", "월", "화", "수", "목", "금", "토", "일", 
        "주소", "위치설명", "권역", "세부권역", "주문메뉴", "지원비용", "추가비용", "방문후특이사항", "뿡이별점", "뿡이코멘트", "쁜찬별점", "쁜찬코멘트"
    ]
    
    ws_overview = create_sheet_if_not_exists(spreadsheet, "overview", overview_headers)
    ws_acc = create_sheet_if_not_exists(spreadsheet, "accommodation_candidates", acc_headers)
    ws_act = create_sheet_if_not_exists(spreadsheet, "activity_candidates", act_headers)
    ws_movies = create_sheet_if_not_exists(spreadsheet, "movies", movies_headers)
    ws_events = create_sheet_if_not_exists(spreadsheet, "events", events_headers)
    ws_2024 = create_sheet_if_not_exists(spreadsheet, "biff_2024", [])

    # Load data
    df_overview = load_data(ws_overview)
    df_acc = load_data(ws_acc)
    df_act = load_data(ws_act)
    df_movies = load_data(ws_movies)
    df_events = load_data(ws_events)
    df_2024 = load_data(ws_2024)

    # --- UI Tabs ---
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
            st.rerun()

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
        if st.button("💾 숙소 후보 저장하기", key="save_acc"):
            save_data(ws_acc, df_acc_new)
            st.success("✅ 숙소 예비 후보 목록이 저장되었습니다!")
            st.rerun()
        st.divider()
        st.subheader("📋 하고 싶은 것들 (엑티비티)")
        df_act_new = st.data_editor(df_act, num_rows="dynamic", use_container_width=True, key="act_editor")
        if st.button("💾 하고 싶은 것들 저장하기", key="save_act"):
            save_data(ws_act, df_act_new)
            st.success("✅ 하고 싶은 것들 목록이 저장되었습니다!")
            st.rerun()

    with tab3:
        st.header("🎬 관람 희망 영화 리스트")
        st.info("BIFF 영화 정보 페이지 URL을 입력하고 '정보 가져오기' 버튼을 누르면, 아래 표에 상영 정보가 자동으로 추가됩니다.")
        
        url = st.text_input("영화 정보 페이지 URL을 붙여넣으세요:", key="movie_url")
        if st.button("정보 가져오기", key="fetch_movie"):
            if url:
                with st.spinner("영화 정보를 크롤링하는 중..."):
                    new_movie_data = fetch_movie_info(url)
                if new_movie_data:
                    new_df = pd.DataFrame(new_movie_data)
                    # 기존 데이터와 합치기 전에 세션 상태에 저장
                    st.session_state.new_movies_to_add = new_df.to_dict('records')
                    st.success(f"{len(new_movie_data)}개의 상영 일정을 찾았습니다! 아래 표에 임시로 추가되었습니다. 최종 저장을 위해 '영화 목록 저장하기' 버튼을 눌러주세요.")
                else:
                    st.error("정보를 가져오는 데 실패했습니다. URL을 확인하거나 사이트 구조가 변경되었을 수 있습니다.")
            else:
                st.warning("URL을 입력해주세요.")
        
        # 세션 상태에 추가할 영화 데이터가 있으면, 현재 표에 합쳐서 보여줌
        if 'new_movies_to_add' in st.session_state:
            new_movies_df = pd.DataFrame(st.session_state.new_movies_to_add)
            display_df = pd.concat([df_movies, new_movies_df], ignore_index=True).fillna('')
        else:
            display_df = df_movies

        st.divider()
        st.subheader("전체 영화 목록")
        df_movies_new = st.data_editor(display_df, num_rows="dynamic", use_container_width=True, key="movies_editor")
        
        if st.button("💾 영화 목록 저장하기", key="save_movies"):
            save_data(ws_movies, df_movies_new)
            # 저장 후 세션 상태 초기화
            if 'new_movies_to_add' in st.session_state:
                del st.session_state.new_movies_to_add
            st.success("✅ 영화 목록이 Google Sheets에 저장되었습니다!")
            st.rerun()

    with tab4:
        st.header("📊 2024년 여행 회고 및 분석")
        if df_2024.empty or '상호' not in df_2024.columns:
            st.warning("작년 여행 데이터가 'biff_2024' 시트에 없거나 형식이 맞지 않습니다.")

        # --- 데이터 전처리 ---
        data24 = df_2024[df_2024['상호'].notna() & (df_2024['상호'] != '') & (~df_2024['상호'].str.contains("Day", na=False))].copy()
        for col in ['지원비용', '추가비용']:
            data24[col] = pd.to_numeric(data24[col], errors='coerce').fillna(0)
        data24['총비용'] = data24['지원비용'] + data24['추가비용']
        
        # --- 1. 핵심 지표 (Key Metrics) ---
        st.subheader("👑 한눈에 보는 작년 여행")
        col1, col2, col3 = st.columns(3)
        col1.metric("총 지출액", f"{int(data24['총비용'].sum()):,} 원")
        col2.metric("실제 지출액 (내돈내산)", f"{int(data24['추가비용'].sum()):,} 원")
        col3.metric("체험단 지원 가치", f"{int(data24['지원비용'].sum()):,} 원")

        # --- 2. 지출 분석 ---
        st.subheader("💸 지출 분석")
        food_cats = ['돼지', '스시/회', '디저트', '소', '카페', '복어', '와인바', '샐러드/포케', '이자카야']
        data24['카테고리'] = data24['종류'].apply(lambda x: '식음료' if x in food_cats else ('교통' if x == '이동수단' else ('문화/예술' if x == '문화예술' else ('숙소' if x == '숙소' else '기타'))))
        spending_by_cat = data24.groupby('카테고리')['총비용'].sum().sort_values(ascending=False)
        st.bar_chart(spending_by_cat)

        # --- 3. 동선 및 지역 분석 ---
        st.subheader("🗺️ 동선 및 지역 분석")
        map_data = data24.copy()
        if 'lat' not in map_data.columns or 'lon' not in map_data.columns:
            map_data['lat'], map_data['lon'] = None, None
        
        rows_to_geocode = map_data[pd.to_numeric(map_data['lat'], errors='coerce').isna()]
        if not rows_to_geocode.empty:
            with st.spinner(f"{len(rows_to_geocode)}개 장소의 좌표 계산 중..."):
                for index, row in rows_to_geocode.iterrows():
                    lat, lon = geocode_address(row.get('주소'), row.get('상호'))
                    map_data.loc[index, 'lat'] = lat
                    map_data.loc[index, 'lon'] = lon
        
        map_data['lat'] = pd.to_numeric(map_data['lat'], errors='coerce')
        map_data['lon'] = pd.to_numeric(map_data['lon'], errors='coerce')
        st.map(map_data.dropna(subset=['lat', 'lon']), zoom=11)

        # --- 4. 시간 관리 분석 ---
        st.subheader("⏰ 시간 관리 분석")
        time_data = data24[['예약시간', '방문시간']].copy()
        time_data = time_data[time_data['예약시간'].str.strip().ne('') & time_data['방문시간'].str.strip().ne('')]
        if not time_data.empty:
            time_data['예약시간_dt'] = pd.to_datetime(time_data['예약시간'], format='%H:%M', errors='coerce')
            time_data['방문시간_dt'] = pd.to_datetime(time_data['방문시간'], format='%H:%M', errors='coerce')
            time_data.dropna(inplace=True)
            time_data['차이(분)'] = (time_data['방문시간_dt'] - time_data['예약시간_dt']).dt.total_seconds() / 60
            avg_diff = time_data['차이(분)'].mean()
            st.metric("평균 도착 시간", f"{'예약보다 ' + str(int(abs(avg_diff))) + '분 일찍' if avg_diff < 0 else '예약보다 ' + str(int(avg_diff)) + '분 늦게'}")



        # --- 데이터 전처리 ---
        data24 = df_2024[df_2024['상호'].notna() & (df_2024['상호'] != '') & (~df_2024['상호'].str.contains("Day", na=False))].copy()
        for col in ['지원비용', '추가비용']:
            data24[col] = pd.to_numeric(data24[col], errors='coerce').fillna(0)
        data24['총비용'] = data24['지원비용'] + data24['추가비용']
        data24['방문일자'] = pd.to_datetime(data24['방문일자'], errors='coerce')
        data24['방문시간_dt'] = pd.to_datetime(data24['방문시간'], format='%H:%M', errors='coerce')
        data24.sort_values(by=['방문일자', '방문시간_dt'], inplace=True)
        data24.dropna(subset=['방문일자'], inplace=True)

        # --- 날짜 선택기 ---
        unique_dates = sorted(data24['방문일자'].dt.date.unique())
        selected_date_str = st.selectbox("분석할 날짜를 선택하세요:", [d.strftime('%Y-%m-%d') for d in unique_dates])
        selected_date = pd.to_datetime(selected_date_str).date()

        day_df = data24[data24['방문일자'].dt.date == selected_date].copy()
        day_df.reset_index(drop=True, inplace=True)

        # --- 좌표 계산 ---
        if 'lat' not in day_df.columns or 'lon' not in day_df.columns:
            day_df['lat'], day_df['lon'] = None, None
        
        rows_to_geocode = day_df[pd.to_numeric(day_df['lat'], errors='coerce').isna()]
        if not rows_to_geocode.empty:
            with st.spinner(f"{len(rows_to_geocode)}개 장소의 좌표 계산 중..."):
                for index, row in rows_to_geocode.iterrows():
                    lat, lon = geocode_address(row.get('주소'), row.get('상호'))
                    day_df.loc[index, 'lat'] = lat
                    day_df.loc[index, 'lon'] = lon
        
        day_df['lat'] = pd.to_numeric(day_df['lat'], errors='coerce')
        day_df['lon'] = pd.to_numeric(day_df['lon'], errors='coerce')
        map_data = day_df.dropna(subset=['lat', 'lon']).copy()
        map_data.reset_index(drop=True, inplace=True)

        if map_data.empty:
            st.warning("선택한 날짜에 지도에 표시할 장소가 없습니다.")        

            # --- Pydeck 시각화 ---
        st.subheader(f"🗺️ {selected_date_str} 이동 경로")

        # 1. 경로 선 레이어 (시간에 따른 색상 변화)
        path_data = []
        for i in range(len(map_data) - 1):
            path_data.append({
                "start": [map_data.loc[i, 'lon'], map_data.loc[i, 'lat']],
                "end": [map_data.loc[i + 1, 'lon'], map_data.loc[i + 1, 'lat']],
                "color": [255, 0, 0, 255 - (i * (200 / len(map_data)))], # 점점 옅어지는 붉은색
                "tooltip": f"{i+1}. {map_data.loc[i, '상호']} -> {i+2}. {map_data.loc[i+1, '상호']}"
            })
        
        path_layer = pdk.Layer(
            "LineLayer",
            data=path_data,
            get_source_position="start",
            get_target_position="end",
            get_color="color",
            get_width=5,
            highlight_color=[255, 255, 0],
            picking_radius=10,
            auto_highlight=True,
        )

        # 2. 비용 기반 원 레이어
        scatter_layer = pdk.Layer(
            "ScatterplotLayer",
            data=map_data,
            get_position=["lon", "lat"],
            get_radius="총비용 * 0.2 + 50", # 비용에 따라 원 크기 조절
            get_fill_color=[30, 144, 255, 180], # 파란색 원
            pickable=True,
        )

        # 3. 순서 아이콘 레이어
        icon_data = []
        for i, row in map_data.iterrows():
            icon_data.append({
                "coordinates": [row['lon'], row['lat']],
                "text": str(i + 1),
                "tooltip": f"**{i+1}. {row['상호']}**\n- 종류: {row['종류']}\n- 총비용: {int(row['총비용']):,}원"
            })

        icon_layer = pdk.Layer(
            "TextLayer",
            data=icon_data,
            get_position="coordinates",
            get_text="text",
            get_size=20,
            get_color=[255, 255, 255],
            get_angle=0,
            get_text_anchor="'middle'",
            get_alignment_baseline="'center'",
        )

        # 지도 초기 시점 설정
        view_state = pdk.ViewState(
            latitude=map_data["lat"].mean(),
            longitude=map_data["lon"].mean(),
            zoom=12,
            pitch=45,
        )

        # 덱 렌더링
        r = pdk.Deck(
            layers=[scatter_layer, path_layer, icon_layer],
            initial_view_state=view_state,
            map_style="mapbox://styles/mapbox/light-v10",
            tooltip={"html": "{tooltip}", "style": {"color": "white"}},
        )
        st.pydeck_chart(r)

        # --- 경로 정보 요약 ---
        st.subheader("📝 경로 정보")
        for i, row in map_data.iterrows():
            st.markdown(f"**{i+1}. {row['상호']}** ({row['방문시간']}) - {int(row['총비용']):,}원")

    with tab5:
        st.header("🗓️ 상세 일정")
        st.info("상세 일정은 Google Sheets에서 직접 편집하는 것이 더 편리할 수 있습니다.")

    with tab6:
        st.header("✨ 체험단 정보")
        df_events_new = st.data_editor(
            df_events, num_rows="dynamic", use_container_width=True, key="events_editor",
            column_config={"웹페이지": st.column_config.LinkColumn("웹페이지")}
        )
        if st.button("💾 체험단 정보 저장하기", key="save_events"):
            save_data(ws_events, df_events_new)
            st.success("✅ 체험단 정보가 저장되었습니다!")
            st.rerun()

except Exception as e:
    st.error(f"앱 로딩 중 오류가 발생했습니다: {e}")