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

# ── 노을 테마 CSS ─────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Noto+Sans+KR:wght@400;500;700&display=swap');

html, body, [data-testid="stAppViewContainer"] {
    background: linear-gradient(160deg, #1a0a2e 0%, #2d1454 25%, #6b2d6b 55%, #c45c3a 80%, #e8874a 100%) !important;
    background-attachment: fixed !important;
    font-family: 'Noto Sans KR', sans-serif;
}
[data-testid="stSidebar"] {
    background: rgba(15, 5, 30, 0.82) !important;
    border-right: 1px solid rgba(180, 80, 180, 0.25) !important;
    backdrop-filter: blur(12px);
}
[data-testid="stSidebar"] * { color: #f0dff8 !important; }
[data-testid="stSidebar"] .stRadio label { color: #d4b8e8 !important; }

/* 메인 텍스트 */
h1, h2, h3 { color: #ffeedd !important; text-shadow: 0 2px 12px rgba(0,0,0,0.4); }
h1 { font-size: 2rem !important; }
.stMarkdown p, .stMarkdown li { color: #f0d8c8; }

/* 카드 컨테이너 */
[data-testid="stVerticalBlockBorderWrapper"] {
    background: rgba(20, 8, 40, 0.65) !important;
    border: 1px solid rgba(200, 100, 180, 0.3) !important;
    border-radius: 16px !important;
    backdrop-filter: blur(10px);
    box-shadow: 0 4px 24px rgba(0,0,0,0.3) !important;
}

/* 메트릭 */
[data-testid="stMetric"] {
    background: rgba(20, 8, 40, 0.55);
    border: 1px solid rgba(200, 100, 180, 0.25);
    border-radius: 12px;
    padding: 12px 16px !important;
    backdrop-filter: blur(8px);
}
[data-testid="stMetricLabel"] { color: #c8a0d8 !important; font-size: 12px; }
[data-testid="stMetricValue"] { color: #ffeedd !important; }

/* 탭 */
[data-testid="stTabs"] button { color: #c8a0d8; font-weight: 500; }
[data-testid="stTabs"] button[aria-selected="true"] {
    color: #ffb347 !important;
    border-bottom: 2px solid #ffb347 !important;
}

/* 버튼 */
.stButton > button {
    background: rgba(150, 60, 150, 0.35);
    border: 1px solid rgba(200, 100, 180, 0.5);
    color: #ffeedd;
    border-radius: 10px;
    backdrop-filter: blur(6px);
    transition: all 0.2s;
}
.stButton > button:hover {
    background: rgba(200, 80, 120, 0.5);
    border-color: #ffb347;
    color: #ffb347;
}

/* 입력 필드 */
.stSelectbox > div > div,
.stTextInput > div > div {
    background: rgba(20, 8, 40, 0.6) !important;
    border-color: rgba(200, 100, 180, 0.35) !important;
    color: #ffeedd !important;
    border-radius: 10px !important;
    backdrop-filter: blur(6px);
}
.stSelectbox label, .stTextInput label { color: #c8a0d8 !important; }

/* 토글 */
.stToggle label { color: #ffffff !important; font-weight: 500; }
.stCheckbox label { color: #ffffff !important; font-weight: 500; }

/* 캡션 */
.stCaption { color: #a080b8 !important; }

/* 구분선 */
hr { border-color: rgba(200, 100, 180, 0.2) !important; }

/* 알림 박스 */
[data-testid="stInfo"]    { background: rgba(10,40,80,0.55)  !important; border-color: rgba(80,140,255,0.5)  !important; color: #c8deff !important; }
[data-testid="stSuccess"] { background: rgba(10,60,30,0.55)  !important; border-color: rgba(80,200,120,0.5)  !important; color: #c8ffe0 !important; }
[data-testid="stWarning"] { background: rgba(60,35,0,0.55)   !important; border-color: rgba(255,160,50,0.5)  !important; color: #ffe4b0 !important; }
[data-testid="stError"]   { background: rgba(60,10,10,0.55)  !important; border-color: rgba(255,80,80,0.5)   !important; color: #ffc8c8 !important; }

/* expander */
[data-testid="stExpander"] {
    background: rgba(20, 8, 40, 0.5) !important;
    border: 1px solid rgba(200, 100, 180, 0.25) !important;
    border-radius: 12px !important;
}
[data-testid="stExpander"] summary { color: #d4b8e8 !important; }

/* 배지 */
.badge {
    display: inline-block;
    padding: 3px 10px;
    border-radius: 20px;
    font-size: 12px;
    font-weight: 600;
}

/* 스크롤바 */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: rgba(20,8,40,0.3); }
::-webkit-scrollbar-thumb { background: rgba(180,80,180,0.4); border-radius: 3px; }
</style>
""", unsafe_allow_html=True)

# ── 상수 ─────────────────────────────────────────────────────────
SEOUL_CENTER = [37.5665, 126.9780]
CSV_URL = "https://raw.githubusercontent.com/kimhl2261/Attractiveness/main/seoul_night.csv"

CONGESTION_COLOR = {"여유": "#4ade80", "보통": "#fbbf24", "붐빔": "#f87171"}
CONGESTION_BG    = {"여유": "rgba(10,60,30,0.6)", "보통": "rgba(60,40,0,0.6)", "붐빔": "rgba(60,10,10,0.6)"}
CONGESTION_ICON  = {"여유": "🟢", "보통": "🟡", "붐빔": "🔴"}
CONGESTION_PRIORITY = {"여유": 0, "보통": 1, "붐빔": 2, "정보없음": 3}

PARKING_COLOR = {"가능": "#60a5fa", "불가": "#f87171"}
PARKING_ICON  = {"가능": "🅿️", "불가": "⛔"}

# ── ★ 핵심: 서울시 공식 122개 장소명 전체 목록 ───────────────────
# 공식 명칭을 정확히 사용해야 API ERROR-500을 피할 수 있음
# 출처: 서울 열린데이터광장 OA-21778 첨부파일 기준
OFFICIAL_AREA_NAMES = [
    "강남 MICE 관광특구", "동대문 관광특구", "명동 관광특구", "이태원 관광특구",
    "잠실 관광특구", "종로·청계 관광특구", "홍대 관광특구",
    "경복궁", "광화문·덕수궁", "북촌한옥마을", "창덕궁·종묘",
    "덕수궁길·정동길", "인사동·익선동",
    "낙산공원·이화마을", "남산공원",
    "강남역", "건대입구역", "고덕·강일", "고양이마을",
    "고척스카이돔", "교대·강남구청역", "구로디지털단지",
    "국립중앙박물관·용산가족공원",
    "남대문시장", "노들섬", "노원·도봉",
    "뚝섬한강공원", "롯데월드타워·몰",
    "망원한강공원", "명동·남대문·북창동",
    "반포한강공원", "북서울꿈의숲",
    "불광천", "비어있음",
    "서리풀공원·몽마르뜨공원", "서울대공원",
    "서울숲공원", "서울식물원·마곡나루",
    "서울어린이대공원",
    "서울역", "서울월드컵경기장",
    "성수카페거리",
    "수락·불암산", "신도림·디지털단지",
    "신림", "쌍문동역",
    "아차산", "압구정로데오거리",
    "양화한강공원", "여의도·영등포",
    "여의도한강공원",
    "연남동", "연트럴파크",
    "영등포 타임스퀘어", "이촌한강공원",
    "인천공항", "잠실종합운동장",
    "잠실한강공원", "장안평 중고차매매단지",
    "청계산", "청담동 명품거리",
    "청량리 제기동 일대", "총신대입구(이수)",
    "창동 신경제중심지", "코엑스",
    "탑골공원", "파주 아울렛",
    "포이동역 일대", "한강진역",
    "한대앞역", "합정·망원",
    "혜화·이화", "홍대입구역",
    "회기역",
    "DDP(동대문디자인플라자)", "DMC(디지털미디어시티)",
    "e스타디움(구로)",
    # 한강 다리·공원 계열
    "가양한강공원", "광나루한강공원", "난지한강공원",
    "마포한강공원", "서강한강공원",
    # 기타
    "기타",
]

# ── CSV 명소명 → 서울시 API 장소명 매핑 ─────────────────────────
# 왼쪽: CSV spot_name / 오른쪽: OFFICIAL_AREA_NAMES 중 정확한 문자열
SPOT_TO_API: dict[str, str | None] = {
    # 관광특구
    "남산서울타워":                          "명동 관광특구",
    "숭례문(남대문)":                        "명동 관광특구",
    "서울로미디어캔버스":                     "명동 관광특구",
    "남산공원 백범광장- 서울한양도성 성곽":    "남산공원",
    "동대문디자인플라자(DDP)":               "DDP(동대문디자인플라자)",
    "장충체육관":                            "DDP(동대문디자인플라자)",
    "낙산공원 - 한양도성 성곽길":             "낙산공원·이화마을",

    # 고궁·문화유산
    "경복궁":                               "경복궁",
    "창덕궁":                               "창덕궁·종묘",
    "창경궁":                               "창덕궁·종묘",
    "덕수궁":                               "광화문·덕수궁",
    "덕수궁 돌담길":                         "덕수궁길·정동길",
    "광화문광장(광화문)":                    "광화문·덕수궁",
    "아뜰리에 광화":                         "광화문·덕수궁",
    "세종문화회관":                          "광화문·덕수궁",
    "서울시립미술관 서소문본관":              "광화문·덕수궁",

    # 한강공원·다리
    "반포대교 달빛무지개 분수":              "반포한강공원",
    "세빛섬":                               "반포한강공원",
    "동호대교":                             "반포한강공원",
    "동작대교":                             "반포한강공원",
    "여의도한강공원 물빛광장":               "여의도한강공원",
    "당산철교":                             "여의도한강공원",
    "마포대교":                             "마포한강공원",
    "뚝섬 자벌레(한강이야기전시관)":         "뚝섬한강공원",
    "뚝섬 음악분수":                        "뚝섬한강공원",
    "성수대교":                             "뚝섬한강공원",
    "이촌한강공원":                         "이촌한강공원",
    "한강대교":                             "노들섬",
    "노들섬복합문화공간":                    "노들섬",
    "용양봉저정 공원":                      "노들섬",
    "사육신공원":                           "노들섬",
    "올림픽대교":                           "잠실한강공원",
    "광진교 8번가":                         "광나루한강공원",
    "난지거울분수":                         "난지한강공원",

    # 공원·문화
    "청계천":                               "종로·청계 관광특구",
    "국립중앙박물관·용산가족공원":            "국립중앙박물관·용산가족공원",
    "서울함 공원":                          None,
    "서울식물원":                           "서울식물원·마곡나루",
    "선유도공원":                           None,
    "하늘공원(월드컵공원내)":               "서울월드컵경기장",
    "문화비축기지":                         "서울월드컵경기장",
    "서울월드컵경기장":                     "서울월드컵경기장",
    "월드컵대교":                           "서울월드컵경기장",
    "성산대교":                             "서울월드컵경기장",
    "고척스카이돔":                         "고척스카이돔",

    # 어린이대공원 계열
    "서울어린이대공원 내 서울상상나라":       "서울어린이대공원",
    "서울어린이대공원 팔각당 오름광장":       "서울어린이대공원",
    "서울어린이대공원 후문 선형공원":        "서울어린이대공원",
    "서울어린이대공원 음악분수":             "서울어린이대공원",

    # 상권
    "석촌호수 루미나리에(송파나루공원)":      "잠실 관광특구",
    "송파책박물관":                         "잠실 관광특구",

    # API 미지원
    "노원불빛정원(화랑대철도공원 내)":        None,
}


# ── 유틸 ─────────────────────────────────────────────────────────
def clean_text(v):
    if pd.isna(v): return ""
    t = html.unescape(str(v))
    t = re.sub(r"<[^>]+>", "", t).replace("~~", "")
    return re.sub(r"\s+", " ", t).strip()

def parse_parking(v: str) -> str | None:
    v = str(v).strip()
    if not v or v in ("-", "nan", ""): return None
    for kw in ["불가", "없음", "불가능"]:
        if kw in v: return "불가"
    for kw in ["가능", "있음", "주차장", "무료", "유료"]:
        if kw in v: return "가능"
    return "가능" if len(v) > 1 else None


# ── CSV 로드 ──────────────────────────────────────────────────────
@st.cache_data(ttl=600)
def load_spot_csv(url: str) -> pd.DataFrame:
    for enc in ["utf-8-sig", "cp949", "euc-kr"]:
        try:
            df = pd.read_csv(url, encoding=enc); break
        except Exception: pass
    else:
        raise ValueError("CSV 읽기 실패")

    df = df.rename(columns={
        "분류":"category","장소명":"spot_name","주소":"address",
        "위도":"lat","경도":"lon","운영시간":"operation_hours",
        "유무료구분":"free_type","이용요금":"fee","내용":"description",
        "주차안내":"parking","전화번호":"phone","홈페이지 URL":"homepage_url",
    })

    sub = df["지하철"].fillna("").astype(str).str.strip() if "지하철" in df.columns else pd.Series([""]*len(df))
    bus = df["버스"].fillna("").astype(str).str.strip()   if "버스"   in df.columns else pd.Series([""]*len(df))
    df["transport"] = [
        f"지하철 {s} / 버스 {b}" if s and b else (f"지하철 {s}" if s else (f"버스 {b}" if b else ""))
        for s, b in zip(sub, bus)
    ]

    df["district"] = df["address"].astype(str).str.extract(r"([가-힣]+구)")[0].fillna("") if "address" in df.columns else ""
    df["lat"] = pd.to_numeric(df["lat"], errors="coerce")
    df["lon"] = pd.to_numeric(df["lon"], errors="coerce")
    df = df.dropna(subset=["lat","lon"]).copy()

    for col in ["category","district","address","operation_hours","free_type","fee",
                "transport","parking","description","phone","homepage_url"]:
        if col not in df.columns: df[col] = ""
        df[col] = df[col].fillna("").astype(str).str.strip()
    for col in ["operation_hours","fee","description","parking","transport","address"]:
        df[col] = df[col].apply(clean_text)

    # API 매핑: SPOT_TO_API 에서 찾고, 없으면 None
    df["api_place_name"] = df["spot_name"].map(lambda x: SPOT_TO_API.get(x, "UNMAPPED"))
    # UNMAPPED = 매핑 테이블에 없는 신규 명소 (None 처리)
    df.loc[df["api_place_name"] == "UNMAPPED", "api_place_name"] = None

    df["parking_available"] = df["parking"].apply(parse_parking)
    return df


# ── API 호출 ──────────────────────────────────────────────────────
def _encode(name: str) -> str:
    """EUC-KR 우선, 실패 시 UTF-8"""
    try:    return quote(name.encode("euc-kr"))
    except: return quote(name)

def call_api(api_key: str, place_name: str, timeout: int = 10) -> dict:
    """EUC-KR → UTF-8 순으로 시도, 둘 다 ERROR-500이면 그대로 반환"""
    for encoded in [_encode(place_name), quote(place_name)]:
        url = f"http://openapi.seoul.go.kr:8088/{api_key}/json/citydata_ppltn/1/5/{encoded}"
        try:
            r = requests.get(url, timeout=timeout)
            r.raise_for_status()
            data = r.json()
            code = (data.get("RESULT") or {}).get("CODE", "")
            if code != "ERROR-500":
                return data        # 성공 or INFO-000
        except Exception as e:
            return {"error": str(e)}
    return {"RESULT": {"CODE": "ERROR-500", "MESSAGE": f"장소명 불일치: {place_name}"}}

def parse_live(raw: dict) -> dict:
    empty = {k: None for k in ["congestion","congestion_message","male_rate","female_rate","ppltn_min","ppltn_max"]}
    if not raw or raw.get("error"):             return empty
    if (raw.get("RESULT") or {}).get("CODE") != "INFO-000": return empty
    city = raw.get("CITYDATA") or {}
    live = city.get("LIVE_PPLTN_STTS")
    if not live: return empty
    item = live[0] if isinstance(live, list) else live
    return {
        "congestion":         item.get("AREA_CONGEST_LVL"),
        "congestion_message": item.get("AREA_CONGEST_MSG"),
        "male_rate":          item.get("MALE_PPLTN_RATE"),
        "female_rate":        item.get("FEMALE_PPLTN_RATE"),
        "ppltn_min":          item.get("AREA_PPLTN_MIN"),
        "ppltn_max":          item.get("AREA_PPLTN_MAX"),
    }

@st.cache_data(ttl=300, show_spinner="실시간 혼잡도 불러오는 중...")
def load_all_data(csv_url: str, api_key: str | None) -> pd.DataFrame:
    df = load_spot_csv(csv_url)
    for c in ["congestion","congestion_message","male_rate","female_rate","ppltn_min","ppltn_max"]:
        df[c] = None

    if not api_key:
        return df

    unique_places = sorted({
        str(p) for p in df["api_place_name"].dropna().unique()
        if str(p).strip() and str(p) != "None"
    })

    # ★ 중첩 @st.cache_data 금지 — 캐시 없는 함수로 직접 루프 실행
    place_data = {}
    for name in unique_places:
        place_data[name] = parse_live(call_api(api_key, name))
        time.sleep(0.15)

    for place_name, parsed in place_data.items():
        if not parsed or parsed.get("congestion") is None:
            continue
        mask = df["api_place_name"] == place_name
        for col, val in parsed.items():
            df.loc[mask, col] = val

    return df


# ── 이미지 스크래핑 ───────────────────────────────────────────────
_HDR = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9"}

def _valid(url: str) -> bool:
    return bool(url and url.startswith("http") and
                not any(p in url.lower() for p in ["icon","logo","favicon","pixel","1x1","sprite"]))

@st.cache_data(ttl=3600, show_spinner=False)
def fetch_image(homepage_url: str, spot_name: str) -> str | None:
    if homepage_url and homepage_url.startswith("http"):
        try:
            r    = requests.get(homepage_url, headers=_HDR, timeout=7, allow_redirects=True)
            soup = BeautifulSoup(r.text, "html.parser")
            for tag, attr in [("meta",{"property":"og:image"}), ("meta",{"name":"twitter:image"})]:
                el = soup.find(tag, attr)
                if el:
                    src = el.get("content","")
                    if not src.startswith("http"): src = urljoin(homepage_url, src)
                    if _valid(src): return src
            for img in soup.find_all("img", src=True):
                src = img["src"]
                if not src.startswith("http"): src = urljoin(homepage_url, src)
                try:
                    w = int(str(img.get("width","200")).replace("px",""))
                    h = int(str(img.get("height","150")).replace("px",""))
                except: w, h = 200, 150
                if w >= 100 and h >= 80 and _valid(src): return src
        except: pass
    try:
        r    = requests.get(f"https://search.naver.com/search.naver?where=image&query={quote(spot_name+' 서울 야경')}", headers=_HDR, timeout=7)
        soup = BeautifulSoup(r.text, "html.parser")
        for img in soup.select("img._image,.image_result img"):
            src = img.get("src") or img.get("data-lazy-src","")
            if src and src.startswith("http") and _valid(src): return src
    except: pass
    return None


# ── 지도 ──────────────────────────────────────────────────────────
def _pin(congestion, parking) -> folium.DivIcon:
    color = CONGESTION_COLOR.get(congestion, "#c084fc")
    badge = ""
    if parking == "가능":
        badge = '<div style="position:absolute;top:-5px;right:-5px;width:15px;height:15px;background:#60a5fa;border-radius:50%;border:2px solid #fff;font-size:8px;font-weight:800;color:#0a0a1a;display:flex;align-items:center;justify-content:center;">P</div>'
    elif parking == "불가":
        badge = '<div style="position:absolute;top:-5px;right:-5px;width:15px;height:15px;background:#f87171;border-radius:50%;border:2px solid #fff;font-size:8px;font-weight:800;color:#0a0a1a;display:flex;align-items:center;justify-content:center;">✕</div>'
    return folium.DivIcon(
        html=f'''<div style="position:relative;width:30px;height:38px;">
          <div style="position:absolute;width:30px;height:30px;background:{color};border-radius:50% 50% 50% 0;transform:rotate(-45deg);border:2.5px solid rgba(255,255,255,0.8);box-shadow:0 3px 10px rgba(0,0,0,0.5);"></div>
          <div style="position:absolute;top:7px;left:7px;width:12px;height:12px;background:rgba(255,255,255,0.9);border-radius:50%;"></div>
          {badge}</div>''',
        icon_size=(30, 38), icon_anchor=(15, 38))

def make_map(df: pd.DataFrame, selected: str | None = None):
    fmap = folium.Map(
        location=SEOUL_CENTER, zoom_start=11,
        tiles="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png",
        attr="CARTO Dark",
    )
    for _, row in df.iterrows():
        cong    = row.get("congestion") or "정보없음"
        parking = row.get("parking_available")
        p_label = (PARKING_ICON.get(parking,"") + " " + (parking or "")) if parking else "정보없음"
        c_color = CONGESTION_COLOR.get(cong, "#c084fc")
        popup_html = (
            f'<div style="font-family:sans-serif;background:rgba(20,8,40,0.95);color:#ffeedd;'
            f'padding:10px 14px;border-radius:10px;min-width:190px;border:1px solid rgba(200,100,180,0.4);">'
            f'<b style="font-size:14px;">{row["spot_name"]}</b><br>'
            f'<span style="color:{c_color}">● {cong}</span><br>'
            f'{row.get("operation_hours","-")}<br>주차: {p_label}</div>'
        )
        icon = _pin(cong, parking)
        if row["spot_name"] == selected:
            icon.options["iconSize"] = [38,48]; icon.options["iconAnchor"] = [19,48]
        folium.Marker(
            [row["lat"], row["lon"]], icon=icon,
            popup=folium.Popup(popup_html, max_width=240),
            tooltip=f'<span style="background:rgba(20,8,40,0.9);color:#ffeedd;padding:4px 8px;border-radius:6px;font-size:12px;">{row["spot_name"]} | {cong}</span>',
        ).add_to(fmap)

    fmap.get_root().html.add_child(folium.Element("""
    <div style="position:fixed;bottom:20px;left:20px;z-index:9999;
        background:rgba(20,8,40,0.88);border:1px solid rgba(200,100,180,0.3);border-radius:12px;
        padding:10px 14px;font-family:sans-serif;font-size:12px;color:#ffeedd;line-height:2;
        backdrop-filter:blur(8px);">
      <b style="color:#c8a0d8;">혼잡도</b><br>
      <span style="color:#4ade80">●</span> 여유 &nbsp;
      <span style="color:#fbbf24">●</span> 보통 &nbsp;
      <span style="color:#f87171">●</span> 붐빔 &nbsp;
      <span style="color:#c084fc">●</span> 정보없음<br>
      <b style="color:#c8a0d8;">주차</b><br>
      <span style="background:#60a5fa;color:#0a0a1a;border-radius:50%;font-size:9px;font-weight:800;padding:1px 4px;">P</span> 가능 &nbsp;
      <span style="background:#f87171;color:#0a0a1a;border-radius:50%;font-size:9px;font-weight:800;padding:1px 3px;">✕</span> 불가
    </div>"""))
    return fmap


# ── 카드 컴포넌트 ─────────────────────────────────────────────────
def c_badge(val):
    if not val or val == "정보없음":
        return '<span class="badge" style="background:rgba(80,40,100,0.5);color:#c8a0d8;border:1px solid rgba(180,80,180,0.3);">정보없음</span>'
    c = CONGESTION_COLOR[val]; b = CONGESTION_BG[val]
    return f'<span class="badge" style="background:{b};color:{c};border:1px solid {c}40;">{CONGESTION_ICON[val]} {val}</span>'

def p_badge(val):
    if not val: return ""
    c = PARKING_COLOR[val]
    return f'<span class="badge" style="background:rgba(10,30,60,0.55);color:{c};border:1px solid {c}40;">{PARKING_ICON[val]} {val}</span>'

def render_card(row: pd.Series, show_image: bool = False, compact: bool = False):
    cong    = row.get("congestion")
    parking = row.get("parking_available")
    with st.container(border=True):
        if show_image:
            img = fetch_image(row.get("homepage_url",""), row.get("spot_name",""))
            if img:
                st.image(img, use_container_width=True)
        st.markdown(
            f'<div style="display:flex;justify-content:space-between;align-items:flex-start;gap:8px;margin-bottom:6px;">'
            f'<span style="font-size:15px;font-weight:700;color:#ffeedd;">{row["spot_name"]}</span>'
            f'<div style="display:flex;gap:6px;flex-shrink:0;">{c_badge(cong)}{p_badge(parking)}</div>'
            f'</div>', unsafe_allow_html=True)
        if not compact:
            op  = row.get("operation_hours","") or ""
            cat = row.get("category","") or ""
            st.markdown(
                f'<div style="color:#c8a0d8;font-size:13px;margin-bottom:4px;">'
                f'{"🕐 "+op if op else ""}{"  ·  " if op and cat else ""}{"📍 "+cat if cat else ""}</div>',
                unsafe_allow_html=True)
            desc = row.get("description","") or ""
            if desc:
                st.markdown(
                    f'<div style="color:#e8d0c0;font-size:13px;line-height:1.55;margin-top:4px;">'
                    f'{desc[:180]+("..." if len(desc)>180 else "")}</div>',
                    unsafe_allow_html=True)
        dist = row.get("district",""); trs = row.get("transport","")
        if dist or trs:
            st.markdown(
                f'<div style="color:#9070a8;font-size:12px;margin-top:6px;">'
                f'{"📌 "+dist if dist else ""}{"　" if dist and trs else ""}{"🚇 "+trs[:40] if trs else ""}</div>',
                unsafe_allow_html=True)


# ── 데이터 로드 ───────────────────────────────────────────────────
api_key = st.secrets.get("SEOUL_API_KEY", None)
try:
    df = load_all_data(CSV_URL, api_key)
except Exception as e:
    st.error(f"데이터 로드 실패: {e}"); st.stop()


# ── 사이드바 ──────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🌇 서울 야간 명소")
    st.markdown('<hr style="border-color:rgba(200,100,180,0.3);margin:8px 0 16px;">', unsafe_allow_html=True)

    if api_key:
        live_cnt = int(df["congestion"].notna().sum())
        st.markdown(
            f'<div style="background:rgba(10,50,20,0.55);border:1px solid rgba(80,200,100,0.4);'
            f'border-radius:10px;padding:9px 13px;font-size:13px;color:#a0f0b0;margin-bottom:12px;">'
            f'✅ API 연결됨 · 혼잡도 {live_cnt}곳 수신</div>', unsafe_allow_html=True)
    else:
        st.markdown(
            '<div style="background:rgba(60,35,0,0.55);border:1px solid rgba(255,160,50,0.4);'
            'border-radius:10px;padding:9px 13px;font-size:12px;color:#ffd580;margin-bottom:12px;">'
            '⚠️ API 키 없음 — 혼잡도 미표시<br><span style="color:#a080b8;font-size:11px;">'
            'secrets에 SEOUL_API_KEY 추가 필요</span></div>', unsafe_allow_html=True)

    page = st.radio("", ["🏠 홈", "🔍 탐색", "📍 명소 상세", "서비스 소개"], label_visibility="collapsed")

    st.markdown('<hr style="border-color:rgba(200,100,180,0.2);margin:12px 0;">', unsafe_allow_html=True)

    total    = len(df)
    easy_cnt = int((df["congestion"] == "여유").sum())
    park_cnt = int((df["parking_available"] == "가능").sum())
    cat_cnt  = df["category"].nunique()
    st.markdown(f"""
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px;">
      <div style="background:rgba(20,8,40,0.55);border:1px solid rgba(180,80,180,0.25);border-radius:10px;padding:10px;text-align:center;">
        <div style="font-size:22px;font-weight:700;color:#ffeedd;">{total}</div>
        <div style="font-size:11px;color:#c8a0d8;">전체 명소</div>
      </div>
      <div style="background:rgba(10,50,20,0.5);border:1px solid rgba(80,200,100,0.3);border-radius:10px;padding:10px;text-align:center;">
        <div style="font-size:22px;font-weight:700;color:#4ade80;">{easy_cnt}</div>
        <div style="font-size:11px;color:#c8a0d8;">여유 명소</div>
      </div>
      <div style="background:rgba(10,30,60,0.5);border:1px solid rgba(100,160,255,0.3);border-radius:10px;padding:10px;text-align:center;">
        <div style="font-size:22px;font-weight:700;color:#60a5fa;">{park_cnt}</div>
        <div style="font-size:11px;color:#c8a0d8;">주차 가능</div>
      </div>
      <div style="background:rgba(20,8,40,0.55);border:1px solid rgba(180,80,180,0.25);border-radius:10px;padding:10px;text-align:center;">
        <div style="font-size:22px;font-weight:700;color:#f0c8ff;">{cat_cnt}</div>
        <div style="font-size:11px;color:#c8a0d8;">분류 수</div>
      </div>
    </div>""", unsafe_allow_html=True)


# ════════════════════════════════════════════════════════════════
# 홈
# ════════════════════════════════════════════════════════════════
if page == "🏠 홈":
    st.markdown("# 오늘 밤, 서울 어디로?")
    st.markdown('<div style="color:#d4a8b8;margin:-12px 0 20px;font-size:15px;">실시간 혼잡도로 찾는 서울 야간 명소</div>', unsafe_allow_html=True)

    show_img = st.toggle("대표 이미지 표시", value=False, help="홈페이지에서 이미지를 불러옵니다 (속도 저하 가능)")

    st.markdown("### 지금 가기 좋은 명소")
    temp = df.copy()
    temp["_p"] = temp["congestion"].map(CONGESTION_PRIORITY).fillna(99)
    rec = temp.sort_values(["_p","spot_name"]).head(3)

    for c, (_, row) in zip(st.columns(3), rec.iterrows()):
        with c: render_card(row, show_image=show_img)

    st.markdown("---")
    st.markdown("### 서울 야간 명소 지도")
    st_folium(make_map(df), height=520, width=None, returned_objects=[])


# ════════════════════════════════════════════════════════════════
# 탐색
# ════════════════════════════════════════════════════════════════
elif page == "🔍 탐색":
    st.markdown("# 명소 탐색")

    f1,f2,f3,f4,f5 = st.columns([2,1,1,1,1])
    with f1: kw      = st.text_input("🔎 검색","",placeholder="명소 이름 검색...")
    with f2: sel_cat  = st.selectbox("분류", ["전체"]+sorted([x for x in df["category"].dropna().unique() if x]))
    with f3: sel_cong = st.selectbox("혼잡도", ["전체","여유","보통","붐빔"])
    with f4: sel_dist = st.selectbox("지역구", ["전체"]+sorted([x for x in df["district"].dropna().unique() if x]))
    with f5: sel_park = st.selectbox("주차", ["전체","가능","불가"])

    fdf = df.copy()
    if kw.strip():        fdf = fdf[fdf["spot_name"].str.contains(kw.strip(), case=False, na=False)]
    if sel_cat  != "전체": fdf = fdf[fdf["category"] == sel_cat]
    if sel_cong != "전체": fdf = fdf[fdf["congestion"] == sel_cong]
    if sel_dist != "전체": fdf = fdf[fdf["district"] == sel_dist]
    if sel_park != "전체": fdf = fdf[fdf["parking_available"] == sel_park]

    fdf = fdf.copy()
    fdf["_p"] = fdf["congestion"].map(CONGESTION_PRIORITY).fillna(99)
    fdf = fdf.sort_values(["_p","spot_name"])

    st.markdown(f'<div style="color:#c8a0d8;font-size:13px;margin-bottom:12px;">총 <b style="color:#ffeedd;">{len(fdf)}개</b> 명소</div>', unsafe_allow_html=True)

    tab_card, tab_map, tab_data = st.tabs(["카드", "지도", "표"])
    with tab_card:
        show_img2 = st.toggle("이미지 표시", value=False, key="img2")
        if not len(fdf): st.info("조건에 맞는 명소가 없습니다.")
        else:
            pairs = list(fdf.iterrows())
            for i in range(0, len(pairs), 2):
                c1, c2 = st.columns(2)
                with c1: render_card(pairs[i][1], show_image=show_img2)
                if i+1 < len(pairs):
                    with c2: render_card(pairs[i+1][1], show_image=show_img2)
    with tab_map:
        if not len(fdf): st.info("표시할 명소 없음")
        else: st_folium(make_map(fdf), height=560, width=None, returned_objects=[])
    with tab_data:
        cols = ["spot_name","category","district","operation_hours","free_type","parking_available","api_place_name","congestion","congestion_message"]
        st.dataframe(fdf[[c for c in cols if c in fdf.columns]], use_container_width=True, hide_index=True)


# ════════════════════════════════════════════════════════════════
# 명소 상세
# ════════════════════════════════════════════════════════════════
elif page == "📍 명소 상세":
    st.markdown("# 명소 상세")
    sel = st.selectbox("명소 선택", sorted(df["spot_name"].astype(str).tolist()), label_visibility="collapsed")
    row = df[df["spot_name"] == sel].iloc[0]

    cong    = row.get("congestion")
    parking = row.get("parking_available")

    st.markdown(
        f'<div style="display:flex;align-items:center;gap:12px;margin:8px 0 16px;">'
        f'<h2 style="margin:0;color:#ffeedd;">{sel}</h2>'
        f'{c_badge(cong)}{p_badge(parking)}</div>', unsafe_allow_html=True)

    left, right = st.columns([3,2])
    with left:
        with st.spinner("이미지 불러오는 중..."): img = fetch_image(row.get("homepage_url",""), sel)
        if img: st.image(img, use_container_width=True)

        msg = row.get("congestion_message","")
        if msg:
            cc = CONGESTION_COLOR.get(cong,"#c084fc"); cb = CONGESTION_BG.get(cong,"rgba(40,10,60,0.6)")
            st.markdown(
                f'<div style="background:{cb};border:1px solid {cc}40;border-radius:10px;'
                f'padding:10px 14px;color:{cc};font-size:13px;margin-bottom:12px;">💬 {msg}</div>',
                unsafe_allow_html=True)

        st.markdown('<b style="color:#ffeedd;">장소 설명</b>', unsafe_allow_html=True)
        st.markdown(f'<div style="color:#e8d0c0;font-size:14px;line-height:1.7;">{row.get("description","") or "설명 없음"}</div>', unsafe_allow_html=True)
        st.markdown('<hr style="border-color:rgba(200,100,180,0.2);margin:14px 0;">', unsafe_allow_html=True)
        st.markdown('<b style="color:#ffeedd;">이용 정보</b>', unsafe_allow_html=True)
        for label, key in [("📍 주소","address"),("🕐 운영시간","operation_hours"),
                            ("💰 요금","fee"),("🚇 교통","transport"),
                            ("🅿️ 주차","parking"),("📞 전화","phone"),("🔗 홈페이지","homepage_url")]:
            val = row.get(key,"") or ""
            if val.strip() and val.strip() != "-":
                st.markdown(
                    f'<div style="display:flex;gap:10px;padding:4px 0;border-bottom:1px solid rgba(150,60,150,0.2);">'
                    f'<span style="color:#c8a0d8;font-size:13px;min-width:80px;">{label}</span>'
                    f'<span style="color:#e8d0c0;font-size:13px;">{val}</span></div>',
                    unsafe_allow_html=True)

    with right:
        st.markdown('<b style="color:#ffeedd;">실시간 인구 현황</b>', unsafe_allow_html=True)
        api_name = row.get("api_place_name","")
        if api_name:
            st.markdown(f'<div style="color:#9070a8;font-size:12px;margin-bottom:8px;">API 매핑: {api_name}</div>', unsafe_allow_html=True)

        if cong:
            c1r, c2r = st.columns(2)
            with c1r:
                st.metric("혼잡도", cong)
                if row.get("male_rate"): st.metric("남성 비율", f'{row["male_rate"]}%')
            with c2r:
                pmin = row.get("ppltn_min"); pmax = row.get("ppltn_max")
                if pmin and pmax: st.metric("추정 인구", f"{pmin}~{pmax}명")
                if row.get("female_rate"): st.metric("여성 비율", f'{row["female_rate"]}%')
        else:
            msg_text = "API 미지원 장소입니다." if api_key and not api_name else \
                       "API 매핑 결과 혼잡도를 가져오지 못했습니다." if api_key else \
                       "API 키 미설정"
            st.markdown(
                f'<div style="color:#c8a0d8;font-size:13px;background:rgba(40,10,60,0.5);'
                f'border-radius:10px;padding:12px;">{msg_text}</div>', unsafe_allow_html=True)

        st.markdown('<hr style="border-color:rgba(200,100,180,0.2);margin:14px 0;">', unsafe_allow_html=True)
        st.markdown('<b style="color:#ffeedd;">위치</b>', unsafe_allow_html=True)
        st_folium(make_map(df[df["spot_name"]==sel], selected=sel), height=250, width=None, returned_objects=[])

    st.markdown('<hr style="border-color:rgba(200,100,180,0.2);margin:20px 0 14px;">', unsafe_allow_html=True)
    st.markdown('<b style="color:#ffeedd;">같은 분류 다른 명소</b>', unsafe_allow_html=True)
    alt = df[(df["spot_name"]!=sel)&(df["category"]==row["category"])].copy()
    alt["_p"] = alt["congestion"].map(CONGESTION_PRIORITY).fillna(99)
    alt = alt.sort_values(["_p","spot_name"]).head(3)
    if not len(alt): st.info("추천할 대체 명소 없음")
    else:
        for c, (_,ar) in zip(st.columns(3), alt.iterrows()):
            with c: render_card(ar, compact=True)


# ════════════════════════════════════════════════════════════════
# 서비스 소개
# ════════════════════════════════════════════════════════════════
elif page == "서비스 소개":
    st.markdown("# 서비스 소개")

    st.markdown("""
    <div style="color:#e8d0c0;line-height:1.9;font-size:15px;">
    서울시 공공데이터를 활용해 야간 명소의 <b style="color:#ffeedd;">실시간 혼잡도</b>와
    <b style="color:#ffeedd;">장소 정보</b>를 한눈에 확인하는 서비스입니다.<br><br>
    <b style="color:#ffb347;">장소명 매핑 방식:</b> CSV의 명소명과 서울시 API의 공식 122개 장소명은 서로 다릅니다.
    <code>SPOT_TO_API</code> 딕셔너리로 양쪽을 연결하며, 매핑 안 된 명소는 혼잡도가 표시되지 않습니다.
    </div>""", unsafe_allow_html=True)

    st.markdown('<hr style="border-color:rgba(200,100,180,0.2);margin:16px 0;">', unsafe_allow_html=True)

    # 매핑 현황 테이블
    with st.expander("🗺️ CSV 명소 ↔ API 장소명 매핑 현황"):
        mv = df[["spot_name","api_place_name","congestion"]].copy()
        mv["매핑"] = mv["api_place_name"].apply(
            lambda x: "✅ 매핑됨" if pd.notna(x) and x else "❌ 미매핑")
        mv["혼잡도 수신"] = mv["congestion"].apply(
            lambda x: "✅ " + str(x) if pd.notna(x) else "—")
        mv = mv.rename(columns={"spot_name":"CSV 명소명","api_place_name":"API 장소명"})
        st.dataframe(mv[["CSV 명소명","API 장소명","매핑","혼잡도 수신"]], use_container_width=True, hide_index=True)

    with st.expander("🔬 API 직접 테스트"):
        st.markdown('<div style="color:#c8a0d8;font-size:13px;margin-bottom:8px;">장소명을 직접 입력해 API 응답을 확인합니다.</div>', unsafe_allow_html=True)

        mapped_places = sorted({
            str(p) for p in df["api_place_name"].dropna().unique()
            if str(p).strip() and str(p) != "None"
        })
        ca, cb2 = st.columns(2)
        with ca: sel_test = st.selectbox("매핑된 장소 선택", ["직접 입력"] + mapped_places)
        with cb2: manual  = st.text_input("또는 직접 입력", "", placeholder="광화문·덕수궁")

        test_place = manual.strip() if sel_test == "직접 입력" else sel_test

        if st.button("🔍 API 호출", use_container_width=True):
            if not api_key:
                st.error("SEOUL_API_KEY가 설정되지 않았습니다.")
            elif not test_place:
                st.warning("장소명을 선택하거나 입력해 주세요.")
            else:
                euckr_url = f".../{_encode(test_place)}"
                st.markdown(
                    f'<div style="background:rgba(20,8,40,0.7);border-radius:8px;padding:10px;'
                    f'font-size:12px;color:#c8a0d8;margin-bottom:8px;font-family:monospace;">'
                    f'EUC-KR: {euckr_url}<br>UTF-8: .../{quote(test_place)}</div>',
                    unsafe_allow_html=True)

                with st.spinner(f"'{test_place}' 호출 중..."):
                    raw = call_api(api_key, test_place)

                code = (raw.get("RESULT") or {}).get("CODE","")
                if code == "INFO-000":
                    parsed = parse_live(raw)
                    st.success(f"✅ 성공! 혼잡도 → **{parsed.get('congestion','N/A')}**")
                    c1,c2,c3 = st.columns(3)
                    c1.metric("혼잡도",    parsed.get("congestion") or "-")
                    c2.metric("추정 인구", f"{parsed.get('ppltn_min','-')}~{parsed.get('ppltn_max','-')}명")
                    c3.metric("성비",      f"남 {parsed.get('male_rate','-')}% / 여 {parsed.get('female_rate','-')}%")
                elif code == "ERROR-500":
                    st.error("❌ ERROR-500 — 장소명이 API 공식 목록과 정확히 일치하지 않습니다.\n\n공식 장소명 예: `광화문·덕수궁`, `명동 관광특구`, `홍대 관광특구`")
                else:
                    st.error(f"❌ {code} — {(raw.get('RESULT') or {}).get('MESSAGE','')}")

                with st.expander("원본 JSON"):
                    st.json(raw)

    with st.expander("📊 데이터 미리보기"):
        st.dataframe(df.head(10), use_container_width=True, hide_index=True)

    with st.expander("🅿️ 주차 현황"):
        pv = df["parking_available"].value_counts().reset_index().dropna()
        pv.columns = ["주차","명소 수"]
        st.dataframe(pv, use_container_width=True, hide_index=True)
