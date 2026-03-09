import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="나의 주식 분석 대시보드", layout="wide")
st.title("📈 주식 재무 데이터 분석기 (분기별)")

# 사이드바에서 티커 입력 (삼성전자 005930.KS 를 기본값으로 설정)
ticker_symbol = st.sidebar.text_input("종목 티커를 입력하세요", "005930.KS")

if ticker_symbol:
    # 티커 정보 가져오기
    ticker = yf.Ticker(ticker_symbol)
    
    # 🌟 연간이 아닌 '분기별(Quarterly)' 재무제표 가져오기
    financials = ticker.quarterly_financials
    cashflow = ticker.quarterly_cashflow
    stats = ticker.info

    # 🌟 최근 8개 분기 데이터 추출 (데이터가 8개 미만일 경우 있는 만큼만 가져옴)
    df_fin = financials.iloc[:, :8].T
    df_cf = cashflow.iloc[:, :8].T

    # 🌟 시간순 정렬 (과거 데이터가 왼쪽, 최근 데이터가 오른쪽으로 오도록 뒤집기)
    df_fin = df_fin.sort_index()
    df_cf = df_cf.sort_index()

    # 보기 편하게 날짜 형식 변경 (예: 2023-03-31 -> 2023-03)
    try:
        df_fin.index = pd.to_datetime(df_fin.index).strftime('%Y-%m')
        df_cf.index = pd.to_datetime(df_cf.index).strftime('%Y-%m')
    except:
        pass # 날짜 변환 에러 시 원본 유지

    # 주요 지표 정리 (결측치는 0으로 처리)
    plot_data = pd.DataFrame({
        '매출액': df_fin.get('Total Revenue', 0),
        '영업이익': df_fin.get('Operating Income', 0),
        '순이익': df_fin.get('Net Income', 0),
        'CFO(영업활동)': df_cf.get('Operating Cash Flow', 0),
        'CFI(투자활동)': df_cf.get('Investing Cash Flow', 0),
        'CFF(재무활동)': df_cf.get('Financing Cash Flow', 0),
        'FCF(잉여현금)': df_cf.get('Free Cash Flow', 0)
    }).fillna(0)

    # 기업 이름 가져오기
    company_name = stats.get('longName', ticker_symbol)
    st.markdown(f"## **{company_name} ({ticker_symbol})**")

    # PER, PBR, ROE (현재 시점 기준 고정)
    st.subheader("📌 현재 주요 투자 지표")
    col1, col2, col3 = st.columns(3)
    col1.metric("현재 PER", f"{stats.get('trailingPE', 'N/A')}")
    col2.metric("현재 PBR", f"{stats.get('priceToBook', 'N/A')}")
    
    roe = stats.get('returnOnEquity', None)
    if roe is not None:
        col3.metric("현재 ROE", f"{roe * 100:.2f}%")
    else:
        col3.metric("현재 ROE", "N/A")

    # --- 시각화 ---
    st.divider()
    
    # 1. 수익성 지표 (매출, 이익)
    st.subheader("📊 분기별 매출 및 이익 추이 (최근 8분기)")
    fig_profit = go.Figure()
    fig_profit.add_trace(go.Bar(x=plot_data.index, y=plot_data['매출액'], name='매출액', marker_color='#1f77b4'))
    fig_profit.add_trace(go.Bar(x=plot_data.index, y=plot_data['영업이익'], name='영업이익', marker_color='#ff7f0e'))
    fig_profit.add_trace(go.Bar(x=plot_data.index, y=plot_data['순이익'], name='순이익', marker_color='#2ca02c'))
    fig_profit.update_layout(barmode='group', xaxis_type='category', hovermode="x unified")
    st.plotly_chart(fig_profit, use_container_width=True)

    # 2. 현금흐름 지표
    st.subheader("💸 분기별 현금흐름 분석 (최근 8분기)")
    fig_cf = go.Figure()
    for col in ['CFO(영업활동)', 'CFI(투자활동)', 'CFF(재무활동)', 'FCF(잉여현금)']:
        fig_cf.add_trace(go.Scatter(x=plot_data.index, y=plot_data[col], name=col, mode='lines+markers'))
    fig_cf.update_layout(xaxis_type='category', hovermode="x unified")
    st.plotly_chart(fig_cf, use_container_width=True)

    # 데이터 테이블 보여주기
    with st.expander("상세 데이터 보기 (단위: 원/달러)"):
        # 표에서도 과거가 왼쪽, 현재가 오른쪽으로 오도록 가로로 눕혀서(T) 보여줌
        st.dataframe(plot_data.T)
