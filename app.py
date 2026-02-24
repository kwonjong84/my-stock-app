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

SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 실시간 감시 (하이브리드)", layout="wide")

# 2. 한투 Access Token 발급
@st.cache_data(ttl=86400)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    res = requests.post(url, data=json.dumps(payload))
    return res.json().get('access_token')

# 3. [우회] 네이버 금융 실시간 지수 조회 (한투 권한 무관)
def get_naver_index():
    try:
        url = "https://polling.finance.naver.com/api/realtime/world/index/KOSPI,KOSDAQ"
        res = requests.get(url).json()
        data = res.get('datas', [])
        # 코스피: 0번, 코스닥: 1번
        kospi = (float(data[0]['now'].replace(',', '')), float(data[0]['rate']))
        kosdaq = (float(data[1]['now'].replace(',', '')), float(data[1]['rate']))
        return kospi, kosdaq
    except:
        return (0.0, 0.0), (0.0, 0.0)

# 4. 한투 종목 현재가 조회
def get_current_price(code, token):
    url = f"{BASE_URL}/uapi/domestic-stock/v1/quotations/inquire-price"
    headers = {"Content-Type": "application/json", "authorization": f"Bearer {token}", "appkey": APP_KEY, "appsecret": APP_SECRET, "tr_id": "FHKST01010100"}
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
    (kp_v, kp_r), (kd_v, kd_r) = get_naver_index() # 네이버에서 가져옴
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1: st.metric("KOSPI", f"{kp_v:,.2f}", f"{kp_r:+.2f}%")
    with c2: st.metric("KOSDAQ", f"{kd_v:,.2f}", f"{kd_r:+.2f}%")
    with c3:
        st.write(f"⏱️ **업데이트:** {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 시세 새로고침"): st.rerun()

# 6. 데이터 로드 및 처리
def load_data(token):
    try:
        df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        prog = st.progress(0, text="한투 시세 동기화 중...")
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            df.at[i, '현재가'], df.at[i, '등락률'], df.at[i, '기준고점'] = curr, rate/100, max(high, curr)
            time.sleep(0.05)
            prog.progress((i+1)/len(df))
        prog.empty()
        # 상태 판별
        df['손절(-10%)'], df['손절(-15%)'] = df['기준고점']*0.9, df['기준고점']*0.85
        df['상태'] = df.apply(lambda r: "🚨위험" if r['현재가'] <= r['손절(-15%)'] else "⚠️주의" if r['현재가'] <= r['손절(-10%)'] else "✅안정", axis=1)
        return df
    except: return pd.DataFrame()

# 7. 출력
res_df = load_data(token)
if not res_df.empty:
    view = res_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    def style(s):
        s.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        s.applymap(lambda v: 'background-color: #ff4b4b; color: white;' if "🚨" in str(v) else 'background-color: #ffa421; color: black;' if "⚠️" in str(v)
