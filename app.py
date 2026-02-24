import streamlit as st
import pandas as pd
import requests
import json
import time
from datetime import datetime
import pytz

# 1. API 보안 정보 (사용자 정보 입력)
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

# 2. 한투 Access Token 발급 (캐싱 적용)
@st.cache_data(ttl=86400)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    res = requests.post(url, data=json.dumps(payload))
    return res.json().get('access_token')

# 3. 실시간 지수 조회 함수 (KOSPI: '0001', KOSDAQ: '1001')
def get_market_index(code, token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-index-price"
    headers = {
        "Content-Type": "application/json",
        "authorization": f"Bearer {token}",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET,
        "tr_id": "FHPST01010000"
    }
    params = {"fid_cond_mrkt_div_code": "U", "fid_input_iscd": code}
    res = requests.get(url, headers=headers, params=params)
    data = res.json().get('output', {})
    return float(data.get('bstp_nmix_prpr', 0)), float(data.get('bstp_nmix_prdy_ctrt', 0))

# 4. 개별 종목 현재가 조회 함수
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
    res = requests.get(url, headers=headers, params=params)
    data = res.json().get('output', {})
    return float(data.get('stck_prpr', 0)), float(data.get('prdy_ctrt', 0))

# 5. 상단 지수 위젯 표시
token = get_access_token()
if token:
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        kp_val, kp_rate = get_market_index("0001", token)
        st.metric("KOSPI", f"{kp_val:,.2f}", f"{kp_rate:+.2f}%")
    with col2:
        kd_val, kd_rate = get_market_index("1001", token)
        st.metric("KOSDAQ", f"{kd_val:,.2f}", f"{kd_rate:+.2f}%")
    with col3:
        st.write(f"⏱️ **마지막 동기화:** {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 시세 즉시 갱신"): st.rerun()

# 6. 데이터 통합 로드 및 판별
def load_data(token):
    try:
        raw_df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}")
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        prog = st.progress(0, text="종목 시세 로드 중...")
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            
            df.at[i, '현재가'] = curr
            df.at[i, '등락률'] = rate / 100
            df.at[i, '기준고점'] = max(high, curr)
            
            time.sleep(0.05) # 지수 조회가 추가되어 속도를 약간 조절
            prog.progress((i+1)/len(df))
        prog.empty()

        # 손절선 및 상태 계산
        df['손절(-10%)'] = df['기준고점'] * 0.90
        df['손절(-15%)'] = df['기준고점'] * 0.85
        df['상태'] = df.apply(lambda r: "🚨위험" if r['현재가'] <= r['손절(-15%)'] else "⚠️주의" if r['현재가'] <= r['손절(-10%)'] else "✅안정", axis=1)
        return df
    except: return pd.DataFrame()

# 7. 메인 화면 출력
final_df = load_data(token)
if not final_df.empty:
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    def apply_style(styler):
        styler.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        def s_color(v):
            if "🚨" in str(v): return 'background-color: #ff4b4b; color: white;'
            if "⚠️" in str(v): return 'background-color: #ffa421; color: black;'
            return 'background-color: #28a745; color: white;'
        styler.applymap(s_color, subset=['상태'])
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
        return styler

    st.dataframe(apply_style(display_df.style.format({
        '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
        '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
    })), use_container_width=True, height=600)
