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

st.set_page_config(page_title="ISA 실시간 감시 (최종안정)", layout="wide")

if 'alert_history' not in st.session_state:
    st.session_state.alert_history = set()

# 2. 지수 수집 함수 (네이버 페이 증권 최신 API)
def get_naver_index():
    try:
        # 이 주소가 현재 네이버에서 가장 안정적으로 지수를 뱉어주는 주소입니다.
        url = "https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI,KOSDAQ"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5).json()
        items = res.get('datas', [])
        
        # 코스피/코스닥 추출
        kp = (float(items[0]['now'].replace(',', '')), float(items[0]['fluctuationRate']))
        kd = (float(items[1]['now'].replace(',', '')), float(items[1]['fluctuationRate']))
        return kp, kd
    except:
        return (0.0, 0.0), (0.0, 0.0)

# 3. 한투 API 함수들
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

# 4. 메인 실행부
token = get_access_token()
if token:
    kp, kd = get_naver_index()
    
    # 지수 미터기 (metric)
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1: st.metric("KOSPI", f"{kp[0]:,.2f}", f"{kp[1]:+.2f}%")
    with c2: st.metric("KOSDAQ", f"{kd[0]:,.2f}", f"{kd[1]:+.2f}%")
    with c3: 
        st.write(f"⏱️ 감시중: {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 알림 리셋"): st.session_state.alert_history.clear(); st.rerun()

    try:
        # 데이터 로드
        df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7]
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        status_list = []
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            
            # 가격 0원(오류) 처리
            if curr <= 0:
                status = "❓데이터오류"
                high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            else:
                past_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                high = max(past_high, curr) # 실시간 고점 갱신
                stop_15 = high * 0.85
                
                if curr <= stop_15:
                    status = "🚨위험"
                    if code not in st.session_state.alert_history:
                        send_telegram_msg(f"‼️ [ISA] {row['종목명']} 이탈\n가: {curr:,.0f} / 고점: {high:,.0f}")
                        st.session_state.alert_history.add(code)
                elif curr <= high * 0.9: status = "⚠️주의"
                else:
                    status = "✅안정"
                    if code in st.session_state.alert_history: st.session_state.alert_history.remove(code)
            
            df.at[i, '현재가'], df.at[i, '등락률'], df.at[i, '기준고점'] = curr, rate/100, high
            df.at[i, '손절(-10%)'], df.at[i, '손절(-15%)'] = high*0.9, high*0.85
            status_list.append(status)
            time.sleep(0.1)

        df['상태'] = status_list
        
        # [수정] 스타일링 로직 (컬러 빠짐 방지)
        def color_rate(v):
            if v > 0: return 'color: #ff4b4b' # 빨강
            if v < 0: return 'color: #1c83e1' # 파랑
            return ''

        def style_status(v):
            if v == "🚨위험": return 'background-color: #ff4b4b; color: white'
            if v == "⚠️주의": return 'background-color: #ffa500; color: black'
            if v == "✅안정": return 'background-color: #28a745; color: white'
            return 'background-color: #808080; color: white'

        # 화면 출력
        view_cols = ['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']
        st.dataframe(
            df[view_cols].style.format({
                '현재가': '{:,.0f}', '등락률': '{:+.2%}', 
                '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
            })
            .map(color_rate, subset=['등락률']) # 등락률 컬러 추가
            .map(style_status, subset=['상태']),
            use_container_width=True, height=600
        )

    except Exception as e:
        st.error(f"⚠️ 시스템 오류: {e}")
