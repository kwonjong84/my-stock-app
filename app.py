import streamlit as st
import pandas as pd
import requests
import json
import time
from datetime import datetime
import pytz

# 1. API 보안 정보
APP_KEY = "PSauHiM9UT2XGwV0tAIWA6c9a9znz5tDLLha"
APP_SECRET = "qq0Kun7IXWgjgnn29cqieu+n6IhUFApMDYzgbaOsflLTPMZtz4l83vc+LywIyT7PZPJyboFSvwYiGuAcElLNvR4LXl+PTO91LdMXnsuwpGedz+Jqo7RoTP2+b27AK4HafMCt2Ru4lJfH4FcrAnGmNs2DkBzNOmBuRcIPodfxe7uLMjHqI7U="
BASE_URL = "https://openapi.koreainvestment.com:9443"

# 구글 시트 및 시간대 설정
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 실시간 감시 (Final)", layout="wide")

# 2. 한투 Access Token 발급
@st.cache_data(ttl=86400)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(url, data=json.dumps(payload))
        return res.json().get('access_token')
    except:
        return None

# 3. 네이버 지수 조회 (데이터 타입 에러 완벽 방어)
def get_market_index_safe():
    try:
        url = "https://polling.finance.naver.com/api/realtime/world/index/KOSPI,KOSDAQ"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers, timeout=5).json()
        items = res.get('datas', [])
        
        results = []
        for item in items:
            # 쉼표 제거 및 숫자 변환
            now_val = str(item.get('now', '0')).replace(',', '')
            rate_val = str(item.get('rate', '0')).replace(',', '')
            results.append((float(now_val), float(rate_val)))
        
        while len(results) < 2:
            results.append((0.0, 0.0))
        return results[0], results[1]
    except:
        return (0.0, 0.0), (0.0, 0.0)

# 4. 한투 종목 현재가 조회
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
        out = res.json().get('output', {})
        return float(out.get('stck_prpr', 0)), float(out.get('prdy_ctrt', 0))
    except:
        return 0.0, 0.0

# 5. 상단 위젯 구성
token = get_access_token()

if token:
    (kp_v, kp_r), (kd_v, kd_r) = get_market_index_safe()
    
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        st.metric("KOSPI", f"{kp_v:,.2f}", f"{kp_r:+.2f}%")
    with col2:
        st.metric("KOSDAQ", f"{kd_v:,.2f}", f"{kd_r:+.2f}%")
    with col3:
        st.write(f"⏱️ **업데이트:** {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 시세 새로고침"):
            st.rerun()

# 6. 데이터 로드 및 처리
def load_data(token):
    try:
        # 구글 시트 읽기 (캐시 방지용 timestamp 추가)
        df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        prog = st.progress(0, text="종목 시세 동기화 중...")
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            
            # 고점 자동 갱신 로직 포함
            high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            df.at[i, '현재가'] = curr
            df.at[i, '등락률'] = rate / 100
            df.at[i, '기준고점'] = max(high, curr)
            
            time.sleep(0.05)
            prog.progress((i+1)/len(df))
        prog.empty()

        # 손절선 및 상태 계산
        df['손절(-10%)'] = df['기준고점'] * 0.90
        df['손절(-15%)'] = df['기준고점'] * 0.85
        def judge(r):
            if r['현재가'] <= 0: return "⏳ 대기"
            if r['현재가'] <= r['손절(-15%)']: return "🚨위험"
            if r['현재가'] <= r['손절(-10%)']: return "⚠️주의"
            return "✅안정"
        df['상태'] = df.apply(judge, axis=1)
        return df
    except:
        return pd.DataFrame()

# 7. 메인 출력
res_df = load_data(token)

if not res_df.empty:
    view = res_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    def style(s):
        # 등락률 글자색
        s.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        # 상태 배경색
        def s_bg(v):
            if "🚨" in str(v): return 'background-color: #ff4b4b; color: white; font-weight: bold'
            if "⚠️" in str(v): return 'background-color: #ffa421; color: black; font-weight: bold'
            if "✅" in str(v): return 'background-color: #28a745; color: white; font-weight: bold'
            return ''
        s.applymap(s_bg, subset=['상태'])
        s.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
        return s

    st.dataframe(style(view.style.format({
        '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
        '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
    })), use_container_width=True, height=600)
else:
    st.error("데이터를 불러오지 못했습니다. 구글 시트 권한이나 인터넷 연결을 확인하세요.")
