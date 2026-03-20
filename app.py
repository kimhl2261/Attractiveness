import time
import re
import html
from urllib.parse import quote

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
CSV_URL = "https://raw.githubusercontent.com/kimhl2261/Attractiveness/main/seoul_night.csv"

CONGESTION_COLOR = {
    "여유": "#22c55e",
    "보통": "#f97316",
    "붐빔": "#ef4444",
    "정보없음": "#3b82f6"
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
# 서울시 실시간 인구 API 매핑
# -----------------------------
API_PLACE_MAPPING = {
    "남산서울타워": "명동관광특구",
    "장충체육관": "동대문디자인플라자",
    "용양봉저정 공원": "노들섬",
    "창경궁": "광화문광장",
    "서울어린이대공원 내 서울상상나라": None,
    "창덕궁": "광화문광장",
    "여의도한강공원 물빛광장": "여의도한강공원",
    "뚝섬 자벌레(한강이야기전시관)": "뚝섬한강공원",
    "청계천": "청계천",
    "성수대교": "뚝섬한강공원",
    "마포대교": "여의도한강공원",
    "난지거울분수": None,
    "이촌한강공원": "국립중앙박물관·용산가족공원",
    "남산공원 백범광장- 서울한양도성 성곽": "명동관광특구",
    "사육신공원": "노들섬",
    "월드컵대교": "서울월드컵경기장",
    "문화비축기지": "서울월드컵경기장",
    "숭례문(남대문)": "명동관광특구",
    "서울월드컵경기장": "서울월드컵경기장",
    "노들섬복합문화공간": "노들섬",
    "광화문광장(광화문)": "광화문광장",
    "하늘공원(월드컵공원내)": "서울월드컵경기장",
    "동대문디자인플라자(DDP)": "동대문디자인플라자",
    "경복궁": "광화문광장",
    "서울로미디어캔버스": "명동관광특구",
    "덕수궁": "광화문광장",
    "반포대교 달빛무지개 분수": "반포한강공원",
    "서울어린이대공원 팔각당 오름광장": None,
    "올림픽대교": "잠실관광특구",
    "세빛섬": "반포한강공원",
    "서울함 공원": None,
    "낙산공원 - 한양도성 성곽길": "동대문디자인플라자",
    "아뜰리에 광화": "광화문광장",
    "당산철교": "여의도한강공원",
    "세종문화회관": "광화문광장",
    "한강대교": "노들섬",
    "동작대교": "반포한강공원",
    "서울시립미술관 서소문본관": "광화문광장",
    "서울식물원": None,
    "덕수궁 돌담길": "광화문광장",
    "광진교 8번가": "광나루한강공원",
    "고척스카이돔": "고척돔",
    "서울어린이대공원 후문 선형공원": None,
    "뚝섬 음악분수": "뚝섬한강공원",
    "석촌호수 루미나리에(송파나루공원)": "잠실관광특구",
    "동호대교": "반포한강공원",
    "선유도공원": None,
    "송파책박물관": "잠실관광특구",
    "노원불빛정원(화랑대철도공원 내)": None,
    "서울어린이대공원 음악분수": None,
    "성산대교": "서울월드컵경기장",
}

# -----------------------------
# 주차 가능 여부 파싱
# -----------------------------
def parse_parking(parking_value: str) -> str:
    """주차 정보 문자열에서 가능/불가/정보없음 반환"""
    if not parking_value or parking_value.strip() in ("", "-", "nan"):
        return "정보없음"
    v = parking_value.strip()
    no_keywords = ["불가", "없음", "주차 불가", "주차없음", "주차 없음", "불가능"]
    yes_keywords = ["가능", "있음", "주차 가능", "주차가능", "주차장", "무료", "유료"]
    for kw in no_keywords:
        if kw in v:
            return "불가"
    for kw in yes_keywords:
        if kw in v:
            return "가능"
    if len(v) > 1:
        return "가능"
    return "정보없음"


# -----------------------------
# 텍스트 정리
# -----------------------------
def clean_text(value):
    if pd.isna(value):
        return ""
    text = str(value)
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("~~", "")
    text = re.sub(r"\s+", " ", text).strip()
    return text


# -----------------------------
# CSV 로드
# -----------------------------
@st.cache_data(ttl=600)
def load_spot_csv(csv_url: str) -> pd.DataFrame:
    encodings = ["utf-8-sig", "cp949", "euc-kr"]
    last_error = None

    for enc in encodings:
        try:
            df = pd.read_csv(csv_url, encoding=enc)
            break
        except Exception as e:
            last_error = e
    else:
        raise ValueError(f"CSV 읽기 실패: {last_error}")

    rename_map = {
        "분류": "category",
        "장소명": "spot_name",
        "주소": "address",
        "위도": "lat",
        "경도": "lon",
        "운영시간": "operation_hours",
        "유무료구분": "free_type",
        "이용요금": "fee",
        "내용": "description",
        "주차안내": "parking",
        "전화번호": "phone",
        "홈페이지 URL": "homepage_url",
        "등록일시": "created_at",
        "수정일시": "updated_at",
    }
    df = df.rename(columns=rename_map)

    subway_series = (
        df["지하철"].fillna("").astype(str).str.strip()
        if "지하철" in df.columns
        else pd.Series([""] * len(df))
    )
    bus_series = (
        df["버스"].fillna("").astype(str).str.strip()
        if "버스" in df.columns
        else pd.Series([""] * len(df))
    )

    transport = []
    for subway, bus in zip(subway_series, bus_series):
        if subway and bus:
            transport.append(f"지하철: {subway} / 버스: {bus}")
        elif subway:
            transport.append(f"지하철: {subway}")
        elif bus:
            transport.append(f"버스: {bus}")
        else:
            transport.append("")
    df["transport"] = transport

    if "address" in df.columns:
        extracted = df["address"].astype(str).str.extract(r"(서울(?:특별시)?\s+)?([가-힣]+구)")
        df["district"] = extracted[1].fillna("")
    else:
        df["district"] = ""

    df["api_place_name"] = df["spot_name"].map(API_PLACE_MAPPING)

    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"]).copy()

    required_cols = ["spot_name", "lat", "lon"]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"CSV 필수 컬럼 누락: {missing}")

    optional_cols = [
        "category", "district", "address", "operation_hours",
        "free_type", "fee", "transport", "parking",
        "description", "phone", "homepage_url", "api_place_name"
    ]
    for col in optional_cols:
        if col not in df.columns:
            df[col] = ""

    text_cols = [
        "spot_name", "category", "district", "address",
        "operation_hours", "free_type", "fee", "transport",
        "parking", "description", "phone", "homepage_url"
    ]
    for col in text_cols:
        df[col] = df[col].fillna("").astype(str).str.strip()

    clean_cols = [
        "operation_hours", "fee", "description",
        "parking", "transport", "address"
    ]
    for col in clean_cols:
        if col in df.columns:
            df[col] = df[col].apply(clean_text)

    # 주차 가능 여부 컬럼 추가
    df["parking_available"] = df["parking"].apply(parse_parking)

    return df


