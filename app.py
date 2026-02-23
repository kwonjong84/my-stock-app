import streamlit as st
import yfinance as yf
import pandas as pd
from datetime import datetime

# [핵심: 국내 주식 데이터 매칭 및 에러 방지] - Persona: 비판적 참모
st.set_page_config(page_title="국내 주식 실시간 감시", layout="wide")

# 1. 국내 주식 전용 데이터 호출 함수
@st.cache_data(ttl=300)
def fetch_korea_data(ticker_list):
    # 한국 종목은 뒤에 .KS(코스피) 또는 .KQ(코스닥)가 붙어야 함
    processed_tickers = []
    for t in ticker_list:
        if not (t.endswith('.KS') or t.endswith('.KQ')):
            # 숫자로만 된 6자리 코드라면 보통 .KS를 기본으로 붙임
            processed_tickers.append(f"{t}.KS")
        else:
            processed_tickers.append(t)
            
    try:
        data = yf.download(processed_tickers, period="5d", interval="1d", group_by='ticker', progress=False)
        return data, processed_tickers
    except Exception as e:
        return None, processed_tickers

# 2. 메인 화면 구성
st.title("🇰🇷 국내 주식 모니터링 (ISA 계좌용)")
st.caption(f"조회 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 3. 종목 설정 (삼성전자, 현대차, 그리고 사용자님의 종목들)
# 종목코드 예: 삼성전자(005930), 현대차(005380), SK하이닉스(000660)
default_stocks = "005930, 005380, 000660" 
watchlist_input = st.sidebar.text_input("종목코드 입력 (6자리, 쉼표 구분)", default_stocks)
watchlist = [t.strip() for t in watchlist_input.split(",")]

if watchlist:
    all_data, final_tickers = fetch_korea_data(watchlist)
    
    if all_data is not None:
        cols = st.columns(len(final_tickers))
        
        for i, ticker in enumerate(final_tickers):
            with cols[i]:
                try:
                    # 데이터 추출
                    ticker_data = all_data[ticker] if len(final_tickers) > 1 else all_data
                    
                    if ticker_data.empty:
                        st.error(f"{ticker} 데이터 없음")
                        continue
                        
                    current_price = ticker_data['Close'].iloc[-1]
                    prev_price = ticker_data['Close'].iloc[-2]
                    delta = current_price - prev_price
                    
                    # 한국 주식은 원화(₩)로 표기
                    st.metric(label=ticker, 
                              value=f"{int(current_price):,}원", 
                              delta=f"{int(delta):,}원")
                    
                    st.line_chart(ticker_data['Close'])
                except Exception as e:
                    st.error(f"{ticker} 표시 오류")

# 4. 비판적 참모의 한마디
st.divider()
st.info("""
**💡 참모의 조언:** 1. 현재 `005930.KS` 처럼 코드가 보일 것입니다. 이는 야후 파이낸스 방식입니다.
2. 내일 **한투 API**를 연결하면 `.KS` 같은 복잡한 접미사 없이 **'삼성전자'**라는 이름과 정밀한 데이터를 바로 띄울 수 있습니다.
3. 지금은 숫자로 된 종목코드 6자리만 입력해 주세요.
""")
