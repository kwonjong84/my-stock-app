import streamlit as st
import pandas as pd
import requests
import json
import time
import yfinance as yf
from datetime import datetime
import pytz

# 1. 보안 및 설정 (생략된 상단 부분은 기존과 동일)
APP_KEY = st.secrets["APP_KEY"]
APP_SECRET = st.secrets["APP_SECRET"]
TG_TOKEN = st.secrets["TG_TOKEN"]
TG_ID = st.secrets["TG_ID"]
BASE_URL = "https://openapi.koreainvestment.com:9443"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 실시간 감시 (알람 완결판)", layout="wide")

if 'alert_history' not in st.session_state:
    st.session_state.alert_history = set()

def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": int(TG_ID), "text": message}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

@st.cache_data(ttl=86400)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(url, data=json.dumps(payload), timeout=5)
        return res.json().get('access_token')
    except: return None

def get_index_yf():
    try:
        tickers = yf.Tickers('^KS11 ^KQ11')
        kp = tickers.tickers['^KS11'].fast_info
        kd = tickers.tickers['^KQ11'].fast_info
        return (kp.last_price, (kp.last_price / kp.previous_close - 1) * 100), (kd.last_price, (kd.last_price / kd.previous_close - 1) * 100)
    except: return (0.0, 0.0), (0.0, 0.0)

def get_current_price(code, token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {"Content-Type": "application/json", "authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010100"}
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        out = res.json().get('output', {})
        return float(out.get('stck_prpr', 0)), float(out.get('prdy_ctrt', 0))
    except: return 0.0, 0.0

# 6. 메인 로직
token = get_access_token()
if token:
    kp, kd = get_index_yf()
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1: st.metric("KOSPI", f"{kp[0]:,.2f}", f"{kp[1]:+.2f}%")
    with col2: st.metric("KOSDAQ", f"{kd[0]:,.2f}", f"{kd[1]:+.2f}%")
    with col3: 
        st.write(f"⏱️ **업데이트:** {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 시세 새로고침"): st.rerun()

    try:
        df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7]
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        status_list = []
        prog = st.progress(0, text="데이터 분석 중...")
        
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            
            # [핵심 수정] 시트의 100일 고점과 현재 실시간 주가를 비교
            past_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            high = max(past_high, curr) 
            
            stop_10, stop_15 = high * 0.9, high * 0.85
            
            if curr <= stop_15:
                status = "🚨위험"
                if code not in st.session_state.alert_history:
                    send_telegram_msg(f"‼️ [급보] {row['종목명']} 손절가 이탈\n현재가: {curr:,.0f}\n손절기준(-15%): {stop_15:,.0f}")
                    st.session_state.alert_history.add(code)
            elif curr <= stop_10:
                status = "⚠️주의"
            else:
                status = "✅안정"
                if code in st.session_state.alert_history: st.session_state.alert_history.remove(code)
                
            df.at[i, '현재가'], df.at[i, '등락률'], df.at[i, '기준고점'] = curr, rate/100, high
            df.at[i, '손절(-10%)'], df.at[i, '손절(-15%)'] = stop_10, stop_15
            status_list.append(status)
            time.sleep(0.2)
            prog.progress((i+1)/len(df))
        
        df['상태'] = status_list
        prog.empty()

        # 스타일링 함수 정의
        def style_df(df):
            # 1. 등락률 글자색 (양수 빨강, 음수 파랑)
            def color_rate(val):
                color = '#ff4b4b' if val > 0 else '#1c83e1' if val < 0 else 'white'
                return f'color: {color}'

            # 2. 상태 배경색
            def color_status(val):
                if val == "🚨위험": return 'background-color: #ff4b4b; color: white'
                elif val == "⚠️주의": return 'background-color: #ffa500; color: black'
                elif val == "✅안정": return 'background-color: #28a745; color: white'
                return ''

            return df.style.format({
                '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
                '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
            }).map(color_rate, subset=['등락률'])\
              .map(color_status, subset=['상태'])

        st.dataframe(style_df(df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]), 
                     use_container_width=True, height=600)

    except Exception as e:
        st.error(f"오류: {e}")
