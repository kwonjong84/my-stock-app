import streamlit as st
import pandas as pd
import requests
import json
import time
from datetime import datetime
import pytz

# 1. API 보안 정보 (사용자님의 키를 입력하세요)
APP_KEY = "PSauHiM9UT2XGwV0tAIWA6c9a9znz5tDLLha"
APP_SECRET = "qq0Kun7IXWgjgnn29cqieu+n6IhUFApMDYzgbaOsflLTPMZtz4l83vc+LywIyT7PZPJyboFSvwYiGuAcElLNvR4LXl+PTO91LdMXnsuwpGedz+Jqo7RoTP2+b27AK4HafMCt2Ru4lJfH4FcrAnGmNs2DkBzNOmBuRcIPodfxe7uLMjHqI7U="
BASE_URL = "https://openapi.koreainvestment.com:9443"

# 기존 텔레그램 및 시트 정보
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 실시간 감시 Pro", layout="wide")

# 2. 한투 Access Token 발급
@st.cache_data(ttl=86400)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    res = requests.post(url, data=json.dumps(payload))
    return res.json().get('access_token')

# 3. 실시간 지수 조회 함수 (완전 보정본)
# 기존 get_market_index를 버리고, 이 방식으로 시도해보세요.
def get_market_index_alt(code, token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01010100" # 지수 전용이 아닌, 일반 주식 조회용 TR 사용
    }
    # 코스피: '001', 코스닥: '101' 또는 '0001', '1001'
    params = {"fid_cond_mrkt_div_code": "U", "fid_input_iscd": code} 
    try:
        res = requests.get(url, headers=headers, params=params)
        data = res.json().get('output', {})
        return float(data.get('stck_prpr', 0)), float(data.get('prdy_ctrt', 0))
    except:
        return 0.0, 0.0

# 4. 종목 현재가 조회 함수
def get_current_price(code, token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHKST01010100"
    }
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    try:
        res = requests.get(url, headers=headers, params=params)
        output = res.json().get('output', {})
        return float(output.get('stck_prpr', 0)), float(output.get('prdy_ctrt', 0))
    except:
        return 0.0, 0.0

# 5. 화면 상단 지수 위젯 레이아웃
token = get_access_token()

if token:
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1:
        kp_v, kp_r = get_market_index("0001", token) # 코스피
        st.metric("KOSPI", f"{kp_v:,.2f}", f"{kp_r:+.2f}%")
    with c2:
        kd_v, kd_r = get_market_index("1001", token) # 코스닥
        st.metric("KOSDAQ", f"{kd_v:,.2f}", f"{kd_r:+.2f}%")
    with c3:
        st.write(f"⏱️ **최근 갱신:** {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 실시간 시세 동기화"):
            st.rerun()

# 6. 데이터 통합 로직
def load_and_process(token):
    try:
        raw = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}")
        df = raw.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        prog = st.progress(0, text="한투 실시간 시세 연결 중...")
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            
            high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            df.at[i, '현재가'] = curr
            df.at[i, '등락률'] = rate / 100
            df.at[i, '기준고점'] = max(high, curr)
            
            time.sleep(0.05) # 호출 제한 방지
            prog.progress((i+1)/len(df))
        prog.empty()

        # 계산 로직
        df['손절(-10%)'] = df['기준고점'] * 0.90
        df['손절(-15%)'] = df['기준고점'] * 0.85
        def get_state(r):
            if r['현재가'] <= 0: return "⏳ 대기"
            if r['현재가'] <= r['손절(-15%)']: return "🚨위험"
            if r['현재가'] <= r['손절(-10%)']: return "⚠️주의"
            return "✅안정"
        df['상태'] = df.apply(get_state, axis=1)
        return df
    except Exception as e:
        st.error(f"데이터 처리 중 오류: {e}")
        return pd.DataFrame()

# 7. 메인 데이터프레임 출력
final_df = load_and_process(token)

if not final_df.empty:
    view_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    def style_df(styler):
        # 등락률 색상
        styler.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        # 상태 배경색
        def bg_color(v):
            if "🚨" in str(v): return 'background-color: #ff4b4b; color: white;'
            if "⚠️" in str(v): return 'background-color: #ffa421; color: black;'
            if "✅" in str(v): return 'background-color: #28a745; color: white;'
            return ''
        styler.applymap(bg_color, subset=['상태'])
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
        return styler

    st.dataframe(style_df(view_df.style.format({
        '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
        '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
    })), use_container_width=True, height=600)
