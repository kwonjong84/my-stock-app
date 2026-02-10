import streamlit as st
import sys
import types

# 1. 환경 설정 및 충돌 방지 (가장 안전한 방식)
if 'pkg_resources' not in sys.modules:
    sys.modules['pkg_resources'] = types.ModuleType('pkg_resources')

import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import pytz

# 페이지 설정
st.set_page_config(page_title="주식 손절선 관리", layout="wide")
st.title("📊 실시간 손절선 관리 앱")

KST = pytz.timezone('Asia/Seoul')

# 2. 종목 리스트 (미래에셋증권 포함)
if 'tickers' not in st.session_state:
    st.session_state.tickers = [
        ('102110', 'Tiger 200'), ('069500', 'KODEX 200'),
        ('000100', '유한양행'), ('005935', '삼성전자우'), 
        ('086790', 'KB금융'), ('229200', 'KODEX 코스닥150'), 
        ('437730', '삼현'), ('005385', '현대차우'), 
        ('103590', '일진전기'), ('037620', '미래에셋증권')
    ]

# 사이드바 관리
with st.sidebar:
    st.header("📍 종목 관리")
    new_ticker = st.text_input("종목코드", placeholder="예: 005930")
    new_name = st.text_input("종목명", placeholder="예: 삼성전자")
    if st.button("➕ 추가"):
        if new_ticker and new_name:
            st.session_state.tickers.append((new_ticker.strip(), new_name.strip()))
            st.rerun()
    st.write("---")
    for i, (t, n) in enumerate(st.session_state.tickers):
        col1, col2 = st.columns([3, 1])
        col1.write(f"{n} ({t})")
        if col2.button("🗑️", key=f"del_{i}"):
            st.session_state.tickers.pop(i)
            st.rerun()

# 3. 리포트 생성 함수 (에러 완벽 방어)
def get_report():
    now_k = datetime.now(KST)
    today = now_k.strftime("%Y%m%d")
    start_date = (now_k - timedelta(days=200)).strftime("%Y%m%d")

    results = []
    for ticker, name in st.session_state.tickers:
        clean_ticker = str(ticker).strip().zfill(6)
        try:
            # 데이터를 가져오고 바로 검증
            df = stock.get_market_ohlcv(start_date, today, clean_ticker)
            
            # df가 None이 아니고 비어있지 않은 경우만 처리
            if df is not None and not df.empty:
                curr = int(df['종가'].iloc[-1])
                high = int(df['고가'].max())
                s10, s15 = int(high * 0.9), int(high * 0.85)
                status = "🚨위험" if curr <= s15 else "⚠️주의" if curr <= s10 else "✅안정"
                
                results.append({
                    '종목명': name, '현재가': curr, '기준고점': high, 
                    '손절(-10%)': s10, '손절(-15%)': s15, '상태': status
                })
            else:
                results.append({'종목명': name, '현재가': "데이터없음", '기준고점': "-", '손절(-10%)': "-", '손절(-15%)': "-", '상태': "확인요망"})
        except Exception as e:
            # 어떤 에러가 나더라도 앱이 멈추지 않게 방어
            results.append({'종목명': name, '현재가': "조회실패", '기준고점': "-", '손절(-10%)': "-", '손절(-15%)': "-", '상태': "에러"})
            continue
            
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
            now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"업데이트 완료 (한국시간): {now_str}")
