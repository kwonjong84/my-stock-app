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
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="주식 손절 감시 시스템 Pro", layout="wide")

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

# [교정] 3. 텔레그램 발송 함수 (특수문자 자동 변환 추가)
def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        # 메시지 전송 시 parse_mode를 명시하되, 전송 실패 시 일반 텍스트로 재시도
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
        resp = requests.get(url, params=params, timeout=10)
        
        if not resp.json().get("ok"):
            # HTML 파싱 에러 발생 시, 모든 태그를 제거하고 일반 텍스트로 강제 발송
            params = {"chat_id": TELEGRAM_CHAT_ID, "text": "파싱 에러로 일반 텍스트 전환 발송:\n" + message.replace("<b>","").replace("</b>","").replace("<i>","").replace("</i>","")}
            requests.get(url, params=params)
    except Exception as e:
        st.error(f"네트워크 오류: {e}")

# 4. 데이터 로드 및 최적화 (캐싱 적용)
@st.cache_data(ttl=60) # 1분간 데이터 캐싱하여 서버 부하 감소
def get_market_index(ticker_symbol):
    try:
        ticker = yf.Ticker(ticker_symbol)
        hist = ticker.history(period="2d", interval="1m")
        if not hist.empty:
            curr = hist['Close'].iloc[-1]
            prev = ticker.info.get('previousClose', curr)
            rate = (curr - prev) / prev
            return curr, rate
    except Exception as e:
        st.warning(f"{ticker_symbol} 지수 로드 실패")
    return 0, 0

def get_data():
    try:
        # 구글 시트 로드
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        # 지수 정보
        kospi_p, kospi_r = get_market_index("^KS11")
        kosdaq_p, kosdaq_r = get_market_index("^KQ11")
            
        # 종목별 데이터 로드 (진행바 추가)
        progress_text = "주식 시세를 가져오는 중입니다..."
        my_bar = st.progress(0, text=progress_text)
        
        for i, row in df.iterrows():
            my_bar.progress((i + 1) / len(df), text=f"[{row['종목명']}] 데이터 분석 중...")
            yf_ticker = yf.Ticker(f"{row['코드']}.KS")
            data = yf_ticker.history(period="1d", interval="1m").tail(1)
            
            if not data.empty:
                curr = data['Close'].iloc[-1]
                sheet_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                df.at[i, '현재가'] = curr
                df.at[i, '기준고점'] = max(sheet_high, curr)
                prev_p = yf_ticker.info.get('previousClose', curr)
                df.at[i, '등락률'] = (curr - prev_p) / prev_p
            time.sleep(0.1) # 과도한 API 호출 방지
        
        my_bar.empty() # 진행바 제거

        for col in ['현재가', '기준고점', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        df['손절(-10%)'] = df['기준고점'] * 0.9
        df['손절(-15%)'] = df['기준고점'] * 0.85
        
        def calc_status(row):
            if row['현재가'] <= row['손절(-15%)']: return "🚨위험"
            elif row['현재가'] <= row['손절(-10%)']: return "⚠️주의"
            return "✅안정"
        df['상태'] = df.apply(calc_status, axis=1)
        
        return df, (kospi_p, kospi_r), (kosdaq_p, kosdaq_r)
    except Exception as e:
        st.error(f"데이터 로드 중 심각한 오류 발생: {e}")
        return pd.DataFrame(), (0,0), (0,0)

# [교정] 5. 실행 및 알림 로직 (데이터 안전하게 감싸기)
# ... 데이터 로드 부분 생략 ...
        if last_p == 0 or current_p <= last_p * 0.97:
            # 변수들을 안전하게 처리 (HTML 충돌 방지)
            safe_name = html.escape(str(name))
            emoji = "🔴" if rate > 0 else "🔵"
            
            msg = (
                f"<b>‼️ [하락 경보] ‼️</b>\n\n"
                f"<b>종목:</b> {safe_name}\n"
                f"<b>현재가:</b> {current_p:,.0f}원 ({emoji} {rate:+.2%})\n"
                f"<b>지수:</b> KOSPI {kospi[0]:,.2f} / KOSDAQ {kosdaq[0]:,.2f}\n\n"
                f"<i>(이전 알림 대비 3% 추가 하락 시 재알림)</i>"
            )
            send_telegram_msg(msg)
            save_price(name, current_p)

# --- 6. UI ---
st.title("📊 주식 감시 시스템 (안정화 버전)")
st.caption(f"동기화: {datetime.now(KST).strftime('%H:%M:%S')} | 1분 캐싱 적용됨")

if st.button("🔄 즉시 새로고침"):
    st.cache_data.clear() # 캐시 강제 삭제 후 리로드
    st.rerun()

col1, col2 = st.columns(2)
with col1:
    if kospi[0] > 0: st.metric("KOSPI 지수", f"{kospi[0]:,.2f}", f"{kospi[1]:+.2%}")
with col2:
    if kosdaq[0] > 0: st.metric("KOSDAQ 지수", f"{kosdaq[0]:,.2f}", f"{kosdaq[1]:+.2%}")

if not final_df.empty:
    def style_df(styler):
        styler.set_properties(**{'text-align': 'center'})
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': '900'})
        styler.applymap(lambda val: f"color: {'#ff4b4b' if val > 0 else '#1c83e1' if val < 0 else '#ffffff'}; font-weight: bold", subset=['등락률'])
        return styler

    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    st.dataframe(style_df(display_df.style.format({'현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'})), use_container_width=True)