# -----------------------------
# 서울시 실시간 인구 API
# -----------------------------
def build_seoul_api_url(api_key: str, api_place_name: str) -> str:
    encoded_place_name = quote(api_place_name)
    return f"http://openapi.seoul.go.kr:8088/{api_key}/json/citydata_ppltn/1/5/{encoded_place_name}"


def call_seoul_population_api(api_key: str, api_place_name: str, timeout: int = 10) -> dict | None:
    url = build_seoul_api_url(api_key, api_place_name)
    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        return {"error": str(e), "url": url}


def parse_population_response(raw_data: dict) -> dict | None:
    if not raw_data:
        return None

    if raw_data.get("error"):
        return {
            "api_place_name": None,
            "congestion": "정보없음",
            "congestion_message": f"요청 오류: {raw_data.get('error')}",
            "male_rate": None,
            "female_rate": None,
            "ppltn_min": None,
            "ppltn_max": None,
        }

    result = raw_data.get("RESULT")
    if result and result.get("CODE") != "INFO-000":
        return {
            "api_place_name": None,
            "congestion": "정보없음",
            "congestion_message": f"API 오류: {result.get('CODE')} / {result.get('MESSAGE', '')}",
            "male_rate": None,
            "female_rate": None,
            "ppltn_min": None,
            "ppltn_max": None,
        }

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
    results = []

    unique_places = (
        spot_df[["spot_name", "api_place_name"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    for _, row in unique_places.iterrows():
        spot_name = row["spot_name"]
        api_place_name = row["api_place_name"]

        if pd.isna(api_place_name) or not str(api_place_name).strip() or str(api_place_name) == "None":
            results.append({
                "spot_name": spot_name,
                "api_place_name": api_place_name,
                "congestion": "정보없음",
                "congestion_message": "실시간 인구 API 미지원 명소",
                "male_rate": None,
                "female_rate": None,
                "ppltn_min": None,
                "ppltn_max": None,
            })
            continue

        api_place_name = str(api_place_name).strip()
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
            parsed["api_place_name"] = api_place_name
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
        df["congestion_message"] = "SEOUL_API_KEY 미설정"
        df["male_rate"] = None
        df["female_rate"] = None
        df["ppltn_min"] = None
        df["ppltn_max"] = None

    return df


# -----------------------------
# [수정1] 커스텀 지도 마커 생성
# -----------------------------
def make_custom_icon(congestion: str, parking: str) -> folium.DivIcon:
    """혼잡도 색상 + 주차 여부를 담은 커스텀 핀 아이콘 생성"""
    color = CONGESTION_COLOR.get(congestion, "#3b82f6")

    # 주차 배지 (P)
    parking_badge = ""
    if parking == "가능":
        parking_badge = (
            '<div style="position:absolute;top:-4px;right:-4px;'
            'width:14px;height:14px;background:#1d4ed8;border-radius:50%;'
            'border:1.5px solid #fff;font-size:8px;font-weight:700;'
            'color:#fff;display:flex;align-items:center;justify-content:center;'
            'line-height:1;">P</div>'
        )
    elif parking == "불가":
        parking_badge = (
            '<div style="position:absolute;top:-4px;right:-4px;'
            'width:14px;height:14px;background:#dc2626;border-radius:50%;'
            'border:1.5px solid #fff;font-size:8px;font-weight:700;'
            'color:#fff;display:flex;align-items:center;justify-content:center;'
            'line-height:1;">✕</div>'
        )

    html_icon = f"""
    <div style="position:relative;width:28px;height:36px;">
      <!-- 핀 몸통 -->
      <div style="
        position:absolute;top:0;left:0;
        width:28px;height:28px;
        background:{color};
        border-radius:50% 50% 50% 0;
        transform:rotate(-45deg);
        border:2.5px solid #fff;
        box-shadow:0 2px 6px rgba(0,0,0,0.35);
      "></div>
      <!-- 핀 내부 흰 원 -->
      <div style="
        position:absolute;top:6px;left:6px;
        width:12px;height:12px;
        background:#fff;
        border-radius:50%;
        transform:rotate(0deg);
        opacity:0.85;
      "></div>
      {parking_badge}
    </div>
    """
    return folium.DivIcon(
        html=html_icon,
        icon_size=(28, 36),
        icon_anchor=(14, 36),
    )


# -----------------------------
# [수정2] 지도 생성 — 커스텀 마커 적용
# -----------------------------
def make_map(df: pd.DataFrame, selected_spot: str | None = None):
    fmap = folium.Map(
        location=SEOUL_CENTER,
        zoom_start=11,
        tiles="CartoDB positron",   # 더 깔끔한 배경 타일
    )

    for _, row in df.iterrows():
        congestion = row.get("congestion", "정보없음")
        parking = row.get("parking_available", "정보없음")

        api_name = row.get("api_place_name", "-")
        if pd.isna(api_name) or str(api_name).strip() == "":
            api_name = "미지원"

        parking_icon = {"가능": "🅿️", "불가": "🚫", "정보없음": "❓"}.get(parking, "❓")

        popup_html = f"""
        <div style="font-family:sans-serif;min-width:200px;">
          <b style="font-size:14px;">{row['spot_name']}</b><br>
          <span style="color:{CONGESTION_COLOR.get(congestion,'#3b82f6')}">● {congestion}</span><br>
          분류: {row.get('category', '-')}<br>
          운영시간: {row.get('operation_hours', '-')}<br>
          주차: {parking_icon} {parking}<br>
          주소: {row.get('address', '-')}
        </div>
        """

        # 선택된 스팟은 크기를 키워서 강조
        if row["spot_name"] == selected_spot:
            icon_size = (36, 46)
        else:
            icon_size = (28, 36)

        custom_icon = make_custom_icon(congestion, parking)
        custom_icon.options["iconSize"] = list(icon_size)
        custom_icon.options["iconAnchor"] = [icon_size[0] // 2, icon_size[1]]

        folium.Marker(
            location=[row["lat"], row["lon"]],
            icon=custom_icon,
            popup=folium.Popup(popup_html, max_width=280),
            tooltip=f"{row['spot_name']} | {congestion} | 주차 {parking}",
        ).add_to(fmap)

    # 범례 추가
    legend_html = """
    <div style="
        position:fixed;bottom:24px;left:24px;z-index:9999;
        background:rgba(255,255,255,0.95);
        border-radius:10px;padding:12px 16px;
        box-shadow:0 2px 10px rgba(0,0,0,0.15);
        font-family:sans-serif;font-size:12px;line-height:1.9;
    ">
      <b style="font-size:13px;">혼잡도</b><br>
      <span style="color:#22c55e">●</span> 여유&nbsp;&nbsp;
      <span style="color:#f97316">●</span> 보통&nbsp;&nbsp;
      <span style="color:#ef4444">●</span> 붐빔&nbsp;&nbsp;
      <span style="color:#3b82f6">●</span> 정보없음<br>
      <b style="font-size:13px;">주차</b><br>
      <span style="background:#1d4ed8;color:#fff;border-radius:50%;padding:0 4px;font-size:10px;font-weight:700;">P</span> 가능&nbsp;&nbsp;
      <span style="background:#dc2626;color:#fff;border-radius:50%;padding:0 3px;font-size:10px;font-weight:700;">✕</span> 불가
    </div>
    """
    fmap.get_root().html.add_child(folium.Element(legend_html))

    return fmap


# -----------------------------
# [수정3] 카드 렌더링 — 밑줄 제거 + 주차 배지 추가
# -----------------------------
def render_spot_card(row: pd.Series):
    badge = CONGESTION_ICON.get(row["congestion"], "⚪")
    parking = row.get("parking_available", "정보없음")
    parking_label = {"가능": "🅿️ 주차 가능", "불가": "🚫 주차 불가", "정보없음": "❓ 주차 정보없음"}.get(parking, "❓")
    parking_color = {"가능": "#1d4ed8", "불가": "#dc2626", "정보없음": "#6b7280"}.get(parking, "#6b7280")

    with st.container(border=True):
        # 제목 + 주차 배지를 한 줄에 표시
        col_title, col_park = st.columns([3, 1])
        with col_title:
            st.markdown(f"### {row['spot_name']}")
        with col_park:
            st.markdown(
                f'<div style="margin-top:18px;text-align:right;'
                f'color:{parking_color};font-size:13px;font-weight:600;">'
                f'{parking_label}</div>',
                unsafe_allow_html=True,
            )

        # 혼잡도 + 분류
        st.markdown(
            f'<p style="margin:0 0 4px 0;">{badge} <b>혼잡도:</b> {row.get("congestion", "정보없음")}&nbsp;&nbsp;'
            f'<b>분류:</b> {row.get("category", "-")}</p>',
            unsafe_allow_html=True,
        )

        # [수정1] 운영시간 — st.write 대신 markdown으로 밑줄 방지
        op_hours = row.get("operation_hours", "-") or "-"
        st.markdown(
            f'<p style="margin:0 0 4px 0;"><b>운영시간:</b> {op_hours}</p>',
            unsafe_allow_html=True,
        )

        # 유/무료
        st.markdown(
            f'<p style="margin:0 0 6px 0;"><b>유/무료:</b> {row.get("free_type", "-")}</p>',
            unsafe_allow_html=True,
        )

        desc = row.get("description", "")
        if desc:
            st.markdown(
                f'<p style="margin:0 0 6px 0;color:#555;font-size:14px;">'
                f'{desc[:250] + ("..." if len(desc) > 250 else "")}</p>',
                unsafe_allow_html=True,
            )

        api_place = row.get("api_place_name", "-")
        if pd.isna(api_place) or str(api_place).strip() == "":
            api_place = "미지원"

        st.caption(
            f"📍 {row.get('district', '-')} | 🚇 {row.get('transport', '-')} | 🔗 API 매핑: {api_place}"
        )


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
    st.subheader("실시간 인구 데이터와 서울시 야경명소 정보를 결합한 야간 외출 추천 서비스")

    col1, col2, col3 = st.columns([2, 1, 1])

    with col1:
        st.markdown(
            """
            이 서비스는 서울시 공공데이터를 활용해  
            현재 상대적으로 덜 붐비는 야간 명소를 찾을 수 있도록 구성했습니다.
            """
        )

    with col2:
        st.metric("전체 명소 수", len(df))
        st.metric("여유 명소 수", int((df["congestion"] == "여유").sum()))

    with col3:
        parking_yes = int((df["parking_available"] == "가능").sum())
        parking_no  = int((df["parking_available"] == "불가").sum())
        st.metric("주차 가능 명소", parking_yes)
        st.metric("주차 불가 명소", parking_no)

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

        selected_category   = st.selectbox("분류", category_options)
        selected_congestion = st.selectbox("혼잡도", congestion_options)
        selected_district   = st.selectbox("지역구", district_options)

        # [신규] 주차 필터
        parking_options = ["전체", "가능", "불가", "정보없음"]
        selected_parking = st.selectbox("🅿️ 주차 여부", parking_options)

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

    # [신규] 주차 필터 적용
    if selected_parking != "전체":
        filtered_df = filtered_df[filtered_df["parking_available"] == selected_parking]

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
            show_cols = [
                "spot_name", "category", "district", "address", "operation_hours",
                "free_type", "fee", "parking_available",
                "api_place_name", "congestion", "congestion_message"
            ]
            existing_cols = [c for c in show_cols if c in filtered_df.columns]
            st.dataframe(filtered_df[existing_cols], use_container_width=True)

# -----------------------------
# 명소 상세
# -----------------------------
elif page == "명소 상세":
    st.title("명소 상세 정보")

    selected_spot_name = st.selectbox("명소 선택", sorted(df["spot_name"].astype(str).tolist()))
    selected_row = df[df["spot_name"] == selected_spot_name].iloc[0]

    badge = CONGESTION_ICON.get(selected_row["congestion"], "⚪")
    parking = selected_row.get("parking_available", "정보없음")
    parking_label = {"가능": "🅿️ 주차 가능", "불가": "🚫 주차 불가", "정보없음": "❓ 주차 정보없음"}.get(parking, "❓")
    parking_color = {"가능": "#1d4ed8", "불가": "#dc2626", "정보없음": "#6b7280"}.get(parking, "#6b7280")

    title_col, park_col = st.columns([4, 1])
    with title_col:
        st.markdown(f"# {selected_row['spot_name']}")
    with park_col:
        st.markdown(
            f'<div style="margin-top:24px;text-align:right;'
            f'color:{parking_color};font-size:15px;font-weight:700;">'
            f'{parking_label}</div>',
            unsafe_allow_html=True,
        )

    st.markdown(
        f'<p>{badge} 혼잡도: <b>{selected_row.get("congestion", "정보없음")}</b></p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p>혼잡 안내: {selected_row.get("congestion_message", "실시간 정보 없음")}</p>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p>분류: {selected_row.get("category", "-")}</p>',
        unsafe_allow_html=True,
    )
    # [수정1] 운영시간 밑줄 제거
    st.markdown(
        f'<p>운영시간: {selected_row.get("operation_hours", "-") or "-"}</p>',
        unsafe_allow_html=True,
    )

    c1, c2 = st.columns([2, 1])

    with c1:
        st.markdown("## 장소 설명")
        st.write(selected_row.get("description", ""))

        st.markdown("## 이용 정보")
        for label, key in [
            ("주소", "address"), ("유/무료", "free_type"), ("이용요금", "fee"),
            ("교통", "transport"), ("주차", "parking"), ("전화번호", "phone"),
            ("홈페이지", "homepage_url"),
        ]:
            val = selected_row.get(key, "-") or "-"
            st.markdown(
                f'<p style="margin:2px 0;"><b>{label}:</b> {val}</p>',
                unsafe_allow_html=True,
            )

        api_name = selected_row.get("api_place_name", "-")
        if pd.isna(api_name) or str(api_name).strip() == "":
            api_name = "미지원"
        st.markdown(
            f'<p style="margin:2px 0;"><b>API 매핑 장소:</b> {api_name}</p>',
            unsafe_allow_html=True,
        )

    with c2:
        st.markdown("## 실시간 정보")
        st.metric("혼잡도", selected_row.get("congestion", "정보없음"))

        male_rate   = selected_row.get("male_rate")
        female_rate = selected_row.get("female_rate")
        ppltn_min   = selected_row.get("ppltn_min")
        ppltn_max   = selected_row.get("ppltn_max")

        st.metric("남성 비율", "-" if pd.isna(male_rate)   else male_rate)
        st.metric("여성 비율", "-" if pd.isna(female_rate) else female_rate)
        st.metric("추정 인구 최소", "-" if pd.isna(ppltn_min) else ppltn_min)
        st.metric("추정 인구 최대", "-" if pd.isna(ppltn_max) else ppltn_max)

        st.markdown("## 주차 안내")
        st.markdown(
            f'<div style="font-size:20px;font-weight:700;color:{parking_color};">'
            f'{parking_label}</div>',
            unsafe_allow_html=True,
        )
        raw_parking = selected_row.get("parking", "") or "-"
        st.caption(raw_parking)

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

        - 실시간 인구 데이터(API)
        - 서울시 야경명소 정보(CSV)

        이를 통해 사용자가 서울의 야간 명소를 선택할 때  
        현재 혼잡도와 장소 정보를 함께 확인할 수 있도록 설계했습니다.
        """
    )

    with st.expander("현재 불러온 CSV 확인"):
        st.write("CSV URL:", CSV_URL)
        st.write("컬럼명:", df.columns.tolist())
        st.dataframe(df.head(), use_container_width=True)

    with st.expander("API 매핑 현황"):
        mapping_view = df[["spot_name", "api_place_name"]].copy()
        mapping_view["api_place_name"] = mapping_view["api_place_name"].fillna("미지원")
        st.dataframe(mapping_view, use_container_width=True)

    with st.expander("주차 현황 요약"):
        parking_summary = df["parking_available"].value_counts().reset_index()
        parking_summary.columns = ["주차 여부", "명소 수"]
        st.dataframe(parking_summary, use_container_width=True)

    with st.expander("실시간 API 테스트"):
        st.write("api_key loaded:", api_key is not None)

        test_place = st.text_input("API 장소명 입력", value="")
        if st.button("응답 확인"):
            if not api_key:
                st.warning("SEOUL_API_KEY가 설정되지 않았습니다.")
            elif not test_place.strip():
                st.warning("장소명을 입력하세요.")
            else:
                raw = call_seoul_population_api(api_key, test_place.strip())
                st.json(raw if raw else {"message": "응답 없음"})
