import time
import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="서울 야간 명소 추천",
    page_icon="🌃",
    layout="wide"
)

# -----------------------------
# 기본 설정
# -----------------------------
SEOUL_CENTER = [37.5665, 126.9780]

# 네 GitHub CSV raw 링크로 바꿔라
# 예:
# https://raw.githubusercontent.com/USER/REPO/main/data/night_spots.csv
CSV_URL = "https://raw.githubusercontent.com/USER/REPO/main/data/night_spots.csv"

CONGESTION_COLOR = {
    "여유": "green",
    "보통": "orange",
    "붐빔": "red",
    "정보없음": "blue"
}

CONGESTION_ICON = {
    "여유": "🟢",
    "보통": "🟠",
    "붐빔": "🔴",
    "정보없음": "🔵"
}

CONGESTION_PRIORITY = {
    "여유": 0,
    "보통": 1,
    "붐빔": 2,
    "정보없음": 3
}


# -----------------------------
# 데이터 로드
# -----------------------------
@st.cache_data(ttl=600)
def load_spot_csv(csv_url: str) -> pd.DataFrame:
    """
    GitHub raw CSV 로드

    권장 컬럼:
    - spot_name
    - api_place_name
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
    """
    df = pd.read_csv(csv_url, encoding="utf-8-sig")

    required_cols = ["spot_name", "api_place_name", "lat", "lon"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV 필수 컬럼 누락: {missing}")

    # 없는 컬럼은 기본 생성
    optional_cols = [
        "category", "district", "address", "operation_hours",
        "fee", "transport", "parking", "description"
    ]
    for col in optional_cols:
        if col not in df.columns:
            df[col] = ""

    return df


# -----------------------------
# 서울시 실시간 인구 API
# -----------------------------
def build_seoul_api_url(api_key: str, api_place_name: str) -> str:
    return f"http://openapi.seoul.go.kr:8088/{api_key}/json/citydata_ppltn/1/5/{api_place_name}"


def call_seoul_population_api(api_key: str, api_place_name: str, timeout: int = 10) -> dict | None:
    url = build_seoul_api_url(api_key, api_place_name)

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException:
        return None


def parse_population_response(raw_data: dict) -> dict | None:
    """
    서울시 실시간 인구 API 응답 파싱
    실제 응답 구조에 맞춰 안전하게 작성
    """
    if not raw_data:
        return None

    citydata = raw_data.get("CITYDATA")
    if not citydata:
        return None

    live_data = citydata.get("LIVE_PPLTN_STTS")
    if not live_data:
        return None

    item = live_data[0] if isinstance(live_data, list) and len(live_data) > 0 else live_data

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
    CSV의 api_place_name 기준으로 실시간 정보 조회
    """
    results = []

    unique_places = (
        spot_df[["spot_name", "api_place_name"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    for _, row in unique_places.iterrows():
        spot_name = row["spot_name"]
        api_place_name = str(row["api_place_name"]).strip()

        raw_data = call_seoul_population_api(api_key, api_place_name)
        parsed = parse_population_response(raw_data)

        if parsed is None:
            results.append({
                "spot_name": spot_name,
                "api_place_name": api_place_name,
                "congestion": "정보없음",
                "congestion_message": "실시간 정보 없음",
                "male_rate": None,
                "female_rate": None,
                "ppltn_min": None,
                "ppltn_max": None,
            })
        else:
            parsed["spot_name"] = spot_name
            parsed["congestion"] = parsed["congestion"] or "정보없음"
            parsed["congestion_message"] = parsed["congestion_message"] or "실시간 정보 없음"
            results.append(parsed)

        time.sleep(0.15)

    return pd.DataFrame(results)


def merge_spot_and_live_data(spot_df: pd.DataFrame, live_df: pd.DataFrame) -> pd.DataFrame:
    merged = spot_df.merge(
        live_df,
        on=["spot_name", "api_place_name"],
        how="left"
    ).copy()

    merged["congestion"] = merged["congestion"].fillna("정보없음")
    merged["congestion_message"] = merged["congestion_message"].fillna("실시간 정보 없음")

    return merged


@st.cache_data(ttl=300)
def load_all_data(csv_url: str, api_key: str | None) -> pd.DataFrame:
    spot_df = load_spot_csv(csv_url)

    if api_key:
        live_df = fetch_live_population_batch(api_key, spot_df)
        df = merge_spot_and_live_data(spot_df, live_df)
    else:
        df = spot_df.copy()
        df["congestion"] = "정보없음"
        df["congestion_message"] = "실시간 정보 없음"
        df["male_rate"] = None
        df["female_rate"] = None
        df["ppltn_min"] = None
        df["ppltn_max"] = None

    return df


# -----------------------------
# 시각화 / UI 함수
# -----------------------------
def make_map(df: pd.DataFrame, selected_spot: str | None = None):
    fmap = folium.Map(location=SEOUL_CENTER, zoom_start=11)

    for _, row in df.iterrows():
        congestion = row.get("congestion", "정보없음")
        color = CONGESTION_COLOR.get(congestion, "blue")
        radius = 12 if row["spot_name"] == selected_spot else 8

        popup_html = f"""
        <b>{row['spot_name']}</b><br>
        카테고리: {row.get('category', '-')}<br>
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


def render_spot_card(row: pd.Series):
    badge = CONGESTION_ICON.get(row["congestion"], "⚪")
    with st.container(border=True):
        st.markdown(f"### {row['spot_name']}")
        st.markdown(
            f"{badge} **혼잡도:** {row.get('congestion', '정보없음')}  \n"
            f"**카테고리:** {row.get('category', '-')}  \n"
            f"**운영시간:** {row.get('operation_hours', '-')}  \n"
            f"**이용요금:** {row.get('fee', '-')}"
        )
        st.write(row.get("description", ""))
        st.caption(f"📍 {row.get('district', '-')} | 🚇 {row.get('transport', '-')}")


def get_recommended_spots(df: pd.DataFrame, top_n: int = 3) -> pd.DataFrame:
    temp = df.copy()
    temp["priority"] = temp["congestion"].map(CONGESTION_PRIORITY).fillna(99)
    temp = temp.sort_values(["priority", "spot_name"])
    return temp.head(top_n)


def get_alternative_spots(df: pd.DataFrame, selected_row: pd.Series, top_n: int = 3) -> pd.DataFrame:
    temp = df[
        (df["spot_name"] != selected_row["spot_name"]) &
        (df["category"] == selected_row["category"])
    ].copy()

    temp["priority"] = temp["congestion"].map(CONGESTION_PRIORITY).fillna(99)
    temp = temp.sort_values(["priority", "spot_name"])

    return temp.head(top_n)


# -----------------------------
# 앱 시작
# -----------------------------
api_key = st.secrets.get("SEOUL_API_KEY", None)

try:
    df = load_all_data(CSV_URL, api_key)
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
    st.stop()

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
        st.markdown(
            """
            이 서비스는 서울시 공공데이터를 활용해  
            **현재 상대적으로 덜 붐비는 야간 명소**를 찾을 수 있도록 구성했습니다.
            """
        )

    with col2:
        st.metric("전체 명소 수", len(df))
        st.metric("여유 명소 수", int((df["congestion"] == "여유").sum()))

    st.markdown("---")
    st.markdown("## 지금 추천하는 명소")

    rec_df = get_recommended_spots(df, top_n=3)
    cols = st.columns(min(3, len(rec_df)) if len(rec_df) > 0 else 1)

    if len(rec_df) == 0:
        st.info("표시할 명소가 없습니다.")
    else:
        for i, (_, row) in enumerate(rec_df.iterrows()):
            with cols[i]:
                render_spot_card(row)

    st.markdown("---")
    st.markdown("## 지도에서 보기")
    st_folium(make_map(df), height=520, width=None)

# -----------------------------
# 탐색
# -----------------------------
elif page == "탐색":
    st.title("야간 명소 탐색")

    left, right = st.columns([1, 3])

    with left:
        keyword = st.text_input("명소 검색", "")
        category_options = ["전체"] + sorted([x for x in df["category"].dropna().unique().tolist() if x != ""])
        congestion_options = ["전체", "여유", "보통", "붐빔", "정보없음"]
        district_options = ["전체"] + sorted([x for x in df["district"].dropna().unique().tolist() if x != ""])

        selected_category = st.selectbox("카테고리", category_options)
        selected_congestion = st.selectbox("혼잡도", congestion_options)
        selected_district = st.selectbox("지역구", district_options)

    filtered_df = df.copy()

    if keyword.strip():
        filtered_df = filtered_df[
            filtered_df["spot_name"].astype(str).str.contains(keyword, case=False, na=False)
        ]

    if selected_category != "전체":
        filtered_df = filtered_df[filtered_df["category"] == selected_category]

    if selected_congestion != "전체":
        filtered_df = filtered_df[filtered_df["congestion"] == selected_congestion]

    if selected_district != "전체":
        filtered_df = filtered_df[filtered_df["district"] == selected_district]

    temp = filtered_df.copy()
    temp["priority"] = temp["congestion"].map(CONGESTION_PRIORITY).fillna(99)
    filtered_df = temp.sort_values(["priority", "spot_name"])

    with right:
        tab1, tab2, tab3 = st.tabs(["카드 보기", "지도 보기", "데이터 보기"])

        with tab1:
            st.write(f"총 **{len(filtered_df)}개** 명소")
            if len(filtered_df) == 0:
                st.info("조건에 맞는 명소가 없습니다.")
            else:
                for _, row in filtered_df.iterrows():
                    render_spot_card(row)

        with tab2:
            if len(filtered_df) == 0:
                st.info("지도에 표시할 명소가 없습니다.")
            else:
                st_folium(make_map(filtered_df), height=560, width=None)

        with tab3:
            st.dataframe(filtered_df, use_container_width=True)

# -----------------------------
# 명소 상세
# -----------------------------
elif page == "명소 상세":
    st.title("명소 상세 정보")

    selected_spot_name = st.selectbox("명소 선택", sorted(df["spot_name"].astype(str).tolist()))
    selected_row = df[df["spot_name"] == selected_spot_name].iloc[0]

    badge = CONGESTION_ICON.get(selected_row["congestion"], "⚪")

    st.markdown(f"# {selected_row['spot_name']}")
    st.markdown(
        f"{badge} **혼잡도:** {selected_row.get('congestion', '정보없음')}  \n"
        f"**혼잡 안내:** {selected_row.get('congestion_message', '실시간 정보 없음')}  \n"
        f"**카테고리:** {selected_row.get('category', '-')}  \n"
        f"**운영시간:** {selected_row.get('operation_hours', '-')}"
    )

    c1, c2 = st.columns([2, 1])

    with c1:
        st.markdown("## 장소 설명")
        st.write(selected_row.get("description", ""))

        st.markdown("## 이용 정보")
        st.write(f"**주소:** {selected_row.get('address', '-')}")
        st.write(f"**이용요금:** {selected_row.get('fee', '-')}")
        st.write(f"**교통:** {selected_row.get('transport', '-')}")
        st.write(f"**주차:** {selected_row.get('parking', '-')}")

    with c2:
        st.markdown("## 실시간 정보")
        st.metric("혼잡도", selected_row.get("congestion", "정보없음"))

        male_rate = selected_row.get("male_rate")
        female_rate = selected_row.get("female_rate")
        ppltn_min = selected_row.get("ppltn_min")
        ppltn_max = selected_row.get("ppltn_max")

        st.metric("남성 비율", "-" if pd.isna(male_rate) else male_rate)
        st.metric("여성 비율", "-" if pd.isna(female_rate) else female_rate)
        st.metric("추정 인구 최소", "-" if pd.isna(ppltn_min) else ppltn_min)
        st.metric("추정 인구 최대", "-" if pd.isna(ppltn_max) else ppltn_max)

    st.markdown("---")
    st.markdown("## 위치")
    st_folium(make_map(df, selected_spot=selected_spot_name), height=450, width=None)

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
    st.markdown(
        """
        이 서비스는 서울시 공공데이터를 활용하여 다음 정보를 결합합니다.

        - **실시간 인구 데이터(API)**
        - **야간 명소 데이터(CSV)**

        이를 통해 사용자가 서울의 야간 명소를 선택할 때  
        현재 혼잡도와 장소 정보를 함께 확인할 수 있도록 설계했습니다.
        """
    )

    with st.expander("CSV 필수 컬럼 예시"):
        st.code(
            "spot_name,api_place_name,category,district,lat,lon,address,operation_hours,fee,transport,parking,description",
            language="text"
        )

    with st.expander("실시간 API 테스트"):
        test_place = st.text_input("API 장소명 입력", value="")
        if st.button("응답 확인"):
            if not api_key:
                st.warning("SEOUL_API_KEY가 설정되지 않았습니다.")
            elif not test_place.strip():
                st.warning("장소명을 입력하세요.")
            else:
                raw = call_seoul_population_api(api_key, test_place.strip())
                st.json(raw if raw else {"message": "응답 없음"})
