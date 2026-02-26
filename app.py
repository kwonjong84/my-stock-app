import streamlit as st
import pandas as pd
import requests
import json
import time
import yfinance as yf
from datetime import datetime
import pytz

# 1. 설정 정보 (Secrets 활용)
APP_KEY = st.secrets["APP_KEY"]
APP_SECRET = st.secrets["APP_SECRET"]
TG_TOKEN = st.secrets["TG_TOKEN"]
TG_ID = st.secrets["TG_ID"]
BASE_URL = "https://openapi.koreainvestment.com:9443"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 실시간 감시 (최종)", layout="wide")

# 알림 중복 방지 세션 저장소
if 'alert_history' not in st.session_state:
    st.session_state.alert_history = set()

# 2. 유틸리티 함수
def send_telegram_msg(message):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": int(TG_ID), "text": message}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

@st.cache_data(ttl=36000) # 10시간마다 토큰 자동 갱신
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(url, data=json.dumps(payload), timeout=5)
        return res.json().get('access_token')
    except: return None

def get_current_price(code, token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {"Content-Type": "application/json", "authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010100"}
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        out = res.json().get('output', {})
        return float(out.get('stck_prpr', 0)), float(out.get('prdy_ctrt', 0))
    except: return 0.0, 0.0

# 3. 메인 로직
token = get_access_token()
if token:
    st.write(f"⏱️ **마지막 감시 시간:** {datetime.now(KST).strftime('%H:%M:%S')}")
    
    if st.button("🔄 알림 기록 리셋 및 새로고침"):
        st.session_state.alert_history.clear()
        st.rerun()

    try:
        # 시트 데이터 로드 및 컬럼명 강제 지정 (not in index 에러 방지)
        raw_df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7]
        raw_df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        status_list = []
        prog = st.progress(0, text="데이터 수집 중...")
        
        for i, row in raw_df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            
            # [수정] 가격 0원일 때 알림 로직 완전 차단
            if curr <= 0:
                status = "❓데이터오류"
                high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                stop_10, stop_15 = high * 0.9, high * 0.85
            else:
                # 과거 고점과 현재 실시간 고점 비교
                past_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                high = max(past_high, curr)
                stop_10, stop_15 = high * 0.9, high * 0.85
                
                # 손절 판정 및 텔레그램 발송
                if curr <= stop_15:
                    status = "🚨위험"
                    if code not in st.session_state.alert_history:
                        send_telegram_msg(f"‼️ [ISA 경보] {row['종목명']} 손절가 이탈\n현재가: {curr:,.0f}\n손절기준: {stop_15:,.0f}")
                        st.session_state.alert_history.add(code)
                elif curr <= stop_10:
                    status = "⚠️주의"
                else:
                    status = "✅안정"
                    if code in st.session_state.alert_history: st.session_state.alert_history.remove(code)
            
            # 데이터 업데이트
            raw_df.at[i, '현재가'] = curr
            raw_df.at[i, '등락률'] = rate / 100
            raw_df.at[i, '기준고점'] = high
            raw_df.at[i, '손절(-10%)'] = stop_10
            raw_df.at[i, '손절(-15%)'] = stop_15
            status_list.append(status)
            
            time.sleep(0.15) # API 호출 제한 고려
            prog.progress((i+1)/len(raw_df))
        
        raw_df['상태'] = status_list
        prog.empty()

        # 4. 스타일링 및 출력
        def style_status(val):
            if val == "🚨위험": return 'background-color: #ff4b4b; color: white'
            if val == "⚠️주의": return 'background-color: #ffa500; color: black'
            if val == "✅안정": return 'background-color: #28a745; color: white'
            return 'background-color: #808080; color: white' # 데이터오류용 회색

        def color_rate(val):
            if val > 0: return 'color: #ff4b4b'
            if val < 0: return 'color: #1c83e1'
            return ''

        # 컬럼 존재 여부 확인하며 안전하게 스타일링
        view_df = raw_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
        styled_df = view_df.style.format({
            '현재가': '{:,.0f}', '등락률': '{:+.2%}', 
            '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
        })

        # '상태'와 '등락률' 컬럼이 인덱스에 있는지 확인 후 적용 (not in index 방지)
        if '상태' in view_df.columns:
            styled_df = styled_df.map(style_status, subset=['상태'])
        if '등락률' in view_df.columns:
            styled_df = styled_df.map(color_rate, subset=['등락률'])

        st.dataframe(styled_df, use_container_width=True, height=600)

    except Exception as e:
        st.error(f"⚠️ 시스템 오류 발생: {e}")
