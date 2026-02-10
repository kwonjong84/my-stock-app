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
        df = pd.read_csv(SHEET_URL)
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)']
        
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
        # --- 판정 로직 수정 시작 ---
        def calc_status(row):
            if pd.isna(row['현재가']) or pd.isna(row['기준고점']):
                return "조회중"
            
            curr = float(row['현재가'])
            s10 = float(row['손절(-10%)'])
            s15 = float(row['손절(-15%)'])
            
            # 더 민감한 판정: 
            # 1. 현재가가 손절(-15%) 가격보다 낮거나 같으면 무조건 위험
            if curr <= s15:
                return "🚨위험"
            # 2. 현재가가 손절(-10%) 가격보다 낮거나 같으면 주의
            elif curr <= s10:
                return "⚠️주의"
            # 3. 그 외엔 안정
            else:
                return "✅안정"
        # --- 판정 로직 수정 끝 ---
            
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

st.info("💡 종목 관리는 구글 시트에서 하시고, 버튼을 누르면 즉시 동기화됩니다.")
