import streamlit as st
import pandas as pd
import pytz
from datetime import datetime

# 사용자 시트 정보
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

st.set_page_config(page_title="주식 손절선 관리 PLUS", layout="wide")
KST = pytz.timezone('Asia/Seoul')

def get_data():
    try:
        raw_df = pd.read_csv(SHEET_URL)
        
        # 1. 지수 데이터 추출 (H열)
        try:
            mkt_idx = raw_df.iloc[0, 7]
            mkt_chg = raw_df.iloc[1, 7]
        except:
            mkt_idx, mkt_chg = 0, 0
            
        # 2. 종목 데이터 정리
        df = raw_df.iloc[:, :6] # A~F열
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)']
        
        # 숫자 변환
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 3. 변동폭 계산 (현재가 - 손절-10%는 고점대비이므로, 전일종가는 시트에서 가져와야 정확함)
        # 구글 파이낸스 특성상 시트에서 전일종가를 가져오도록 보강하는 것이 좋으나, 
        # 우선 현재가와 기준고점 대비 위치를 시각화하는 데 집중하겠습니다.
        
        def calc_status(row):
            if pd.isna(row['현재가']): return "조회중"
            curr, s10, s15 = row['현재가'], row['손절(-10%)'], row['손절(-15%)']
            if curr <= s15: return "🚨위험"
            elif curr <= s10: return "⚠️주의"
            return "✅안정"
        
        df['상태'] = df.apply(calc_status, axis=1)
        return df, mkt_idx, mkt_chg
    except Exception as e:
        st.error(f"연동 실패: {e}")
        return pd.DataFrame(), 0, 0

st.title("📊 실시간 주식 모니터링")

if st.button("🔄 데이터 업데이트"):
    final_df, mkt_idx, mkt_chg = get_data()
    
    # 상단 지수 영역 (메트릭)
    if mkt_idx != 0:
        st.metric("KOSPI 지수", f"{mkt_idx:,.2f}", f"{mkt_chg:.2%}")
    
    if not final_df.empty:
        # 가독성을 위한 스타일링
        st.subheader("종목별 상태 리포트")
        st.dataframe(
            final_df[['종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '상태']].style.format({
                '현재가': '{:,.0f}', '기준고점': '{:,.0f}', 
                '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
            }).set_properties(subset=['현재가'], **{
                'background-color': '#e6f3ff', # 현재가 배경 강조
                'color': '#0056b3', 
                'font-weight': 'bold',
                'font-size': '18px'
            }).map(lambda x: 
                'background-color: #ffcccc; color: #cc0000; font-weight: bold' if x == "🚨위험" 
                else ('background-color: #fff3cd; color: #856404;' if x == "⚠️주의" 
                else 'background-color: #d4edda; color: #155724;'), subset=['상태']),
            use_container_width=True,
            height=500
        )
        st.caption(f"최종 업데이트: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")
