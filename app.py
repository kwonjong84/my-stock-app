import streamlit as st
import pandas as pd
import requests
import os
import time
from datetime import datetime
import pytz

# 1. 환경 설정
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
# 구글 시트에서 수식 결과를 가져오기 위해 CSV 내보내기 링크 사용
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="ISA 감시 시스템 (최종 안정화)", layout="wide")

# 2. 데이터 로드 함수 (오류 방어막 강화)
def get_data():
    try:
        # 캐시를 피하기 위해 URL 뒤에 타임스탬프 추가
        url = f"{SHEET_URL}&t={int(time.time())}"
        df = pd.read_csv(url)
        
        # [비판적 수정] 시트 열 개수가 부족해도 터지지 않게 안전하게 슬라이싱
        # 데이터가 있는 만큼만 가져오고 나머지는 0으로 채움
        expected_cols = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률', '상태']
        
        # 실제 시트 컬럼 수가 부족할 경우를 대비해 컬럼명 강제 재지정
        if df.shape[1] >= len(expected_cols):
            df = df.iloc[:, :len(expected_cols)]
            df.columns = expected_cols
        else:
            st.error("⚠️ 구글 시트의 열 개수가 부족합니다. (A~H열까지 채워주세요)")
            return pd.DataFrame()

        # 숫자형 변환 (수식 에러 #N/A 등을 0으로 치환)
        for col in ['현재가', '기준고점', '등락률', '손절(-10%)', '손절(-15%)']:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # 문자열 정리
        df['상태'] = df['상태'].fillna("데이터 확인중")
        
        return df
    except Exception as e:
        st.error(f"❌ 데이터 읽기 실패: {e}")
        return pd.DataFrame()

# 3. 메인 실행부
st.title("📊 ISA 감시 시스템 (Google 수식 모드)")
st.caption(f"동기화 시간: {datetime.now(KST).strftime('%H:%M:%S')}")

if st.button("🔄 새로고침"):
    st.rerun()

final_df = get_data()

if not final_df.empty:
    # UI 출력부 (기존 스타일 적용)
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    def apply_style(styler):
        # 등락률 색상
        styler.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        # 상태 배경색
        styler.applymap(lambda v: f'background-color: {"#ff4b4b" if "🚨" in str(v) else "#ffa421" if "⚠️" in str(v) else "#28a745"}; color: white; font-weight: bold', subset=['상태'])
        # 현재가 강조
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
        return styler

    st.dataframe(apply_style(display_df.style.format({
        '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
        '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
    })), use_container_width=True, height=600)

    # 4. 알림 로직 (기존 텔레그램 함수 필요 시 추가 가능)
    #
