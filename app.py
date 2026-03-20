import time
import re
import html
from urllib.parse import quote, urljoin

import requests
import pandas as pd
import streamlit as st
import folium
from streamlit_folium import st_folium
from bs4 import BeautifulSoup

# ── 페이지 설정 ──────────────────────────────────────────────────
st.set_page_config(
    page_title="서울 야간 명소",
    page_icon="🌃",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── 전역 CSS (야간 감성 테마) ─────────────────────────────────────
st.markdown("""
<style>
/* 전체 배경 */
[data-testid="stAppViewContainer"] {
    background: #0d1117;
}
[data-testid="stSidebar"] {
    background: #161b22 !important;
    border-right: 1px solid #30363d;
}
/* 사이드바 텍스트 */
[data-testid="stSidebar"] * { color: #e6edf3 !important; }

/* 메인 텍스트 */
h1, h2, h3, h4, .stMarkdown p { color: #e6edf3; }
.stMarkdown { color: #c9d1d9; }

/* 메트릭 카드 */
[data-testid="stMetric"] {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 12px 16px !important;
}
[data-testid="stMetricLabel"] { color: #8b949e !important; font-size: 12px; }
[data-testid="stMetricValue"] { color: #e6edf3 !important; }

/* 컨테이너 카드 */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: #161b22 !important;
    border: 1px solid #30363d !important;
    border-radius: 14px !important;
}

/* 탭 */
[data-testid="stTabs"] button {
    color: #8b949e;
    font-size: 14px;
    font-weight: 500;
}
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #58a6ff !important;
    border-bottom: 2px solid #58a6ff;
}

/* 버튼 */
.stButton > button {
    background: #21262d;
    border: 1px solid #30363d;
    color: #c9d1d9;
    border-radius: 8px;
}
.stButton > button:hover {
    background: #30363d;
    border-color: #58a6ff;
    color: #58a6ff;
}

/* 셀렉트박스 / 인풋 */
.stSelectbox > div > div,
.stTextInput > div > div {
    background: #21262d !important;
    border-color: #30363d !important;
    color: #e6edf3 !important;
    border-radius: 8px !important;
}

/* 토글 */
.stToggle label { color: #c9d1d9 !important; }

/* 캡션 */
.stCaption { color: #6e7681 !important; }

/* 배지 공통 */
.badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
    letter-spacing: 0.3px;
}

/* 구분선 */
hr { border-color: #30363d; }

/* 정보 박스 */
[data-testid="stInfo"] { background: #0d2137 !important; border-color: #1f6feb !important; }
[data-testid="stSuccess"] { background: #0d2d1a !important; border-color: #238636 !important; }
[data-testid="stWarning"] { background: #2d1e00 !important; border-color: #9e6a03 !important; }
[data-testid="stError"] { background: #2d0f0f !important; border-color: #da3633 !important; }
</style>
""", unsafe_allow_html=True)

# ── 상수 ─────────────────────────────────────────────────────────
SEOUL_CENTER = [37.5665, 126.9780]
CSV_URL = "https://raw.githubusercontent.com/kimhl2261/Attractiveness/main/seoul_night.csv"

CONGESTION_COLOR  = {"여유": "#3fb950", "보통": "#d29922", "붐빔": "#f85149"}
CONGESTION_BG     = {"여유": "#0d2d1a", "보통": "#2d1e00", "붐빔": "#2d0f0f"}
CONGESTION_ICON   = {"여유": "🟢", "보통": "🟡", "붐빔": "🔴"}
CONGESTION_LABEL  = {"여유": "여유", "보통": "보통", "붐빔": "붐빔"}
CONGESTION_PRIORITY = {"여유": 0, "보통": 1, "붐빔": 2, "정보없음": 3}

PARKING_COLOR = {"가능": "#58a6ff", "불가": "#f85149"}
PARKING_BG    = {"가능": "#0d2137", "불가": "#2d0f0f"}
PARKING_ICON  = {"가능": "🅿️", "불가": "⛔"}

# ── 공식 122 장소명 매핑 (정확한 명칭 기준) ───────────────────────
API_PLACE_MAPPING = {
    "남산서울타워":                    "명동관광특구",
    "장충체육관":                      "동대문디자인플라자",
    "용양봉저정 공원":                  "노들섬",
    "창경궁":                         "광화문·덕수궁",
    "서울어린이대공원 내 서울상상나라":   None,
    "창덕궁":                         "광화문·덕수궁",
    "여의도한강공원 물빛광장":           "여의도한강공원",
    "뚝섬 자벌레(한강이야기전시관)":     "뚝섬한강공원",
    "청계천":                         "청계천·종로",
    "성수대교":                        "뚝섬한강공원",
    "마포대교":                        "여의도한강공원",
    "난지거울분수":                     None,
    "이촌한강공원":                     "국립중앙박물관·용산가족공원",
    "남산공원 백범광장- 서울한양도성 성곽": "명동관광특구",
    "사육신공원":                       "노들섬",
    "월드컵대교":                       "서울월드컵경기장",
    "문화비축기지":                     "서울월드컵경기장",
    "숭례문(남대문)":                   "명동관광특구",
    "서울월드컵경기장":                  "서울월드컵경기장",
    "노들섬복합문화공간":                "노들섬",
    "광화문광장(광화문)":               "광화문·덕수궁",
    "하늘공원(월드컵공원내)":            "서울월드컵경기장",
    "동대문디자인플라자(DDP)":           "동대문디자인플라자",
    "경복궁":                          "광화문·덕수궁",
    "서울로미디어캔버스":                "명동관광특구",
    "덕수궁":                          "광화문·덕수궁",
    "반포대교 달빛무지개 분수":          "반포한강공원",
    "서울어린이대공원 팔각당 오름광장":   None,
    "올림픽대교":                       "잠실한강공원",
    "세빛섬":                          "반포한강공원",
    "서울함 공원":                      None,
    "낙산공원 - 한양도성 성곽길":        "동대문디자인플라자",
    "아뜰리에 광화":                    "광화문·덕수궁",
    "당산철교":                        "여의도한강공원",
    "세종문화회관":                     "광화문·덕수궁",
    "한강대교":                        "노들섬",
    "동작대교":                        "반포한강공원",
    "서울시립미술관 서소문본관":         "광화문·덕수궁",
    "서울식물원":                       None,
    "덕수궁 돌담길":                    "광화문·덕수궁",
    "광진교 8번가":                     "광나루한강공원",
    "고척스카이돔":                     "고척스카이돔",
    "서울어린이대공원 후문 선형공원":     None,
    "뚝섬 음악분수":                    "뚝섬한강공원",
    "석촌호수 루미나리에(송파나루공원)":  "잠실관광특구",
    "동호대교":                        "반포한강공원",
    "선유도공원":                       None,
    "송파책박물관":                     "잠실관광특구",
    "노원불빛정원(화랑대철도공원 내)":    None,
    "서울어린이대공원 음악분수":          None,
    "성산대교":                        "서울월드컵경기장",
}

# ── 유틸 함수 ─────────────────────────────────────────────────────
def clean_text(value):
    if pd.isna(value):
        return ""
    text = str(value)
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", "", text)
    text = text.replace("~~", "")
    return re.sub(r"\s+", " ", text).strip()

def parse_parking(v: str) -> str:
    if not v or str(v).strip() in ("", "-", "nan"):
        return None   # ← 정보없음 대신 None으로 통일 (필터·표시에서 제외)
    v = str(v).strip()
    for kw in ["불가", "없음", "불가능"]:
        if kw in v: return "불가"
    for kw in ["가능", "있음", "주차장", "무료", "유료"]:
        if kw in v: return "가능"
    return "가능" if len(v) > 1 else None

# ── CSV 로드 ──────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_spot_csv(csv_url: str) -> pd.DataFrame:
    for enc in ["utf-8-sig", "cp949", "euc-kr"]:
        try:
            df = pd.read_csv(csv_url, encoding=enc); break
        except Exception: pass
    else:
        raise ValueError("CSV 읽기 실패")

    df = df.rename(columns={
        "분류": "category", "장소명": "spot_name", "주소": "address",
        "위도": "lat", "경도": "lon", "운영시간": "operation_hours",
        "유무료구분": "free_type", "이용요금": "fee", "내용": "description",
        "주차안내": "parking", "전화번호": "phone", "홈페이지 URL": "homepage_url",
    })

    subway = df["지하철"].fillna("").astype(str).str.strip() if "지하철" in df.columns else pd.Series([""] * len(df))
    bus    = df["버스"].fillna("").astype(str).str.strip()    if "버스"   in df.columns else pd.Series([""] * len(df))
    df["transport"] = [
        f"지하철 {s} / 버스 {b}" if s and b else (f"지하철 {s}" if s else (f"버스 {b}" if b else ""))
        for s, b in zip(subway, bus)
    ]

    if "address" in df.columns:
        df["district"] = df["address"].astype(str).str.extract(r"([가-힣]+구)")[0].fillna("")
    else:
        df["district"] = ""

    df["api_place_name"] = df["spot_name"].map(API_PLACE_MAPPING)
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat", "lon"]).copy()

    for col in ["category","district","address","operation_hours","free_type","fee",
                "transport","parking","description","phone","homepage_url"]:
        if col not in df.columns: df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()

    for col in ["operation_hours","fee","description","parking","transport","address"]:
        df[col] = df[col].apply(clean_text)

    # 주차: None(정보없음) / "가능" / "불가" — None은 UI에서 표시 안 함
    df["parking_available"] = df["parking"].apply(parse_parking)
    return df

# ── 인구 API ──────────────────────────────────────────────────────
def _euckr_encode(name: str) -> str:
    try:
        return quote(name.encode("euc-kr"))
    except (UnicodeEncodeError, LookupError):
        return quote(name.encode("utf-8"))

def call_population_api(api_key: str, place_name: str, timeout: int = 10) -> dict:
    """EUC-KR 인코딩 우선, ERROR-500이면 UTF-8 재시도"""
    urls = [
        f"http://openapi.seoul.go.kr:8088/{api_key}/json/citydata_ppltn/1/5/{_euckr_encode(place_name)}",
        f"http://openapi.seoul.go.kr:8088/{api_key}/json/citydata_ppltn/1/5/{quote(place_name)}",
    ]
    for url in urls:
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            code = (data.get("RESULT") or {}).get("CODE", "")
            if code == "ERROR-500":
                continue   # 다음 인코딩 시도
            return data
        except Exception as e:
            return {"error": str(e)}
    return {"RESULT": {"CODE": "ERROR-500", "MESSAGE": "두 인코딩 모두 실패"}}

def parse_population(raw: dict) -> dict:
    empty = {"congestion": None, "congestion_message": None,
             "male_rate": None, "female_rate": None,
             "ppltn_min": None, "ppltn_max": None}
    if not raw or raw.get("error"):
        return empty
    result = raw.get("RESULT") or {}
    if result.get("CODE") != "INFO-000":
        return empty
    city = raw.get("CITYDATA") or {}
    live = city.get("LIVE_PPLTN_STTS")
    if not live:
        return empty
    item = live[0] if isinstance(live, list) else live
    return {
        "congestion":         item.get("AREA_CONGEST_LVL"),
        "congestion_message": item.get("AREA_CONGEST_MSG"),
        "male_rate":          item.get("MALE_PPLTN_RATE"),
        "female_rate":        item.get("FEMALE_PPLTN_RATE"),
        "ppltn_min":          item.get("AREA_PPLTN_MIN"),
        "ppltn_max":          item.get("AREA_PPLTN_MAX"),
    }

@st.cache_data(ttl=300)
def fetch_population_batch(api_key: str, spot_df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for place_name, grp in spot_df.groupby("api_place_name", dropna=True):
        raw    = call_population_api(api_key, str(place_name))
        parsed = parse_population(raw)
        for spot_name in grp["spot_name"].tolist():
            rows.append({"spot_name": spot_name, "api_place_name": place_name, **parsed})
        time.sleep(0.15)
    return pd.DataFrame(rows)

@st.cache_data(ttl=300)
def load_all_data(csv_url: str, api_key: str | None) -> pd.DataFrame:
    df = load_spot_csv(csv_url)
    if api_key:
        live = fetch_population_batch(api_key, df[df["api_place_name"].notna()])
        df   = df.merge(live[["spot_name","congestion","congestion_message",
                               "male_rate","female_rate","ppltn_min","ppltn_max"]],
                        on="spot_name", how="left")
    else:
        for c in ["congestion","congestion_message","male_rate","female_rate","ppltn_min","ppltn_max"]:
            df[c] = None
    return df

# ── 이미지 스크래핑 ───────────────────────────────────────────────
_HDR = {"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,ko;q=0.9"}

def _valid_img(url: str) -> bool:
    if not url or not url.startswith("http"): return False
    return not any(p in url.lower() for p in ["icon","logo","favicon","pixel","1x1","sprite","blank"])

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_image(homepage_url: str, spot_name: str) -> str | None:
    if homepage_url and homepage_url.startswith("http"):
        try:
            r    = requests.get(homepage_url, headers=_HDR, timeout=7, allow_redirects=True)
            soup = BeautifulSoup(r.text, "html.parser")
            for sel in [("meta", {"property": "og:image"}), ("meta", {"name": "twitter:image"})]:
                tag = soup.find(*sel)
                if tag:
                    src = tag.get("content", "")
                    if not src.startswith("http"): src = urljoin(homepage_url, src)
                    if _valid_img(src): return src
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if not src.startswith("http"): src = urljoin(homepage_url, src)
                try:
                    w = int(str(img.get("width","200")).replace("px",""))
                    h = int(str(img.get("height","150")).replace("px",""))
                except: w, h = 200, 150
                if w >= 100 and h >= 80 and _valid_img(src): return src
        except: pass
    try:
        r    = requests.get(f"https://search.naver.com/search.naver?where=image&query={quote(spot_name+' 서울 야경')}", headers=_HDR, timeout=7)
        soup = BeautifulSoup(r.text, "html.parser")
        for img in soup.select("img._image,.image_result img"):
            src = img.get("src") or img.get("data-lazy-src","")
            if src and src.startswith("http") and _valid_img(src): return src
    except: pass
    return None

# ── 지도 ──────────────────────────────────────────────────────────
def _pin_icon(congestion, parking) -> folium.DivIcon:
    color  = CONGESTION_COLOR.get(congestion, "#8b949e")
    badge  = ""
    if parking == "가능":
        badge = '<div style="position:absolute;top:-5px;right:-5px;width:15px;height:15px;background:#58a6ff;border-radius:50%;border:2px solid #0d1117;font-size:8px;font-weight:800;color:#0d1117;display:flex;align-items:center;justify-content:center;">P</div>'
    elif parking == "불가":
        badge = '<div style="position:absolute;top:-5px;right:-5px;width:15px;height:15px;background:#f85149;border-radius:50%;border:2px solid #0d1117;font-size:9px;font-weight:800;color:#0d1117;display:flex;align-items:center;justify-content:center;">✕</div>'
    return folium.DivIcon(
        html=f'''<div style="position:relative;width:30px;height:38px;">
          <div style="position:absolute;width:30px;height:30px;background:{color};border-radius:50% 50% 50% 0;transform:rotate(-45deg);border:2.5px solid #0d1117;box-shadow:0 3px 8px rgba(0,0,0,0.6);"></div>
          <div style="position:absolute;top:7px;left:7px;width:12px;height:12px;background:#0d1117;border-radius:50%;opacity:0.7;"></div>
          {badge}</div>''',
        icon_size=(30, 38), icon_anchor=(15, 38),
    )

def make_map(df: pd.DataFrame, selected: str | None = None):
    fmap = folium.Map(
        location=SEOUL_CENTER, zoom_start=11,
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> &copy; <a href="https://carto.com/">CARTO</a>',
    )
    for _, row in df.iterrows():
        cong    = row.get("congestion") or "정보없음"
        parking = row.get("parking_available")
        p_label = PARKING_ICON.get(parking, "") + " " + (parking or "") if parking else "정보없음"
        popup_html = f"""<div style="font-family:sans-serif;background:#161b22;color:#e6edf3;padding:10px;border-radius:8px;min-width:180px;border:1px solid #30363d;">
          <b style="font-size:14px;">{row['spot_name']}</b><br>
          <span style="color:{CONGESTION_COLOR.get(cong,'#8b949e')}">● {cong}</span><br>
          {row.get('operation_hours','-')}<br>
          주차: {p_label}
        </div>"""
        icon = _pin_icon(cong, parking)
        if row["spot_name"] == selected:
            icon.options["iconSize"] = [38, 48]; icon.options["iconAnchor"] = [19, 48]
        folium.Marker(
            [row["lat"], row["lon"]], icon=icon,
            popup=folium.Popup(popup_html, max_width=240),
            tooltip=f"<span style='background:#161b22;color:#e6edf3;padding:4px 8px;border-radius:6px;font-size:12px;'>{row['spot_name']} | {cong}</span>",
        ).add_to(fmap)
    # 범례
    fmap.get_root().html.add_child(folium.Element("""
    <div style="position:fixed;bottom:20px;left:20px;z-index:9999;background:#161b22;border:1px solid #30363d;border-radius:10px;padding:10px 14px;font-family:sans-serif;font-size:12px;color:#e6edf3;line-height:1.8;">
      <div style="font-weight:700;margin-bottom:4px;color:#8b949e;">혼잡도</div>
      <span style="color:#3fb950">●</span> 여유 &nbsp;
      <span style="color:#d29922">●</span> 보통 &nbsp;
      <span style="color:#f85149">●</span> 붐빔 &nbsp;
      <span style="color:#8b949e">●</span> 정보없음<br>
      <div style="font-weight:700;margin:4px 0 2px;color:#8b949e;">주차</div>
      <span style="background:#58a6ff;color:#0d1117;border-radius:50%;font-size:9px;font-weight:800;padding:1px 4px;">P</span> 가능 &nbsp;
      <span style="background:#f85149;color:#0d1117;border-radius:50%;font-size:9px;font-weight:800;padding:1px 3px;">✕</span> 불가
    </div>"""))
    return fmap

# ── 카드 ──────────────────────────────────────────────────────────
def congestion_badge(val):
    if not val or val == "정보없음":
        return '<span class="badge" style="background:#21262d;color:#8b949e;">정보없음</span>'
    c = CONGESTION_COLOR.get(val, "#8b949e")
    b = CONGESTION_BG.get(val, "#21262d")
    return f'<span class="badge" style="background:{b};color:{c};border:1px solid {c}40;">{CONGESTION_ICON.get(val,"")} {val}</span>'

def parking_badge(val):
    if not val: return ""
    c = PARKING_COLOR.get(val, "#8b949e")
    b = PARKING_BG.get(val, "#21262d")
    icon = PARKING_ICON.get(val, "")
    return f'<span class="badge" style="background:{b};color:{c};border:1px solid {c}40;">{icon} 주차 {val}</span>'

def render_card(row: pd.Series, show_image: bool = False, compact: bool = False):
    cong    = row.get("congestion")
    parking = row.get("parking_available")
    with st.container(border=True):
        if show_image:
            img = fetch_image(row.get("homepage_url",""), row.get("spot_name",""))
            if img:
                st.image(img, use_container_width=True)
        # 제목 + 배지
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:6px;">'
            f'<span style="font-size:16px;font-weight:700;color:#e6edf3;">{row["spot_name"]}</span>'
            f'<div style="display:flex;gap:6px;flex-shrink:0;">{congestion_badge(cong)}{parking_badge(parking)}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        if not compact:
            # 운영시간 + 분류
            op = row.get("operation_hours","") or ""
            cat = row.get("category","") or ""
            st.markdown(
                f'<div style="color:#8b949e;font-size:13px;margin-bottom:4px;">'
                f'{"🕐 " + op if op else ""}'
                f'{"&nbsp;&nbsp;·&nbsp;&nbsp;" if op and cat else ""}'
                f'{"📍 " + cat if cat else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )
            desc = row.get("description","") or ""
            if desc:
                st.markdown(
                    f'<div style="color:#c9d1d9;font-size:13px;line-height:1.5;margin-top:4px;">'
                    f'{desc[:180]+("..." if len(desc)>180 else "")}</div>',
                    unsafe_allow_html=True,
                )
        district = row.get("district","")
        transport = row.get("transport","")
        if district or transport:
            st.markdown(
                f'<div style="color:#6e7681;font-size:12px;margin-top:6px;">'
                f'{"📌 "+district if district else ""}'
                f'{"　" if district and transport else ""}'
                f'{"🚇 "+transport[:40] if transport else ""}'
                f'</div>',
                unsafe_allow_html=True,
            )

# ── 데이터 로드 ───────────────────────────────────────────────────
api_key = st.secrets.get("SEOUL_API_KEY", None)

try:
    df = load_all_data(CSV_URL, api_key)
except Exception as e:
    st.error(f"데이터 로드 실패: {e}")
    st.stop()

# ── 사이드바 ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌃 서울 야간 명소")
    st.markdown('<div style="height:1px;background:#30363d;margin:8px 0 16px;"></div>', unsafe_allow_html=True)

    # API 키 상태 표시
    if api_key:
        st.markdown('<div style="background:#0d2d1a;border:1px solid #238636;border-radius:8px;padding:8px 12px;color:#3fb950;font-size:13px;">✅ API 키 연결됨</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="background:#2d1e00;border:1px solid #9e6a03;border-radius:8px;padding:8px 12px;color:#d29922;font-size:12px;">⚠️ API 키 없음 — 혼잡도 미표시<br><span style="color:#8b949e;">secrets에 SEOUL_API_KEY 설정 필요</span></div>', unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:#30363d;margin:14px 0;"></div>', unsafe_allow_html=True)

    page = st.radio(
        "페이지",
        ["🏠 홈", "🔍 탐색", "📍 명소 상세", "ℹ️ 서비스 소개"],
        label_visibility="collapsed",
    )

    st.markdown('<div style="height:1px;background:#30363d;margin:14px 0;"></div>', unsafe_allow_html=True)

    # 전역 통계
    total       = len(df)
    easy_cnt    = int((df["congestion"] == "여유").sum())
    parking_cnt = int((df["parking_available"] == "가능").sum())
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
      <div style="background:#21262d;border-radius:8px;padding:10px;text-align:center;">
        <div style="font-size:20px;font-weight:700;color:#e6edf3;">{total}</div>
        <div style="font-size:11px;color:#8b949e;">전체 명소</div>
      </div>
      <div style="background:#0d2d1a;border-radius:8px;padding:10px;text-align:center;">
        <div style="font-size:20px;font-weight:700;color:#3fb950;">{easy_cnt}</div>
        <div style="font-size:11px;color:#8b949e;">여유 명소</div>
      </div>
      <div style="background:#0d2137;border-radius:8px;padding:10px;text-align:center;">
        <div style="font-size:20px;font-weight:700;color:#58a6ff;">{parking_cnt}</div>
        <div style="font-size:11px;color:#8b949e;">주차 가능</div>
      </div>
      <div style="background:#21262d;border-radius:8px;padding:10px;text-align:center;">
        <div style="font-size:20px;font-weight:700;color:#c9d1d9;">{len(df["category"].unique())}</div>
        <div style="font-size:11px;color:#8b949e;">분류 수</div>
      </div>
    </div>
    """, unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# 홈
# ════════════════════════════════════════════════════════════════
if page == "🏠 홈":
    st.markdown("# 오늘 밤, 서울 어디로?")
    st.markdown('<div style="color:#8b949e;margin:-12px 0 20px;">실시간 혼잡도 기반 서울 야간 명소 추천</div>', unsafe_allow_html=True)

    # API 키가 없을 때 안내
    if not api_key:
        st.warning(
            "**혼잡도가 표시되지 않는 이유**\n\n"
            "서울시 실시간 인구 API 키가 설정되지 않았습니다.\n"
            "`.streamlit/secrets.toml`에 `SEOUL_API_KEY = '발급받은키'`를 추가해 주세요.\n\n"
            "> 🔑 [서울 열린데이터광장에서 키 발급](https://data.seoul.go.kr) — "
            "샘플 키는 **광화문·덕수궁** 단 1곳만 조회 가능합니다."
        )

    # 추천 명소
    st.markdown("### 지금 가기 좋은 명소")
    show_img = st.toggle("대표 이미지 표시", value=False, help="홈페이지에서 이미지를 불러옵니다 (속도 저하 가능)")

    # 혼잡도 있는 것 우선, 없으면 전체에서 추천
    temp = df.copy()
    temp["_pri"] = temp["congestion"].map(CONGESTION_PRIORITY).fillna(99)
    rec = temp.sort_values(["_pri","spot_name"]).head(3)

    cols = st.columns(3)
    for i, (_, row) in enumerate(rec.iterrows()):
        with cols[i]:
            render_card(row, show_image=show_img)

    st.markdown("---")
    st.markdown("### 지도")
    st_folium(make_map(df), height=520, width=None, returned_objects=[])


# ════════════════════════════════════════════════════════════════
# 탐색
# ════════════════════════════════════════════════════════════════
elif page == "🔍 탐색":
    st.markdown("# 명소 탐색")

    # ── 필터 바 (상단 가로 배치) ──────────────────────────────
    f1, f2, f3, f4, f5 = st.columns([2, 1, 1, 1, 1])
    with f1: keyword   = st.text_input("🔎 검색", "", placeholder="명소 이름 검색...")
    with f2: sel_cat   = st.selectbox("분류", ["전체"] + sorted([x for x in df["category"].dropna().unique() if x]))
    with f3: sel_cong  = st.selectbox("혼잡도", ["전체", "여유", "보통", "붐빔"])
    with f4: sel_dist  = st.selectbox("지역구", ["전체"] + sorted([x for x in df["district"].dropna().unique() if x]))
    # 주차: "정보없음" 완전 제외
    with f5: sel_park  = st.selectbox("주차", ["전체", "가능", "불가"])

    fdf = df.copy()
    if keyword.strip():
        fdf = fdf[fdf["spot_name"].str.contains(keyword.strip(), case=False, na=False)]
    if sel_cat  != "전체": fdf = fdf[fdf["category"] == sel_cat]
    if sel_cong != "전체": fdf = fdf[fdf["congestion"] == sel_cong]
    if sel_dist != "전체": fdf = fdf[fdf["district"] == sel_dist]
    if sel_park != "전체": fdf = fdf[fdf["parking_available"] == sel_park]

    fdf = fdf.copy()
    fdf["_pri"] = fdf["congestion"].map(CONGESTION_PRIORITY).fillna(99)
    fdf = fdf.sort_values(["_pri","spot_name"])

    st.markdown(f'<div style="color:#8b949e;font-size:13px;margin-bottom:12px;">총 <b style="color:#e6edf3;">{len(fdf)}개</b> 명소</div>', unsafe_allow_html=True)

    tab_card, tab_map, tab_data = st.tabs(["카드", "지도", "표"])

    with tab_card:
        show_img2 = st.toggle("이미지 표시", value=False, key="search_img")
        if len(fdf) == 0:
            st.info("조건에 맞는 명소가 없습니다.")
        else:
            # 2열 그리드
            pairs = list(fdf.iterrows())
            for i in range(0, len(pairs), 2):
                c1, c2 = st.columns(2)
                with c1: render_card(pairs[i][1], show_image=show_img2)
                if i+1 < len(pairs):
                    with c2: render_card(pairs[i+1][1], show_image=show_img2)

    with tab_map:
        if len(fdf) == 0: st.info("표시할 명소 없음")
        else: st_folium(make_map(fdf), height=560, width=None, returned_objects=[])

    with tab_data:
        show_cols = ["spot_name","category","district","operation_hours",
                     "free_type","parking_available","congestion","congestion_message"]
        st.dataframe(fdf[[c for c in show_cols if c in fdf.columns]],
                     use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════
# 명소 상세
# ════════════════════════════════════════════════════════════════
elif page == "📍 명소 상세":
    st.markdown("# 명소 상세")

    sel_name = st.selectbox("명소 선택", sorted(df["spot_name"].astype(str).tolist()), label_visibility="collapsed")
    row = df[df["spot_name"] == sel_name].iloc[0]

    cong    = row.get("congestion")
    parking = row.get("parking_available")

    # 헤더
    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin:8px 0 16px;">'
        f'<h2 style="margin:0;color:#e6edf3;">{sel_name}</h2>'
        f'{congestion_badge(cong)}{parking_badge(parking)}</div>',
        unsafe_allow_html=True,
    )

    left, right = st.columns([3, 2])

    with left:
        # 이미지
        with st.spinner("이미지 불러오는 중..."):
            img = fetch_image(row.get("homepage_url",""), sel_name)
        if img:
            st.image(img, use_container_width=True)

        # 혼잡 메시지
        msg = row.get("congestion_message","")
        if msg:
            color = CONGESTION_COLOR.get(cong, "#8b949e")
            st.markdown(
                f'<div style="background:{CONGESTION_BG.get(cong,"#21262d")};border:1px solid {color}40;'
                f'border-radius:8px;padding:10px 14px;color:{color};font-size:13px;margin-bottom:12px;">'
                f'💬 {msg}</div>',
                unsafe_allow_html=True,
            )

        st.markdown("**장소 설명**")
        desc = row.get("description","") or "설명 없음"
        st.markdown(f'<div style="color:#c9d1d9;font-size:14px;line-height:1.7;">{desc}</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:1px;background:#30363d;margin:14px 0;"></div>', unsafe_allow_html=True)
        st.markdown("**이용 정보**")
        info_items = [
            ("📍 주소",    row.get("address","")),
            ("🕐 운영시간", row.get("operation_hours","")),
            ("💰 요금",    f'{row.get("free_type","")} {row.get("fee","")}'.strip()),
            ("🚇 교통",    row.get("transport","")),
            ("🅿️ 주차",   row.get("parking","")),
            ("📞 전화",    row.get("phone","")),
            ("🔗 홈페이지", row.get("homepage_url","")),
        ]
        for label, val in info_items:
            if val and str(val).strip() not in ("", "-"):
                st.markdown(
                    f'<div style="display:flex;gap:10px;padding:4px 0;border-bottom:1px solid #21262d;">'
                    f'<span style="color:#8b949e;font-size:13px;min-width:80px;">{label}</span>'
                    f'<span style="color:#c9d1d9;font-size:13px;">{val}</span></div>',
                    unsafe_allow_html=True,
                )

    with right:
        # 실시간 인구 지표
        st.markdown("**실시간 인구 현황**")
        pmin = row.get("ppltn_min"); pmax = row.get("ppltn_max")
        mrate = row.get("male_rate"); frate = row.get("female_rate")

        if cong:
            c1r, c2r = st.columns(2)
            with c1r:
                st.metric("혼잡도", cong)
                if mrate: st.metric("남성 비율", f"{mrate}%")
            with c2r:
                if pmin and pmax: st.metric("추정 인구", f"{pmin}~{pmax}명")
                if frate: st.metric("여성 비율", f"{frate}%")
        else:
            if api_key:
                st.markdown('<div style="color:#8b949e;font-size:13px;background:#21262d;border-radius:8px;padding:12px;">이 장소는 실시간 API 미지원 장소입니다.</div>', unsafe_allow_html=True)
            else:
                st.markdown('<div style="color:#d29922;font-size:13px;background:#2d1e00;border:1px solid #9e6a0340;border-radius:8px;padding:12px;">API 키가 없어 혼잡도를 불러올 수 없습니다.</div>', unsafe_allow_html=True)

        st.markdown('<div style="height:1px;background:#30363d;margin:14px 0;"></div>', unsafe_allow_html=True)
        st.markdown("**위치**")
        mini_df = df[df["spot_name"] == sel_name]
        st_folium(make_map(mini_df, selected=sel_name), height=240, width=None, returned_objects=[])

    # 대체 명소
    st.markdown('<div style="height:1px;background:#30363d;margin:20px 0 14px;"></div>', unsafe_allow_html=True)
    st.markdown("**같은 분류 다른 명소**")
    alt = df[(df["spot_name"] != sel_name) & (df["category"] == row["category"])].copy()
    alt["_pri"] = alt["congestion"].map(CONGESTION_PRIORITY).fillna(99)
    alt = alt.sort_values(["_pri","spot_name"]).head(3)
    if len(alt) == 0:
        st.info("추천할 대체 명소가 없습니다.")
    else:
        ac1, ac2, ac3 = st.columns(3)
        for col, (_, arow) in zip([ac1, ac2, ac3], alt.iterrows()):
            with col: render_card(arow, compact=True)


# ════════════════════════════════════════════════════════════════
# 서비스 소개
# ════════════════════════════════════════════════════════════════
elif page == "ℹ️ 서비스 소개":
    st.markdown("# 서비스 소개")
    st.markdown("""
    <div style="color:#c9d1d9;line-height:1.8;font-size:15px;">
    서울시 공공데이터를 활용해 야간 명소의 <b style="color:#e6edf3;">실시간 혼잡도</b>와
    <b style="color:#e6edf3;">장소 정보</b>를 한눈에 확인할 수 있는 서비스입니다.
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:#30363d;margin:16px 0;"></div>', unsafe_allow_html=True)

    # 혼잡도 안내 박스
    st.markdown("### 혼잡도가 표시되지 않나요?")
    st.markdown("""
    <div style="background:#2d1e00;border:1px solid #9e6a03;border-radius:10px;padding:16px 20px;color:#c9d1d9;font-size:14px;line-height:1.9;">
    <b style="color:#d29922;">⚠️ 샘플 키 사용 시 제한사항</b><br>
    서울시 실시간 인구 API 샘플 키는 <b style="color:#e6edf3;">122개 장소 중 '광화문·덕수궁' 단 1곳</b>만 조회 가능합니다.<br>
    나머지 장소는 모두 <code>ERROR-500</code>이 반환되어 혼잡도가 표시되지 않습니다.<br><br>
    <b style="color:#d29922;">✅ 해결 방법</b><br>
    1. <a href="https://data.seoul.go.kr" style="color:#58a6ff;">서울 열린데이터광장</a>에서 정식 API 키 발급<br>
    2. <code>.streamlit/secrets.toml</code>에 아래 내용 추가:
    <pre style="background:#161b22;border-radius:6px;padding:8px 12px;margin-top:8px;color:#3fb950;">SEOUL_API_KEY = "발급받은_키_입력"</pre>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div style="height:1px;background:#30363d;margin:16px 0;"></div>', unsafe_allow_html=True)

    with st.expander("📊 데이터 미리보기"):
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)

    with st.expander("🗺️ API 장소명 매핑 현황"):
        mv = df[["spot_name","api_place_name"]].copy()
        mv["매핑 상태"] = mv["api_place_name"].apply(lambda x: "✅ 매핑됨" if pd.notna(x) and x else "❌ 미지원")
        st.dataframe(mv, use_container_width=True, hide_index=True)

    with st.expander("🅿️ 주차 현황"):
        pv = df["parking_available"].value_counts().reset_index()
        pv.columns = ["주차 여부", "명소 수"]
        # None 행 제거
        pv = pv[pv["주차 여부"].notna()]
        st.dataframe(pv, use_container_width=True, hide_index=True)

    with st.expander("🔬 API 직접 테스트"):
        st.markdown('<div style="color:#8b949e;font-size:13px;">장소명을 직접 입력해 API 응답을 확인합니다.</div>', unsafe_allow_html=True)
        test_place = st.text_input("장소명", value="광화문·덕수궁", placeholder="예: 광화문·덕수궁, 명동관광특구")
        if st.button("🔍 API 호출", use_container_width=True):
            if not api_key:
                st.error("SEOUL_API_KEY가 설정되지 않았습니다.")
            else:
                with st.spinner("호출 중..."):
                    raw = call_population_api(api_key, test_place.strip())
                code = (raw.get("RESULT") or {}).get("CODE","")
                if code == "INFO-000": st.success(f"✅ 성공 — {code}")
                elif code:             st.error(f"❌ 실패 — {code}: {(raw.get('RESULT') or {}).get('MESSAGE','')}")
                st.json(raw)
