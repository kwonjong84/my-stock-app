import streamlit as st
import pandas as pd
import requests
import json
import time
import yfinance as yf # 3차 백업용 지수 라이브러리
from datetime import datetime
import pytz

# 1. API 보안 정보
APP_KEY = st.secrets["APP_KEY"]
APP_SECRET = st.secrets["APP_SECRET"]
BASE_URL = "https://openapi.koreainvestment.com:9443"

SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 실시간 감시 (지수 완결판)", layout="wide")

# 2. 한투 Access Token 발급
@st.cache_data(ttl=86400)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(url, data=json.dumps(payload), timeout=5)
        return res.json().get('access_token')
    except: return None

# 3. [최종 병기] Yahoo Finance를 이용한 지수 조회
def get_index_yf():
    try:
        # 코스피(^KS11), 코스닥(^KQ11)
        tickers = yf.Tickers('^KS11 ^KQ11')
        kp = tickers.tickers['^KS11'].fast_info
        kd = tickers.tickers['^KQ11'].fast_info
        
        # (현재가, 등락률)
        kp_data = (kp.last_price, (kp.last_price / kp.previous_close - 1) * 100)
        kd_data = (kd.last_price, (kd.last_price / kd.previous_close - 1) * 100)
        return kp_data, kd_data
    except:
        return (0.0, 0.0), (0.0, 0.0)

# 4. 한투 종목 현재가 조회
def get_current_price(code, token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {"Content-Type": "application/json", "authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010100"}
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        out = res.json().get('output', {})
        return float(out.get('stck_prpr', 0)), float(out.get('prdy_ctrt', 0))
    except: return 0.0, 0.0

# 5. UI 출력 로직
token = get_access_token()
if token:
    # 지수 로드 (YFinance)
    kp, kd = get_index_yf()
    
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.metric("KOSPI", f"{kp[0]:,.2f}", f"{kp[1]:+.2f}%")
    with col2:
        st.metric("KOSDAQ", f"{kd[0]:,.2f}", f"{kd[1]:+.2f}%")
    with col3:
        st.write(f"⏱️ **업데이트:** {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 시세 새로고침"): st.rerun()

    # 6. 데이터 로드
    try:
        df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7]
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        prog = st.progress(0, text="한투 실시간 데이터 수신 중...")
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            df.at[i, '현재가'], df.at[i, '등락률'], df.at[i, '기준고점'] = curr, rate/100, max(high, curr)
            time.sleep(0.05)
            prog.progress((i+1)/len(df))
        prog.empty()

        # 계산 및 상태
        df['손절(-10%)'], df['손절(-15%)'] = df['기준고점']*0.9, df['기준고점']*0.85
        df['상태'] = df.apply(lambda r: "🚨위험" if r['현재가'] <= r['손절(-15%)'] else "⚠️주의" if r['현재가'] <= r['손절(-10%)'] else "✅안정", axis=1)

        # 7. 출력
        view = df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
        
        def apply_style(styler):
            styler.map(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
            def s_bg(v):
                if "🚨" in str(v): return 'background-color: #ff4b4b; color: white;'
                if "⚠️" in str(v): return 'background-color: #ffa421; color: black;'
                return 'background-color: #28a745; color: white;'
            styler.map(s_bg, subset=['상태'])
            styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
            return styler

        st.dataframe(apply_style(view.style.format({
            '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
            '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
        })), use_container_width=True, height=600)
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
