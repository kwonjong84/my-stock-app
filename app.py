import streamlit as st
import pandas as pd
import requests
import json
import time
from datetime import datetime
import pytz

# 1. 설정 정보
APP_KEY = st.secrets["APP_KEY"]
APP_SECRET = st.secrets["APP_SECRET"]
TG_TOKEN = st.secrets["TG_TOKEN"]
TG_ID = st.secrets["TG_ID"]
BASE_URL = "https://openapi.koreainvestment.com:9443"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 실시간 감시 (한투 전용)", layout="wide")

if 'alert_history' not in st.session_state:
    st.session_state.alert_history = set()

# 2. 유틸리티 함수
def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": int(TG_ID), "text": message}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

@st.cache_data(ttl=36000)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(url, data=json.dumps(payload), timeout=5)
        return res.json().get('access_token')
    except: return None

def get_market_index(token, code="0001"): # 0001: 코스피, 1001: 코스닥
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-index-price"
    headers = {
        "Content-Type": "application/json", "authorization": f"Bearer {token}",
        "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST03010100"
    }
    params = {"fid_cond_mrkt_div_code": "U", "fid_input_iscd": code}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        out = res.json().get('output', {})
        return float(out.get('bstp_nmix_prpr', 0)), float(out.get('bstp_nmix_prdy_ctrt', 0))
    except: return 0.0, 0.0

def get_current_price(code, token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {
        "Content-Type": "application/json", "authorization": f"Bearer {token}",
        "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010100"
    }
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        out = res.json().get('output', {})
        return float(out.get('stck_prpr', 0)), float(out.get('prdy_ctrt', 0))
    except: return 0.0, 0.0

# 3. 메인 로직
token = get_access_token()
if token:
    # 지수 조회 (한투 API 사용)
    kospi_val, kospi_rate = get_market_index(token, "0001")
    kosdaq_val, kosdaq_rate = get_market_index(token, "1001")

    col1, col2, col3 = st.columns([1, 1, 2])
    with col1: st.metric("KOSPI", f"{kospi_val:,.2f}", f"{kospi_rate:+.2f}%")
    with col2: st.metric("KOSDAQ", f"{kosdaq_val:,.2f}", f"{kosdaq_rate:+.2f}%")
    with col3:
        st.write(f"⏱️ **감시 시간:** {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 알림 리셋 & 시세 새로고침"):
            st.session_state.alert_history.clear()
            st.rerun()

    try:
        raw_df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7]
        raw_df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        status_list = []
        
        for i, row in raw_df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            
            if curr <= 0:
                status = "❓데이터오류"
                high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                stop_10, stop_15 = high * 0.9, high * 0.85
            else:
                past_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                high = max(past_high, curr)
                stop_10, stop_15 = high * 0.9, high * 0.85
                
                if curr <= stop_15:
                    status = "🚨위험"
                    if code not in st.session_state.alert_history:
                        send_telegram_msg(f"‼️ [ISA 경보] {row['종목명']} 이탈\n현재가: {curr:,.0f}\n손절가: {stop_15:,.0f}")
                        st.session_state.alert_history.add(code)
                elif curr <= stop_10:
                    status = "⚠️주의"
                else:
                    status = "✅안정"
                    if code in st.session_state.alert_history: st.session_state.alert_history.remove(code)
            
            raw_df.at[i, '현재가'], raw_df.at[i, '등락률'], raw_df.at[i, '기준고점'] = curr, rate/100, high
            raw_df.at[i, '손절(-10%)'], raw_df.at[i, '손절(-15%)'] = stop_10, stop_15
            status_list.append(status)
            time.sleep(0.1)
        
        raw_df['상태'] = status_list
        
        # 4. 스타일링 및 출력
        view_df = raw_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
        styled_df = view_df.style.format({'현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'})
        
        def style_status(val):
            if val == "🚨위험": return 'background-color: #ff4b4b; color: white'
            if val == "⚠️주의": return 'background-color: #ffa500; color: black'
            if val == "✅안정": return 'background-color: #28a745; color: white'
            return 'background-color: #808080; color: white'

        def color_rate(val):
            return 'color: #ff4b4b' if val > 0 else 'color: #1c83e1' if val < 0 else ''

        if '상태' in view_df.columns: styled_df = styled_df.map(style_status, subset=['상태'])
        if '등락률' in view_df.columns: styled_df = styled_df.map(color_rate, subset=['등락률'])

        st.dataframe(styled_df, use_container_width=True, height=600)

    except Exception as e:
        st.error(f"⚠️ 시스템 오류: {e}")
