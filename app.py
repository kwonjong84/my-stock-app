import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
import requests
import os
import html
from datetime import datetime

# [핵심] yfinance 내부 에러 방지를 위한 강제 초기화
def fix_yfinance():
    try:
        # 야후의 쿠키 시스템을 초기화하기 위한 더미 호출
        yf.pdr_override() 
    except:
        pass

# 1. 환경 설정 (유지)
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="주식 감시 시스템 Pro (오류 수정판)", layout="wide")
fix_yfinance()

# 2~3. 저장소 및 텔레그램 (기존 유지)
def get_saved_price(stock_name):
    if os.path.exists(PRICE_LOG):
        with open(PRICE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    p = line.strip().split(",")
                    if len(p) == 2 and p[0] == stock_name: return float(p[1])
                except: continue
    return 0.0

def save_price(stock_name, price):
    prices = {}
    if os.path.exists(PRICE_LOG):
        with open(PRICE_LOG, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    p = line.strip().split(",")
                    if len(p) == 2: prices[p[0]] = p[1]
                except: continue
    prices[stock_name] = str(price)
    with open(PRICE_LOG, "w", encoding="utf-8") as f:
        for n, p in prices.items(): f.write(f"{n},{p}\n")

def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=5)
    except: pass

# 4. 데이터 로드 (오류 회피형 로직)
def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        progress_bar = st.progress(0, text="야후 서버와 보안 연결 중...")
        
        for i, row in df.iterrows():
            ticker_symbol = f"{str(row['코드']).zfill(6)}.KS"
            progress_bar.progress((i + 1) / len(df), text=f"[{row['종목명']}] 수신 중")
            
            # [수정] t.history 대신 download를 사용하여 Crumb 에러 우회
            try:
                # 1분 단위가 아닌 1일 단위로 가져와서 차단 최소화
                d = yf.download(ticker_symbol, period="2d", interval="1m", progress=False)
                if not d.empty:
                    curr = float(d['Close'].iloc[-1])
                    prev = float(d['Close'].iloc[0])
                    high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                    
                    df.at[i, '현재가'] = curr
                    df.at[i, '기준고점'] = max(high, curr)
                    df.at[i, '등락률'] = (curr - prev) / prev
            except:
                continue
                
            time.sleep(0.5)
            
        progress_bar.empty()
        
        # 지수 데이터
        kp = yf.download("^KS11", period="2d", progress=False)
        kq = yf.download("^KQ11", period="2d", progress=False)
        kospi = (kp['Close'].iloc[-1], (kp['Close'].iloc[-1]-kp['Close'].iloc[-2])/kp['Close'].iloc[-2])
        kosdaq = (kq['Close'].iloc[-1], (kq['Close'].iloc[-1]-kq['Close'].iloc[-2])/kq['Close'].iloc[-2])

        for col in ['현재가', '기준고점', '등락률']: df[col] = pd.to_numeric(df[col], errors='coerce')
        df['손절(-10%)'] = df['기준고점'] * 0.9
        df['손절(-15%)'] = df['기준고점'] * 0.85
        df['상태'] = df.apply(lambda r: "🚨위험" if r['현재가'] <= r['손절(-15%)'] else "⚠️주의" if r['현재가'] <= r['손절(-10%)'] else "✅안정", axis=1)
        
        return df, kospi, kosdaq
    except Exception as e:
        st.error(f"⚠️ 시스템 경보: {e}")
        return pd.DataFrame(), (0,0), (0,0)

# 5~6. 실행 및 UI (기존 컬러 유지)
final_df, kospi, kosdaq = get_data()

if not final_df.empty:
    for _, s in final_df[final_df['상태'] == "🚨위험"].iterrows():
        last_p = get_saved_price(s['종목명'])
        if last_p == 0 or s['현재가'] <= last_p * 0.97:
            msg = f"<b>‼️ [하락 경보] ‼️</b>\n\n<b>종목:</b> {s['종목명']}\n<b>현재가:</b> {s['현재가']:,.0f}원"
            send_telegram_msg(msg)
            save_price(s['종목명'], s['현재가'])

st.title("📊 ISA 감시 시스템 (오류 긴급 패치)")
c1, c2 = st.columns(2)
with c1: st.metric("KOSPI", f"{kospi[0]:,.2f}", f"{kospi[1]:+.2%}")
with c2: st.metric("KOSDAQ", f"{kosdaq[0]:,.2f}", f"{kosdaq[1]:+.2%}")

if not final_df.empty:
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    def color_df(styler):
        styler.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        styler.applymap(lambda v: f'background-color: {"#ff4b4b" if v == "🚨위험" else "#ffa421" if v == "⚠️주의" else "#28a745"}; color: white; font-weight: bold', subset=['상태'])
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
        return styler
    st.dataframe(color_df(display_df.style.format({'현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'})), use_container_width=True, height=600)
