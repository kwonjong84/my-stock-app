import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
import requests
import os
from datetime import datetime

# 1. 환경 설정 및 텔레그램 정보
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt" # 가격 저장용 파일

st.set_page_config(page_title="주식 손절 감시 시스템 Pro", layout="wide")

# 2. 영구 저장소 로직 (파일 읽기/쓰기)
def get_saved_price(stock_name):
    if os.path.exists(PRICE_LOG):
        with open(PRICE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                name, price = line.strip().split(",")
                if name == stock_name:
                    return float(price)
    return 999999999.0 # 기록 없으면 매우 높은 가격 반환

def save_price(stock_name, price):
    prices = {}
    if os.path.exists(PRICE_LOG):
        with open(PRICE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    name, p = line.strip().split(",")
                    prices[name] = p
                except: continue
    prices[stock_name] = str(price)
    with open(PRICE_LOG, "w", encoding="utf-8") as f:
        for name, p in prices.items():
            f.write(f"{name},{p}\n")

# 3. 텔레그램 발송 함수
def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.get(url, params=params)
    except: pass

# 4. 데이터 로드 및 실시간 동기화
def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        yf_idx = yf.Ticker("^KS11")
        idx_hist = yf_idx.history(period="2d", interval="1m")
        if not idx_hist.empty:
            mkt_idx = idx_hist['Close'].iloc[-1]
            prev_close = yf_idx.info.get('previousClose', mkt_idx)
            mkt_chg_rate = (mkt_idx - prev_close) / prev_close
        else:
            mkt_idx, mkt_chg_rate = 0, 0
            
        for i, row in df.iterrows():
            yf_ticker = yf.Ticker(f"{row['코드']}.KS")
            data = yf_ticker.history(period="1d", interval="1m").tail(1)
            if not data.empty:
                curr = data['Close'].iloc[-1]
                sheet_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                df.at[i, '현재가'] = curr
                df.at[i, '기준고점'] = max(sheet_high, curr)
                prev_p = yf_ticker.info.get('previousClose', curr)
                df.at[i, '등락률'] = (curr - prev_p) / prev_p

        for col in ['현재가', '기준고점', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['손절(-10%)'] = df['기준고점'] * 0.9
        df['손절(-15%)'] = df['기준고점'] * 0.85
        def calc_status(row):
            if row['현재가'] <= row['손절(-15%)']: return "🚨위험"
            elif row['현재가'] <= row['손절(-10%)']: return "⚠️주의"
            return "✅안정"
        df['상태'] = df.apply(calc_status, axis=1)
        return df, mkt_idx, mkt_chg_rate
    except: return pd.DataFrame(), 0, 0

# --- 5. 알림 로직 (파일 기반 영구 기억) ---
final_df, mkt_idx, mkt_chg_rate = get_data()

if not final_df.empty:
    danger_stocks = final_df[final_df['상태'] == "🚨위험"]
    for _, s in danger_stocks.iterrows():
        name = s['종목명']
        current_p = s['현재가']
        last_p = get_saved_price(name) # 파일에서 불러오기
        
        # 3% 추가 하락 엄격 체크
        if current_p <= last_p * 0.97:
            msg = f"‼️ [하락 경보] ‼️\n종목: {name}\n현재가: {current_p:,.0f}\n(추가 3% 하락 시에만 재알림)"
            send_telegram_msg(msg)
            save_price(name, current_p) # 파일에 저장

# --- 6. UI 디자인 복구 ---
st.title("📊 실시간 주식 감시 시스템 (영구 기억)")
st.caption(f"동기화 시각: {datetime.now(KST).strftime('%H:%M:%S')} | 중복 알림 방지 가동 중")

if st.button("🔄 시세 새로고침"):
    st.rerun()

if mkt_idx > 0:
    st.metric("KOSPI 실시간 지수", f"{mkt_idx:,.2f}", f"{mkt_chg_rate:.2%}")

if not final_df.empty:
    def style_df(styler):
        styler.set_properties(**{'text-align': 'center'})
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': '900', 'font-size': '1.1em'})
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
