import streamlit as st
import pandas as pd
from pykrx import stock
from datetime import datetime, timedelta
import pytz
import time

# --- 앱 설정 ---
st.set_page_config(page_title="나의 주식 관리기", layout="wide")
st.title("📊 실시간 손절선 관리 앱")

# --- 종목 리스트 관리 (세션 상태 활용) ---
if 'tickers' not in st.session_state:
    # 초기 종목 리스트 (미래에셋은 나중에 안정화 후 추가하기 위해 일단 제외)
    st.session_state.tickers = [
        ('102110', 'Tiger 200'), ('069500', 'KODEX 200'),
        ('000100', '유한양행'), ('005935', '삼성전자우'), ('086790', 'KB금융'),
        ('229200', 'KODEX 코스닥150'), ('437730', '삼현'), ('005385', '현대차우'),
        ('103590', '일진전기')
    ]

# --- 1. 종목 관리 UI (왼쪽 사이드바) ---
with st.sidebar:
    st.header("🛠️ 종목 관리")
    st.write("새로운 종목을 추가하거나 삭제하세요.")
    
    new_name = st.text_input("종목명 입력", placeholder="예: 삼성전자")
    new_code = st.text_input("종목코드 입력", placeholder="예: 005930")
    
    if st.button("➕ 종목 추가"):
        if new_name and new_code:
            st.session_state.tickers.append((new_code, new_name))
            st.success(f"[{new_name}] 리스트에 추가되었습니다!")
            time.sleep(1)
            st.rerun()
        else:
            st.error("종목명과 코드를 모두 입력해주세요.")

    st.write("---")
    st.subheader("📋 현재 감시 중인 종목")
    
    # 리스트에서 종목 삭제 기능
    for i, (code, name) in enumerate(st.session_state.tickers):
        cols = st.columns([3, 1])
        cols[0].write(f"{name} ({code})")
        if cols[1].button("🗑️", key=f"del_{i}"):
            st.session_state.tickers.pop(i)
            st.rerun()

# --- 2. 분석 실행 및 리포트 출력 ---
if st.button("🔄 리포트 갱신 (실시간 고점 반영)"):
    seoul_tz = pytz.timezone('Asia/Seoul')
    now_k = datetime.now(seoul_tz)
    today = now_k.strftime("%Y%m%d")
    # 영업일 100일을 확보하기 위해 넉넉히 150일 전부터 가져옵니다.
    start_date = (now_k - timedelta(days=150)).strftime("%Y%m%d")

    results = []
    progress_bar = st.progress(0)
    
    with st.spinner('데이터를 분석 중입니다...'):
        for idx, (ticker, name) in enumerate(st.session_state.tickers):
            try:
                # 데이터 수집
                df = stock.get_market_ohlcv(start_date, today, ticker)
                
                if not df.empty:
                    # 최근 100거래일 기준
                    df = df.tail(100)
                    curr = int(df['종가'].iloc[-1])
                    m_high = int(df['고가'].max())
                    
                    # [핵심 로직] 현재 시점 가격이 고점보다 높으면 즉시 갱신
                    high = max(m_high, curr)
                    
                    # 손절가 계산
                    s10, s15 = int(high * 0.9), int(high * 0.85)
                    status = "🚨위험" if curr <= s15 else ("⚠️주의" if curr <= s10 else "✅안정")
                    
                    results.append({
                        '종목명': name, 
                        '현재가': curr, 
                        '기준고점': high, 
                        '손절(-10%)': s10, 
                        '손절(-15%)': s15, 
                        '상태': status
                    })
                time.sleep(0.05) # 서버 부하 방지
            except:
                continue
            progress_bar.progress((idx + 1) / len(st.session_state.tickers))

    # --- 3. 표 출력 ---
    if results:
        final_df = pd.DataFrame(results)
        
        # 상태에 따른 색상 강조 스타일 정의
        def highlight_status(val):
            if '위험' in val: color = '#FF4B4B'  # 빨강
            elif '주의' in val: color = '#FFA500' # 주황
            else: color = '#28A745'              # 초록
            return f'color: {color}; font-weight: bold'

        # 깔끔한 표 렌더링
        st.dataframe(
            final_df.style.applymap(highlight_status, subset=['상태'])
            .format({'현재가': '{:,}원', '기준고점': '{:,}원', '손절(-10%)': '{:,}원', '손절(-15%)': '{:,}원'}),
            use_container_width=True
        )
        st.info(f"✅ 분석 완료 (기준 시각: {now_k.strftime('%Y-%m-%d %H:%M:%S')})")
    else:
        st.warning("분석할 종목이 없습니다. 왼쪽 메뉴에서 종목을 추가해주세요.")

else:
    st.info("위의 [리포트 갱신] 버튼을 눌러 실시간 분석을 시작하세요.")
