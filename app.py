import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# 페이지 설정
st.set_page_config(page_title="나의 주식 분석 대시보드", layout="wide")
st.title("📈 주식 재무 데이터 분석기")

# 사이드바 설정
st.sidebar.header("검색 설정")
ticker_symbol = st.sidebar.text_input("종목 티커를 입력하세요 (한국: 005930.KS, 미국: AAPL)", "AAPL")
period_option = st.sidebar.radio("데이터 기간을 선택하세요", ("연간 (최근 3년)", "분기별 (최근 분기 최대 5개)"))

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

    # 2. 현재 주가 및 포맷팅 함수
    try:
        current_price = ticker.history(period="1d")['Close'].iloc[-1]
    except:
        current_price = stats.get('currentPrice', 0)

    def format_price(price):
        if price is None or price == 'N/A' or price == 0 or pd.isna(price):
            return "N/A"
        return f"{price:,.0f}" if price > 1000 else f"{price:,.2f}"

    # 3. 데이터 불러오기
    if period_option == "연간 (최근 3년)":
        fin_data = ticker.financials
        bs_data = ticker.balance_sheet
        cf_data = ticker.cashflow
        limit = 3
        date_format = '%Y'
        title_suffix = "(연간)"
    else:
        fin_data = ticker.quarterly_financials
        bs_data = ticker.quarterly_balance_sheet
        cf_data = ticker.quarterly_cashflow
        limit = 5  # 분기 데이터 최대 5개로 축소
        date_format = '%Y-%m'
        title_suffix = "(분기별)"

    # 데이터 추출 및 시간순 정렬
    df_fin = fin_data.iloc[:, :limit].T.sort_index()
    df_bs = bs_data.iloc[:, :limit].T.sort_index()
    df_cf = cf_data.iloc[:, :limit].T.sort_index()

    try:
        df_fin.index = pd.to_datetime(df_fin.index).strftime(date_format)
        df_bs.index = pd.to_datetime(df_bs.index).strftime(date_format)
        df_cf.index = pd.to_datetime(df_cf.index).strftime(date_format)
    except:
        pass

    # --- 항목별 데이터 추출 (결측치 대비 보수적 접근) ---
    def get_data(df, cols):
        for col in cols:
            if col in df.columns:
                return df[col].fillna(0)
        return pd.Series(0, index=df.index)

    revenue = get_data(df_fin, ['Total Revenue', 'Operating Revenue'])
    op_income = get_data(df_fin, ['Operating Income', 'EBIT'])
    net_income = get_data(df_fin, ['Net Income'])
    interest_exp = get_data(df_fin, ['Interest Expense', 'Interest Expense Non Operating']).abs()
    
    total_assets = get_data(df_bs, ['Total Assets'])
    total_liab = get_data(df_bs, ['Total Liabilities Net Minority Interest', 'Total Liabilities'])
    equity = get_data(df_bs, ['Stockholders Equity', 'Total Equity Gross Minority Interest'])
    invested_capital = get_data(df_bs, ['Invested Capital'])
    if invested_capital.sum() == 0:
        invested_capital = equity + get_data(df_bs, ['Total Debt'])

    # --- 신규 지표 계산 ---
    debt_ratio = (total_liab / equity.replace(0, np.nan)) * 100
    interest_cov = op_income / interest_exp.replace(0, np.nan)
    roic = (op_income / invested_capital.replace(0, np.nan)) * 100

    # 듀퐁 분석 요소
    npm = (net_income / revenue.replace(0, np.nan)) * 100  
    ato = revenue / total_assets.replace(0, np.nan)        
    em = total_assets / equity.replace(0, np.nan)          
    dupont_roe = (npm / 100) * ato * em * 100              

    # 절대금액 데이터프레임
    plot_data_abs = pd.DataFrame({
        '매출액': revenue,
        '영업이익': op_income,
        '순이익': net_income,
        'CFO(영업활동)': get_data(df_cf, ['Operating Cash Flow']),
        'CFI(투자활동)': get_data(df_cf, ['Investing Cash Flow']),
        'CFF(재무활동)': get_data(df_cf, ['Financing Cash Flow']),
        'FCF(잉여현금)': get_data(df_cf, ['Free Cash Flow']),
        '총자산': total_assets,
        '총부채': total_liab,
        '자본총계': equity
    }) / divisor

    # --- 화면 출력 시작 ---
    company_name = stats.get('longName', ticker_symbol)
    st.markdown(f"## **{company_name} ({ticker_symbol})**")

    # 📌 섹션 1: 기본 지표
    st.subheader("📌 기본 투자 지표")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("현재 주가", format_price(current_price))
    col2.metric("현재 PER", f"{stats.get('trailingPE', 'N/A')}")
    col3.metric("현재 PBR", f"{stats.get('priceToBook', 'N/A')}")
    roe_current = stats.get('returnOnEquity', None)
    col4.metric("현재 ROE", f"{roe_current * 100:.2f}%" if roe_current is not None else "N/A")

    # 💡 섹션 2: 재무 건전성 및 고급 지표
    st.divider()
    st.subheader("🛡️ 재무 건전성 및 수익성 (최근 기준)")
    col_adv1, col_adv2, col_adv3, col_adv4 = st.columns(4)
    
    latest_debt = debt_ratio.iloc[-1] if not debt_ratio.empty else np.nan
    latest_icov = interest_cov.iloc[-1] if not interest_cov.empty else np.nan
    latest_roic = roic.iloc[-1] if not roic.empty else np.nan
    short_ratio = stats.get('shortPercentOfFloat', None)

    col_adv1.metric("부채비율", f"{latest_debt:.2f}%" if pd.notna(latest_debt) else "N/A")
    col_adv2.metric("이자보상배율", f"{latest_icov:.2f}배" if pd.notna(latest_icov) else "N/A")
    col_adv3.metric("ROIC", f"{latest_roic:.2f}%" if pd.notna(latest_roic) else "N/A")
    col_adv4.metric("공매도 비율", f"{short_ratio * 100:.2f}%" if short_ratio else "N/A")

    # 🎯 섹션 3: 애널리스트 목표가 (다시 추가된 부분)
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

    # 🌳 섹션 4: 듀퐁 분석 (DuPont Analysis)
    st.divider()
    st.subheader(f"🔬 듀퐁 분석 (ROE 분해) {title_suffix}")
    st.markdown("기업의 자기자본이익률(ROE)이 **마진(순이익률), 효율성(총자산회전율), 레버리지(자기자본승수)** 중 어디서 비롯되었는지 파악합니다.")

    latest_npm = npm.iloc[-1] if not npm.empty else 0
    latest_ato = ato.iloc[-1] if not ato.empty else 0
    latest_em = em.iloc[-1] if not em.empty else 0
    latest_roe = dupont_roe.iloc[-1] if not dupont_roe.empty else 0

    col_d1, col_sign1, col_d2, col_sign2, col_d3, col_sign3, col_d4 = st.columns([2, 0.5, 2, 0.5, 2, 0.5, 2])
    col_d1.metric("ROE (자기자본이익률)", f"{latest_roe:.2f}%")
    col_sign1.markdown("<h2 style='text-align: center;'>=</h2>", unsafe_allow_html=True)
    col_d2.metric("순이익률 (마진)", f"{latest_npm:.2f}%")
    col_sign2.markdown("<h2 style='text-align: center;'>×</h2>", unsafe_allow_html=True)
    col_d3.metric("총자산회전율 (효율성)", f"{latest_ato:.2f}배")
    col_sign3.markdown("<h2 style='text-align: center;'>×</h2>", unsafe_allow_html=True)
    col_d4.metric("자기자본승수 (레버리지)", f"{latest_em:.2f}배")

    fig_dupont = make_subplots(specs=[[{"secondary_y": True}]])
    fig_dupont.add_trace(go.Bar(x=dupont_roe.index, y=dupont_roe, name='ROE (%)', opacity=0.6, marker_color='indigo'), secondary_y=False)
    fig_dupont.add_trace(go.Scatter(x=npm.index, y=npm, name='순이익률 (%)', mode='lines+markers', line=dict(color='green', width=2)), secondary_y=False)
    fig_dupont.add_trace(go.Scatter(x=ato.index, y=ato, name='총자산회전율 (배)', mode='lines+markers', line=dict(color='orange', width=2)), secondary_y=True)
    fig_dupont.add_trace(go.Scatter(x=em.index, y=em, name='자기자본승수 (배)', mode='lines+markers', line=dict(color='red', width=2)), secondary_y=True)
    
    fig_dupont.update_layout(title_text="최근 기간 듀퐁 지표 추이", hovermode="x unified", barmode='group')
    fig_dupont.update_yaxes(title_text="비율 (%)", secondary_y=False)
    fig_dupont.update_yaxes(title_text="배수 (배)", secondary_y=True)
    st.plotly_chart(fig_dupont, use_container_width=True)

    # --- 섹션 5: 수익성 & 현금흐름 차트 ---
    st.divider()
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.subheader(f"📊 매출 및 이익 추이")
        fig_profit = go.Figure()
        fig_profit.add_trace(go.Bar(x=plot_data_abs.index, y=plot_data_abs['매출액'], name='매출액', marker_color='#1f77b4'))
        fig_profit.add_trace(go.Bar(x=plot_data_abs.index, y=plot_data_abs['영업이익'], name='영업이익', marker_color='#ff7f0e'))
        fig_profit.add_trace(go.Bar(x=plot_data_abs.index, y=plot_data_abs['순이익'], name='순이익', marker_color='#2ca02c'))
        fig_profit.update_layout(barmode='group', xaxis_type='category', hovermode="x unified", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_profit, use_container_width=True)

    with col_chart2:
        st.subheader(f"💸 현금흐름 분석")
        fig_cf = go.Figure()
        for col in ['CFO(영업활동)', 'CFI(투자활동)', 'CFF(재무활동)', 'FCF(잉여현금)']:
            fig_cf.add_trace(go.Scatter(x=plot_data_abs.index, y=plot_data_abs[col], name=col, mode='lines+markers'))
        fig_cf.update_layout(xaxis_type='category', hovermode="x unified", legend=dict(orientation="h", y=-0.2))
        st.plotly_chart(fig_cf, use_container_width=True)

    # 상세 데이터 표 정리
    detail_df = plot_data_abs.copy()
    detail_df['부채비율(%)'] = debt_ratio
    detail_df['이자보상배율(배)'] = interest_cov
    detail_df['ROIC(%)'] = roic
    
    with st.expander(f"상세 재무 데이터 보기 (단위: {unit_text})"):
        st.dataframe(detail_df.T.style.format("{:,.2f}"))
