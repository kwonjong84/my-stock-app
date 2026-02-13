import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
import requests
from datetime import datetime

# 1. 환경 설정 및 텔레그램 개인 정보 (여기에 입력하세요)
TELEGRAM_TOKEN = "여기에_받은_토큰_입력"
TELEGRAM_CHAT_ID = "여기에_숫자_ID_입력"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="주식 손절 감시 시스템", layout="wide")

# 2. 텔레그램 발송 함수
def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM}/sendMessage"
        params = {"chat_id": 63395333, "text": message}
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
            for i, row in df.iterrows():
                # 야후 파이낸스 실시간 호출
                yf_ticker = yf.Ticker(f"{row['코드']}.KS")
                data = yf_ticker.history(period="1d", interval="1m").tail(1)
                if not data.empty:
                    curr = data['Close'].iloc[-1]
                    high = data['High'].iloc[-1]
                    
                    df.at[i, '현재가'] = curr
                    df.at[i, '기준고점'] = max(float(row['기준고점']), high, curr)

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
        return df
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame()

# --- 실행 및 알림 로직 ---
if "alert_history" not in st.session_state:
    st.session_state.alert_history = [] # 알림 중복 방지 리스트

final_df = get_data()

# 위험 종목 알림 체크
danger_stocks = final_df[final_df['상태'] == "🚨위험"]
for _, s in danger_stocks.iterrows():
    alert_key = f"{s['종목명']}_{s['상태']}"
    if alert_key not in st.session_state.alert_history:
        msg = f"‼️ [손절 경보] ‼️\n종목: {s['종목명']}\n현재가: {s['현재가']:,.0f}\n기준고점: {s['기준고점']:,.0f}\n즉시 차트를 확인하세요!"
        send_telegram_msg(msg)
        st.session_state.alert_history.append(alert_key) # 보낸 알림은 저장

# (디자인 및 표 출력 부분은 이전과 동일하게 유지...)
st.title("📊 실시간 주식 감시 & 알림 시스템")
st.caption(f"동기화 시각: {datetime.now(KST).strftime('%H:%M:%S')}")

if not final_df.empty:
    # ... (st.dataframe 출력 코드) ...
    st.dataframe(final_df, use_container_width=True)
