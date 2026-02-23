import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
import requests
import os
import html  # 특수문자 변환을 위해 필수 추가
from datetime import datetime

# 1. 환경 설정
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="주식 감시 시스템 Pro (안정화)", layout="wide")

# 2. 영구 저장소 로직
def get_saved_price(stock_name):
    if os.path.exists(PRICE_LOG):
        with open(PRICE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    parts = line.strip().split(",")
                    if len(parts) == 2 and parts[0] == stock_name:
                        return float(parts[1])
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
        for name, p in prices.items():
            f.write(f"{name},{p}\n")

# 3. 텔레그램 발송 함수 (HTML 에러 완벽 방어)
def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        # 1차 시도: HTML 모드로 전송
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.get(url, params=params, timeout=10)
        
        # 만약 HTML 파싱 에러(400)가 나면 태그를 제거하고 일반 텍스트로 2차 시도
        if not resp.json().get("ok"):
            clean_text = message.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>","")
            params = {"chat_id": TELEGRAM_CHAT_ID, "text": "[재전송]\n" + clean_text}
            requests.get(url, params=params)
    except Exception as e:
        st.error(f"네트워크 오류: {e}")

# 4. 데이터 로드 및 최적화
@st.cache_data(ttl=60)
def get_market_index(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="2d", interval="1m")
        if not hist.empty:
            curr = hist['Close'].iloc[-1]
            prev = ticker.info.get('previousClose', curr)
            rate = (curr - prev) / prev
            return curr, rate
    except: pass
    return 0, 0

def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        kospi_p, kospi_r = get_market_index("^KS11")
        kosdaq_p, kosdaq_r = get_market_index("^KQ11")
            
        progress_text = "데이터 분석 중..."
        my_bar = st.progress(0, text=progress_text)
        
        for i, row in df.iterrows():
            my_bar.progress((i + 1) / len(df), text=f"[{row['종목명']}] 조회 중")
            yf_ticker = yf.Ticker(f"{row['코드']}.KS")
            data = yf_ticker.history(period="1d", interval="1m").tail(1)
            if not data.empty:
                curr = data['Close'].iloc[-1]
                sheet_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                df.at[i, '현재가'] = curr
                df.at[i, '기준고점'] = max(sheet_high, curr)
                prev_p = yf_ticker.info.get('previousClose', curr)
                df.at[i, '등락률'] = (curr - prev_p) / prev_p
            time.sleep(0.1)
        
        my_bar.empty()
        for col in ['현재가', '기준고점', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['손절(-10%)'] = df['기준고점'] * 0.9
        df['손절(-15%)'] = df['기준고점'] * 0.85
        df['상태'] = df.apply(lambda r: "🚨위험" if r['현재가'] <= r['손절(-15%)'] else "⚠️주의" if r['현재가'] <= r['손절(-10%)'] else "✅안정", axis=1)
        
        return df, (kospi_p, kospi_r), (kosdaq_p, kosdaq_r)
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return pd.DataFrame(), (0,0), (0,0)

# --- 5. 실행 로직 ---
final_df, kospi, kosdaq = get_data()

if not final_df.empty:
    danger_stocks = final_df[final_df['상태'] == "🚨위험"]
    for _, s in danger_stocks.iterrows():
        name = s['종목명']
        current_p = s['현재가']
        rate = s['등락률']
        last_p = get_saved_price(name)
        
        if last_p == 0 or current_p <= last_p * 0.97:
            # 특수문자 안전하게 변환
            s_name = html.escape(str(name))
            emoji = "🔴" if rate > 0 else "🔵"
            
            # 메시지 구성
            msg = (
                f"<b>‼️ [하락 경보] ‼️</b>\n\n"
                f"<b>종목:</b> {s_name}\n"
                f"<b>현재가:</b> {current_p:,.0f}원 ({emoji} {rate:+.2%})\n"
                f"<b>코스피:</b> {kospi[0]:,.2f} ({kospi[1]:+.2%})\n"
                f"<b>코스닥:</b> {kosdaq[0]:,.2f} ({kosdaq[1]:+.2%})\n\n"
                f"<i>(이전 대비 3% 추가 하락 시 재알림)</i>"
            )
            send_telegram_msg(msg)
            save_price(name, current_p)

# --- 6. UI ---
st.title("📊 주식 감시 시스템 (최종 안정화)")
st.caption(f"동기화: {datetime.now(KST).strftime('%H:%M:%S')}")

if st.button("🔄 즉시 새로고침"):
    st.cache_data.clear()
    st.rerun()

c1, c2 = st.columns(2)
with c1: st.metric("KOSPI", f"{kospi[0]:,.2f}", f"{kospi[1]:+.2%}")
with c2: st.metric("KOSDAQ", f"{kosdaq[0]:,.2f}", f"{kosdaq[1]:+.2%}")

if not final_df.empty:
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    st.dataframe(display_df.style.format({'현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'}), use_container_width=True)
