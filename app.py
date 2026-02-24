import streamlit as st
import pandas as pd
import requests
import json
import time
import os
from datetime import datetime
import pytz

# 1. API 보안 정보 (복사해두신 값을 여기에 넣으세요)
APP_KEY = "PSauHiM9UT2XGwV0tAIWA6c9a9znz5tDLLha"
APP_SECRET = "qq0Kun7IXWgjgnn29cqieu+n6IhUFApMDYzgbaOsflLTPMZtz4l83vc+LywIyT7PZPJyboFSvwYiGuAcElLNvR4LXl+PTO91LdMXnsuwpGedz+Jqo7RoTP2+b27AK4HafMCt2Ru4lJfH4FcrAnGmNs2DkBzNOmBuRcIPodfxe7uLMjHqI7U="
BASE_URL = "https://openapi.koreainvestment.com:9443" # 실전투자 서버

# 기존 텔레그램 및 시트 정보 (사용자님 정보 유지)
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 실시간 감시 (한투 API Pro)", layout="wide")

# 2. 한투 Access Token 발급 (출입증 받기)
@st.cache_data(ttl=86400)
def get_access_token():
    url = f"{BASE_URL}/oauth2/tokenP"
    payload = {
        "grant_type": "client_credentials",
        "appkey": APP_KEY,
        "appsecret": APP_SECRET
    }
    res = requests.post(url, data=json.dumps(payload))
    return res.json().get('access_token')

# 3. 실시간 현재가 조회 함수
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
    res = requests.get(url, headers=headers, params=params)
    data = res.json().get('output', {})
    # 현재가와 등락률(전일대비율) 반환
    return float(data.get('stck_prpr', 0)), float(data.get('prdy_ctrt', 0))

# 4. 데이터 통합 로드
def get_integrated_data():
    token = get_access_token()
    if not token:
        st.error("❌ 한투 API 인증 실패! Key와 Secret을 다시 확인하세요.")
        return pd.DataFrame()

    try:
        # 구글 시트에서 종목 리스트 로드
        raw_df = pd.read_csv(f"{SHEET_URL}&t={int(time.time())}")
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        progress_bar = st.progress(0, text="한투 서버에서 실시간 시세 수신 중...")
        
        for i, row in df.iterrows():
            code = str(row['코드']).zfill(6) # 종목코드 6자리 유지
            curr, rate = get_current_price(code, token)
            
            high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
            df.at[i, '현재가'] = curr
            df.at[i, '등락률'] = rate / 100 # % 단위를 소수로 변환
            df.at[i, '기준고점'] = max(high, curr)
            
            time.sleep(0.1) # 초당 10건 제한 준수
            progress_bar.progress((i+1)/len(df))
        
        progress_bar.empty()
        
        # 상태 판별 및 손절선 계산
        df['손절(-10%)'] = df['기준고점'] * 0.90
        df['손절(-15%)'] = df['기준고점'] * 0.85
        df['상태'] = df.apply(lambda r: "🚨위험" if r['현재가'] <= r['손절(-15%)'] else "⚠️주의" if r['현재가'] <= r['손절(-10%)'] else "✅안정", axis=1)
        
        return df
    except Exception as e:
        st.error(f"데이터 로드 중 오류 발생: {e}")
        return pd.DataFrame()

# 5. 메인 UI (사용자님 스타일 유지)
st.title("🚀 ISA 실시간 감시 (한국투자증권 연동)")
st.caption(f"최종 동기화: {datetime.now(KST).strftime('%H:%M:%S')}")

if st.button("🔄 시세 새로고침"):
    st.rerun()

final_df = get_integrated_data()

if not final_df.empty:
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    def apply_style(styler):
        styler.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        def status_color(v):
            if "🚨" in str(v): return 'background-color: #ff4b4b; color: white;'
            if "⚠️" in str(v): return 'background-color: #ffa421; color: black;'
            return 'background-color: #28a745; color: white;'
        styler.applymap(status_color, subset=['상태'])
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
        return styler

    st.dataframe(apply_style(display_df.style.format({
        '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
        '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
    })), use_container_width=True, height=600)
