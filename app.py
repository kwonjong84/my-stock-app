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
        # 한국 종목 코드 형식 (코스피는 .KS, 코스닥은 .KQ)
        # 6자리 숫자인 경우만 처리
        if len(str(ticker_code)) == 6:
            # 기본적으로 코스피(.KS)로 시도하고 안되면 코스닥(.KQ) 시도
            yf_ticker = yf.Ticker(f"{ticker_code}.KS")
            # 최근 5일간의 데이터를 가져와서 그중 장중 최고가(High)를 추출
            hist = yf_ticker.history(period="5d")
            if not hist.empty:
                yf_high = hist['High'].max()
                # 구글 데이터보다 야후 데이터가 높으면 야후 데이터를 반환
                return max(google_high, yf_high)
        return google_high
    except:
        return google_high

# 3. 데이터 로드 및 처리
def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        
        # 지수 추출 (H열)
        try:
            mkt_idx = raw_df.iloc[0, 7]
            mkt_chg = raw_df.iloc[1, 7]
        except:
            mkt_idx, mkt_chg = 0, 0
            
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # [참모의 보정] 구글 고점과 야후 실시간 고점을 비교하여 최댓값 채택
        with st.spinner('실시간 고점 동기화 중 (Yahoo Finance)...'):
            df['기준고점'] = df.apply(lambda row: get_yahoo_high(row['코드'], row['기준고점']), axis=1)
            # 현재가가 고점보다 높으면 다시 한번 보정
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

# --- UI 레이아웃 (이후 동일) ---
st.title("📊 하이브리드 주식 모니터링")
st.caption(f"최종 동기화 시각 (KST): {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

if st.button("🔄 데이터 강제 업데이트"):
    st.rerun()

final_df, mkt_idx, mkt_chg = get_data()

if mkt_idx != 0:
    st.metric("KOSPI 지수", f"{mkt_idx:,.2f}", f"{mkt_chg:.2%}")

if not final_df.empty:
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    st.dataframe(
        display_df.style.format({
            '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
            '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
        }).map(lambda x: 'background-color: #ff4b4b; color: white;' if x == "🚨위험" else ''),
        use_container_width=True, height=600
    )
