import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# [핵심: 효율적 데이터 관리와 직관적 UI] - Persona: 비판적 참모
st.set_page_config(page_title="Global Stock Monitor", layout="wide")

# 1. 데이터 호출 최적화 (캐싱 설정)
@st.cache_data(ttl=300) # 5분간 데이터를 보관하여 서버 차단 방지
def fetch_data(tickers):
    try:
        # 여러 종목을 한 번에 호출하여 통신 횟수 최소화
        data = yf.download(tickers, period="5d", interval="1d", group_by='ticker', progress=False)
        return data
    except Exception as e:
        st.error(f"데이터 로드 실패: {e}")
        return None

# 2. 사이드바 - 설정 및 관리
st.sidebar.title("🛠️ 감시 설정")
watchlist = st.sidebar.text_input("감시 종목 (쉼표로 구분)", "TSLA, NVDA, AAPL, MSFT").upper().replace(" ", "").split(",")
auto_refresh = st.sidebar.checkbox("자동 새로고침 모드 (5분 단위)")

# 3. 메인 대시보드
st.title("📈 해외 주식 실시간 모니터링")
st.caption(f"최종 업데이트: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (5분마다 자동 갱신 권장)")

if watchlist:
    all_data = fetch_data(watchlist)
    
    if all_data is not None:
        # 종목별 카드 배치
        cols = st.columns(len(watchlist))
        
        for i, ticker in enumerate(watchlist):
            with cols[i]:
                try:
                    # 단일 종목 데이터 추출 (yfinance 구조 대응)
                    if len(watchlist) > 1:
                        ticker_data = all_data[ticker]
                    else:
                        ticker_data = all_data
                    
                    current_price = ticker_data['Close'].iloc[-1]
                    prev_price = ticker_data['Close'].iloc[-2]
                    delta = current_price - prev_price
                    delta_percent = (delta / prev_price) * 100
                    
                    st.metric(label=ticker, 
                              value=f"${current_price:.2f}", 
                              delta=f"{delta:.2f} ({delta_percent:.2f}%)")
                    
                    # 차트 시각화
                    st.line_chart(ticker_data['Close'], height=200)
                except:
                    st.error(f"{ticker} 분석 불가")

# 4. 비판적 참모의 기술 점검
st.divider()
st.subheader("💡 시스템 진단")
col1, col2 = st.columns(2)
with col1:
    st.info("**안정성:** 캐싱(TTL 300s) 적용 완료. 야후 서버로부터의 IP 차단 가능성을 최소화했습니다.")
with col2:
    st.warning("**한계점:** 현재 15분 지연 시세입니다. 내일 한투 API 연동 후 '0초 지연' 실시간 모드로 전환 예정입니다.")
