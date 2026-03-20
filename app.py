
import streamlit as st
import pandas as pd
import requests
import folium
from streamlit_folium import st_folium

# -----------------------------
# 기본 설정
# -----------------------------
st.set_page_config(
    page_title="서울 야간 명소 추천",
    page_icon="🌃",
    layout="wide"
)

SEOUL_CENTER = [37.5665, 126.9780]

CONGESTION_COLOR = {
    "여유": "green",
    "보통": "orange",
    "붐빔": "red"
}

CONGESTION_ICON = {
    "여유": "🟢",
    "보통": "🟠",
    "붐빔": "🔴"
}


# -----------------------------
# 1. CSV 로드
# -----------------------------
@st.cache_data
def load_spot_csv(csv_path: str) -> pd.DataFrame:
    """
    명소 CSV 파일 로드

    예시 필수 컬럼
    - spot_name
    - category
    - district
    - lat
    - lon
    - address
    - operation_hours
    - fee
    - transport
    - parking
    - description
    - api_place_name  # 서울시 API 장소명 매핑용
    """
    df = pd.read_csv(csv_path)
    return df


# -----------------------------
# 2. 서울시 실시간 인구 API 호출
# -----------------------------
def call_seoul_population_api(api_key: str, api_place_name: str) -> dict | None:
    """
    서울시 실시간 인구 API 1건 호출

    실제 엔드포인트는 네가 쓰는 API 형식에 맞게 수정
    """
    url = f"http://openapi.seoul.go.kr:8088/{api_key}/json/citydata_ppltn/1/5/{api_place_name}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"[API 오류] {api_place_name}: {e}")
        return None


def parse_population_response(raw_data: dict) -> dict | None:
    """
    서울시 API 응답에서 필요한 값만 추출
    실제 응답 구조에 따라 반드시 수정 필요
    """
    if not raw_data:
        return None

    citydata = raw_data.get("CITYDATA", {})
    live_list = citydata.get("LIVE_PPLTN_STTS", [])

    if not live_list:
        return None

    item = live_list[0] if isinstance(live_list, list) else live_list

    return {
        "api_place_name": citydata.get("AREA_NM"),
        "congestion": item.get("AREA_CONGEST_LVL"),
        "congestion_message": item.get("AREA_CONGEST_MSG"),
        "male_rate": item.get("MALE_PPLTN_RATE"),
        "female_rate": item.get("FEMALE_PPLTN_RATE"),
        "ppltn_min": item.get("AREA_PPLTN_MIN"),
        "ppltn_max": item.get("AREA_PPLTN_MAX"),
    }


@st.cache_data(ttl=300)
def fetch_live_population_batch(api_key: str, spot_df: pd.DataFrame) -> pd.DataFrame:
    """
    CSV 안의 api_place_name 컬럼 기준으로 실시간 인구 데이터 조회
    """
    results = []

    for _, row in spot_df.iterrows():
        api_place_name = row["api_place_name"]
        spot_name = row["spot_name"]

        raw_data = call_seoul_population_api(api_key, api_place_name)
        parsed = parse_population_response(raw_data)

        if parsed is None:
            results.append({
                "spot_name": spot_name,
                "api_place_name": api_place_name,
                "congestion": None,
                "congestion_message": None,
                "male_rate": None,
                "female_rate": None,
                "ppltn_min": None,
                "ppltn_max": None,
            })
        else:
            parsed["spot_name"] = spot_name
            results.append(parsed)

    return pd.DataFrame(results)


# -----------------------------
# 3. CSV + API 결합
# -----------------------------
def merge_spot_and_live_data(spot_df: pd.DataFrame, live_df: pd.DataFrame) -> pd.DataFrame:
    merged = spot_df.merge(
        live_df,
        on=["spot_name", "api_place_name"],
        how="left"
    )

    # API 값이 없으면 기본값 처리
    merged["congestion"] = merged["congestion"].fillna("정보없음")
    merged["congestion_message"] = merged["congestion_message"].fillna("실시간 정보 없음")

    return merged


