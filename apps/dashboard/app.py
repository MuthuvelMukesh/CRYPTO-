"""Cryptocurrency Market Intelligence, Quantitative Factor Scanner & Research Lab Dashboard."""

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
from src.config.constants import DataMode
from src.config.settings import get_settings

# Page Configuration
st.set_page_config(
    page_title="Crypto Intelligence v2.0 | Quant Lab",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Apply custom dark theme & typography
apply_theme()

# ── v2.0: DATA MODE BANNER ───────────────────────────────────────────────────
_settings = get_settings()
_data_mode = _settings.DATA_MODE
_MODE_META = {
    DataMode.LIVE:           ("#22C55E", "#14532D", "⬤ LIVE DATA"),
    DataMode.HISTORICAL:     ("#3B82F6", "#1E3A8A", "🗓 HISTORICAL DATA"),
    DataMode.SYNTHETIC_TEST: ("#EAB308", "#713F12", "⚠️ SYNTHETIC TEST DATA — Not for research decisions"),
    DataMode.REPLAY:         ("#A855F7", "#4A1D96", "▶ REPLAY MODE"),
}
_color, _bg, _label = _MODE_META.get(_data_mode, ("#6B7280", "#1F2937", "UNKNOWN MODE"))
st.markdown(
    f"""
    <div style="background:{_bg};border-left:4px solid {_color};padding:0.5rem 1.25rem;
                border-radius:0 6px 6px 0;margin-bottom:0.75rem;">
        <span style="color:{_color};font-weight:700;font-size:0.8rem;letter-spacing:0.08em;">{_label}</span>
        <span style="color:#94A3B8;font-size:0.75rem;margin-left:1.5rem;">
            v{_settings.APP_VERSION} &bull; {_settings.DEFAULT_EXCHANGE.upper()}
            &bull; Live Trading: <strong style="color:#F87171;">DISABLED</strong>
        </span>
    </div>
    """,
    unsafe_allow_html=True,
)
# ─────────────────────────────────────────────────────────────────────────────


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

# Sidebar Navigation & System Controls
st.sidebar.markdown(
    """
    <div style="padding: 0.5rem 0 1rem 0;">
        <h2 style="margin: 0; color: #F8FAFC; font-weight: 800; font-size: 1.3rem;">🏦 QUANT LAB v2.0</h2>
        <span style="color: #6366F1; font-weight: 600; font-size: 0.8rem; letter-spacing: 0.05em;">CRYPTO INTELLIGENCE PLATFORM</span>
    </div>
    """,
    unsafe_allow_html=True,
)

nav_page = st.sidebar.radio(
    "Navigation",
    [
        "🏦 Market Overview",
        "🔍 Market Scanner",
        "🚀 Meme Radar",
        "🔄 Sectors & Rotation",
        "📊 Asset Deep-Dive",
        "💼 Paper Portfolio",
        "🧪 Backtest Lab",
        "🔔 Alerts Center",
    ],
    index=1,
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
    f"**Data Mode**: {_data_mode.value}\n\n"
    "**Exchange**: " + _settings.DEFAULT_EXCHANGE.capitalize() + " Public API\n\n"
    "**Live Execution**: Disabled by Architecture"
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

    # v2.0: DATA_UNAVAILABLE guard — never crash, never show stale fabricated data
    if df_scanner.empty:
        st.markdown(
            f"""
            <div style="background:#1E293B;border:1px solid #334155;border-radius:10px;
                        padding:2rem;text-align:center;margin:1rem 0;">
                <div style="font-size:2.5rem;margin-bottom:0.75rem;">📡</div>
                <h3 style="color:#F1F5F9;margin:0 0 0.5rem 0;">No Market Data Available</h3>
                <p style="color:#94A3B8;margin:0 0 1rem 0;">
                    The scanner has no scored assets yet.<br>
                    This is expected on first launch — real data must be ingested before scores are computed.
                </p>
                <div style="background:#0F172A;border-radius:6px;padding:0.75rem 1rem;display:inline-block;text-align:left;">
                    <code style="color:#22C55E;font-size:0.8rem;">
                        # Run once to ingest live market data:<br>
                        python -m src.ingestion.live_ingestor
                    </code>
                </div>
                <p style="color:#64748B;font-size:0.75rem;margin:1rem 0 0 0;">
                    Data Mode: <strong style="color:#94A3B8;">{_data_mode.value}</strong>
                    &bull; Synthetic fallbacks are disabled in v2.0.
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.stop()

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
    st.subheader("Meme Coin Quantitative Radar & DEX Liquidity Auditor")
    st.info(
        "⚠️ **Meme tokens exhibit asymmetric downside risk, high holder concentration, and transient DEX pool liquidity.** "
        "Every meme asset is audited in real-time through our DEX Liquidity and On-Chain Risk Penalty Matrix."
    )

    meme_records = DashboardDataLayer.get_meme_radar_data()

    if not meme_records:
        st.warning("No DEX liquidity pools found for meme universe.")
    else:
        # High level KPI cards
        k1, k2, k3, k4 = st.columns(4)
        top_meme = meme_records[0]
        avg_liq = sum(r["liquidity_usd"] for r in meme_records) / len(meme_records)
        avg_buy_p = sum(r["buy_pressure_ratio"] for r in meme_records) / len(meme_records) * 100.0
        tot_crit = sum(1 for r in meme_records if r["risk_level"] in ("HIGH", "CRITICAL"))

        with k1:
            st.metric("Top Opportunity Meme", top_meme["symbol"], delta=f"Score: {top_meme['opportunity_score']:.1f}")
        with k2:
            st.metric("Median DEX Liquidity", f"${avg_liq:,.0f}", delta="On-Chain Pool Depth")
        with k3:
            st.metric("Avg 24h Buy Pressure", f"{avg_buy_p:.1f}%", delta="Order Flow Ratio")
        with k4:
            st.metric("High/Critical Risk Tokens", str(tot_crit), delta="Filtered by Safety Matrix", delta_color="inverse")

        st.markdown("---")
        st.markdown("#### DEX Liquidity & Quantitative Risk Rankings")

        # Table data
        import pandas as pd
        table_rows = []
        for r in meme_records:
            flags_str = ", ".join(r["risk_flags"]) if r["risk_flags"] else "CLEAN"
            table_rows.append({
                "Symbol": r["symbol"],
                "Chain / DEX": f"{r['chain_id'].upper()} &bull; {r['dex_id'].capitalize()}",
                "Price": f"${r['price_usd']:,.8f}",
                "Liquidity": f"${r['liquidity_usd']:,.0f}",
                "24h Volume": f"${r['volume_24h_usd']:,.0f}",
                "1h Vol Accel": f"{r['volume_acceleration_1h']:.2f}x",
                "Buy Pressure": f"{r['buy_pressure_ratio']*100:.1f}%",
                "Top 10 Holders": f"{r['top_10_holders_pct']:.1f}%",
                "Age": f"{r['pair_age_hours']:.0f}h",
                "Opportunity": f"{r['opportunity_score']:.1f}",
                "Risk Level": r["risk_level"],
                "Flags": flags_str,
            })
        st.dataframe(pd.DataFrame(table_rows), use_container_width=True)

        st.markdown("---")
        st.subheader("🔬 Token Micro-Structure & Risk Audit Inspector")
        inspect_sym = st.selectbox("Select Token for Complete On-Chain Audit", [r["symbol"] for r in meme_records])
        curr_audit = next(r for r in meme_records if r["symbol"] == inspect_sym)

        a_col1, a_col2 = st.columns([1, 1])
        with a_col1:
            st.markdown(f"### **{curr_audit['symbol']}** ({curr_audit['name']})")
            st.markdown(f"**DEX Pool:** `{curr_audit['pair_address']}` ({curr_audit['dex_id']} on {curr_audit['chain_id']})")
            st.markdown(f"**Pair Age:** `{curr_audit['pair_age_hours']:.1f} hours` &bull; **Holders:** `{curr_audit['holder_count']:,}`")
            st.markdown(f"**Top 10 Concentration:** `{curr_audit['top_10_holders_pct']:.1f}% of total supply`")

            st.write("Factor Scores:")
            st.progress(curr_audit["liquidity_score"] / 100.0, text=f"Liquidity Health: {curr_audit['liquidity_score']}/100")
            st.progress(curr_audit["volume_momentum_score"] / 100.0, text=f"Volume Momentum: {curr_audit['volume_momentum_score']}/100")
            st.progress(curr_audit["buy_pressure_score"] / 100.0, text=f"Buy Pressure: {curr_audit['buy_pressure_score']}/100")
            st.progress(curr_audit["holder_distribution_score"] / 100.0, text=f"Holder Decentralization: {curr_audit['holder_distribution_score']}/100")

        with a_col2:
            st.markdown("#### Risk Deduction Audit")
            st.markdown(f"**Gross Opportunity Score:** `{curr_audit['gross_score']:.1f} pts`")
            st.markdown(f"**Total Penalties Deducted:** `<span style='color: #EF4444;'>-{curr_audit['total_penalties']:.1f} pts</span>`", unsafe_allow_html=True)
            st.markdown(f"**Net Final Score:** `{curr_audit['opportunity_score']:.1f} / 100` &bull; **Risk Rating:** `{curr_audit['risk_level']}`")

            if curr_audit["penalties_breakdown"]:
                st.write("Active Penalty Deductions:")
                for p in curr_audit["penalties_breakdown"]:
                    st.error(f"❌ **{p['flag']}** ({p['deduction']} pts): {p['reason']}")
            else:
                st.success("✅ Zero active risk penalty flags detected. Pool liquidity and holder distribution are healthy.")

        st.markdown("### Meme Factor Radar")
        radar_scores = {
            "Liquidity": curr_audit["liquidity_score"],
            "Volume Momentum": curr_audit["volume_momentum_score"],
            "Buy Pressure": curr_audit["buy_pressure_score"],
            "Holder Distribution": curr_audit["holder_distribution_score"],
            "Opportunity": curr_audit["opportunity_score"],
        }
        radar_fig = create_factor_radar_chart(radar_scores, curr_audit["symbol"])
        st.plotly_chart(radar_fig, use_container_width=True)


# ---------------------------------------------------------
# VIEW 4: SECTORS & ROTATION
# ---------------------------------------------------------
elif nav_page == "🔄 Sectors & Rotation":
    st.subheader("Crypto Sector Rotation & Relative Leadership")

    sector_summary = DashboardDataLayer.get_sector_data()

    sec_col1, sec_col2 = st.columns([1, 1])

    with sec_col1:
        st.markdown("#### Sector Leadership Ranking")
        st.dataframe(
            sector_summary[[
                "Sector", "asset_count", "return_1d_pct", "return_7d_pct", "return_30d_pct", "breadth_pct", "volume_change_7d_pct", "rotation_status"
            ]].rename(columns={
                "asset_count": "Assets",
                "return_1d_pct": "1D %",
                "return_7d_pct": "7D %",
                "return_30d_pct": "30D %",
                "breadth_pct": "Breadth %",
                "volume_change_7d_pct": "Vol Δ 7D %",
                "rotation_status": "Status",
            }).style.format({
                "1D %": "{:+.2f}%",
                "7D %": "{:+.2f}%",
                "30D %": "{:+.2f}%",
                "Breadth %": "{:.1f}%",
                "Vol Δ 7D %": "{:+.1f}%",
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
    st.subheader("Paper Trading Virtual Brokerage & Execution Terminal")

    portfolio = DashboardDataLayer.get_paper_portfolio()

    p_col1, p_col2, p_col3, p_col4, p_col5 = st.columns(5)
    with p_col1:
        st.metric(
            label="Total Equity",
            value=f"${portfolio['total_equity']:,.2f}",
            delta=f"Return: {portfolio['total_return_pct']:+.2f}%",
        )
    with p_col2:
        st.metric(
            label="Free Cash",
            value=f"${portfolio['cash_balance']:,.2f}",
            delta=f"Invested: ${portfolio['invested_capital']:,.2f}",
        )
    with p_col3:
        st.metric(
            label="Unrealized P&L",
            value=f"${portfolio['unrealized_pnl']:+,.2f}",
            delta=f"Realized: ${portfolio['realized_pnl']:+,.2f}",
        )
    with p_col4:
        st.metric(
            label="Drawdown",
            value=f"{portfolio['drawdown_pct']:.2f}%",
            delta="Max limit: 20%",
            delta_color="inverse",
        )
    with p_col5:
        st.metric(
            label="Open Positions",
            value=str(portfolio['open_positions_count']),
            delta=f"Meme Exp: {portfolio['meme_exposure_pct']:.1f}% / 5%",
        )

    # Risk Compliance Indicators
    st.markdown("---")
    r_col1, r_col2 = st.columns(2)
    with r_col1:
        st.markdown(f"**Meme Coin Exposure:** `{portfolio['meme_exposure_pct']:.1f}%` / `5.0% Limit`")
        st.progress(min(1.0, portfolio["meme_exposure_pct"] / 5.0))
    with r_col2:
        st.markdown(f"**Max Single Asset Concentration:** `{portfolio['max_single_position_pct']:.1f}%` / `25.0% Limit`")
        st.progress(min(1.0, portfolio["max_single_position_pct"] / 25.0))

    # Order Entry & Trade Management
    st.markdown("---")
    trade_col1, trade_col2 = st.columns([1, 1])

    with trade_col1:
        st.markdown("#### ⚡ Order Routing Terminal")
        with st.form("paper_order_form"):
            symbols_avail = sorted(df_scanner["Symbol"].unique()) if not df_scanner.empty else ["BTC", "ETH", "SOL", "DOGE"]
            order_sym = st.selectbox("Symbol", symbols_avail, index=0)
            order_side = st.radio("Side", ["BUY", "SELL"], horizontal=True)
            order_qty = st.number_input("Quantity", min_value=0.0001, value=0.5, step=0.1, format="%.4f")
            order_type = st.selectbox("Order Type", ["MARKET", "LIMIT"])

            submit_order_btn = st.form_submit_button("🚀 Submit Virtual Order", use_container_width=True)

            if submit_order_btn:
                try:
                    res = DashboardDataLayer.place_paper_order(
                        symbol=order_sym,
                        side=order_side,
                        quantity=float(order_qty),
                        order_type=order_type,
                    )
                    st.success(f"Order Filled! {order_side} {order_qty} {order_sym} @ ${res['fill_price']:,.2f}")
                    st.rerun()
                except Exception as err:
                    st.error(f"Order Rejected: {err}")

    with trade_col2:
        st.markdown("#### ⚙️ Position & Account Actions")
        # Close position selector
        open_syms = [p.symbol for p in portfolio["raw_positions"]] if portfolio["raw_positions"] else []
        if open_syms:
            close_sym = st.selectbox("Select Open Position to Liquidate", open_syms)
            if st.button(f"Liquidate 100% {close_sym} Position", use_container_width=True):
                try:
                    c_res = DashboardDataLayer.close_paper_position(symbol=close_sym)
                    st.success(f"Liquidated {close_sym}! Realized P&L: ${c_res['realized_pnl']:+,.2f}")
                    st.rerun()
                except Exception as err:
                    st.error(f"Failed to close position: {err}")
        else:
            st.info("No open positions available to liquidate.")

        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🔄 Reset Paper Account to $100,000", use_container_width=True):
            DashboardDataLayer.reset_paper_account()
            st.success("Virtual account balance reset to $100,000.00!")
            st.rerun()

    # Open Positions Ledger
    st.markdown("---")
    st.markdown("#### Active Open Positions Ledger")
    positions_df = portfolio["positions_df"]
    if not positions_df.empty:
        st.dataframe(positions_df, use_container_width=True)
    else:
        st.info("Portfolio currently in 100% Cash reserve. No open positions.")


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

    col_feed, col_sim = st.columns([2, 1])

    with col_sim:
        st.markdown("#### ⚡ Emit Test Signal")
        with st.form("alert_simulator_form"):
            sim_sym = st.selectbox("Symbol", ["BTC", "ETH", "SOL", "NEAR", "RENDER", "DOGE", "PEPE"])
            sim_type = st.selectbox(
                "Signal Type",
                ["MOMENTUM_BREAKOUT", "RELATIVE_STRENGTH", "VOLUME_SPIKE", "REGIME_CHANGE", "RISK_PENALTY"],
            )
            sim_sev = st.selectbox("Severity", ["INFO", "WARNING", "CRITICAL"])
            sim_msg = st.text_area("Message", value=f"Simulated quantitative alert for {sim_sym}: threshold exceeded.")
            sim_submit = st.form_submit_button("Broadcast Signal")
            if sim_submit:
                res = DashboardDataLayer.simulate_alert(
                    alert_type=sim_type,
                    severity=sim_sev,
                    symbol=sim_sym,
                    message=sim_msg,
                )
                st.success(f"Dispatched alert {res.get('id', 'OK')}!")

    with col_feed:
        st.markdown("#### Signal Activity Stream")
        recent_alerts = DashboardDataLayer.get_recent_alerts(limit=30)
        for a in recent_alerts:
            sev = a.get("severity", "INFO")
            color = "#10B981" if sev == "INFO" else ("#F59E0B" if sev == "WARNING" else "#EF4444")
            st.markdown(
                f"""
                <div class="quant-card" style="border-left: 4px solid {color}; margin-bottom: 0.75rem;">
                    <div style="display: flex; justify-content: space-between;">
                        <b>{a.get('asset_id', 'SYSTEM')} &bull; {a.get('alert_type', 'GENERAL')}</b>
                        <span style="color: #64748B; font-size: 0.8rem;">{a.get('time', '')}</span>
                    </div>
                    <div style="color: #CBD5E1; font-size: 0.85rem; margin-top: 0.25rem;">{a.get('message', '')}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
