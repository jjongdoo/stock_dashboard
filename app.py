import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pykrx import stock
import datetime
import os

# 페이지 설정
st.set_page_config(page_title="나의 주식 분석 대시보드", layout="wide")

# 📱 모바일 UI 최적화 커스텀 CSS
st.markdown("""
    <style>
    .block-container { padding-top: 2rem; padding-bottom: 2rem; padding-left: 1rem; padding-right: 1rem; }
    [data-testid="stMetricValue"] { font-size: 1.6rem !important; }
    .stDataFrame { width: 100%; }
    </style>
""", unsafe_allow_html=True)

# 🚀 FinanceDataReader(fdr)를 아예 삭제하고, 우리가 올린 CSV 파일만 읽도록 강제 지정!
@st.cache_data
def load_krx_mapping():
    try:
        # dtype={'Code': str}을 통해 '005930' 앞의 0이 지워지는 것을 방지
        df = pd.read_csv('krx_mapping.csv', dtype={'Code': str})
        return df
    except Exception as e:
        # 파일이 없을 경우 앱이 죽지 않도록 빈 표 반환 및 에러 메시지 출력
        st.error("🚨 깃허브에서 krx_mapping.csv 파일을 찾을 수 없습니다. 파일이 제대로 업로드되었는지 확인해주세요.")
        return pd.DataFrame(columns=['Code', 'Name', 'Market'])

krx_df = load_krx_mapping()

st.title("📈 주식 재무 데이터 분석기")

# 사이드바 설정
st.sidebar.header("검색 설정")
user_input = st.sidebar.text_input("종목명(한글) 또는 티커(미국) 입력", "삼성전자").strip()
period_option = st.sidebar.radio("데이터 기간을 선택하세요", ("연간 (최근 3년)", "분기별 (최근 분기 최대 5개)"))

