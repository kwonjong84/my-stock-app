import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
import requests
from datetime import datetime

# 1. 환경 설정 및 텔레그램 개인 정보 (반드시 변수로 정의해야 에러가 안 납니다)
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="주식 손절 감시 시스템", layout="wide")

# 2. 텔레그램 발송 함수 (f-string 오류 수정 완료)
def send_telegram_msg(message):
    try:
        # 토큰 변수를 사용해 중괄호{} 안의 콜론 문제를 해결함
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.get(url, params=params)
    except Exception as e:
        st.error(f"알림 전송 실패: {e}")

# 3. 데이터 로드 및 실시간 동기화
def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        with st.spinner('실시간 시세 감시 및 알림 체크 중...'):
            # 코스피 실시간 지수 호출 (야후 티커 ^KS11)
            yf_idx = yf.Ticker("^KS11")
            idx_data = yf_idx.history(period="1d", interval="1m").tail(1)
            mkt_idx = idx_data['Close'].iloc[-1] if not idx_data.empty else 0
            
            for i, row in df.iterrows():
                # 야후 파이낸스 실시간 호출 (1분 간격 최신 데이터)
                yf_ticker = yf.Ticker(f"{row['코드']}.KS")
                data = yf_ticker.history(period="1d", interval="1m").tail(1)
                if not data.empty:
                    curr = data['Close'].iloc[-1]
                    high = data['High'].iloc[-1]
                    
                    df.at[i, '현재가'] = curr
                    # 시트 고점과 실시간 고점 중 더 높은 것 유지
                    sheet_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                    df.at[i, '기준고점'] = max(sheet_high, high, curr)

        # 수치 변환 및 손절선 계산
        for col in ['현재가', '기준고점']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        df['손절(-10%)'] = df['기준고점'] * 0.9
        df['손절(-15%)'] = df['기준고점'] * 0.85

        def calc_status(row):
            if pd.isna(row['현재가']): return "조회중"
            if row['현재가'] <= row['손절(-15%)']: return "🚨위험"
            elif row['현재가'] <= row['손절(-10%)']: return "⚠️주의"
            return "✅안정"
        
        df['상태'] = df.apply(calc_status, axis=1)
        return df, mkt_idx
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame(), 0

# --- 실행 및 알림 로직 ---
if "alert_history" not in st.session_state:
    st.session_
