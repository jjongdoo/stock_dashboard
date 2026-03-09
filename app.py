import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# ... (여기에 위에서 드린 전체 코드를 그대로 붙여넣으세요) ...

import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="나의 주식 분석 대시보드", layout="wide")
st.title("📈 주식 재무 데이터 분석기")

# 사이드바에서 티커 입력 (삼성전자 005930.KS 를 기본값으로 설정)
ticker_symbol = st.sidebar.text_input("종목 티커를 입력하세요", "005930.KS")

if ticker_symbol:
    # 티커 정보 가져오기
    ticker = yf.Ticker(ticker_symbol)
    
    # 데이터 가져오기 (연간 재무제표)
    financials = ticker.financials
    cashflow = ticker.cashflow
    stats = ticker.info

    # 필요한 행 추출 및 최근 3년 데이터 필터링 (최근 데이터가 앞에 오므로 슬라이싱)
    df_fin = financials.iloc[:, :3].T
    df_cf = cashflow.iloc[:, :3].T

    # 주요 지표 정리 (데이터가 없을 경우 0으로 처리)
    plot_data = pd.DataFrame({
        '매출액': df_fin.get('Total Revenue', 0),
        '영업이익': df_fin.get('Operating Income', 0),
        '순이익': df_fin.get('Net Income', 0),
        '영업현금흐름': df_cf.get('Operating Cash Flow', 0),
        '투자현금흐름': df_cf.get('Investing Cash Flow', 0),
        '재무현금흐름': df_cf.get('Financing Cash Flow', 0),
        'Free Cash Flow': df_cf.get('Free Cash Flow', 0)
    })

    # 기업 이름 가져오기
    company_name = stats.get('longName', ticker_symbol)
    st.markdown(f"## **{company_name} ({ticker_symbol})**")

    # PER, PBR, ROE (현재 시점 기준)
    st.subheader("주요 투자 지표")
    col1, col2, col3 = st.columns(3)
    col1.metric("PER", f"{stats.get('trailingPE', 'N/A')}")
    col2.metric("PBR", f"{stats.get('priceToBook', 'N/A')}")
    
    # ROE 계산 (데이터가 있는지 확인 후 출력)
    roe = stats.get('returnOnEquity', None)
    if roe is not None:
        col3.metric("ROE", f"{roe * 100:.2f}%")
    else:
        col3.metric("ROE", "N/A")

    # --- 시각화 ---
    st.divider()
    
    # 1. 수익성 지표 (매출, 이익)
    st.subheader("매출 및 이익 추이 (최근 3년)")
    fig_profit = go.Figure()
    fig_profit.add_trace(go.Bar(x=plot_data.index.year, y=plot_data['매출액'], name='매출액', marker_color='#1f77b4'))
    fig_profit.add_trace(go.Bar(x=plot_data.index.year, y=plot_data['영업이익'], name='영업이익', marker_color='#ff7f0e'))
    fig_profit.add_trace(go.Bar(x=plot_data.index.year, y=plot_data['순이익'], name='순이익', marker_color='#2ca02c'))
    fig_profit.update_layout(barmode='group', xaxis_type='category')
    st.plotly_chart(fig_profit, use_container_width=True)

    # 2. 현금흐름 지표
    st.subheader("현금흐름 분석 (최근 3년)")
    fig_cf = go.Figure()
    for col in ['영업현금흐름', '투자현금흐름', '재무현금흐름', 'Free Cash Flow']:
        fig_cf.add_trace(go.Scatter(x=plot_data.index.year, y=plot_data[col], name=col, mode='lines+markers'))
    fig_cf.update_layout(xaxis_type='category')
    st.plotly_chart(fig_cf, use_container_width=True)

    # 데이터 테이블 보여주기
    with st.expander("상세 데이터 보기 (단위: 원)"):
        st.dataframe(plot_data)
