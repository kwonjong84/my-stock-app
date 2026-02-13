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

st.set_page_config(page_title="주식 손절선 관리 PLUS (Real-time)", layout="wide")

# 2. 야후 파이낸스 실시간 데이터 추출 함수 (보정 완료)
def get_realtime_data(ticker_code, google_price, google_high):
    try:
        if len(str(ticker_code)) == 6:
            yf_ticker = yf.Ticker(f"{ticker_code}.KS")
            # 1분 단위 최신 데이터
            data = yf_ticker.history(period="1d", interval="1m")
            if not data.empty:
                real_price = data['Close'].iloc[-1]
                # 최근 5일 고점과 비교
                hist_5d = yf_ticker.history(period="5d")
                real_high = max(google_high, hist_5d['High'].max())
                return real_price, real_high
        return google_price, google_high
    except Exception:
        return google_price, google_high

# 3. 데이터 로드 및 처리
def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        try:
            mkt_idx = raw_df.iloc[0, 7]
            mkt_chg = raw_df.iloc[1, 7]
        except Exception:
            mkt_idx, mkt_chg = 0, 0
            
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        # 실시간 데이터 동기화 루프
        with st.spinner('미래에셋 앱 수준 실시간 동기화 중...'):
            for i, row in df.iterrows():
                # 에러가 발생했던 지점 수정 완료
                r_price, r_high = get_realtime_data(row['코드'], row['현재가'], row['기준고점'])
                df.at[i, '현재가'] = r_price
                df.at[i, '기준고점'] = max(r_price, r_high)

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
st.title("📊 실시간 주식 모니터링 (Full-Hybrid)")
st.caption(f"최종 동기화 시각 (KST): {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

if st.button("🔄 실시간 시세 새로고침"):
    st.rerun()

final_df, mkt_idx, mkt_chg = get_data()

if mkt_idx != 0:
    st.metric("KOSPI 지수 (참고용)", f"{mkt_idx:,.2f}", f"{mkt_chg:.2%}")

if not final_df.empty:
    def style_df(styler):
        styler.set_properties(**{'text-align': 'center'})
        # 현재가 강조 (사이언 컬러)
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': '900', 'font-size': '1.2em'})
        
        # 등락률 컬러 (상승 빨강, 하락 파랑)
        def color_rate(val):
            color = '#ff4b4b' if val > 0 else '#1c83e1' if val < 0 else '#ffffff'
            return f'color: {color}; font-weight: bold'
        styler.applymap(color_rate, subset=['등락률'])
        
        # 상태 배경색
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
        use_container_width=True, height=600
    )