# -----------------------------
# 4. 지도 생성
# -----------------------------
def make_map(df: pd.DataFrame, selected_spot: str | None = None):
    fmap = folium.Map(location=SEOUL_CENTER, zoom_start=11)

    for _, row in df.iterrows():
        congestion = row.get("congestion", "정보없음")
        color = CONGESTION_COLOR.get(congestion, "blue")
        radius = 12 if row["spot_name"] == selected_spot else 8

        popup_html = f"""
        <b>{row['spot_name']}</b><br>
        카테고리: {row.get('category', '-') }<br>
        혼잡도: {congestion}<br>
        운영시간: {row.get('operation_hours', '-')}<br>
        주소: {row.get('address', '-')}
        """

        folium.CircleMarker(
            location=[row["lat"], row["lon"]],
            radius=radius,
            color=color,
            fill=True,
            fill_opacity=0.8,
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=f"{row['spot_name']} ({congestion})"
        ).add_to(fmap)

    return fmap


# -----------------------------
# 5. 카드 UI
# -----------------------------
def render_spot_card(row: pd.Series):
    badge = CONGESTION_ICON.get(row["congestion"], "⚪")

    with st.container(border=True):
        st.markdown(f"### {row['spot_name']}")
        st.markdown(
            f"{badge} **혼잡도:** {row['congestion']}  \n"
            f"**카테고리:** {row.get('category', '-')}  \n"
            f"**운영시간:** {row.get('operation_hours', '-')}  \n"
            f"**이용요금:** {row.get('fee', '-')}"
        )
        st.write(row.get("description", "설명 없음"))
        st.caption(f"📍 {row.get('district', '-')} | 🚇 {row.get('transport', '-')}")


