import streamlit as st
import sys
import types
import pandas as pd
from datetime import datetime, timedelta
import pytz

# 1. 라이브러리 충돌 방지
if 'pkg_resources' not in sys.modules:
    sys.modules['pkg_resources'] = types.ModuleType('pkg_resources')
from pykrx import stock

# [아이디 적용 완료] 사용자님의 구글 시트 ID입니다.
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:csv"

st.set_page_config(page_title="주식 손절선 관리", layout="wide")
st.title("📊 실시간 손절선 관리 앱")

KST = pytz.timezone('Asia/Seoul')

# 데이터 로드 함수 (구글 시트 연동)
def load_tickers_from_sheet():
    try:
        df = pd.read_csv(SHEET_URL)
        # 시트의 A열(ticker)과 B열(name)을 읽어옵니다.
        return list(zip(df['ticker'].astype(str).str.zfill(6), df['name']))
    except Exception as e:
        st.error("구글 시트를 읽어오지 못했습니다. 시트 우측 상단 [공유] 버튼을 눌러 '링크가 있는 모든 사용자'가 볼 수 있게 설정했는지 확인해주세요!")
        return []

def get_report(tickers):
    now_k = datetime.now(KST)
    today = now_k.strftime("%Y%m%d")
    start_date = (now_k - timedelta(days=250)).strftime("%Y%m%d")

    results = []
    for ticker, name in tickers:
        try:
            # KRX 서버에서 데이터 가져오기
            df = stock.get_market_ohlcv(start_date, today, ticker)
            if df is not None and not df.empty:
                curr = int(df['종가'].iloc[-1])
                high = int(df['고가'].max())
                s10, s15 = int(high * 0.9), int(high * 0.85)
                status = "🚨위험" if curr <= s15 else "⚠️주의" if curr <= s10 else "✅안정"
                results.append({'종목명': name, '현재가': curr, '기준고점': high, '손절(-10%)': s10, '손절(-15%)': s15, '상태': status})
            else:
                results.append({'종목명': name, '현재가': "조회실패", '기준고점': "-", '손절(-10%)': "-", '손절(-15%)': "-", '상태': "데이터없음"})
        except:
            results.append({'종목명': name, '현재가': "에러", '기준고점': "-", '손절(-10%)': "-", '손절(-15%)': "-", '상태': "오류"})
    return pd.DataFrame(results)

def highlight_status(val):
    if val == "🚨위험": return 'background-color: #ffcccc'
    if val == "⚠️주의": return 'background-color: #fff3cd'
    if val == "✅안정": return 'background-color: #d4edda'
    return ''

# 메인 실행부
if st.button("🔄 리포트 갱신"):
    with st.spinner('구글 시트에서 목록을 읽어 분석 중...'):
        current_tickers = load_tickers_from_sheet()
        if current_tickers:
            df_result = get_report(current_tickers)
            if not df_result.empty:
                st.dataframe(df_result.style.map(highlight_status, subset=['상태']), use_container_width=True)
                now_str = datetime.now(KST).strftime('%Y-%m-%d %H:%M:%S')
                st.success(f"업데이트 완료 (한국시간): {now_str}")
        else:
            st.warning("시트에 등록된 종목이 없습니다.")

st.info("💡 종목 수정은 구글 시트에서 하시면 됩니다. (A열: 티커, B열: 종목명)")
