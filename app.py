import streamlit as st
import pandas as pd
import pytz
from datetime import datetime

# 사용자님의 시트 ID
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

st.set_page_config(page_title="주식 손절선 관리", layout="wide")
st.title("📊 실시간 손절선 관리 앱")

KST = pytz.timezone('Asia/Seoul')

def get_final_report():
    try:
        # 1. 구글 시트 읽기 (헤더가 없어도 위치로 파악하도록 함)
        df = pd.read_csv(SHEET_URL)
        
        # 2. 열 이름 강제 재지정 (A:코드, B:명칭, C:현재가, D:고점, E:-10%, F:-15%)
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)']
        
        # 3. 숫자로 확실히 변환 (문자열 섞임 방지)
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # 4. 상태 판정 로직 (가장 중요 ⭐)
        def calc_status(row):
            if pd.isna(row['현재가']) or pd.isna(row['손절(-10%)']):
                return "조회중"
            
            curr = float(row['현재가'])
            s10 = float(row['손절(-10%)'])
            s15 = float(row['손절(-15%)'])
            
            # 판정 기준: -15% 이하면 위험, -10% 이하면 주의, 그 이상은 안정
            if curr <= s15:
                return "🚨위험"
            elif curr <= s10:
                return "⚠️주의"
            else:
                return "✅안정"
            
        df['상태'] = df.apply(calc_status, axis=1)
        return df
    except Exception as e:
        st.error(f"데이터 연동 실패: {e}")
        return pd.DataFrame()

def highlight_status(val):
    if val == "🚨위험": return 'background-color: #ffcccc; color: black;'
    if val == "⚠️주의": return 'background-color: #fff3cd; color: black;'
    if val == "✅안정": return 'background-color: #d4edda; color: black;'
    return ''

if st.button("🔄 실시간 데이터 동기화"):
    with st.spinner('구글 시트 분석 중...'):
        final_df = get_final_report()
        if not final_df.empty:
            show_cols = ['종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '상태']
            st.dataframe(final_df[show_cols].style.format({
                '현재가': '{:,.0f}', '기준고점': '{:,.0f}', 
                '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
            }).map(highlight_status, subset=['상태']), use_container_width=True)
            
            now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
            st.success(f"최신화 완료: {now_str}")

st.info("💡 이제 삼현이나 현대차우처럼 고점 대비 많이 떨어진 종목은 자동으로 위험/주의가 뜹니다.")
