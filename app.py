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

st.set_page_config(page_title="ISA 실시간 감시 시스템", layout="wide")

if 'alert_history' not in st.session_state:
    st.session_state.alert_history = set()

# 2. 유틸리티 함수
def is_market_open():
    """평일 09:00 ~ 18:00 사이만 True 반환 (알림 발송 기준)"""
    now = datetime.now(KST)
    if now.weekday() >= 5: return False
    # 시간 비교를 위해 정수형 분으로 변환 (900 ~ 1800)
    current_time_int = now.hour * 100 + now.minute
    return 900 <= current_time_int < 1800

def send_telegram_msg(message):
    # [이중 잠금] 함수 실행 시점에 시간이 지났으면 절대 발송하지 않음
    if not is_market_open():
        return
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
        # [상태창 유지] 장 마감 여부와 관계없이 현재 시각과 상태를 명확히 표시
        if market_active:
            st.success(f"🟢 실시간 감시 가동 중 ({datetime.now(KST).strftime('%H:%M:%S')})")
        else:
            st.warning(f"⚪ 장 마감 상태 ({datetime.now(KST).strftime('%H:%M:%S')}) - 알림이 차단되었습니다.")
        
        if st.button("🔄 리셋 & 새로고침"):
            st.session_state.alert_history.clear()
            st.rerun()

    try:
        df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7]
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        status_list = []
        # 장이 마감되어도 표는 보여주되, 알림만 안 가게 설정
        prog_bar = st.progress(0, text="📊 데이터 분석 중...")
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            past_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            high = max(past_high, curr) if curr > 0 else past_high
            
            if curr <= 0: status = "❓데이터오류"
            elif curr <= high * 0.85:
                status = "🚨위험"
                # [핵심] 여기서 send_telegram_msg가 시간을 한 번 더 체크함
                if code not in st.session_state.alert_history:
                    send_telegram_msg(f"‼️ [ISA] {row['종목명']} 이탈\n현재가: {curr:,.0f}")
                    st.session_state.alert_history.add(code)
            elif curr <= high * 0.9: status = "⚠️주의"
            else:
                status = "✅안정"
                if code in st.session_state.alert_history: st.session_state.alert_history.remove(code)
            
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
            colors = {"🚨위험": "background-color: #ff4b4b; color: white", 
                      "⚠️주의": "background-color: #ffa500; color: black", 
                      "✅안정": "background-color: #28a745; color: white"}
            return colors.get(v, "background-color: #808080; color: white")

        st.dataframe(
            df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
            .style.format({'현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'})
            .map(color_rate, subset=['등락률']).map(style_status, subset=['상태']),
            use_container_width=True, height=600
        )
    except Exception as e:
        st.error(f"⚠️ 시스템 오류: {e}")
