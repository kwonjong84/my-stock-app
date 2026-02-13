import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
from datetime import datetime

# 1. 환경 설정
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="주식 손절선 관리 PLUS (Hybrid)", layout="wide")

# 2. 야후 파이낸스 고가 보정 함수
def get_yahoo_high(ticker_code, google_high):
    try:
        if len(str(ticker_code)) == 6:
            yf_ticker = yf.Ticker(f"{ticker_code}.KS")
            hist = yf_ticker.history(period="5d")
            if not hist.empty:
                yf_high = hist['High'].max()
                return max(google_high, yf_high)
        return google_high
    except:
        return google_high

# 3. 데이터 로드 및 처리
def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        
        # 지수 추출
        try:
            mkt_idx = raw_df.iloc[0, 7]
            mkt_chg = raw_df.iloc[1, 7]
        except:
            mkt_idx, mkt_chg = 0, 0
            
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 야후 데이터 보정
        with st.spinner('실시간 고점 동기화 중 (Yahoo Finance)...'):
            df['기준고점'] = df.apply(lambda row: get_yahoo_high(row['코드'], row['기준고점']), axis=1)
            df['기준고점'] = df[['현재가', '기준고점']].max(axis=1)

        def calc_status(row):
            if pd.isna(row['현재가']): return "조회중"
            curr, s10, s15 = row['현재가'], row['손절(-10%)'], row['손절(-15%)']
            if curr <= s15: return "🚨위험"
            elif curr <= s10: return "⚠️주의"
            return "✅안정"
        
        df['상태'] = df.apply(calc_status, axis=1)
        return df, mkt_idx, mkt_chg
    except Exception as e:
        st.error(f"데이터 연동 실패: {e}")
        return pd.DataFrame(), 0, 0

# --- UI 레이아웃 ---
st.title("📊 실시간 주식 모니터링 시스템")
st.caption(f"최종 동기화 시각 (KST): {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

if st.button("🔄 데이터 강제 업데이트"):
    st.rerun()

final_df, mkt_idx, mkt_chg = get_data()

# 지수 영역 (카드 형태로 개선)
if mkt_idx != 0:
    st.metric("KOSPI 지수", f"{mkt_idx:,.2f}", f"{mkt_chg:.2%}", delta_color="normal")

if not final_df.empty:
    st.subheader("종목별 실시간 리포트")
    
    # 1. 등락률 색상 지정 (한국형: 상승-빨강, 하락-파랑)
    def style_variation(val):
        color = '#ff4b4b' if val > 0 else '#31333f'
        if val < 0: color = '#1c83e1'
        return f'color: {color}; font-weight: bold'

    # 2. 현재가 열 강조 스타일
    current_price_style = 'background-color: #f0f2f6; color: #0e1117; font-size: 1.1em; font-weight: 900;'

    # 화면용 데이터프레임 가공
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    st.dataframe(
        display_df.style.format({
            '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
            '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
        })
        .set_properties(subset=['현재가'], **{'background-color': '#f0f2f6', 'font-weight': '900'})
        .applymap(style_variation, subset=['등락률'])
        .map(lambda x: 
            'background-color: #ff4b4b; color: white; font-weight: bold' if x == "🚨위험" 
            else ('background-color: #ffa421; color: black;' if x == "⚠️주의" 
            else 'background-color: #28a745; color: white;'), subset=['상태']),
        use_container_width=True,
        height=600
    )
