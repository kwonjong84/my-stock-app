import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
import requests
from datetime import datetime

# 1. 환경 설정 및 텔레그램 정보
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="주식 손절 감시 시스템 Pro", layout="wide")

# 2. 텔레그램 발송 함수
def send_telegram_msg(message):
    try:
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
        
        with st.spinner('실시간 시세 분석 및 추가 하락 감시 중...'):
            yf_idx = yf.Ticker("^KS11")
            idx_data = yf_idx.history(period="1d", interval="1m").tail(1)
            mkt_idx = idx_data['Close'].iloc[-1] if not idx_data.empty else 0
            
            for i, row in df.iterrows():
                yf_ticker = yf.Ticker(f"{row['코드']}.KS")
                data = yf_ticker.history(period="1d", interval="1m").tail(1)
                if not data.empty:
                    curr = data['Close'].iloc[-1]
                    high = data['High'].iloc[-1]
                    df.at[i, '현재가'] = curr
                    sheet_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                    df.at[i, '기준고점'] = max(sheet_high, high, curr)

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

# --- 4. 알림 로직 (전략 B: 추가 하락 시에만 알림) ---
if "last_notified_price" not in st.session_state:
    st.session_state.last_notified_price = {} # {종목명: 마지막으로 알림 보낸 가격}

final_df, mkt_idx = get_data()

if not final_df.empty:
    danger_stocks = final_df[final_df['상태'] == "🚨위험"]
    for _, s in danger_stocks.iterrows():
        name = s['종목명']
        current_p = s['현재가']
        last_p = st.session_state.last_notified_price.get(name, float('inf'))
        
        # 조건: 처음 발견했거나, 마지막 알림 가격보다 3% 이상 더 하락했을 때만 발송
        if current_p <= last_p * 0.97:
            msg = f"‼️ [추가 하락 경보] ‼️\n종목: {name}\n현재가: {current_p:,.0f}\n이전 알림 대비 3% 이상 추가 하락했습니다!"
            send_telegram_msg(msg)
            st.session_state.last_notified_price[name] = current_p

# --- 5. UI 출력 ---
st.title("📊 실시간 주식 감시 시스템 (전략 B 적용)")
st.caption(f"동기화 시각: {datetime.now(KST).strftime('%H:%M:%S')} (3% 추가 하락 시에만 재알림)")

if st.button("🔄 시세 새로고침"):
    st.rerun()

if mkt_idx > 0:
    st.metric("KOSPI 실시간", f"{mkt_idx:,.2f}")

if not final_df.empty:
    def style_df(styler):
        styler.set_properties(**{'text-align': 'center'})
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': '900', 'font-size': '1.2em'})
        
        def color_rate(val):
            color = '#ff4b4b' if val > 0 else '#1c83e1' if val < 0 else '#ffffff'
            return f'color: {color}; font-weight: bold'
        styler.applymap(color_rate, subset=['등락률'])
        
        def color_status(val):
            if val == "🚨위험": return 'background-color: #ff4b4b; color: white; font-weight: bold'
            if val == "⚠️주의": return 'background-color: #ffa421; color: black; font-weight: bold'
            return 'background-color: #28a745; color: white; font-weight: bold'
        styler.applymap(color_status, subset=['상태'])
        return styler

    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    st.dataframe(style_df(display_df.style.format({'현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'})), use_container_width=True, height=600)
