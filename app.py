import streamlit as st
import pandas as pd
import pytz
import time
import yfinance as yf
import requests
import os
from datetime import datetime

# 1. 환경 설정 및 텔레그램 정보
TELEGRAM_TOKEN = "7922092759:AAHG-8NYQSMu5b0tO4lzLWst3gFuC4zn0UM"
TELEGRAM_CHAT_ID = "63395333"
SHEET_ID = "1_W1Vdhc3V5xbTLlCO6A7UfmGY8JAAiFZ-XVhaQWjGYI"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid=0&t={int(time.time())}"
KST = pytz.timezone('Asia/Seoul')
LOG_FILE = "alert_log.txt"

st.set_page_config(page_title="주식 손절 감시 시스템 Pro", layout="wide")

# 2. 유틸리티 함수 (알림 발송 및 기록 저장/로드)
def send_telegram_msg(message):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        params = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
        requests.get(url, params=params)
    except:
        pass

def get_last_notified_price(stock_name):
    """파일에서 종목별 마지막 알림 가격 로드"""
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    name, price = line.strip().split(",")
                    if name == stock_name:
                        return float(price)
        except:
            pass
    return float('inf')

def save_notified_price(stock_name, price):
    """파일에 종목별 마지막 알