if user_input:
    # 1. 한글 종목명 -> 코드로 스마트 변환 로직
    matched_row = krx_df[krx_df['Name'] == user_input]
    
    if not matched_row.empty:
        pure_ticker = str(matched_row.iloc[0]['Code'])
        market = matched_row.iloc[0]['Market']
        suffix = '.KS' if market in ['KOSPI', 'KOSPI200'] else '.KQ'
        ticker_symbol = pure_ticker + suffix
        is_korean = True
        company_name = user_input
    else:
        # 미국 주식이거나 티커를 직접 입력한 경우
        ticker_symbol = user_input.upper()
        pure_ticker = ticker_symbol.split('.')[0]
        is_korean = ticker_symbol.endswith('.KS') or ticker_symbol.endswith('.KQ')
        company_name = ticker_symbol

    ticker = yf.Ticker(ticker_symbol)
    stats = ticker.info

    if 'longName' in stats and not is_korean:
        company_name = stats['longName']

    # 화폐 단위 설정
    if is_korean:
        divisor = 100_000_000
        unit_text = "억원"
    else:
        divisor = 1_000_000
        unit_text = "백만 달러"

    def format_price(price):
        if price is None or price == 'N/A' or price == 0 or pd.isna(price):
            return "N/A"
        return f"{price:,.0f}" if price > 1000 else f"{price:,.2f}"

    # 날짜 세팅
    today = datetime.datetime.today()
    start_date_7d = (today - datetime.timedelta(days=7)).strftime("%Y%m%d")
    end_date_today = today.strftime("%Y%m%d")
    start_date_1y = (today - datetime.timedelta(days=365)).strftime("%Y%m%d")

    # 2. 데이터 하이브리드 수집 (pykrx + yfinance)
    hist_1y_fund = pd.DataFrame() 

    if is_korean:
        try:
            # KRX 1년치 시세
            krx_ohlcv = stock.get_market_ohlcv(start_date_1y, end_date_today, pure_ticker)
            if not krx_ohlcv.empty:
                krx_ohlcv.index.name = 'Date'
                hist_1y = krx_ohlcv.rename(columns={'시가':'Open', '고가':'High', '저가':'Low', '종가':'Close', '거래량':'Volume'})
                current_price = hist_1y['Close'].iloc[-1]
            else:
                hist_1y = pd.DataFrame()
                current_price = 0

            # KRX 1년치 펀더멘털 (역사적 PER/PBR용)
            krx_fund = stock.get_market_fundamental(start_date_1y, end_date_today, pure_ticker)
            if not krx_fund.empty:
                hist_1y_fund = krx_fund[['PER', 'PBR']].replace(0, np.nan) 
                disp_per = krx_fund['PER'].iloc[-1] if krx_fund['PER'].iloc[-1] > 0 else "N/A"
                disp_pbr = krx_fund['PBR'].iloc[-1] if krx_fund['PBR'].iloc[-1] > 0 else "N/A"
            else:
                disp_per, disp_pbr = "N/A", "N/A"

            # KRX 공매도 비중
            krx_short = stock.get_shorting_volume_by_ticker(start_date_7d, end_date_today, pure_ticker)
            if not krx_short.empty and not krx_ohlcv.empty:
                disp_short = krx_short['공매도거래량'].iloc[-1] / krx_ohlcv['Volume'].iloc[-1]
            else:
                disp_short = None
                
            disp_roe = stats.get('returnOnEquity', None)
            
        except Exception:
            # KRX 서버 차단 시 yfinance 데이터로 자연스럽게 우회 대체 (앱 크래시 방지)
            hist_1y = ticker.history(period="1y")
            current_price = stats.get('currentPrice', hist_1y['Close'].iloc[-1] if not hist_1y.empty else 0)
            disp_per = stats.get('trailingPE', 'N/A')
            disp_pbr = stats.get('priceToBook', 'N/A')
            disp_roe = stats.get('returnOnEquity', None)
            disp_short = stats.get('shortPercentOfFloat', None)
    else:
        # 미국 주식
        hist_1y = ticker.history(period="1y")
        current_price = stats.get('currentPrice', hist_1y['Close'].iloc[-1] if not hist_1y.empty else 0)
        disp_per = stats.get('trailingPE', 'N/A')
        disp_pbr = stats.get('priceToBook', 'N/A')
        disp_roe = stats.get('returnOnEquity', None)
        disp_short = stats.get('shortPercentOfFloat', None)

    # 무위험 수익률
    try:
        rfr_ticker = yf.Ticker("^TNX")
        rfr = rfr_ticker.history(period="1d")['Close'].iloc[-1] / 100
    except:
        rfr = 0.04 

    # 리스크 지표
    if not hist_1y.empty:
        daily_returns = hist_1y['Close'].pct_change().dropna()
        ann_return = daily_returns.mean() * 252
        ann_vol = daily_returns.std() * np.sqrt(252)
        sharpe_ratio = (ann_return - rfr) / ann_vol if ann_vol != 0 else np.nan
    else:
        sharpe_ratio = np.nan

    beta = stats.get('beta', None)
    mrp = 0.055 
    capm_return = rfr + (beta * mrp) if (beta is not None and pd.notna(beta)) else None

    # 3. yfinance 재무 데이터 불러오기
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
        limit = 5  
        date_format = '%Y-%m'
        title_suffix = "(분기별)"

    df_fin = fin_data.iloc[:, :limit].T.sort_index()
    df_bs = bs_data.iloc[:, :limit].T.sort_index()
    df_cf = cf_data.iloc[:, :limit].T.sort_index()

    try:
        df_fin.index = pd.to_datetime(df_fin.index).strftime(date_format)
        df_bs.index = pd.to_datetime(df_bs.index).strftime(date_format)
        df_cf.index = pd.to_datetime(df_cf.index).strftime(date_format)
    except:
        pass

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

    debt_ratio = (total_liab / equity.replace(0, np.nan)) * 100
    interest_cov = op_income / interest_exp.replace(0, np.nan)
    roic = (op_income / invested_capital.replace(0, np.nan)) * 100

    npm = (net_income / revenue.replace(0, np.nan)) * 100  
    ato = revenue / total_assets.replace(0, np.nan)        
    em = total_assets / equity.replace(0, np.nan)          
    dupont_roe = (npm / 100) * ato * em * 100              

    plot_data_abs = pd.DataFrame({
        '매출액': revenue,
        '영업이익': op_income,
        '순이익': net_income,
        'CFO(영업활동)': get_data(df_cf, ['Operating Cash Flow']),
        'CFI(투자활동)': get_data(df_cf, ['Investing Cash Flow']),
        'CFF(재무활동)': get_data(df_cf, ['Financing Cash Flow']),
        'CAPEX(자본적지출)': get_data(df_cf, ['Capital Expenditure']),
        'FCF(잉여현금)': get_data(df_cf, ['Free Cash Flow']),
        '총자산': total_assets,
        '총부채': total_liab,
        '자본총계': equity
    }) / divisor

    # --- 화면 출력 시작 ---
    st.markdown(f"## **{company_name} ({ticker_symbol})**")

    # 📈 섹션 1: 1년 캔들차트
    if not hist_1y.empty:
        fig_candle = go.Figure(data=[go.Candlestick(
            x=hist_1y.index, open=hist_1y['Open'], high=hist_1y['High'], low=hist_1y['Low'], close=hist_1y['Close'], name="주가"
        )])
        fig_candle.update_layout(title="최근 1년 주가 추이", xaxis_rangeslider_visible=False, margin=dict(l=10, r=10, t=40, b=10), height=400)
        st.plotly_chart(fig_candle, use_container_width=True)

    # 📌 섹션 2: 기본 투자 지표
    st.subheader("📌 기본 투자 지표")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("현재 주가", format_price(current_price))
    
    per_val = f"{disp_per:.2f}" if isinstance(disp_per, (int, float)) else "N/A"
    pbr_val = f"{disp_pbr:.2f}" if isinstance(disp_pbr, (int, float)) else "N/A"
    roe_val = f"{disp_roe * 100:.2f}%" if disp_roe is not None else "N/A"
    
    col2.metric("현재 PER", per_val)
    col3.metric("현재 PBR", pbr_val)
    col4.metric("현재 ROE", roe_val)

    # 📊 섹션 3: 역사적 PER / PBR 추이 (한국 주식 전용)
    if is_korean and not hist_1y_fund.empty:
        st.divider()
        st.subheader("📊 역사적 밸류에이션 추이 (최근 1년)")
        st.markdown("주가가 기업가치 대비 고평가/저평가 구간 중 어디에 위치해 있는지 파악합니다.")
        
        fig_val = make_subplots(specs=[[{"secondary_y": True}]])
        fig_val.add_trace(go.Scatter(x=hist_1y_fund.index, y=hist_1y_fund['PER'], name='PER (배)', mode='lines', line=dict(color='blue', width=2)), secondary_y=False)
        fig_val.add_trace(go.Scatter(x=hist_1y_fund.index, y=hist_1y_fund['PBR'], name='PBR (배)', mode='lines', line=dict(color='purple', width=2)), secondary_y=True)
        
        fig_val.update_layout(hovermode="x unified", margin=dict(l=10, r=10, t=20, b=10), legend=dict(orientation="h", y=-0.2))
        fig_val.update_yaxes(title_text="PER (배)", secondary_y=False)
        fig_val.update_yaxes(title_text="PBR (배)", secondary_y=True)
        st.plotly_chart(fig_val, use_container_width=True)
    elif not is_korean:
        st.caption("※ 미국 주식의 과거 PER/PBR 추이는 API 구조상 제공되지 않습니다.")

    # ⚖️ 섹션 4: 리스크 및 성과 지표
    st.divider()
    st.subheader("⚖️ 리스크 및 성과 지표 (최근 1년 기준)")
    col_risk1, col_risk2, col_risk3, col_risk4 = st.columns(4)
    col_risk1.metric("베타 (Beta)", f"{beta:.2f}" if pd.notna(beta) else "N/A")
    col_risk2.metric("샤프 지수 (Sharpe)", f"{sharpe_ratio:.2f}" if pd.notna(sharpe_ratio) else "N/A")
    col_risk3.metric("CAPM 기대수익률", f"{capm_return * 100:.2f}%" if capm_return is not None else "N/A")
    col_risk4.metric("무위험 수익률 (10Y)", f"{rfr * 100:.2f}%")

    # 💡 섹션 5: 재무 건전성 및 기타 지표
    st.divider()
    st.subheader("🛡️ 재무 건전성 및 기타 지표")
    col_adv1, col_adv2, col_adv3, col_adv4 = st.columns(4)
    latest_debt = debt_ratio.iloc[-1] if not debt_ratio.empty else np.nan
    latest_icov = interest_cov.iloc[-1] if not interest_cov.empty else np.nan
    latest_roic = roic.iloc[-1] if not roic.empty else np.nan

    col_adv1.metric("부채비율", f"{latest_debt:.2f}%" if pd.notna(latest_debt) else "N/A")
    col_adv2.metric("이자보상배율", f"{latest_icov:.2f}배" if pd.notna(latest_icov) else "N/A")
    col_adv3.metric("ROIC", f"{latest_roic:.2f}%" if pd.notna(latest_roic) else "N/A")
    
    short_disp_val = f"{disp_short * 100:.2f}%" if disp_short is not None else "N/A"
    col_adv4.metric("공매도 비중", short_disp_val)

    # 🎯 섹션 6: 애널리스트 목표가
    st.divider()
    st.subheader("🎯 월가 컨센서스 목표가")
    col_tgt1, col_tgt2, col_tgt3, col_tgt4 = st.columns(4)
    target_mean = stats.get('targetMeanPrice', None)
    target_high = stats.get('targetHighPrice', None)
    target_low = stats.get('targetLowPrice', None)
    analyst_cnt = stats.get('numberOfAnalystOpinions', None)

    col_tgt1.metric("평균 목표가", format_price(target_mean))
    col_tgt2.metric("최고 목표가", format_price(target_high))
    col_tgt3.metric("최저 목표가", format_price(target_low))
    col_tgt4.metric("분석가 수", f"{analyst_cnt}명" if analyst_cnt else "N/A")

    # 🌳 섹션 7: 듀퐁 분석
    st.divider()
    st.subheader(f"🔬 듀퐁 분석 (ROE 분해) {title_suffix}")
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

    fig_dupont = make_subplots(specs=[[{"secondary_y": True}]])
    fig_dupont.add_trace(go.Bar(x=dupont_roe.index, y=dupont_roe, name='ROE (%)', opacity=0.6, marker_color='indigo'), secondary_y=False)
    fig_dupont.add_trace(go.Scatter(x=npm.index, y=npm, name='순이익률 (%)', mode='lines+markers', line=dict(color='green', width=2)), secondary_y=False)
    fig_dupont.add_trace(go.Scatter(x=ato.index, y=ato, name='총자산회전율 (배)', mode='lines+markers', line=dict(color='orange', width=2)), secondary_y=True)
    fig_dupont.add_trace(go.Scatter(x=em.index, y=em, name='자기자본승수 (배)', mode='lines+markers', line=dict(color='red', width=2)), secondary_y=True)
    fig_dupont.update_layout(title_text="최근 기간 듀퐁 지표 추이", hovermode="x unified", barmode='group', margin=dict(l=10, r=10, t=40, b=10), legend=dict(orientation="h", y=-0.2))
    st.plotly_chart(fig_dupont, use_container_width=True)

    # --- 섹션 8: 수익성 및 현금흐름 차트 ---
    st.divider()
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader(f"📊 매출 및 이익 추이")
        fig_profit = go.Figure()
        fig_profit.add_trace(go.Bar(x=plot_data_abs.index, y=plot_data_abs['매출액'], name='매출액', marker_color='#1f77b4'))
        fig_profit.add_trace(go.Bar(x=plot_data_abs.index, y=plot_data_abs['영업이익'], name='영업이익', marker_color='#ff7f0e'))
        fig_profit.add_trace(go.Bar(x=plot_data_abs.index, y=plot_data_abs['순이익'], name='순이익', marker_color='#2ca02c'))
        fig_profit.update_layout(barmode='group', xaxis_type='category', hovermode="x unified", legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_profit, use_container_width=True)

    with col_chart2:
        st.subheader(f"💸 현금흐름 분석 (CAPEX 포함)")
        fig_cf = go.Figure()
        for col in ['CFO(영업활동)', 'CFI(투자활동)', 'CFF(재무활동)', 'CAPEX(자본적지출)', 'FCF(잉여현금)']:
            line_style = dict(dash='dot', width=2) if col == 'CAPEX(자본적지출)' else dict(width=2)
            fig_cf.add_trace(go.Scatter(x=plot_data_abs.index, y=plot_data_abs[col], name=col, mode='lines+markers', line=line_style))
        fig_cf.update_layout(xaxis_type='category', hovermode="x unified", legend=dict(orientation="h", y=-0.2), margin=dict(l=10, r=10, t=30, b=10))
        st.plotly_chart(fig_cf, use_container_width=True)

    detail_df = plot_data_abs.copy()
    detail_df['부채비율(%)'] = debt_ratio
    detail_df['이자보상배율(배)'] = interest_cov
    detail_df['ROIC(%)'] = roic
    
    with st.expander(f"상세 재무 데이터 보기 (단위: {unit_text})"):
        st.dataframe(detail_df.T.style.format("{:,.2f}"), use_container_width=True)
