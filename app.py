import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="나의 주식 분석 대시보드", layout="wide")
st.title("📈 주식 재무 데이터 분석기")

# 사이드바 설정
st.sidebar.header("검색 설정")
ticker_symbol = st.sidebar.text_input("종목 티커를 입력하세요 (한국: 005930.KS, 미국: AAPL)", "005930.KS")
period_option = st.sidebar.radio("데이터 기간을 선택하세요", ("연간 (최근 3년)", "분기별 (최근 분기 최대 8개)"))

if ticker_symbol:
    ticker = yf.Ticker(ticker_symbol)
    stats = ticker.info

    # 1. 한국 주식 vs 미국 주식에 따른 단위 및 나누기 설정
    is_korean = ticker_symbol.endswith('.KS') or ticker_symbol.endswith('.KQ')
    if is_korean:
        divisor = 100_000_000  # 1억으로 나누기
        unit_text = "억원"
    else:
        divisor = 1_000_000    # 100만으로 나누기
        unit_text = "백만 달러"

    # 2. 현재 주가 가져오기
    try:
        current_price = ticker.history(period="1d")['Close'].iloc[-1]
    except:
        current_price = stats.get('currentPrice', 0)

    # 3. 사용자가 선택한 옵션에 따라 데이터 불러오기
    if period_option == "연간 (최근 3년)":
        fin_data = ticker.financials
        cf_data = ticker.cashflow
        limit = 3
        date_format = '%Y'
        title_suffix = "(연간)"
    else:
        fin_data = ticker.quarterly_financials
        cf_data = ticker.quarterly_cashflow
        limit = 8 
        date_format = '%Y-%m'
        title_suffix = "(분기별)"

    # 데이터 추출 및 시간순 정렬 (과거가 왼쪽)
    df_fin = fin_data.iloc[:, :limit].T.sort_index()
    df_cf = cf_data.iloc[:, :limit].T.sort_index()

    # 날짜 형식 변경
    try:
        df_fin.index = pd.to_datetime(df_fin.index).strftime(date_format)
        df_cf.index = pd.to_datetime(df_cf.index).strftime(date_format)
    except:
        pass

    # 주요 지표 정리 및 단위 나누기 적용
    plot_data = pd.DataFrame({
        '매출액': df_fin.get('Total Revenue', 0),
        '영업이익': df_fin.get('Operating Income', 0),
        '순이익': df_fin.get('Net Income', 0),
        'CFO(영업활동)': df_cf.get('Operating Cash Flow', 0),
        'CFI(투자활동)': df_cf.get('Investing Cash Flow', 0),
        'CFF(재무활동)': df_cf.get('Financing Cash Flow', 0),
        'FCF(잉여현금)': df_cf.get('Free Cash Flow', 0)
    }).fillna(0)

    plot_data = plot_data / divisor  # 여기서 일괄적으로 단위를 축소합니다.

    # 상단 요약 정보
    company_name = stats.get('longName', ticker_symbol)
    st.markdown(f"## **{company_name} ({ticker_symbol})**")

    st.subheader("📌 현재 주요 지표")
    col1, col2, col3, col4 = st.columns(4)
    
    # 주가 표시 (천 단위 콤마)
    if current_price > 1000:
        col1.metric("현재 주가", f"{current_price:,.0f}")
    else:
        col1.metric("현재 주가", f"{current_price:,.2f}")
        
    col2.metric("현재 PER", f"{stats.get('trailingPE', 'N/A')}")
    col3.metric("현재 PBR", f"{stats.get('priceToBook', 'N/A')}")
    
    roe = stats.get('returnOnEquity', None)
    if roe is not None:
        col4.metric("현재 ROE", f"{roe * 100:.2f}%")
    else:
        col4.metric("현재 ROE", "N/A")

    # --- 시각화 ---
    st.divider()
    
    # 수익성 차트
    st.subheader(f"📊 매출 및 이익 추이 {title_suffix} / 단위: {unit_text}")
    fig_profit = go.Figure()
    fig_profit.add_trace(go.Bar(x=plot_data.index, y=plot_data['매출액'], name='매출액', marker_color='#1f77b4'))
    fig_profit.add_trace(go.Bar(x=plot_data.index, y=plot_data['영업이익'], name='영업이익', marker_color='#ff7f0e'))
    fig_profit.add_trace(go.Bar(x=plot_data.index, y=plot_data['순이익'], name='순이익', marker_color='#2ca02c'))
    fig_profit.update_layout(barmode='group', xaxis_type='category', hovermode="x unified")
    st.plotly_chart(fig_profit, use_container_width=True)

    # 현금흐름 차트
    st.subheader(f"💸 현금흐름 분석 {title_suffix} / 단위: {unit_text}")
    fig_cf = go.Figure()
    for col in ['CFO(영업활동)', 'CFI(투자활동)', 'CFF(재무활동)', 'FCF(잉여현금)']:
        fig_cf.add_trace(go.Scatter(x=plot_data.index, y=plot_data[col], name=col, mode='lines+markers'))
    fig_cf.update_layout(xaxis_type='category', hovermode="x unified")
    st.plotly_chart(fig_cf, use_container_width=True)

    # 상세 데이터 표 (천 단위 콤마 포맷팅 적용)
    with st.expander(f"상세 데이터 보기 (단위: {unit_text})"):
        # style.format("{:,.0f}")를 사용하여 소수점 없이 콤마만 찍어줍니다.
        st.dataframe(plot_data.T.style.format("{:,.0f}"))
