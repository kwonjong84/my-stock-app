import streamlit as st
import pandas as pd
import pytz
from datetime import datetime

SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"

st.set_page_config(page_title="주식 손절선 관리 PLUS", layout="wide")

# 스타일 설정 (현재가 강조용)
st.markdown("""
    <style>
    .current-price {
        font-size: 20px !important;
        font-weight: bold !important;
        color: #1E90FF !important;
    }
    </style>
    """, unsafe_allow_html=True)

KST = pytz.timezone('Asia/Seoul')

def get_final_report():
    try:
        df = pd.read_csv(SHEET_URL)
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
        return df
    except Exception as e:
        st.error(f"데이터 연동 실패: {e}")
        return pd.DataFrame()

# 상단 지수 영역 (임시 데이터 - 나중에 시트에 지수 추가하면 연동 가능)
st.title("📊 주식 손절선 관리 시스템")
col_idx1, col_idx2 = st.columns(2)
with col_idx1:
    st.metric("KOSPI (예시)", "2,620.45", "-0.15%")

if st.button("🔄 실시간 데이터 동기화"):
    final_df = get_final_report()
    if not final_df.empty:
        # 데이터프레임 시각화 개선
        st.dataframe(
            final_df[['종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '상태']].style.format({
                '현재가': '{:,.0f}', '기준고점': '{:,.0f}', 
                '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
            }).set_properties(subset=['현재가'], **{'background-color': '#f0f8ff', 'color': '#007bff', 'font-weight': 'bold'})
              .map(lambda x: 'background-color: #ffcccc' if x == "🚨위험" else ('background-color: #fff3cd' if x == "⚠️주의" else 'background-color: #d4edda'), subset=['상태']),
            use_container_width=True,
            height=400
        )
        st.success(f"최신화 완료: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")

st.info("💡 현재가는 파란색 배경으로 강조되어 있습니다. 종목 관리는 구글 시트에서 계속해 주세요!")
