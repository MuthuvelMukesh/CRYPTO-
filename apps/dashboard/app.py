"""Cryptocurrency Market Intelligence, Quantitative Factor Scanner & Research Lab Dashboard."""

import pandas as pd
import streamlit as st

from apps.dashboard.components.charts import (
    create_candlestick_chart,
    create_equity_curve_chart,
    create_factor_radar_chart,
    create_sector_rotation_chart,
    create_underwater_drawdown_chart,
)
from apps.dashboard.components.explainability import render_explainability_card
from apps.dashboard.data_layer import DashboardDataLayer
from apps.dashboard.theme import apply_theme

# Page Configuration
st.set_page_config(
    page_title="Crypto Quant Lab | Intelligence & Scanner",
    page_icon="🏛️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply custom dark theme & typography
apply_theme()

# Load Dashboard Data
df_scanner = DashboardDataLayer.get_scanner_data()
regime_data = DashboardDataLayer.get_market_regime()

# Sidebar Navigation & System Controls
st.sidebar.markdown(
    """
    <div style="padding: 0.5rem 0 1rem 0;">
        <h2 style="margin: 0; color: #F8FAFC; font-weight: 800; font-size: 1.3rem;">🏛️ QUANT LAB</h2>
        <span style="color: #6366F1; font-weight: 600; font-size: 0.8rem; letter-spacing: 0.05em;">CRYPTO MARKET INTELLIGENCE</span>
    </div>
    """,
    unsafe_allow_html=True,
)

nav_page = st.sidebar.radio(
    "Navigation",
    [
        "🏛️ Market Overview",
        "🔍 Market Scanner",
        "🚀 Meme Radar",
        "🔄 Sectors & Rotation",
        "📊 Asset Deep-Dive",
        "💼 Paper Portfolio",
        "🧪 Backtest Lab",
        "🔔 Alerts Center",
    ],
    index=1,  # Default to Scanner
)

st.sidebar.markdown("---")

# Sidebar Status Widget
regime_name = regime_data.get("regime", "NEUTRAL")
regime_class = f"regime-{regime_name.lower().replace('_', '-')}"

st.sidebar.markdown(
    f"""
    <div style="margin-bottom: 1rem;">
        <span style="color: #94A3B8; font-size: 0.75rem; text-transform: uppercase; font-weight: 600;">Active Market State</span>
        <div style="margin-top: 0.25rem;">
            <span class="regime-badge {regime_class}">&bull; {regime_name}</span>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.sidebar.caption(
    "**Mode**: Research & Paper Trading Only\n\n"
    "**Exchange Feeds**: Binance Public, CCXT, CoinGecko\n\n"
    "**Real-Money Execution**: Disabled by Architecture"
)

# Header Banner
st.markdown(
    f"""
    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid rgba(255,255,255,0.08); padding-bottom: 1rem; margin-bottom: 1.5rem;">
        <div>
            <h1 style="margin: 0; font-size: 1.8rem; font-weight: 800; color: #F8FAFC;">Crypto Intelligence & Multi-Factor Scanner</h1>
            <span style="color: #94A3B8; font-size: 0.9rem;">Empirical factor research, market regime classification, and paper-trading laboratory</span>
        </div>
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="text-align: right;">
                <span style="color: #64748B; font-size: 0.75rem; text-transform: uppercase; font-weight: 600;">Macro Regime</span>
                <div><span class="regime-badge {regime_class}">{regime_name} ({regime_data.get('confidence', 0.6)*100:.0f}%)</span></div>
            </div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------
# VIEW 1: MARKET OVERVIEW
# ---------------------------------------------------------
if nav_page == "🏛️ Market Overview":
    st.subheader("Macro Market Regime & Asset Breadth")

    # Metrics Row
    m_col1, m_col2, m_col3, m_col4 = st.columns(4)
    with m_col1:
        st.metric(
            label="Market State",
            value=regime_name,
            delta=f"{regime_data.get('confidence', 0.6)*100:.0f}% Model Confidence",
        )
    with m_col2:
        breadth = regime_data.get("breadth_pct", 50.0)
        st.metric(
            label="Market Breadth",
            value=f"{breadth:.1f}%",
            delta="+5.2% vs 7D" if breadth > 50 else "-4.1% vs 7D",
        )
    with m_col3:
        btc_row = df_scanner[df_scanner["Symbol"] == "BTC"]
        btc_p = btc_row["Price"].values[0] if not btc_row.empty else 64000.0
        btc_1d = btc_row["1D %"].values[0] if not btc_row.empty else 2.1
        st.metric(label="Bitcoin (BTC)", value=f"${btc_p:,.2f}", delta=f"{btc_1d:+.2f}%")
    with m_col4:
        eth_row = df_scanner[df_scanner["Symbol"] == "ETH"]
        eth_p = eth_row["Price"].values[0] if not eth_row.empty else 3400.0
        eth_1d = eth_row["1D %"].values[0] if not eth_row.empty else 1.8
        st.metric(label="Ethereum (ETH)", value=f"${eth_p:,.2f}", delta=f"{eth_1d:+.2f}%")

    st.markdown("---")

    # Top Opportunities Cards
    st.subheader("Top Quantitative Opportunities")
    top_5 = df_scanner.head(4)
    o_cols = st.columns(4)

    for i, (_, row) in enumerate(top_5.iterrows()):
        with o_cols[i]:
            st.markdown(
                f"""
                <div class="quant-card">
                    <div style="display: flex; justify-content: space-between; align-items: baseline;">
                        <span style="font-weight: 700; font-size: 1.2rem; color: #F8FAFC;">{row['Symbol']}</span>
                        <span class="score-pill score-high">{row['Opportunity']:.1f}</span>
                    </div>
                    <div style="font-size: 0.8rem; color: #64748B; margin-bottom: 0.5rem;">{row['Name']} &bull; {row['Sector']}</div>
                    <div style="font-size: 1.3rem; font-weight: 700; color: #E2E8F0; margin-bottom: 0.25rem;">
                        ${row['Price']:,.4f}
                    </div>
                    <div style="font-size: 0.85rem; color: {'#10B981' if row['7D %'] >= 0 else '#EF4444'}; font-weight: 600;">
                        7D: {row['7D %']:+.2f}%
                    </div>
                    <div style="margin-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.5rem; font-size: 0.75rem; color: #94A3B8;">
                        Mom: <b>{row['Momentum']:.0f}</b> &bull; RS: <b>{row['Relative Strength']:.0f}</b> &bull; Trend: <b>{row['Trend']:.0f}</b>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # Macro Rationale Box
    st.markdown("### Regime Decision Factors")
    for reason in regime_data.get("rationale", []):
        st.markdown(f"- 📈 **{reason}**")


# ---------------------------------------------------------
# VIEW 2: MARKET SCANNER
# ---------------------------------------------------------
elif nav_page == "🔍 Market Scanner":
    st.subheader("Multi-Factor Quantitative Screener")

    # Filter controls
    f_col1, f_col2, f_col3, f_col4 = st.columns([2, 2, 2, 2])

    with f_col1:
        classes = ["All"] + sorted(df_scanner["Class"].unique())
        sel_class = st.selectbox("Asset Class", classes, index=0)

    with f_col2:
        sectors = ["All"] + sorted(df_scanner["Sector"].unique())
        sel_sector = st.selectbox("Sector", sectors, index=0)

    with f_col3:
        min_opp = st.slider("Min Opportunity Score", 0.0, 95.0, 50.0, step=5.0)

    with f_col4:
        exclude_flags = st.checkbox("Exclude Active Risk Flags", value=False)

    # Filter dataframe
    filtered_df = df_scanner.copy()
    if sel_class != "All":
        filtered_df = filtered_df[filtered_df["Class"] == sel_class]
    if sel_sector != "All":
        filtered_df = filtered_df[filtered_df["Sector"] == sel_sector]
    filtered_df = filtered_df[filtered_df["Opportunity"] >= min_opp]
    if exclude_flags:
        filtered_df = filtered_df[filtered_df["Risk Flags"].apply(lambda x: len(x) == 0)]

    # Display Table
    table_cols = [
        "Symbol",
        "Name",
        "Class",
        "Sector",
        "Price",
        "1D %",
        "7D %",
        "30D %",
        "Opportunity",
        "Momentum",
        "Relative Strength",
        "Trend",
        "Volume",
        "Quality",
        "Risk",
        "Liquidity",
    ]

    st.dataframe(
        filtered_df[table_cols].style.format({
            "Price": "${:,.4f}",
            "1D %": "{:+.2f}%",
            "7D %": "{:+.2f}%",
            "30D %": "{:+.2f}%",
            "Opportunity": "{:.1f}",
            "Momentum": "{:.0f}",
            "Relative Strength": "{:.0f}",
            "Trend": "{:.0f}",
            "Volume": "{:.0f}",
            "Quality": "{:.0f}",
            "Risk": "{:.0f}",
            "Liquidity": "{:.0f}",
        }),
        use_container_width=True,
        height=320,
    )

    st.markdown("---")

    # Click-to-Inspect Explainability Card
    st.subheader("💡 Factor Decomposition & Explainability Inspector")
    st.caption("Click any asset to see its exact additive points and risk deductions.")

    sel_sym = st.selectbox(
        "Select Asset for Full Factor Decomposition",
        filtered_df["Symbol"].tolist() if not filtered_df.empty else ["BTC"],
    )

    if sel_sym:
        asset_record = df_scanner[df_scanner["Symbol"] == sel_sym].iloc[0].to_dict()
        render_explainability_card(asset_record)


# ---------------------------------------------------------
# VIEW 3: MEME RADAR
# ---------------------------------------------------------
elif nav_page == "🚀 Meme Radar":
    st.subheader("Meme Coin Quantitative Radar & Safety Matrix")
    st.info(
        "⚠️ **Meme tokens exhibit asymmetric downside risk, high concentration, and transient liquidity.** "
        "Every meme asset is evaluated through our specialized Meme Model with strict risk penalty filters."
    )

    meme_df = df_scanner[df_scanner["Class"] == "MEME"]

    if meme_df.empty:
        st.write("No meme assets currently registered.")
    else:
        for _, row in meme_df.iterrows():
            flags = row["Risk Flags"]
            flag_html = ""
            if flags:
                flag_html = "".join([f'<span class="risk-tag">{f}</span>' for f in flags])
            else:
                flag_html = '<span style="color: #10B981; font-weight: 600; font-size: 0.8rem;">&check; Zero Active Risk Flags</span>'

            st.markdown(
                f"""
                <div class="quant-card">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <h3 style="margin: 0; color: #F8FAFC;">{row['Symbol']} &bull; {row['Name']}</h3>
                            <span style="color: #94A3B8; font-size: 0.85rem;">Price: <b>${row['Price']:,.8f}</b> &bull; 7D Return: <b>{row['7D %']:+.2f}%</b></span>
                        </div>
                        <div style="text-align: right;">
                            <span class="score-pill score-mid">Opportunity: {row['Opportunity']:.1f}</span>
                        </div>
                    </div>
                    <div style="margin-top: 0.75rem; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 0.5rem;">
                        <span style="font-size: 0.8rem; color: #94A3B8; margin-right: 0.5rem; text-transform: uppercase; font-weight: 600;">Risk Status:</span>
                        {flag_html}
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("### Meme Factor Radar")
        top_meme = meme_df.iloc[0]["Symbol"]
        scores_dict = meme_df.iloc[0].to_dict()
        radar_fig = create_factor_radar_chart(scores_dict, top_meme)
        st.plotly_chart(radar_fig, use_container_width=True)


# ---------------------------------------------------------
# VIEW 4: SECTORS & ROTATION
# ---------------------------------------------------------
elif nav_page == "🔄 Sectors & Rotation":
    st.subheader("Crypto Sector Rotation & Relative Leadership")

    # Aggregate sector stats
    sector_summary = (
        df_scanner.groupby("Sector")
        .agg({
            "Symbol": "count",
            "1D %": "mean",
            "7D %": "mean",
            "30D %": "mean",
            "Opportunity": "mean",
        })
        .reset_index()
        .rename(columns={
            "Symbol": "asset_count",
            "1D %": "return_1d_pct",
            "7D %": "return_7d_pct",
            "30D %": "return_30d_pct",
            "Opportunity": "avg_opportunity",
        })
    )
    sector_summary["return_1d"] = sector_summary["return_1d_pct"] / 100.0
    sector_summary["return_7d"] = sector_summary["return_7d_pct"] / 100.0
    sector_summary["sector_name"] = sector_summary["Sector"]
    sector_summary["rotation_status"] = sector_summary["return_7d"].apply(
        lambda r: "LEADING" if r > 0.05 else ("ACCELERATING" if r > 0.0 else "WEAKENING")
    )

    sec_col1, sec_col2 = st.columns([1, 1])

    with sec_col1:
        st.markdown("#### Sector Leadership Ranking")
        st.dataframe(
            sector_summary[[
                "Sector", "asset_count", "return_1d_pct", "return_7d_pct", "return_30d_pct", "rotation_status"
            ]].style.format({
                "return_1d_pct": "{:+.2f}%",
                "return_7d_pct": "{:+.2f}%",
                "return_30d_pct": "{:+.2f}%",
            }),
            use_container_width=True,
            height=380,
        )

    with sec_col2:
        rot_fig = create_sector_rotation_chart(sector_summary)
        st.plotly_chart(rot_fig, use_container_width=True)


# ---------------------------------------------------------
# VIEW 5: ASSET DEEP-DIVE
# ---------------------------------------------------------
elif nav_page == "📊 Asset Deep-Dive":
    st.subheader("Asset Quantitative Deep-Dive & Multi-Factor Decomposition")

    symbols = sorted(df_scanner["Symbol"].unique())
    sel_sym = st.selectbox("Select Asset to Inspect", symbols, index=0)

    asset_row = df_scanner[df_scanner["Symbol"] == sel_sym].iloc[0].to_dict()

    # Candlestick chart
    df_candles = DashboardDataLayer.get_candlestick_data(sel_sym)
    candle_fig = create_candlestick_chart(df_candles, sel_sym)
    st.plotly_chart(candle_fig, use_container_width=True)

    c_col1, c_col2 = st.columns([1, 1])
    with c_col1:
        radar_fig = create_factor_radar_chart(asset_row, sel_sym)
        st.plotly_chart(radar_fig, use_container_width=True)

    with c_col2:
        render_explainability_card(asset_row)


# ---------------------------------------------------------
# VIEW 6: PAPER PORTFOLIO
# ---------------------------------------------------------
elif nav_page == "💼 Paper Portfolio":
    st.subheader("Paper Trading Virtual Portfolio & Execution Journal")

    p_col1, p_col2, p_col3, p_col4 = st.columns(4)
    with p_col1:
        st.metric(label="Virtual Capital", value="$100,000.00", delta="Starting: $100k")
    with p_col2:
        st.metric(label="Invested Capital", value="$24,500.00", delta="24.5% Exposure")
    with p_col3:
        st.metric(label="Unrealized P&L", value="+$1,420.50", delta="+1.42%")
    with p_col4:
        st.metric(label="Current Drawdown", value="0.0%", delta="Max limit: 15.0%")

    st.markdown("---")
    st.markdown("#### Open Paper Positions")
    sample_positions = pd.DataFrame([
        {"Asset": "BTC", "Side": "LONG", "Entry Price": "$62,400.00", "Current Price": "$64,200.00", "Size (USD)": "$10,000", "Unrealized P&L": "+$288.46 (+2.88%)", "Stop Loss": "$59,800.00"},
        {"Asset": "SOL", "Side": "LONG", "Entry Price": "$144.50", "Current Price": "$155.00", "Size (USD)": "$8,000", "Unrealized P&L": "+$581.31 (+7.27%)", "Stop Loss": "$138.00"},
        {"Asset": "NEAR", "Side": "LONG", "Entry Price": "$4.85", "Current Price": "$5.20", "Size (USD)": "$6,500", "Unrealized P&L": "+$469.07 (+7.22%)", "Stop Loss": "$4.55"},
    ])
    st.dataframe(sample_positions, use_container_width=True)


# ---------------------------------------------------------
# VIEW 7: BACKTEST LAB
# ---------------------------------------------------------
elif nav_page == "🧪 Backtest Lab":
    st.subheader("Quantitative Strategy Backtesting & Walk-Forward Validation")

    b_col1, b_col2, b_col3, b_col4 = st.columns([3, 2, 2, 2])
    with b_col1:
        strategy_options = [
            "MomentumBreakout",
            "TrendRegimeFilter",
            "RelativeStrengthRotation",
            "FactorRankModel",
        ]
        sel_strat = st.selectbox("Strategy Model", strategy_options, index=0)

    with b_col2:
        init_capital = st.number_input("Initial Capital ($)", min_value=1000.0, max_value=1000000.0, value=100000.0, step=10000.0)

    with b_col3:
        lookback_days = st.selectbox("Simulation Window", [30, 60, 90, 180], index=2)

    with b_col4:
        slip_choice = st.selectbox("Slippage Model", ["market_impact", "fixed_bps", "none"], index=0)

    # Simulation execution
    run_btn = st.button("🚀 Run Backtest Simulation", use_container_width=True)

    # Run backtest or use cached session result
    if run_btn or "backtest_result" not in st.session_state or st.session_state.get("last_strat") != sel_strat:
        with st.spinner(f"Simulating event-driven execution for {sel_strat}..."):
            bt_data = DashboardDataLayer.run_backtest(
                strategy_name=sel_strat,
                initial_capital=float(init_capital),
                days=int(lookback_days),
                slippage_model=slip_choice,
            )
            st.session_state["backtest_result"] = bt_data
            st.session_state["last_strat"] = sel_strat

    bt_res = st.session_state.get("backtest_result")
    if bt_res:
        metrics = bt_res["metrics"]
        equity_df = bt_res["equity_df"]
        trades_df = bt_res["trades_df"]

        st.markdown("---")
        st.markdown(f"#### Performance Attribution Snapshot: **{sel_strat}**")

        kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
        tot_ret = metrics.get("total_return_pct", 0.0)
        cagr = metrics.get("cagr", 0.0)
        bm_ret = metrics.get("benchmark_return_pct", 0.0)
        sharpe = metrics.get("sharpe_ratio", 0.0)
        sortino = metrics.get("sortino_ratio", 0.0)
        max_dd = metrics.get("max_drawdown_pct", 0.0)
        calmar = metrics.get("calmar_ratio", 0.0)
        win_rate = metrics.get("win_rate", 0.0)
        pf = metrics.get("profit_factor", 0.0)

        with kpi1:
            st.metric(
                label="Total Return",
                value=f"{tot_ret:+.2f}%",
                delta=f"Excess Alpha: {tot_ret - bm_ret:+.1f}% vs BTC",
            )
        with kpi2:
            st.metric(
                label="CAGR (Annualized)",
                value=f"{cagr:+.2f}%",
                delta=f"Vol: {metrics.get('annualized_volatility', 0.0):.1f}%",
            )
        with kpi3:
            st.metric(
                label="Sharpe Ratio",
                value=f"{sharpe:.2f}",
                delta=f"Sortino: {sortino:.2f}",
            )
        with kpi4:
            st.metric(
                label="Max Drawdown",
                value=f"-{abs(max_dd):.2f}%",
                delta=f"Calmar: {calmar:.2f}",
                delta_color="inverse",
            )
        with kpi5:
            st.metric(
                label="Win Rate",
                value=f"{win_rate:.1f}%",
                delta=f"Profit Factor: {pf:.2f} ({int(metrics.get('total_trades', 0))} trades)",
            )

        # Interactive Charts
        st.markdown("---")
        eq_fig = create_equity_curve_chart(equity_df, strategy_name=sel_strat, benchmark_name="BTC Benchmark")
        st.plotly_chart(eq_fig, use_container_width=True)

        dd_fig = create_underwater_drawdown_chart(equity_df)
        st.plotly_chart(dd_fig, use_container_width=True)

        # Trade History Log
        st.markdown("---")
        st.markdown("#### Closed Simulated Trade Journal")
        if not trades_df.empty:
            display_cols = ["asset_id", "entry_time", "exit_time", "entry_price", "exit_price", "pnl_pct", "pnl_usd", "fees_usd", "slippage_usd", "exit_reason"]
            avail_cols = [c for c in display_cols if c in trades_df.columns]
            st.dataframe(trades_df[avail_cols], use_container_width=True)
        else:
            st.info("No closed trades logged during this simulation window.")


# ---------------------------------------------------------
# VIEW 8: ALERTS CENTER
# ---------------------------------------------------------
elif nav_page == "🔔 Alerts Center":
    st.subheader("Real-Time Signals & Operational Alerts")

    alerts = [
        {"Time": "10 mins ago", "Type": "MOMENTUM_BREAKOUT", "Asset": "SOL", "Severity": "INFO", "Message": "SOL 24h momentum acceleration exceeded +15% with 2.8x RVOL."},
        {"Time": "45 mins ago", "Type": "RELATIVE_STRENGTH_ALPHA", "Asset": "NEAR", "Severity": "INFO", "Message": "NEAR expanding relative strength ratio vs BTC > EMA50."},
        {"Time": "3 hours ago", "Type": "SUPPLY_RISK", "Asset": "RENDER", "Severity": "WARNING", "Message": "Tokenomics upcoming unlock alert: 3.2% circulating supply unlocks in 48h."},
    ]

    for a in alerts:
        color = "#10B981" if a["Severity"] == "INFO" else "#F59E0B"
        st.markdown(
            f"""
            <div class="quant-card" style="border-left: 4px solid {color};">
                <div style="display: flex; justify-content: space-between;">
                    <b>{a['Asset']} &bull; {a['Type']}</b>
                    <span style="color: #64748B; font-size: 0.8rem;">{a['Time']}</span>
                </div>
                <div style="color: #CBD5E1; font-size: 0.85rem; margin-top: 0.25rem;">{a['Message']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