# -----------------------------
# 6. 추천 로직
# -----------------------------
def get_recommended_spots(df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    priority = {"여유": 0, "보통": 1, "붐빔": 2, "정보없음": 3}
    temp = df.copy()
    temp["priority"] = temp["congestion"].map(priority).fillna(99)
    temp = temp.sort_values(["priority", "spot_name"])
    return temp.head(top_n)


def get_alternative_spots(df: pd.DataFrame, selected_row: pd.Series, top_n: int = 3) -> pd.DataFrame:
    priority = {"여유": 0, "보통": 1, "붐빔": 2, "정보없음": 3}

    same_category = df[
        (df["spot_name"] != selected_row["spot_name"]) &
        (df["category"] == selected_row["category"])
    ].copy()

    same_category["priority"] = same_category["congestion"].map(priority).fillna(99)
    same_category = same_category.sort_values(["priority", "spot_name"])

    return same_category.head(top_n)


# -----------------------------
# 7. 메인 데이터 준비
# -----------------------------
def load_all_data():
    # 파일 경로 예시
    spot_csv_path = "data/night_spots.csv"

    spot_df = load_spot_csv(spot_csv_path)

    api_key = st.secrets.get("SEOUL_API_KEY", None)

    if api_key:
        live_df = fetch_live_population_batch(api_key, spot_df)
        merged_df = merge_spot_and_live_data(spot_df, live_df)
    else:
        st.warning("SEOUL_API_KEY가 없어 CSV 데이터만 표시합니다.")
        merged_df = spot_df.copy()
        if "congestion" not in merged_df.columns:
            merged_df["congestion"] = "정보없음"
            merged_df["congestion_message"] = "실시간 정보 없음"

    return merged_df


# -----------------------------
# 8. 앱 실행
# -----------------------------
df = load_all_data()

st.sidebar.title("🌃 서울 야간 명소 추천")
page = st.sidebar.radio(
    "메뉴",
    ["홈", "탐색", "명소 상세", "서비스 소개"]
)

# -----------------------------
# 홈
# -----------------------------
if page == "홈":
    st.title("오늘 밤, 서울 어디로 갈까?")
    st.subheader("실시간 인구 데이터와 야간 명소 정보를 결합한 서울 야간 외출 추천 서비스")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.markdown("""
        이 웹페이지는 서울시 공공데이터를 활용하여  
        **현재 덜 붐비는 야간 명소**를 빠르게 찾을 수 있도록 구성했습니다.
        """)

    with col2:
        st.metric("전체 명소 수", len(df))
        st.metric("여유 명소 수", int((df["congestion"] == "여유").sum()))

    st.markdown("---")
    st.markdown("## 지금 추천하는 명소")

    rec_df = get_recommended_spots(df, top_n=3)
    cols = st.columns(3)

    for i, (_, row) in enumerate(rec_df.iterrows()):
        with cols[i]:
            render_spot_card(row)

    st.markdown("---")
    st.markdown("## 지도에서 보기")
    fmap = make_map(df)
    st_folium(fmap, height=500, width=None)


# -----------------------------
# 탐색
# -----------------------------
elif page == "탐색":
    st.title("야간 명소 탐색")

    col1, col2 = st.columns([1, 3])

    with col1:
        category_options = ["전체"] + sorted(df["category"].dropna().unique().tolist())
        congestion_options = ["전체", "여유", "보통", "붐빔", "정보없음"]
        district_options = ["전체"] + sorted(df["district"].dropna().unique().tolist())

        selected_category = st.selectbox("카테고리", category_options)
        selected_congestion = st.selectbox("혼잡도", congestion_options)
        selected_district = st.selectbox("지역구", district_options)

    filtered_df = df.copy()

    if selected_category != "전체":
        filtered_df = filtered_df[filtered_df["category"] == selected_category]

    if selected_congestion != "전체":
        filtered_df = filtered_df[filtered_df["congestion"] == selected_congestion]

    if selected_district != "전체":
        filtered_df = filtered_df[filtered_df["district"] == selected_district]

    with col2:
        tab1, tab2 = st.tabs(["카드 보기", "지도 보기"])

        with tab1:
            st.write(f"총 **{len(filtered_df)}개** 명소")
            for _, row in filtered_df.iterrows():
                render_spot_card(row)

        with tab2:
            fmap = make_map(filtered_df)
            st_folium(fmap, height=550, width=None)


# -----------------------------
# 명소 상세
# -----------------------------
elif page == "명소 상세":
    st.title("명소 상세 정보")

    selected_spot_name = st.selectbox("명소 선택", df["spot_name"].tolist())
    selected_row = df[df["spot_name"] == selected_spot_name].iloc[0]

    badge = CONGESTION_ICON.get(selected_row["congestion"], "⚪")

    st.markdown(f"# {selected_row['spot_name']}")
    st.markdown(
        f"{badge} **혼잡도:** {selected_row['congestion']}  \n"
        f"**혼잡 안내:** {selected_row.get('congestion_message', '-')}  \n"
        f"**카테고리:** {selected_row.get('category', '-')}  \n"
        f"**운영시간:** {selected_row.get('operation_hours', '-')}"
    )

    c1, c2 = st.columns([2, 1])

    with c1:
        st.markdown("## 장소 설명")
        st.write(selected_row.get("description", "설명 없음"))

        st.markdown("## 이용 정보")
        st.write(f"**주소:** {selected_row.get('address', '-')}")
        st.write(f"**이용요금:** {selected_row.get('fee', '-')}")
        st.write(f"**교통:** {selected_row.get('transport', '-')}")
        st.write(f"**주차:** {selected_row.get('parking', '-')}")

    with c2:
        st.markdown("## 실시간 정보")
        st.metric("혼잡도", selected_row["congestion"])
        st.metric("남성 비율", selected_row["male_rate"] if pd.notna(selected_row.get("male_rate")) else "-")
        st.metric("여성 비율", selected_row["female_rate"] if pd.notna(selected_row.get("female_rate")) else "-")

    st.markdown("---")
    st.markdown("## 위치")
    fmap = make_map(df, selected_spot=selected_spot_name)
    st_folium(fmap, height=450, width=None)

    st.markdown("---")
    st.markdown("## 비슷한 대체 명소")
    alt_df = get_alternative_spots(df, selected_row, top_n=3)

    if len(alt_df) == 0:
        st.info("추천할 대체 명소가 없습니다.")
    else:
        for _, row in alt_df.iterrows():
            render_spot_card(row)


# -----------------------------
# 서비스 소개
# -----------------------------
elif page == "서비스 소개":
    st.title("서비스 소개")
    st.markdown("""
    이 서비스는 서울시 공공데이터를 활용하여 다음 정보를 제공합니다.

    - **실시간 인구 데이터(API)**
    - **야간 명소 정보(CSV)**

    이를 결합해 사용자가 서울의 야간 명소를 선택할 때  
    현재 혼잡도와 장소 정보를 함께 확인할 수 있도록 설계했습니다.
    """)
