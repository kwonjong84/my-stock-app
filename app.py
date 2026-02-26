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

st.set_page_config(page_title="ISA 실시간 감시 (무결점 가동)", layout="wide")

if 'alert_history' not in st.session_state:
    st.session_state.alert_history = set()

# 2. 지수 수집 함수 (데이터 확인용 디버깅 포함)
def get_naver_index():
    try:
        url = "https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI,KOSDAQ"
        headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://finance.naver.com/"}
        res = requests.get(url, headers=headers, timeout=5).json()
        items = res.get('datas', [])
        
        if not items: return (0.0, 0.0), (0.0, 0.0)
        
        # 키 값이 'now'인지 'nv'인지 자동 판별
        def parse(item):
            price = float(str(item.get('now') or item.get('nv') or "0").replace(',', ''))
            rate = float(str(item.get('fluctuationRate') or item.get('cr') or "0").replace(',', ''))
            return (price, rate)
            
        return parse(items[0]), parse(items[1])
    except:
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

# 3. 메인 로직 시작
token = get_access_token()
if token:
    # [지수 로직]
    kp, kd = get_naver_index()
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1: st.metric("KOSPI", f"{kp[0]:,.2f}", f"{kp[1]:+.2f}%")
    with col2: st.metric("KOSDAQ", f"{kd[0]:,.2f}", f"{kd[1]:+.2f}%")
    with col3: 
        st.write(f"⏱️ 감시중: {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 리셋 및 갱신"): st.session_state.alert_history.clear(); st.rerun()

    # [로딩 바 가동]
    try:
        raw_df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7]
        raw_df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        status_list = []
        # 로딩 바를 데이터프레임 처리 전 명시적으로 생성
        progress_text = "🔄 실시간 시세 분석 중입니다. 잠시만 기다려주세요."
        my_bar = st.progress(0, text=progress_text)
        
        for i, row in raw_df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            
            # 실시간 연산 로직
            past_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            high = max(past_high, curr) if curr > 0 else past_high
            
            if curr <= 0: status = "❓데이터오류"
            elif curr <= high * 0.85:
                status = "🚨위험"
                if code not in st.session_state.alert_history:
                    requests.post(f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage", 
                                  json={"chat_id": TG_ID, "text": f"‼️ [ISA] {row['종목명']} 이탈\n현재가: {curr:,.0f}"})
                    st.session_state.alert_history.add(code)
            elif curr <= high * 0.9: status = "⚠️주의"
            else: status = "✅안정"
            
            raw_df.at[i, '현재가'], raw_df.at[i, '등락률'], raw_df.at[i, '기준고점'] = curr, rate/100, high
            raw_df.at[i, '손절(-10%)'], raw_df.at[i, '손절(-15%)'] = high*0.9, high*0.85
            status_list.append(status)
            
            # 로딩 바 업데이트
            my_bar.progress((i + 1) / len(raw_df), text=f"📊 {row['종목명']} 분석 중...")
            time.sleep(0.1) # API 호출 안정성을 위한 짧은 휴지
            
        raw_df['상태'] = status_list
        my_bar.empty() # 완료 후 로딩 바 제거

        # 4. 스타일링 및 출력
        def color_rate(v): return 'color: #ff4b4b' if v > 0 else 'color: #1c83e1' if v < 0 else ''
        def style_status(v):
            colors = {"🚨위험": "background-color: #ff4b4b; color: white", 
                      "⚠️주의": "background-color: #ffa500; color: black", 
                      "✅안정": "background-color: #28a745; color: white"}
            return colors.get(v, "background-color: #808080; color: white")

        st.dataframe(
            raw_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
            .style.format({'현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'})
            .map(color_rate, subset=['등락률'])
            .map(style_status, subset=['상태']),
            use_container_width=True, height=600
        )
    except Exception as e:
        st.error(f"⚠️ 데이터 로드 오류: {e}")
