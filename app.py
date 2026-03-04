import streamlit as st
import pandas as pd
import requests
import json
import time
from datetime import datetime
import pytz

# 1. 설정 및 세션 초기화
APP_KEY = st.secrets["APP_KEY"]
APP_SECRET = st.secrets["APP_SECRET"]
TG_TOKEN = st.secrets["TG_TOKEN"]
TG_ID = st.secrets["TG_ID"]
BASE_URL = "https://openapi.koreainvestment.com:9443"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 실시간 감시 (단계별 알림)", layout="wide")

# [수정] 단계별 알림 기록을 위한 딕셔너리 세션
if 'alert_levels' not in st.session_state:
    st.session_state.alert_levels = {} # { '종목코드': 마지막보낸레벨(int) }

# 2. 유틸리티 함수
def is_market_open():
    now = datetime.now(KST)
    if now.weekday() >= 5: return False
    current_time_int = now.hour * 100 + now.minute
    return 900 <= current_time_int < 1800

def send_telegram_msg(message):
    if not is_market_open(): return
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {"chat_id": int(TG_ID), "text": message}
    try: requests.post(url, json=payload, timeout=5)
    except: pass

def get_naver_index():
    try:
        url = "https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI,KOSDAQ"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"}
        res = requests.get(url, headers=headers, timeout=5).json()
        items = res.get('datas', [])
        if len(items) >= 2:
            kp = (float(items[0]['closePrice'].replace(',', '')), float(items[0]['fluctuationsRatio']))
            kd = (float(items[1]['closePrice'].replace(',', '')), float(items[1]['fluctuationsRatio']))
            return kp, kd
    except: pass
    return (0.0, 0.0), (0.0, 0.0)

@st.cache_data(ttl=36000)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(url, data=json.dumps(payload), timeout=5)
        return res.json().get('access_token')
    except: return None

def get_current_price(code, token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {"Content-Type": "application/json", "authorization": f"Bearer {token}",
               "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010100"}
    params = {"fid_cond_mrkt_div_code": "J", "fid_input_iscd": code}
    try:
        res = requests.get(url, headers=headers, params=params, timeout=5)
        out = res.json().get('output', {})
        return float(out.get('stck_prpr', 0)), float(out.get('prdy_ctrt', 0))
    except: return 0.0, 0.0

# 3. 메인 실행부
token = get_access_token()
market_active = is_market_open()

if token:
    kp, kd = get_naver_index()
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1: st.metric("KOSPI", f"{kp[0]:,.2f}", f"{kp[1]:+.2f}%")
    with col2: st.metric("KOSDAQ", f"{kd[0]:,.2f}", f"{kd[1]:+.2f}%")
    with col3:
        if market_active: st.success(f"🟢 실시간 감시 가동 중 ({datetime.now(KST).strftime('%H:%M:%S')})")
        else: st.warning(f"⚪ 장 마감 상태 ({datetime.now(KST).strftime('%H:%M:%S')}) - 알림 차단됨")
        if st.button("🔄 알림 기록 리셋 & 새로고침"):
            st.session_state.alert_levels.clear()
            st.rerun()

    try:
        df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7]
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        status_list = []
        prog_bar = st.progress(0, text="📊 데이터 분석 중...")
        
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            past_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            high = max(past_high, curr) if curr > 0 else past_high
            
            # 하락률 계산 및 알림 단계 판정 (0.85 이하 = 15%, 0.80 이하 = 20% ...)
            drop_ratio = (curr / high) if high > 0 else 1.0
            current_lv = 0
            if drop_ratio <= 0.70: current_lv = 30
            elif drop_ratio <= 0.75: current_lv = 25
            elif drop_ratio <= 0.80: current_lv = 20
            elif drop_ratio <= 0.85: current_lv = 15
            
            # 알림 로직 (이전에 보낸 단계보다 더 낮아졌을 때만 발송)
            last_sent_lv = st.session_state.alert_levels.get(code, 0)
            if current_lv > last_sent_lv:
                send_telegram_msg(f"🚨 [ISA 단계경보] {row['종목명']}\n현재가: {curr:,.0f} (-{current_lv}% 돌파)\n기준고점: {high:,.0f}")
                st.session_state.alert_levels[code] = current_lv
            
            # [참모 제언] 반등 시 리셋 로직: 하락률이 -10% 위로 회복되면 알림 단계 초기화
            if drop_ratio > 0.90 and last_sent_lv > 0:
                st.session_state.alert_levels[code] = 0

            # 상태 표시 문자열 구성
            if curr <= 0: status = "❓데이터오류"
            elif drop_ratio <= 0.85: status = f"🚨위험(-{current_lv}%)"
            elif drop_ratio <= 0.90: status = "⚠️주의(-10%)"
            else: status = "✅안정"
            
            df.at[i, '현재가'], df.at[i, '등락률'], df.at[i, '기준고점'] = curr, rate/100, high
            df.at[i, '손절(-10%)'], df.at[i, '손절(-15%)'] = high*0.9, high*0.85
            status_list.append(status)
            prog_bar.progress((i+1)/len(df))
            time.sleep(0.05)
        
        df['상태'] = status_list
        prog_bar.empty()

        # 4. 스타일링 및 출력
        def color_rate(v): return 'color: #ff4b4b' if v > 0 else 'color: #1c83e1' if v < 0 else ''
        def style_status(v):
            if "🚨위험" in v: return "background-color: #ff4b4b; color: white"
            if "⚠️주의" in v: return "background-color: #ffa500; color: black"
            if "✅안정" in v: return "background-color: #28a745; color: white"
            return "background-color: #808080; color: white"

        st.dataframe(
            df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
            .style.format({'현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'})
            .map(color_rate, subset=['등락률']).map(style_status, subset=['상태']),
            use_container_width=True, height=600
        )
    except Exception as e:
        st.error(f"⚠️ 시스템 오류: {e}")
