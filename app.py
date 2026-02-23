import streamlit as st
import pandas as pd
import pytz
import requests
import os
import html
import time
from datetime import datetime

# [핵심] 야후 파이낸스 라이브러리 완전 제거 (오류의 근원 차단)
# 1. 환경 설정 (유지)
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
# 구글 시트의 시세를 실시간으로 반영하기 위해 t=시간 파라미터 유지
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="ISA 감시 시스템 (생존 모드)", layout="wide")

# 2~3. 저장소 및 텔레그램 (기존 로직 유지)
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

# 4. 데이터 로드 (구글 시트가 계산한 시세를 그대로 사용)
def get_data():
    try:
        # 구글 시트에 미리 =GOOGLEFINANCE(코드, "price")가 설정되어 있어야 합니다.
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :8].copy() # 상태 컬럼까지 포함
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률', '상태']
        
        # 숫자형 변환 및 전처리
        for col in ['현재가', '기준고점', '등락률', '손절(-10%)', '손절(-15%)']:
            df[col] = pd.to_numeric(df[col].replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
        
        # 지수 정보 (야후 대신 시트의 특정 셀에서 가져오거나 임시 0 처리)
        kospi = (0, 0) 
        kosdaq = (0, 0)
        
        return df, kospi, kosdaq
    except Exception as e:
        st.error(f"시트 로드 오류: {e}")
        return pd.DataFrame(), (0,0), (0,0)

# 5. 메인 로직
final_df, kospi, kosdaq = get_data()

if not final_df.empty:
    # 텔레그램 알림 로직 (위험 종목 탐색)
    for _, s in final_df[final_df['상태'].str.contains("위험", na=False)].iterrows():
        last_p = get_saved_price(s['종목명'])
        if last_p == 0 or s['현재가'] <= last_p * 0.97:
            msg = f"<b>‼️ [하락 경보] ‼️</b>\n\n<b>종목:</b> {s['종목명']}\n<b>현재가:</b> {s['현재가']:,.0f}원"
            send_telegram_msg(msg)
            save_price(s['종목명'], s['현재가'])

# 6. UI 시각화 (컬러 스타일 보존)
st.title("📊 ISA 감시 시스템 (라이브러리 제거판)")
st.info("💡 야후 파이낸스 오류로 인해 '구글 시트 시세 데이터'를 직접 사용 중입니다.")

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
