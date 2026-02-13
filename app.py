import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
from datetime import datetime

# 1. 환경 설정
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
# 시트는 종목 리스트를 불러오는 용도로만 사용 (캐시 방지 적용)
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="주식 손절선 관리 PLUS (Real-time)", layout="wide")

# 2. 야후 파이낸스 실시간 데이터 추출 함수
def get_realtime_data(ticker_code, google_price, google_high):
    try:
        if len(str(ticker_code)) == 6:
            yf_ticker = yf.Ticker(f"{ticker_code}.KS")
            # 최신 1일 데이터를 1분 단위로 가져와 가장 최근값 추출
            data = yf_ticker.history(period="1d", interval="1m")
            if not data.empty:
                real_price = data['Close'].iloc[-1]  # 가장 최근 체결가
                # 5일치 고가 데이터를 가져와서 고점 보정
                hist_5d = yf_ticker.history(period="5d")
                real_high = max(google_high, hist_5d['High'].max())
                return real_price, real_high
        return google_price, google_high
    except:
        return google_price, google_high

def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        # 지수 데이터 (구글 지수는 어쩔 수 없는 지연이 발생하므로 참고용)
        try:
            mkt_idx = raw_df.iloc[0, 7]
            mkt_chg = raw_df.iloc[1, 7]
        except:
            mkt_idx, mkt_chg = 0, 0
            
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        # 숫자 변환
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # [참모의 한수] 현재가와 고가를 모두 야후 데이터로 강제 동기화
        with st.spinner('증권사급 실시간 데이터 동기화 중...'):
            for i, row in df.iterrows():
                r_price, r_high = get_realtime
