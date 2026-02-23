import streamlit as st
import pandas as pd
import requests
import os
import time
from datetime import datetime
import pytz

# 1. 환경 설정 (기존 유지)
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')

st.set_page_config(page_title="ISA 감시 시스템 (로직 내장형)", layout="wide")

# 2. 데이터 로드 및 '상태' 실시간 계산 (핵심 수정)
def get_data():
    try:
        df = pd.read_csv(SHEET_URL)
        
        # [비판적 조치] 필요한 열만 정확히 추출 (시트의 열 순서에 의존하지 않음)
        # 시트의 헤더 이름이 아래와 일치해야 합니다.
        target_cols = ['코드', '종목명', '현재가', '기준고점', '등락률']
        df = df[target_cols].copy()

        # 숫자형 변환 (에러 방지)
        for col in ['현재가', '기준고점', '등락률']:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(',', ''), errors='coerce').fillna(0)
        
        # [핵심] 파이썬에서 직접 손절선 및 상태 계산
        df['손절(-10%)'] = df['기준고점'] * 0.90
        df['손절(-15%)'] = df['기준고점'] * 0.85
        
        def calculate_status(row):
            if row['현재가'] <= 0: return "⏳ 대기" # 데이터가 0인 경우
            if row['현재가'] <= row['손절(-15%)']: return "🚨위험"
            if row['현재가'] <= row['손절(-10%)']: return "⚠️주의"
            return "✅안정"
        
        df['상태'] = df.apply(calculate_status, axis=1)
        
        return df
    except Exception as e:
        st.error(f"데이터 처리 오류: {e}")
        return pd.DataFrame()

# 3. UI 및 시각화 (기존 스타일 유지)
st.title("📊 ISA 감시 시스템 (실시간 판별 모드)")
st.caption(f"업데이트 시간: {datetime.now(KST).strftime('%H:%M:%S')}")

if st.button("🔄 즉시 동기화"):
    st.rerun()

final_df = get_data()

if not final_df.empty:
    # 화면 표시용 순서 재정렬
    display_df = final_df[['종목명', '현재가', '등락률', '기준고점', '손절(-10%)', '손절(-15%)', '상태']]
    
    def apply_style(styler):
        # 등락률 컬러링
        styler.applymap(lambda v: f'color: {"#ff4b4b" if v > 0 else "#1c83e1" if v < 0 else "white"}; font-weight: bold', subset=['등락률'])
        # 상태 배경색 컬러링 (이모지 기준 판별)
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
