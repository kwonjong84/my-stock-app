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

# 2. 보강된 실시간 데이터 함수 (야후 파이낸스 최신 틱 유도)
def get_realtime_data(ticker_code, is_index=False):
    try:
        symbol = f"{ticker_code}.KS" if not is_index else ticker_code
        yf_ticker = yf.Ticker(symbol)
        
        # 최신 1분 봉 데이터 중 가장 마지막 값 추출 (캐시 최소화)
        data = yf_ticker.history(period="1d", interval="1m").tail(1)
        if not data.empty:
            current_p = data['Close'].iloc[-1]
            high_p = data['High'].iloc[-1]
            
            # 지수가 아닌 일반 종목의 경우 5일 고가와 비교 보정
            if not is_index:
                hist_5d = yf_ticker.history(period="5d")
                final_high = max(high_p, hist_5d['High'].max())
                return current_p, final_high
            return current_p, None # 지수는 현재가만 반환
        return None, None
    except:
        return None, None

def get_data():
    try:
        # 1. 시트에서 종목 리스트 로드
        raw_df = pd.read_csv(SHEET_URL)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        # 2. 실시간 지수 호출 (KOSPI 야후 티커: ^KS11)
        with st.spinner('실시간 지수 및 시세 동기화 중...'):
            mkt_idx, _ = get_realtime_data("^KS11", is_index=True)
            # 이전 지수 대비 변동률은 시트 데이터 참고 (비교용)
            mkt_chg = raw_df.iloc[1, 7] if not pd.isna(raw_df.iloc[1, 7]) else 0
            
            # 3. 종목별 현재가 및 고점 실시간 동기화
            for i, row in df.iterrows():
                r_price, r_high = get_realtime_data(row['코드'])
                if r_price:
                    df.at[i, '현재가'] = r_price
                    # 시트의 고점과 야후의 고점 중 더 높은 것을 채택
                    sheet_high = pd.to_numeric(row['기준고점'], errors='coerce') or 0
                    df.at[i, '기준고점'] = max(r_price, r_high, sheet_high)

        # 숫자 변환 및 상태 계산
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 손절선 재계산 (고점 기준)
        df['손절(-10%)'] = df['기준고점'] * 0.9
        df['손절(-15%)'] = df['기준고점'] * 0.85

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

if st.button("🔄 실시간 시세 새로고침"):
    st.rerun()

final_df, mkt_idx, mkt_chg = get_data()

# 지수 영역 (야후 실시간 지수 적용)
if mkt_idx:
    st.metric("KOSPI 실시간 지수", f"{mkt_idx:,.2f}", f"{mkt_chg:.2%}")

if not final_df.empty:
    def style_df(styler):
        styler.set_properties(**{'text-align': 'center'})
        # 현재가 시인성 극대화
        styler.set_properties(subset=['현재가'], **{
            'color': '#00d1ff', 'font-weight': '900', 'font-size': '1.2em'
        })
        # 등락률 컬러 로직
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
