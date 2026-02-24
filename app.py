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

st.set_page_config(page_title="ISA 실시간 감시 Pro", layout="wide")

# 2. 한투 Access Token 발급
@st.cache_data(ttl=86400)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {"grant_type": "client_credentials", "appkey": APP_KEY, "appsecret": APP_SECRET}
    try:
        res = requests.post(url, data=json.dumps(payload), timeout=5)
        return res.json().get('access_token')
    except: return None

# 3. 네이버 금융 지수 조회 (가장 안전한 방식)
def get_naver_index():
    try:
        url = "https://polling.finance.naver.com/api/realtime/world/index/KOSPI,KOSDAQ"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5).json()
        datas = res.get('datas', [])
        
        # 데이터 정제 함수
        def clean_val(item, key):
            val = str(item.get(key, '0')).replace(',', '')
            return float(val)

        kp = (clean_val(datas[0], 'now'), clean_val(datas[0], 'rate'))
        kd = (clean_val(datas[1], 'now'), clean_val(datas[1], 'rate'))
        return kp, kd
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

# 5. 메인 UI 구성
token = get_access_token()

if not token:
    st.error("🔑 한투 API 연결 실패! Key와 Secret을 확인하세요.")
else:
    # 지수 섹션
    kp, kd = get_naver_index()
    c1, c2, c3 = st.columns([1, 1, 2])
    with c1: st.metric("KOSPI", f"{kp[0]:,.2f}", f"{kp[1]:+.2f}%")
    with c2: st.metric("KOSDAQ", f"{kd[0]:,.2f}", f"{kd[1]:+.2f}%")
    with c3:
        st.write(f"⏱️ **업데이트:** {datetime.now(KST).strftime('%H:%M:%S')}")
        if st.button("🔄 시세 새로고침"): st.rerun()

    # 6. 데이터 처리
    try:
        df_raw = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}").iloc[:, :7]
        df_raw.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        prog = st.progress(0, text="실시간 시세 동기화 중...")
        for i, row in df_raw.iterrows():
            code = str(row['코드']).zfill(6)
            curr, rate = get_current_price(code, token)
            high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            
            df_raw.at[i, '현재가'] = curr
            df_raw.at[i, '등락률'] = rate / 100
            df_raw.at[i, '기준고점'] = max(high, curr)
            
            time.sleep(0.05)
            prog.progress((i+1)/len(df_raw))
        prog.empty()

        # 손절 계산 및 상태
        df_raw['손절(-10%)'] = df_raw['기준고점'] * 0.90
        df_raw['손절(-15%)'] = df_raw['기준고점'] * 0.85
        def get_status(r):
            if r['현재가'] <= r['손절(-15%)']: return "🚨위험"
            if r['현재가'] <= r['손절(-10%)']: return "⚠️주의"
            return "✅안정"
        df_raw['상태'] = df_raw.apply(get_status, axis=1)

        # 7. 스타일링 및 출력 (최신 Streamlit map 방식)
        view = df_raw[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
        
        def apply_style(styler):
            # 등락률 색상
            styler.map(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
            # 상태 배경색
            def status_bg(v):
                if "🚨" in str(v): return 'background-color: #ff4b4b; color: white;'
                if "⚠️" in str(v): return 'background-color: #ffa421; color: black;'
                return 'background-color: #28a745; color: white;'
            styler.map(status_bg, subset=['상태'])
            styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
            return styler

        st.dataframe(apply_style(view.style.format({
            '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
            '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
        })), use_container_width=True, height=600)

    except Exception as e:
        st.error(f"⚠️ 데이터 로드 중 오류 발생: {e}")
