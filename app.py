import streamlit as st
import sys
import types

# 1. 최신 파이썬 버전에서의 라이브러리 충돌 방지 (가장 중요)
if 'pkg_resources' not in sys.modules:
    sys.modules['pkg_resources'] = types.ModuleType('pkg_resources')

import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import pytz

# 페이지 설정
st.set_page_config(page_title="주식 손절선 관리", layout="wide")
st.title("📊 실시간 손절선 관리 앱")

# 2. 종목 리스트 고정 (앞에 '0'이 안 빠지게 문자열로 관리)
if 'tickers' not in st.session_state:
    st.session_state.tickers = [
        ('102110', 'Tiger 200'), ('069500', 'KODEX 200'),
        ('000100', '유한양행'), ('005935', '삼성전자우'), 
        ('086790', 'KB금융'), ('229200', 'KODEX 코스닥150'), 
        ('437730', '삼현'), ('005385', '현대차우'), 
        ('103590', '일진전기'), ('037620', '미래에셋증권')
    ]

# 사이드바 관리창
with st.sidebar:
    st.header("📍 종목 관리")
    new_ticker = st.text_input("종목코드 (6자리)", placeholder="예: 005930")
    new_name = st.text_input("종목명", placeholder="예: 삼성전자")
    
    if st.button("➕ 종목 추가"):
        if new_ticker and new_name:
            st.session_state.tickers.append((new_ticker, new_name))
            st.rerun()

    st.write("---")
    st.subheader("현재 감시 목록")
    for i, (t, n) in enumerate(st.session_state.tickers):
        col1, col2 = st.columns([3, 1])
        col1.write(f"{n} ({t})")
        if col2.button("🗑️", key=f"del_{i}"):
            st.session_state.tickers.pop(i)
            st.rerun()

# 3. 리포트 생성 함수 (데이터 누락 방지 로직 추가)
def get_report():
    seoul_tz = pytz.timezone('Asia/Seoul')
    now_k = datetime.now(seoul_tz)
    today = now_k.strftime("%Y%m%d")
    # 기준 고점을 찾기 위해 기간을 150일로 늘렸습니다.
    start_date = (now_k - timedelta(days=150)).strftime("%Y%m%d")

    results = []
    for ticker, name in st.session_state.tickers:
        # 종목코드 앞의 0을 보존하는 핵심 코드
        t_code = str(ticker).zfill(6)
        try:
            df = stock.get_market_ohlcv(start_date, today, t_code)
            if not df.empty:
                curr = int(df['종가'].iloc[-1])
                high = int(df['고가'].max())
                s10 = int(high * 0.9)
                s15 = int(high * 0.85)
                
                if curr <= s15: status = "🚨위험"
                elif curr <= s10: status = "⚠️주의"
                else: status = "✅안정"

                results.append({
                    '종목명': name, '현재가': curr, '기준고점': high,
                    '손절(-10%)': s10, '손절(-15%)': s15, '상태': status
                })
            else:
                # 데이터가 안 불러와져도 표에 '데이터 없음'으로 표시
                results.append({
                    '종목명': name, '현재가': "불러오기 실패", '기준고점': "-",
                    '손절(-10%)': "-", '손절(-15%)': "-", '상태': "확인불가"
                })
        except:
            continue
    return pd.DataFrame(results)

# 상태별 색상
def highlight_status(val):
    if val == "🚨위험": return 'background-color: #ffcccc'
    if val == "⚠️주의": return 'background-color: #fff3cd'
    if val == "✅안정": return 'background-color: #d4edda'
    return ''

# 메인 화면 버튼
if st.button("🔄 리포트 갱신"):
    with st.spinner('데이터를 불러오는 중...'):
        df_result = get_report()
        if not df_result.empty:
            # .style.map으로 색상 적용
            st.dataframe(df_result.style.map(highlight_status, subset=['상태']), use_container_width=True)
            st.success(f"업데이트 완료: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
