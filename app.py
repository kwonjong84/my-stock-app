import streamlit as st
import pandas as pd
import pytz
import time
import requests
import os
import html
from datetime import datetime

# 1. 환경 설정 (기존 유지)
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
# t={int(time.time())}를 통해 구글 시트의 최신 계산 결과를 강제로 새로고침함
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="주식 감시 시스템 (Google 기반)", layout="wide")

# 2~3. 저장소 및 텔레그램 (기존 로직 100% 보존)
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

def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=5)
    except: pass

# 4. 데이터 로드 (yfinance 제거, 시트 값 직접 사용)
def get_data():
    try:
        # 구글 시트에서 수식이 계산된 결과값을 CSV로 한 번에 가져옴
        df = pd.read_csv(SHEET_URL)
        # 사용자님의 시트 구조에 맞게 슬라이싱 (0~7번 열)
        df = df.iloc[:, :8].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률', '상태']
        
        # 데이터 타입 정리 (숫자로 강제 변환)
        for col in ['현재가', '기준고점', '등락률', '손절(-10%)', '손절(-15%)']:
            df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
            
        return df
    except Exception as e:
        st.error(f"구글 시트 로드 오류: {e}")
        return pd.DataFrame()

# 5. 실행 및 알림
final_df = get_data()

if not final_df.empty:
    # '🚨위험' 상태인 종목 추출 (시트의 '상태' 열 기준)
    danger_df = final_df[final_df['상태'].str.contains("위험", na=False)]
    for _, s in danger_df.iterrows():
        last_p = get_saved_price(s['종목명'])
        if last_p == 0 or s['현재가'] <= last_p * 0.97:
            msg = f"<b>‼️ [하락 경보] ‼️</b>\n\n<b>종목:</b> {s['종목명']}\n<b>현재가:</b> {s['현재가']:,.0f}원\n<b>등락률:</b> {s['등락률']:+.2%}"
            send_telegram_msg(msg)
            save_price(s['종목명'], s['현재가'])

# 6. UI 시각화 (기존 컬러 스타일 유지)
st.title("📊 ISA 감시 시스템 (No-Error 모드)")
st.info("💡 야후 차단 문제를 해결하기 위해 구글 시트의 실시간 수식 데이터를 직접 참조 중입니다.")

if not final_df.empty:
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    def apply_style(styler):
        styler.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        styler.applymap(lambda v: f'background-color: {"#ff4b4b" if "🚨" in str(v) else "#ffa421" if "⚠️" in str(v) else "#28a745"}; color: white; font-weight: bold', subset=['상태'])
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
        return styler

    st.dataframe(apply_style(display_df.style.format({
        '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
        '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
    })), use_container_width=True, height=600)
