import streamlit as st
import pandas as pd
import pytz
from datetime import datetime

# 사용자님의 시트 ID (이미 확인하신 그 ID입니다)
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

st.set_page_config(page_title="주식 손절선 관리", layout="wide")
st.title("📊 실시간 손절선 관리 앱")

KST = pytz.timezone('Asia/Seoul')

def get_final_report():
    try:
        # 구글 시트 읽기
        df = pd.read_csv(SHEET_URL)
        
        # 열 이름 매칭 (A: ticker, B: name, C: 현재가, D: 기준고점, E: 손절10, F: 손절15)
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)']
        
        # 숫자 변환 및 에러 처리
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        def calc_status(row):
            if pd.isna(row['현재가']): return "조회중"
            curr, s10, s15 = row['현재가'], row['손절(-10%)'], row['손절(-15%)']
            if curr <= s15: return "🚨위험"
            elif curr <= s10: return "⚠️주의"
            return "✅안정"
            
        df['상태'] = df.apply(calc_status, axis=1)
        return df
    except Exception as e:
        st.error(f"데이터 연동 실패: {e}")
        return pd.DataFrame()

def highlight_status(val):
    if val == "🚨위험": return 'background-color: #ffcccc'
    if val == "⚠️주의": return 'background-color: #fff3cd'
    if val == "✅안정": return 'background-color: #d4edda'
    return ''

if st.button("🔄 실시간 데이터 동기화"):
    with st.spinner('구글 시트에서 데이터를 가져오는 중...'):
        final_df = get_final_report()
        if not final_df.empty:
            show_cols = ['종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '상태']
            st.dataframe(final_df[show_cols].style.format({
                '현재가': '{:,.0f}', '기준고점': '{:,.0f}', 
                '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
            }).map(highlight_status, subset=['상태']), use_container_width=True)
            st.success(f"최신화 완료: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

st.info("💡 구글 시트에서 037620을 006800으로 수정하면 미래에셋증권도 바로 뜹니다!")
