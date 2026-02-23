import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
import requests
import os
import html
from datetime import datetime

# 1. 환경 설정
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="주식 감시 시스템 Pro (컬러 복구)", layout="wide")

# 2. 저장소 로직
def get_saved_price(stock_name):
    if os.path.exists(PRICE_LOG):
        with open(PRICE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    parts = line.strip().split(",")
                    if len(parts) == 2 and parts[0] == stock_name: return float(parts[1])
                except: continue
    return 0.0

def save_price(stock_name, price):
    prices = {}
    if os.path.exists(PRICE_LOG):
        with open(PRICE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    parts = line.strip().split(",")
                    if len(parts) == 2: prices[parts[0]] = parts[1]
                except: continue
    prices[stock_name] = str(price)
    with open(PRICE_LOG, "w", encoding="utf-8") as f:
        for name, p in prices.items(): f.write(f"{name},{p}\n")

# 3. 텔레그램 발송 (2중 안전장치 유지)
def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.get(url, params=params, timeout=10)
        if not resp.json().get("ok"):
            clean_text = message.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>","")
            requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": "[일반텍스트전송]\n" + clean_text})
    except: pass

# 4. 데이터 로드 (캐싱 및 지수 포함)
@st.cache_data(ttl=60)
def get_market_info(ticker_symbol):
    try:
        t = yf.Ticker(ticker_symbol)
        h = t.history(period="2d", interval="1m")
        if not h.empty:
            curr = h['Close'].iloc[-1]
            prev = t.info.get('previousClose', curr)
            return curr, (curr - prev) / prev
    except: pass
    return 0, 0

def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        kospi_p, kospi_r = get_market_info("^KS11")
        kosdaq_p, kosdaq_r = get_market_info("^KQ11")
            
        progress_bar = st.progress(0, text="시세 데이터를 동기화 중...")
        for i, row in df.iterrows():
            progress_bar.progress((i + 1) / len(df), text=f"[{row['종목명']}] 로딩 중")
            t = yf.Ticker(f"{row['코드']}.KS")
            d = t.history(period="1d", interval="1m").tail(1)
            if not d.empty:
                curr = d['Close'].iloc[-1]
                high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                df.at[i, '현재가'] = curr
                df.at[i, '기준고점'] = max(high, curr)
                prev = t.info.get('previousClose', curr)
                df.at[i, '등락률'] = (curr - prev) / prev
            time.sleep(0.1)
        progress_bar.empty()

        for col in ['현재가', '기준고점', '등락률']: df[col] = pd.to_numeric(df[col], errors='coerce')
        df['손절(-10%)'] = df['기준고점'] * 0.9
        df['손절(-15%)'] = df['기준고점'] * 0.85
        df['상태'] = df.apply(lambda r: "🚨위험" if r['현재가'] <= r['손절(-15%)'] else "⚠️주의" if r['현재가'] <= r['손절(-10%)'] else "✅안정", axis=1)
        
        return df, (kospi_p, kospi_r), (kosdaq_p, kosdaq_r)
    except Exception as e:
        st.error(f"오류 발생: {e}")
        return pd.DataFrame(), (0,0), (0,0)

# 5. 실행 및 알림
final_df, kospi, kosdaq = get_data()

if not final_df.empty:
    for _, s in final_df[final_df['상태'] == "🚨위험"].iterrows():
        last_p = get_saved_price(s['종목명'])
        if last_p == 0 or s['현재가'] <= last_p * 0.97:
            s_name = html.escape(str(s['종목명']))
            emoji = "🔴" if s['등락률'] > 0 else "🔵"
            msg = f"<b>‼️ [하락 경보] ‼️</b>\n\n<b>종목:</b> {s_name}\n<b>현재가:</b> {s['현재가']:,.0f}원 ({emoji} {s['등락률']:+.2%})\n<b>시장:</b> KOSPI {kospi[0]:,.2f} / KOSDAQ {kosdaq[0]:,.2f}"
            send_telegram_msg(msg)
            save_price(s['종목명'], s['현재가'])

# 6. UI 시각화 (컬러 복구 섹션)
st.title("📊 주식 실시간 감시 (컬러 UI)")
st.caption(f"최종 업데이트: {datetime.now(KST).strftime('%H:%M:%S')}")

if st.button("🔄 즉시 새로고침"):
    st.cache_data.clear()
    st.rerun()

c1, c2 = st.columns(2)
with c1: st.metric("KOSPI", f"{kospi[0]:,.2f}", f"{kospi[1]:+.2%}")
with c2: st.metric("KOSDAQ", f"{kosdaq[0]:,.2f}", f"{kosdaq[1]:+.2%}")

# 스타일 정의 함수
def apply_color_style(styler):
    # 등락률 컬러 (빨강/파랑)
    def color_rate(val):
        color = '#ff4b4b' if val > 0 else '#1c83e1' if val < 0 else '#ffffff'
        return f'color: {color}; font-weight: bold'
    
    # 상태 배경색
    def color_status(val):
        if val == "🚨위험": return 'background-color: #ff4b4b; color: white; font-weight: bold'
        if val == "⚠️주의": return 'background-color: #ffa421; color: black; font-weight: bold'
        return 'background-color: #28a745; color: white; font-weight: bold'

    styler.applymap(color_rate, subset=['등락률'])
    styler.applymap(color_status, subset=['상태'])
    styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
    return styler

if not final_df.empty:
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    styled_df = apply_color_style(display_df.style.format({
        '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
        '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
    }))
    st.dataframe(styled_df, use_container_width=True, height=600)
