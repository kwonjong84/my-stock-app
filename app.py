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

# 2. 데이터 처리 및 보정
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

def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        try:
            mkt_idx = raw_df.iloc[0, 7]
            mkt_chg = raw_df.iloc[1, 7]
        except:
            mkt_idx, mkt_chg = 0, 0
            
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        with st.spinner('실시간 고점 동기화 중...'):
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

if mkt_idx != 0:
    st.metric("KOSPI 지수", f"{mkt_idx:,.2f}", f"{mkt_chg:.2%}")

if not final_df.empty:
    st.subheader("종목별 실시간 리포트")
    
    # 1. 스타일 정의
    def style_df(styler):
        # 전체 텍스트 컬러 및 정렬
        styler.set_properties(**{'text-align': 'center'})
        
        # 현재가 열: 가독성을 위해 배경색 제거하고 폰트 크기 및 두께만 강조
        styler.set_properties(subset=['현재가'], **{
            'color': '#00d1ff',  # 형광 파란색으로 포인트
            'font-weight': '900',
            'font-size': '1.2em'
        })
        
        # 등락률 색상 (상승 빨강, 하락 파랑)
        def color_rate(val):
            color = '#ff4b4b' if val > 0 else '#1c83e1' if val < 0 else '#ffffff'
            return f'color: {color}; font-weight: bold'
        styler.applymap(color_rate, subset=['등락률'])
        
        # 상태 열 배경색
        def color_status(val):
            if val == "🚨위험": return 'background-color: #ff4b4b; color: white; font-weight: bold'
            if val == "⚠️주의": return 'background-color: #ffa421; color: black; font-weight: bold'
            return 'background-color: #28a745; color: white; font-weight: bold'
        styler.applymap(color_status, subset=['상태'])
        
        return styler

    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    st.dataframe(
        style_df(display_df.style.format({
            '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
            '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
        })),
        use_container_width=True,
        height=600
    )
