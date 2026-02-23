import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
import requests
import os
import html
from datetime import datetime

# 1. 환경 설정 (유지)
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="주식 감시 시스템 Pro (최종 수정)", layout="wide")

# 2. 저장소 로직 (유지)
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

# 3. 텔레그램 발송 (유지)
def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.get(url, params=params, timeout=10)
    except: pass

# 4. 데이터 로드 (멀티인덱스 오류 해결판)
def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        # 종목 리스트 생성
        ticker_list = [f"{str(c).zfill(6)}.KS" for c in df['코드']]
        
        # [핵심 수정] auto_adjust=True 및 개별 호출 방식으로 안정성 확보
        # Batch 호출의 인덱스 꼬임을 방지하기 위해 순차 호출하되 지연시간 최적화
        progress_bar = st.progress(0, text="데이터 정밀 동기화 중...")
        
        for i, row in df.iterrows():
            ticker_symbol = f"{str(row['코드']).zfill(6)}.KS"
            progress_bar.progress((i + 1) / len(df), text=f"[{row['종목명']}] 동기화")
            
            # 단일 종목 호출 (구조 꼬임 방지)
            t = yf.Ticker(ticker_symbol)
            hist = t.history(period="2d", interval="1m")
            
            if not hist.empty:
                curr = float(hist['Close'].iloc[-1])
                prev = t.info.get('previousClose', hist['Close'].iloc[0])
                high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                
                df.at[i, '현재가'] = curr
                df.at[i, '기준고점'] = max(high, curr)
                df.at[i, '등락률'] = (curr - prev) / prev
            time.sleep(0.2) # 서버 차단 방지용 최소 지연
            
        progress_bar.empty()
        
        # 지수 데이터
        kp = yf.Ticker("^KS11").history(period="2d")
        kq = yf.Ticker("^KQ11").history(period="2d")
        kospi = (kp['Close'].iloc[-1], (kp['Close'].iloc[-1]-kp['Close'].iloc[-2])/kp['Close'].iloc[-2])
        kosdaq = (kq['Close'].iloc[-1], (kq['Close'].iloc[-1]-kq['Close'].iloc[-2])/kq['Close'].iloc[-2])

        for col in ['현재가', '기준고점', '등락률']: df[col] = pd.to_numeric(df[col], errors='coerce')
        df['손절(-10%)'] = df['기준고점'] * 0.9
        df['손절(-15%)'] = df['기준고점'] * 0.85
        df['상태'] = df.apply(lambda r: "🚨위험" if r['현재가'] <= r['손절(-15%)'] else "⚠️주의" if r['현재가'] <= r['손절(-10%)'] else "✅안정", axis=1)
        
        return df, kospi, kosdaq
    except Exception as e:
        st.error(f"오류: {e}")
        return pd.DataFrame(), (0,0), (0,0)

# 5. 실행 및 알림 (유지)
final_df, kospi, kosdaq = get_data()

if not final_df.empty:
    for _, s in final_df[final_df['상태'] == "🚨위험"].iterrows():
        last_p = get_saved_price(s['종목명'])
        if last_p == 0 or s['현재가'] <= last_p * 0.97:
            msg = f"<b>‼️ [하락 경보] ‼️</b>\n\n<b>종목:</b> {s['종목명']}\n<b>현재가:</b> {s['현재가']:,.0f}원\n<b>시장:</b> KOSPI {kospi[0]:,.2f}"
            send_telegram_msg(msg)
            save_price(s['종목명'], s['현재가'])

# 6. UI 시각화 (컬러 스타일 복구)
st.title("📊 주식 실시간 감시 (구조 보정판)")
st.caption(f"조회 시간: {datetime.now(KST).strftime('%H:%M:%S')}")

if st.button("🔄 즉시 새로고침"):
    st.cache_data.clear()
    st.rerun()

c1, c2 = st.columns(2)
with c1: st.metric("KOSPI", f"{kospi[0]:,.2f}", f"{kospi[1]:+.2%}")
with c2: st.metric("KOSDAQ", f"{kosdaq[0]:,.2f}", f"{kosdaq[1]:+.2%}")

def apply_color_style(styler):
    styler.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "#ffffff"}; font-weight: bold', subset=['등락률'])
    styler.applymap(lambda v: f'background-color: {"#ff4b4b" if v == "🚨위험" else "#ffa421" if v == "⚠️주의" else "#28a745"}; color: white; font-weight: bold', subset=['상태'])
    styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
    return styler

if not final_df.empty:
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    st.dataframe(apply_color_style(display_df.style.format({'현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'})), use_container_width=True, height=600)
