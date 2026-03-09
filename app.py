import streamlit as st
import yfinance as yf
import pandas as pd
import plotly.graph_objects as go

# 페이지 설정
st.set_page_config(page_title="나의 주식 분석 대시보드", layout="wide")
st.title("📈 주식 재무 데이터 분석기")

# 사이드바 설정
st.sidebar.header("검색 설정")
ticker_symbol = st.sidebar.text_input("종목 티커를 입력하세요 (한국: 005930.KS, 미국: AAPL)", "AAPL") # 기본값을 미국 주식으로 변경해 테스트 추천
period_option = st.sidebar.radio("데이터 기간을 선택하세요", ("연간 (최근 3년)", "분기별 (최근 분기 최대 8개)"))

if ticker_symbol:
    ticker = yf.Ticker(ticker_symbol)
    stats = ticker.info

    # 1. 한국 주식 vs 미국 주식 단위 설정
    is_korean = ticker_symbol.endswith('.KS') or ticker_symbol.endswith('.KQ')
    if is_korean:
        divisor = 100_000_000
        unit_text = "억원"
    else:
        divisor = 1_000_000
        unit_text = "백만 달러"

    # 2. 현재 주가 가져오기
    try:
        current_price = ticker.history(period="1d")['Close'].iloc[-1]
    except:
        current_price = stats.get('currentPrice', 0)

    # 가격 포맷팅을 위한 보조 함수
    def format_price(price):
        if price is None or price == 'N/A' or price == 0:
            return "N/A"
        return f"{price:,.0f}" if price > 1000 else f"{price:,.2f}"

    # 3. 데이터 불러오기
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

    # 데이터 추출 및 시간순 정렬
    df_fin = fin_data.iloc[:, :limit].T.sort_index()
    df_cf = cf_data.iloc[:, :limit].T.sort_index()

    try:
        df_fin.index = pd.to_datetime(df_fin.index).strftime(date_format)
        df_cf.index = pd.to_datetime(df_cf.index).strftime(date_format)
    except:
        pass

    plot_data = pd.DataFrame({
        '매출액': df_fin.get('Total Revenue', 0),
        '영업이익': df_fin.get('Operating Income', 0),
        '순이익': df_fin.get('Net Income', 0),
        'CFO(영업활동)': df_cf.get('Operating Cash Flow', 0),
        'CFI(투자활동)': df_cf.get('Investing Cash Flow', 0),
        'CFF(재무활동)': df_cf.get('Financing Cash Flow', 0),
        'FCF(잉여현금)': df_cf.get('Free Cash Flow', 0)
    }).fillna(0)

    plot_data = plot_data / divisor

    # --- 화면 출력 시작 ---
    company_name = stats.get('longName', ticker_symbol)
    st.markdown(f"## **{company_name} ({ticker_symbol})**")

    # 📌 섹션 1: 기본 지표
    st.subheader("📌 기본 투자 지표")
    col1, col2, col3, col4 = st.columns(4)
    
    col1.metric("현재 주가", format_price(current_price))
    col2.metric("현재 PER", f"{stats.get('trailingPE', 'N/A')}")
    col3.metric("현재 PBR", f"{stats.get('priceToBook', 'N/A')}")
    
    roe = stats.get('returnOnEquity', None)
    col4.metric("현재 ROE", f"{roe * 100:.2f}%" if roe is not None else "N/A")

    # 💡 섹션 2: 고급 투자 지표 (새로 추가됨)
    st.divider()
    st.subheader("💡 고급 지표 및 주주 구성")
    col_adv1, col_adv2, col_adv3, col_adv4 = st.columns(4)

    peg = stats.get('pegRatio', None)
    col_adv1.metric("PEG 비율", f"{peg}" if peg else "N/A")

    short_ratio = stats.get('shortPercentOfFloat', None)
    col_adv2.metric("공매도 비율", f"{short_ratio * 100:.2f}%" if short_ratio else "N/A")

    insider_held = stats.get('heldPercentInsiders', None)
    col_adv3.metric("내부자 지분율", f"{insider_held * 100:.2f}%" if insider_held else "N/A")

    inst_held = stats.get('heldPercentInstitutions', None)
    col_adv4.metric("기관 지분율", f"{inst_held * 100:.2f}%" if inst_held else "N/A")

    # 🎯 섹션 3: 애널리스트 목표가 (새로 추가됨)
    st.divider()
    st.subheader("🎯 월가 컨센서스 목표가")
    st.caption("※ 야후 파이낸스 제공 데이터 기준 (일부 한국 주식은 제공되지 않을 수 있습니다.)")
    col_tgt1, col_tgt2, col_tgt3, col_tgt4 = st.columns(4)

    target_mean = stats.get('targetMeanPrice', None)
    target_high = stats.get('targetHighPrice', None)
    target_low = stats.get('targetLowPrice', None)
    analyst_cnt = stats.get('numberOfAnalystOpinions', None)

    col_tgt1.metric("평균 목표가", format_price(target_mean))
    col_tgt2.metric("최고 목표가", format_price(target_high))
    col_tgt3.metric("최저 목표가", format_price(target_low))
    col_tgt4.metric("분석가 수", f"{analyst_cnt}명" if analyst_cnt else "N/A")

    # --- 시각화 ---
    st.divider()
    
    st.subheader(f"📊 매출 및 이익 추이 {title_suffix} / 단위: {unit_text}")
    fig_profit = go.Figure()
    fig_profit.add_trace(go.Bar(x=plot_data.index, y=plot_data['매출액'], name='매출액', marker_color='#1f77b4'))
    fig_profit.add_trace(go.Bar(x=plot_data.index, y=plot_data['영업이익'], name='영업이익', marker_color='#ff7f0e'))
    fig_profit.add_trace(go.Bar(x=plot_data.index, y=plot_data['순이익'], name='순이익', marker_color='#2ca02c'))
    fig_profit.update_layout(barmode='group', xaxis_type='category', hovermode="x unified")
    st.plotly_chart(fig_profit, use_container_width=True)

    st.subheader(f"💸 현금흐름 분석 {title_suffix} / 단위: {unit_text}")
    fig_cf = go.Figure()
    for col in ['CFO(영업활동)', 'CFI(투자활동)', 'CFF(재무활동)', 'FCF(잉여현금)']:
        fig_cf.add_trace(go.Scatter(x=plot_data.index, y=plot_data[col], name=col, mode='lines+markers'))
    fig_cf.update_layout(xaxis_type='category', hovermode="x unified")
    st.plotly_chart(fig_cf, use_container_width=True)

    with st.expander(f"상세 데이터 보기 (단위: {unit_text})"):
        st.dataframe(plot_data.T.style.format("{:,.0f}"))
