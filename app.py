import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pykrx import stock
import datetime

# 페이지 설정
st.set_page_config(page_title="나의 주식 분석 대시보드", layout="wide")

# 📱 모바일 UI 최적화 & 탭 스타일링
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; padding-left: 1rem; padding-right: 1rem; }
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; }
    .stDataFrame { width: 100%; }
    .stTabs [data-baseweb="tab-list"] { gap: 24px; }
    .stTabs [data-baseweb="tab"] { height: 50px; font-weight: bold; font-size: 1.1rem; }
    </style>
""", unsafe_allow_html=True)

# 1. 깃허브 CSV 파일 읽기 (서버 차단 방어)
@st.cache_data
def load_krx_mapping():
    try:
        return pd.read_csv('krx_mapping.csv', dtype={'Code': str})
    except Exception:
        st.error("🚨 깃허브에서 krx_mapping.csv 파일을 찾을 수 없습니다. 파일 업로드를 확인해주세요.")
        return pd.DataFrame(columns=['Code', 'Name', 'Market'])

krx_df = load_krx_mapping()

st.title("📈 주식 재무 데이터 분석기")

# 사이드바 설정
st.sidebar.header("검색 설정")
user_input = st.sidebar.text_input("종목명(한글) 또는 티커(미국) 입력", "삼성전자").strip()
period_option = st.sidebar.radio("데이터 기간을 선택하세요", ("연간 (최근 3년)", "분기별 (최근 분기 최대 5개)"))

if user_input:
    # 한글 종목명 -> 코드 변환
    matched_row = krx_df[krx_df['Name'] == user_input]
    
    if not matched_row.empty:
        pure_ticker = str(matched_row.iloc[0]['Code'])
        market = matched_row.iloc[0]['Market']
        suffix = '.KS' if market in ['KOSPI', 'KOSPI200'] else '.KQ'
        ticker_symbol = pure_ticker + suffix
        is_korean = True
        company_name = user_input
    else:
        ticker_symbol = user_input.upper()
        pure_ticker = ticker_symbol.split('.')[0]
        is_korean = ticker_symbol.endswith('.KS') or ticker_symbol.endswith('.KQ')
        company_name = ticker_symbol
        market = 'US'

    ticker = yf.Ticker(ticker_symbol)
    stats = ticker.info

    if 'longName' in stats and not is_korean:
        company_name = stats['longName']

    divisor = 100_000_000 if is_korean else 1_000_000
    unit_text = "억원" if is_korean else "백만 달러"

    def format_price(price):
        if price is None or price == 'N/A' or price == 0 or pd.isna(price): return "N/A"
        return f"{price:,.0f}" if price > 1000 else f"{price:,.2f}"

    # 날짜 세팅
    today = datetime.datetime.today()
    end_date_today = today.strftime("%Y%m%d")
    start_date_7d = (today - datetime.timedelta(days=7)).strftime("%Y%m%d")
    start_date_1y = (today - datetime.timedelta(days=365)).strftime("%Y%m%d")
    
    # 🌟 연간 선택 시 3년 밴드, 분기 선택 시 5년 밴드를 위한 날짜 분기 처리
    if "연간" in period_option:
        start_val_date = (today - datetime.timedelta(days=365*3)).strftime("%Y%m%d")
        band_title = "3년"
    else:
        start_val_date = (today - datetime.timedelta(days=365*5)).strftime("%Y%m%d")
        band_title = "5년"

    # 🚀 데이터 로딩 (캐싱을 통한 속도 최적화)
    @st.cache_data(ttl=3600)
    def get_stock_data(symbol, pure_sym, is_kr, val_start):
        hist_1y = yf.Ticker(symbol).history(period="1y")
        krx_fund_val, krx_fund_current = pd.DataFrame(), {}
        
        if is_kr:
            try:
                # 밸류에이션 밴드용 (월간 간격으로 조회하여 로딩 최적화)
                krx_fund_val = stock.get_market_fundamental(val_start, end_date_today, pure_sym, freq="m")
                recent_fund = stock.get_market_fundamental(start_date_7d, end_date_today, pure_sym)
                if not recent_fund.empty:
                    krx_fund_current = recent_fund.iloc[-1].to_dict()
            except:
                pass
        return hist_1y, krx_fund_val, krx_fund_current

    @st.cache_data(ttl=3600)
    def get_benchmark_data(is_kr, mkt):
        bench_sym = "^KS11" if is_kr and mkt in ['KOSPI', 'KOSPI200'] else "^KQ11" if is_kr else "^GSPC"
        bench_hist = yf.Ticker(bench_sym).history(period="1y")
        try: rfr = yf.Ticker("^TNX").history(period="1d")['Close'].iloc[-1] / 100
        except: rfr = 0.04
        return bench_hist, rfr

    # 데이터 호출
    hist_1y, krx_fund_val, krx_fund_current = get_stock_data(ticker_symbol, pure_ticker, is_korean, start_val_date)
    bench_hist, rfr = get_benchmark_data(is_korean, market)

    current_price = stats.get('currentPrice', hist_1y['Close'].iloc[-1] if not hist_1y.empty else 0)

    # 파이썬 자체 연산 (Beta, Sharpe, CAPM)
    disp_per, disp_pbr, disp_roe, beta, sharpe_ratio, capm_return = "N/A", "N/A", "N/A", np.nan, np.nan, None
    if not hist_1y.empty and not bench_hist.empty:
        daily_ret = hist_1y['Close'].pct_change().dropna()
        bench_ret = bench_hist['Close'].pct_change().dropna()
        
        ann_return = daily_ret.mean() * 252
        ann_vol = daily_ret.std() * np.sqrt(252)
        sharpe_ratio = (ann_return - rfr) / ann_vol if ann_vol != 0 else np.nan
        
        ret_df = pd.concat([daily_ret, bench_ret], axis=1).dropna()
        ret_df.columns = ['Stock', 'Bench']
        if not ret_df.empty:
            cov_mat = ret_df.cov()
            beta = cov_mat.iloc[0, 1] / cov_mat.iloc[1, 1]
            capm_return = rfr + (beta * 0.055)

    if is_korean and krx_fund_current:
        disp_per = krx_fund_current.get('PER', "N/A")
        disp_pbr = krx_fund_current.get('PBR', "N/A")
        if disp_per != "N/A" and disp_per > 0 and disp_pbr != "N/A":
            disp_roe = disp_pbr / disp_per 
    else:
        disp_per = stats.get('trailingPE', 'N/A')
        disp_pbr = stats.get('priceToBook', 'N/A')
        disp_roe = stats.get('returnOnEquity', "N/A")

    # yfinance 재무 데이터 불러오기
    if period_option == "연간 (최근 3년)":
        limit, date_format = 3, '%Y'
        df_fin = ticker.financials.iloc[:, :limit].T.sort_index() if not ticker.financials.empty else pd.DataFrame()
        df_bs = ticker.balance_sheet.iloc[:, :limit].T.sort_index() if not ticker.balance_sheet.empty else pd.DataFrame()
        df_cf = ticker.cashflow.iloc[:, :limit].T.sort_index() if not ticker.cashflow.empty else pd.DataFrame()
    else:
        limit, date_format = 5, '%Y-%m'
        df_fin = ticker.quarterly_financials.iloc[:, :limit].T.sort_index() if not ticker.quarterly_financials.empty else pd.DataFrame()
        df_bs = ticker.quarterly_balance_sheet.iloc[:, :limit].T.sort_index() if not ticker.quarterly_balance_sheet.empty else pd.DataFrame()
        df_cf = ticker.quarterly_cashflow.iloc[:, :limit].T.sort_index() if not ticker.quarterly_cashflow.empty else pd.DataFrame()

    try:
        if not df_fin.empty: df_fin.index = pd.to_datetime(df_fin.index).strftime(date_format)
        if not df_bs.empty: df_bs.index = pd.to_datetime(df_bs.index).strftime(date_format)
        if not df_cf.empty: df_cf.index = pd.to_datetime(df_cf.index).strftime(date_format)
    except: pass

    def get_data(df, cols):
        for col in cols:
            if not df.empty and col in df.columns: return df[col].fillna(0)
        return pd.Series(0, index=df.index if not df.empty else [0])

    revenue = get_data(df_fin, ['Total Revenue', 'Operating Revenue'])
    op_income = get_data(df_fin, ['Operating Income', 'EBIT'])
    net_income = get_data(df_fin, ['Net Income'])
    total_assets = get_data(df_bs, ['Total Assets'])
    equity = get_data(df_bs, ['Stockholders Equity', 'Total Equity Gross Minority Interest'])
    
    # 듀퐁 분석 요소
    npm = (net_income / revenue.replace(0, np.nan)) * 100  
    ato = revenue / total_assets.replace(0, np.nan)        
    em = total_assets / equity.replace(0, np.nan)          
    dupont_roe = (npm / 100) * ato * em * 100              

    # 데이터 표 생성
    plot_data_abs = pd.DataFrame({
        '매출액': revenue, '영업이익': op_income, '순이익': net_income,
        'CFO(영업활동)': get_data(df_cf, ['Operating Cash Flow']),
        'CFI(투자활동)': get_data(df_cf, ['Investing Cash Flow']),
        'CFF(재무활동)': get_data(df_cf, ['Financing Cash Flow']),
        'CAPEX(자본적지출)': get_data(df_cf, ['Capital Expenditure']),
        'FCF(잉여현금)': get_data(df_cf, ['Free Cash Flow'])
    }) / divisor

    # --- 화면 출력 시작 ---
    st.markdown(f"## **{company_name} ({ticker_symbol})**")

    # 기본 요약 지표 (최상단)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("현재 주가", format_price(current_price))
    col2.metric("현재 PER", f"{disp_per:.2f}" if isinstance(disp_per, (int, float)) and disp_per > 0 else "N/A")
    col3.metric("현재 PBR", f"{disp_pbr:.2f}" if isinstance(disp_pbr, (int, float)) and disp_pbr > 0 else "N/A")
    col4.metric("현재 ROE", f"{disp_roe * 100:.2f}%" if isinstance(disp_roe, (int, float)) else "N/A")

    st.divider()

    # 🌟 탭(Tabs) 분리
    tab1, tab2, tab3 = st.tabs(["📊 가격 & 재무 차트", "📈 밸류에이션 & 목표가", "⚖️ 리스크 & 듀퐁 분석"])

    # --- TAB 1: 가격 & 재무 차트 ---
    with tab1:
        if not hist_1y.empty:
            fig_candle = go.Figure(data=[go.Candlestick(
                x=hist_1y.index, open=hist_1y['Open'], high=hist_1y['High'], low=hist_1y['Low'], close=hist_1y['Close'], name="주가"
            )])
            fig_candle.update_layout(title="최근 1년 주가 캔들차트", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=40, b=10), height=400)
            st.plotly_chart(fig_candle, use_container_width=True)

        col_c1, col_c2 = st.columns(2)
        with col_c1:
            st.subheader(f"매출 및 이익 추이")
            fig_profit = go.Figure()
            if not df_fin.empty:
                fig_profit.add_trace(go.Bar(x=df_fin.index, y=revenue/divisor, name='매출액', marker_color='#1f77b4'))
                fig_profit.add_trace(go.Bar(x=df_fin.index, y=op_income/divisor, name='영업이익', marker_color='#ff7f0e'))
                fig_profit.add_trace(go.Bar(x=df_fin.index, y=net_income/divisor, name='순이익', marker_color='#2ca02c'))
            fig_profit.update_layout(barmode='group', hovermode="x unified", legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_profit, use_container_width=True)

        with col_c2:
            st.subheader(f"현금흐름 분석 (CAPEX 포함)")
            fig_cf = go.Figure()
            if not df_cf.empty:
                for col_name, item in [('CFO(영업활동)', 'Operating Cash Flow'), ('CFI(투자활동)', 'Investing Cash Flow'), ('CFF(재무활동)', 'Financing Cash Flow'), ('CAPEX(자본적지출)', 'Capital Expenditure'), ('FCF(잉여현금)', 'Free Cash Flow')]:
                    line_style = dict(dash='dot', width=2) if col_name == 'CAPEX(자본적지출)' else dict(width=2)
                    fig_cf.add_trace(go.Scatter(x=df_cf.index, y=get_data(df_cf, [item])/divisor, name=col_name, mode='lines+markers', line=line_style))
            fig_cf.update_layout(hovermode="x unified", legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=30, b=10))
            st.plotly_chart(fig_cf, use_container_width=True)

        # 🌟 상세 데이터 표 복구 (항상 보이거나 토글로 확인 가능)
        with st.expander(f"상세 재무 데이터 보기 (단위: {unit_text})"):
            st.dataframe(plot_data_abs.T.style.format("{:,.2f}"), use_container_width=True)

    # --- TAB 2: 밸류에이션 및 애널리스트 목표가 ---
    with tab2:
        # 🌟 애널리스트 목표가
        st.subheader("🎯 월가 컨센서스 목표가")
        col_tgt1, col_tgt2, col_tgt3, col_tgt4 = st.columns(4)
        target_mean = stats.get('targetMeanPrice', None)
        col_tgt1.metric("평균 목표가", format_price(target_mean))
        col_tgt2.metric("최고 목표가", format_price(stats.get('targetHighPrice', None)))
        col_tgt3.metric("최저 목표가", format_price(stats.get('targetLowPrice', None)))
        col_tgt4.metric("분석가 수", f"{stats.get('numberOfAnalystOpinions', 'N/A')}명")

        st.divider()

        # 🌟 3년/5년 동적 밴드 차트
        if is_korean and not krx_fund_val.empty:
            st.subheader(f"📊 역사적 PER / PBR 밴드 (최근 {band_title} 월간 추이)")
            krx_fund_val = krx_fund_val.replace(0, np.nan)
            
            fig_val = make_subplots(specs=[[{"secondary_y": True}]])
            fig_val.add_trace(go.Scatter(x=krx_fund_val.index, y=krx_fund_val['PER'], name='PER (배)', mode='lines', line=dict(color='blue', width=2)), secondary_y=False)
            fig_val.add_trace(go.Scatter(x=krx_fund_val.index, y=krx_fund_val['PBR'], name='PBR (배)', mode='lines', line=dict(color='purple', width=2)), secondary_y=True)
            
            fig_val.update_layout(height=450, hovermode="x unified", margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h", y=-0.2))
            fig_val.update_yaxes(title_text="PER (배)", secondary_y=False)
            fig_val.update_yaxes(title_text="PBR (배)", secondary_y=True)
            st.plotly_chart(fig_val, use_container_width=True)
        else:
            st.info("💡 미국 주식은 야후 파이낸스 무료 API 구조상 과거 장기 EPS/BPS를 불러올 수 없어 밸류에이션 밴드 차트가 생략됩니다.")

    # --- TAB 3: 리스크 & 듀퐁 분석 ---
    with tab3:
        st.subheader("⚖️ 리스크 및 성과 지표 (최근 1년 기준)")
        c_r1, c_r2, c_r3, c_r4 = st.columns(4)
        c_r1.metric("베타 (Beta)", f"{beta:.2f}" if pd.notna(beta) else "N/A")
        c_r2.metric("샤프 지수 (Sharpe)", f"{sharpe_ratio:.2f}" if pd.notna(sharpe_ratio) else "N/A")
        c_r3.metric("CAPM 기대수익률", f"{capm_return * 100:.2f}%" if capm_return is not None else "N/A")
        c_r4.metric("무위험 수익률 (10Y)", f"{rfr * 100:.2f}%")

        st.divider()

        st.subheader("🔬 듀퐁 분석 (ROE 분해)")
        latest_npm = npm.iloc[-1] if not npm.empty else 0
        latest_ato = ato.iloc[-1] if not ato.empty else 0
        latest_em = em.iloc[-1] if not em.empty else 0
        latest_roe = dupont_roe.iloc[-1] if not dupont_roe.empty else 0

        col_d1, col_sign1, col_d2, col_sign2, col_d3, col_sign3, col_d4 = st.columns([2, 0.5, 2, 0.5, 2, 0.5, 2])
        col_d1.metric("ROE (자기자본이익률)", f"{latest_roe:.2f}%")
        col_sign1.markdown("<h3 style='text-align: center; margin-top: 10px;'>=</h3>", unsafe_allow_html=True)
        col_d2.metric("순이익률 (마진)", f"{latest_npm:.2f}%")
        col_sign2.markdown("<h3 style='text-align: center; margin-top: 10px;'>×</h3>", unsafe_allow_html=True)
        col_d3.metric("총자산회전율 (효율성)", f"{latest_ato:.2f}배")
        col_sign3.markdown("<h3 style='text-align: center; margin-top: 10px;'>×</h3>", unsafe_allow_html=True)
        col_d4.metric("자기자본승수 (레버리지)", f"{latest_em:.2f}배")

        # 🌟 듀퐁 분석 차트 복구
        if not dupont_roe.empty:
            fig_dupont = make_subplots(specs=[[{"secondary_y": True}]])
            fig_dupont.add_trace(go.Bar(x=dupont_roe.index, y=dupont_roe, name='ROE (%)', opacity=0.6, marker_color='indigo'), secondary_y=False)
            fig_dupont.add_trace(go.Scatter(x=npm.index, y=npm, name='순이익률 (%)', mode='lines+markers', line=dict(color='green', width=2)), secondary_y=False)
            fig_dupont.add_trace(go.Scatter(x=ato.index, y=ato, name='총자산회전율 (배)', mode='lines+markers', line=dict(color='orange', width=2)), secondary_y=True)
            fig_dupont.add_trace(go.Scatter(x=em.index, y=em, name='자기자본승수 (배)', mode='lines+markers', line=dict(color='red', width=2)), secondary_y=True)
            
            fig_dupont.update_layout(height=400, hovermode="x unified", barmode='group', margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.2))
            fig_dupont.update_yaxes(title_text="비율 (%)", secondary_y=False)
            fig_dupont.update_yaxes(title_text="배수 (배)", secondary_y=True)
            st.plotly_chart(fig_dupont, use_container_width=True)
