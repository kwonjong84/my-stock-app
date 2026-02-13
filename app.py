import streamlit as st
import pandas as pd
import pytz
import time
from datetime import datetime

# 1. 환경 설정 및 상수
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
# 캐시 방지를 위해 URL 뒤에 실시간 타임스탬프 추가
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="주식 손절선 관리 PLUS", layout="wide")

# 2. 데이터 로드 함수
def get_data():
    try:
        # 파일 읽기 시 캐시를 타지 않도록 설정
        raw_df = pd.read_csv(SHEET_URL)
        
        # 지수 데이터 추출 (기존 시트 구조 H열 기준)
        try:
            mkt_idx = raw_df.iloc[0, 7]  # H2: KOSPI 지수
            mkt_chg = raw_df.iloc[1, 7]  # H3: 변동률
        except:
            mkt_idx, mkt_chg = 0, 0
            
        # 종목 데이터 정리 (A~G열)
        df = raw_df.iloc[:, :7].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        # 숫자 변환 및 전처리
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # [참모의 한수] 현재가가 고점보다 높으면 고점을 현재가로 임시 보정 (시트 미반영 시 대비)
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

# 3. UI 레이아웃
st.title("📊 실시간 주식 모니터링 시스템")
st.caption(f"최종 동기화 시각 (KST): {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

# 데이터 업데이트 버튼
if st.button("🔄 최신 데이터 불러오기"):
    st.rerun()

final_df, mkt_idx, mkt_chg = get_data()

# 상단 지수 영역
if mkt_idx != 0:
    col1, col2 = st.columns([1, 4])
    with col1:
        st.metric("KOSPI 지수", f"{mkt_idx:,.2f}", f"{mkt_chg:.2%}")
    with col2:
        st.info("💡 구글 파이낸스 지수는 실시간 대비 약 20분 지연될 수 있습니다.")

# 메인 리포트 영역
if not final_df.empty:
    st.subheader("종목별 실시간 리포트")
    
    # 등락률 색상 지정
    def color_variation(val):
        color = '#d73027' if val > 0 else '#4575b4' if val < 0 else '#31333F'
        return f'color: {color}; font-weight: bold'

    # 출력용 데이터프레임 가공
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    st.dataframe(
        display_df.style.format({
            '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
            '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
        }).set_properties(subset=['현재가'], **{
            'background-color': '#f0f2f6', 'color': '#0e1117', 'font-weight': 'bold'
        }).applymap(color_variation, subset=['등락률'])
          .map(lambda x: 
            'background-color: #ff4b4b; color: white; font-weight: bold' if x == "🚨위험" 
            else ('background-color: #ffa421; color: black;' if x == "⚠️주의" 
            else 'background-color: #28a745; color: white;'), subset=['상태']),
        use_container_width=True,
        height=600
    )
else:
    st.warning("데이터를 불러오는 중입니다. 잠시만 기다려주세요.")

st.markdown("---")
st.caption("본 앱은 구글 시트의 데이터를 기반으로 작동하며, 모든 투자 판단의 책임은 본인에게 있습니다.")
