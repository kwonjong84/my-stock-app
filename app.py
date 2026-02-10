import streamlit as st
import sys
import types

# 1. 라이브러리 충돌 방지용 가짜 모듈 (유지)
if 'pkg_resources' not in sys.modules:
    sys.modules['pkg_resources'] = types.ModuleType('pkg_resources')

import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import pytz

# 페이지 설정
st.set_page_config(page_title="주식 손절선 관리", layout="wide")
st.title("📊 실시간 손절선 관리 앱")

# 2. 한국 시간 설정
KST = pytz.timezone('Asia/Seoul')

# 종목 리스트 초기화 (문자열로 정확히 저장)
if 'tickers' not in st.session_state:
    st.session_state.tickers = [
        ('102110', 'Tiger 200'), ('069500', 'KODEX 200'),
        ('000100', '유한양행'), ('005935', '삼성전자우'), 
        ('086790', 'KB금융'), ('229200', 'KODEX 코스닥150'), 
        ('437730', '삼현'), ('005385', '현대차우'), 
        ('103590', '일진전기'), ('037620', '미래에셋증권')
    ]

# 사이드바 (종목 관리)
with st.sidebar:
    st.header("📍 종목 관리")
    new_ticker = st.text_input("종목코드 (6자리)", placeholder="예: 005930")
    new_name = st.text_input("종목명", placeholder="예: 삼성전자")
    
    if st.button("➕ 종목 추가"):
        if new_ticker and new_name:
            st.session_state.tickers.append((new_ticker.strip(), new_name.strip()))
            st.rerun()

    st.write("---")
    st.subheader("현재 감시 목록")
    for i, (t, n) in enumerate(st.session_state.tickers):
        col1, col2 = st.columns([3, 1])
        col1.write(f"{n} ({t})")
        if col2.button("🗑️", key=f"del_{i}"):
            st.session_state.tickers.pop(i)
            st.rerun()

# 3. 리포트 생성 함수 (강력 보강)
def get_report():
    now_k = datetime.now(KST)
    today = now_k.strftime("%Y%m%d")
    # 고점 탐색 기간을 넉넉히 200일로 설정
    start_date = (now_k - timedelta(days=200)).strftime("%Y%m%d")

    results = []
    for ticker, name in st.session_state.tickers:
        # 핵심: 입력된 코드가 무엇이든 강제로 '0'을 채운 6자리 문자열로 변환
        clean_ticker = str(ticker).strip().zfill(6)
        try:
            df = stock.get_market_ohlcv(start_date, today, clean_ticker)
            if not df.empty:
                curr = int(df['종가'].iloc[-1])
                high = int(df['고가'].max())
                s10, s15 = int(high * 0.9), int(high * 0.85)
                
                status = "🚨위험" if curr <= s15 else "⚠️주의" if curr <= s10 else "✅안정"
                results.append({'종목명': name, '현재가': curr, '기준고점': high, '손절(-10%)': s10, '손절(-15%)': s15, '상태': status})
            else:
                results.append({'종목명': name, '현재가': "조회 실패", '기준고점': "-", '손절(-10%)': "-", '손절(-15%)': "-", '상태': "코드확인요망"})
        except:
            results.append({'종목명': name, '현재가': "에러", '기준고점': "-", '손절(-10%)': "-", '손절(-15%)': "-", '상태': "에러"})
    return pd.DataFrame(results)

# 색상 지정
def highlight_status(val):
    if val == "🚨위험": return 'background-color: #ffcccc'
    if val == "⚠️주의": return 'background-color: #fff3cd'
    if val == "✅안정": return 'background-color: #d4edda'
    return ''

# 메인 버튼
if st.button("🔄 리포트 갱신"):
    with st.spinner('데이터를 분석 중입니다...'):
        df_result = get_report()
        if not df_result.empty:
            st.dataframe(df_result.style.map(highlight_status, subset=['상태']), use_container_width=True)
            # 하단 시간 표시를 한국 시간으로 강제 적용
            now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"업데이트 완료 (한국시간): {now_str}")
