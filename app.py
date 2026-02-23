import streamlit as st
import pd as pd
import pytz
import time
import yfinance as yf
import requests
import os
import html
from datetime import datetime

# 1. 환경 설정 (기존 유지)
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="주식 감시 시스템 Pro (최적화 완료)", layout="wide")

# 2. 저장소 로직 (기존 유지)
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

# 3. 텔레그램 발송 (기존 유지)
def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.get(url, params=params, timeout=10)
        if not resp.json().get("ok"):
            clean_text = message.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>","")
            requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": "[일반텍스트전송]\n" + clean_text})
    except: pass

# 4. 데이터 로드 최적화 (핵심 수정 사항)
@st.cache_data(ttl=60)
def get_market_indices():
    """지수 데이터를 별도로 가져와 캐싱"""
    try:
        indices = yf.download(["^KS11", "^KQ11"], period="2d", interval="1m", group_by='ticker', progress=False)
        kospi_curr = indices["^KS11"]['Close'].iloc[-1]
        kospi_prev = indices["^KS11"]['Close'].iloc[0]
        kosdaq_curr = indices["^KQ11"]['Close'].iloc[-1]
        kosdaq_prev = indices["^KQ11"]['Close'].iloc[0]
        return (kospi_curr, (kospi_curr-kospi_prev)/kospi_prev), (kosdaq_curr, (kosdaq_curr-kosdaq_prev)/kosdaq_prev)
    except:
        return (0,0), (0,0)

def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        # [변경점] 모든 종목 코드를 리스트로 만들어 한 번에 다운로드 (차단 방지 핵심)
        ticker_list = [f"{str(c).zfill(6)}.KS" for c in df['코드']]
        progress_bar = st.progress(0, text="전체 종목 시세 일괄 동기화 중...")
        
        # Batch Download 실행
        all_stocks_data = yf.download(ticker_list, period="2d", interval="1m", group_by='ticker', progress=False)
        
        for i, row in df.iterrows():
            ticker = f"{str(row['코드']).zfill(6)}.KS"
            try:
                # 멀티인덱스 대응 데이터 추출
                d = all_stocks_data[ticker] if len(ticker_list) > 1 else all_stocks_data
                if not d.empty:
                    curr = float(d['Close'].iloc[-1])
                    prev = float(d['Close'].iloc[0])
                    high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                    
                    df.at[i, '현재가'] = curr
                    df.at[i, '기준고점'] = max(high, curr)
                    df.at[i, '등락률'] = (curr - prev) / prev
            except: continue
        
        progress_bar.empty()
        kospi, kosdaq = get_market_indices()

        for col in ['현재가', '기준고점', '등락률']: df[col] = pd.to_numeric(df[col], errors='coerce')
        df['손절(-10%)'] = df['기준고점'] * 0.9
        df['손절(-15%)'] = df['기준고점'] * 0.85
        df['상태'] = df.apply(lambda r: "🚨위험" if r['현재가'] <= r['손절(-15%)'] else "⚠️주의" if r['현재가'] <= r['손절(-10%)'] else "✅안정", axis=1)
        
        return df, kospi, kosdaq
    except Exception as e:
        st.error(f"데이터 로드 중 오류: {e}")
        return pd.DataFrame(), (0,0), (0,0)

# 5. 실행 및 알림 (기존 유지)
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

# 6. UI 시각화 (기존 컬러 스타일 완벽 복구)
st.title("📊 주식 실시간 감시 (최적화 버전)")
st.caption(f"최종 업데이트: {datetime.now(KST).strftime('%H:%M:%S')}")

if st.button("🔄 즉시 새로고침"):
    st.cache_data.clear()
    st.rerun()

c1, c2 = st.columns(2)
with c1: st.metric("KOSPI", f"{kospi[0]:,.2f}", f"{kospi[1]:+.2%}")
with c2: st.metric("KOSDAQ", f"{kosdaq[0]:,.2f}", f"{kosdaq[1]:+.2%}")

def apply_color_style(styler):
    def color_rate(val):
        color = '#ff4b4b' if val > 0 else '#1c83e1' if val < 0 else '#ffffff'
        return f'color: {color}; font-weight: bold'
    
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
