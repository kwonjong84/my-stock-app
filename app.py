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
        
        # 1. 지수 데이터 추출 (H2, H3 위치)
        try:
            mkt_idx = raw_df.iloc[0, 7]  # H2
            mkt_chg = raw_df.iloc[1, 7]  # H3
        except:
            mkt_idx, mkt_chg = 0, 0
            
        # 2. 종목 데이터 정리 (A~G열)
        df = raw_df.iloc[:, :7] 
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        
        # 숫자 변환
        for col in ['현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
        
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
    
    # 상단 지수 영역
    if mkt_idx != 0:
        st.metric("KOSPI 지수", f"{mkt_idx:,.2f}", f"{mkt_chg:.2%}")
    
    if not final_df.empty:
        st.subheader("종목별 실시간 리포트")
        
        # 등락률 색상 지정 함수
        def color_variation(val):
            color = 'red' if val > 0 else 'blue' if val < 0 else 'black'
            return f'color: {color}; font-weight: bold'

        # 화면 출력용 데이터프레임
        display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
        
        st.dataframe(
            display_df.style.format({
                '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
                '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
            }).set_properties(subset=['현재가'], **{
                'background-color': '#e6f3ff', 'color': '#0056b3', 'font-weight': 'bold'
            }).applymap(color_variation, subset=['등락률'])
              .map(lambda x: 
                'background-color: #ffcccc; color: #cc0000; font-weight: bold' if x == "🚨위험" 
                else ('background-color: #fff3cd; color: #856404;' if x == "⚠️주의" 
                else 'background-color: #d4edda; color: #155724;'), subset=['상태']),
            use_container_width=True,
            height=550
        )
        st.caption(f"최종 업데이트: {datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')}")
