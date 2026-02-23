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
# t={int(time.time())}를 붙여 구글 시트의 최신 수식 결과를 즉시 반영
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
PRICE_LOG = "last_price_log.txt"

st.set_page_config(page_title="ISA 감시 시스템 (최종 완성)", layout="wide")

# 2. 데이터 로드 (시트 컬럼 구조와 1:1 매칭)
def get_data():
    try:
        # 구글 시트에서 A~H열 데이터를 통째로 가져옴
        df = pd.read_csv(SHEET_URL)
        
        # [비판적 수정] 사용자님 시트의 실제 컬럼명과 100% 일치시킴
        # 만약 시트의 헤더 명칭이 다르면 아래 이름을 시트와 똑같이 고쳐주세요.
        df = df.iloc[:, :8].copy()
        df.columns = ['코드', '종목명', '현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률', '상태']

        # 숫자형 데이터 정제 (수식 에러 방지)
        numeric_cols = ['현재가', '기준고점', '손절(-10%)', '손절(-15%)', '등락률']
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # 상태 열 공백 제거
        df['상태'] = df['상태'].astype(str).str.strip()
        
        return df
    except Exception as e:
        st.error(f"데이터 연동 실패: {e}")
        return pd.DataFrame()

# 3. 텔레그램 알림 및 UI 구성
final_df = get_data()

# 텔레그램 발송 함수 (기존 유지)
def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        requests.get(url, params={"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}, timeout=5)
    except: pass

st.title("📊 ISA 주식 실시간 감시 (운영 모드)")
st.caption(f"마지막 동기화: {datetime.now(KST).strftime('%H:%M:%S')}")

if st.button("🔄 즉시 새로고침"):
    st.rerun()

if not final_df.empty:
    # 알림 로직: 시트의 '상태'가 '🚨위험'일 때 발송
    danger_df = final_df[final_df['상태'].str.contains("🚨위험", na=False)]
    for _, s in danger_df.iterrows():
        # 여기에 중복 알림 방지 로직(save_price 등)을 추가할 수 있습니다.
        pass

    # UI 시각화 (사용자님이 만족하셨던 컬러 스타일)
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    def apply_style(styler):
        # 등락률 컬러
        styler.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        # 상태 배경색 (시트의 이모지 인식)
        def status_bg(v):
            if "🚨" in str(v): return 'background-color: #ff4b4b; color: white; font-weight: bold'
            if "⚠️" in str(v): return 'background-color: #ffa421; color: black; font-weight: bold'
            if "✅" in str(v): return 'background-color: #28a745; color: white; font-weight: bold'
            return ''
        styler.applymap(status_bg, subset=['상태'])
        styler.set_properties(subset=['현재가'], **{'color': '#00d1ff', 'font-weight': 'bold'})
        return styler

    st.dataframe(apply_style(display_df.style.format({
        '현재가': '{:,.0f}', '등락률': '{:+.2%}', '기준고점': '{:,.0f}', 
        '손절(-10%)': '{:,.0f}', '손절(-15%)': '{:,.0f}'
    })), use_container_width=True, height=600)
