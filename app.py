import streamlit as st
import pandas as pd
import pytz
from datetime import datetime

# 사용자님의 시트 ID 및 URL
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

st.set_page_config(page_title="주식 손절선 관리 시스템", layout="wide")

KST = pytz.timezone('Asia/Seoul')

def get_data():
    try:
        # 1. 구글 시트 전체 읽기 (지수 데이터 포함)
        raw_df = pd.read_csv(SHEET_URL)
        
        # 2. 지수 정보 추출 (H열이 7번째 인덱스라고 가정)
        # 만약 위치가 다르면 iloc 숫자를 조정해야 합니다.
        try:
            market_index = raw_df.iloc[0, 7] # H2 셀 (지수 가격)
            market_change = raw_df.iloc[1, 7] # H3 셀 (지수 등락률)
        except:
            market_index, market_change = 0, 0
            
        # 3. 종목 리포트용 데이터 정리
        df = raw_df.iloc[:, :6] # A~F열만 선택
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)']
        
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        def calc_status(row):
            if pd.isna(row['현재가']): return "조회중"
            curr, s10, s15 = row['현재가'], row['손절(-10%)'], row['손절(-15%)']
            if curr <= s15: return "🚨위험"
            elif curr <= s10: return "⚠️주의"
            return "✅안정"
        
        df['상태'] = df.apply(calc_status, axis=1)
        return df, market_index, market_change
    except Exception as e:
        st.error(f"데이터 연동 실패: {e}")
        return pd.DataFrame(), 0, 0

st.title("📊 주식 손절선 관리 시스템")

if st.button("🔄 실시간 데이터 동기화"):
    final_df, mkt_idx, mkt_chg = get_data()
    
    # 상단 지수 표시 (실시간 연동)
    if mkt_idx != 0:
        st.metric("KOSPI", f"{mkt_idx:,.2f}", f"{mkt_chg:.2%}")
    
    if not final_df.empty:
        # 현재가 강조 디자인 적용
        st.dataframe(
            final_df[['종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '상태']].style.format({
                '현재가': '{:,.0f}', '기준고점': '{:,.0f}', 
                '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
            }).set_properties(subset=['현재가'], **{
                'background-color': '#e6f3ff', 
                'color': '#0056b3', 
                'font-weight': 'bold',
                'font-size': '16px'
            }).map(lambda x: 'background-color: #ffcccc' if x == "🚨위험" else ('background-color: #fff3cd' if x == "⚠️주의" else 'background-color: #d4edda'), subset=['상태']),
            use_container_width=True,
            height=450
        )
        st.success(f"최신화 완료: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")
