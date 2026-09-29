"""Streamlit Dashboard Entrypoint for Crypto Intelligence Platform."""

import streamlit as st

st.set_page_config(
    page_title="Crypto Intelligence Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for quantitative terminal aesthetic
st.markdown(
    """
    <style>
    .main {
        background-color: #0b0f19;
        color: #e2e8f0;
    }
    .metric-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 10px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }
    .regime-badge-risk-on {
        background-color: #065f46;
        color: #34d399;
        padding: 0.3rem 0.8rem;
        border-radius: 6px;
        font-weight: bold;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🏛️ Crypto Intelligence & Quantitative Research Lab")
st.caption("Multi-Factor Market Scanner • Bias-Free Backtesting • Paper Trading Broker")

st.markdown("---")

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Market Regime", value="NEUTRAL", delta="Regime Model V1")

with col2:
    st.metric(label="Paper Account Equity", value="$100,000.00", delta="+0.0%")

with col3:
    st.metric(label="Active Universe Assets", value="8 Monitored", delta="Milestone 1")

with col4:
    st.metric(label="System Mode", value="PAPER / RESEARCH", delta="Live Orders Disabled")

st.markdown("---")

st.subheader("Platform Status & Architecture Health")

st.info(
    "**System Operational**: Database models registered, async SQLAlchemy engine active, "
    "Redis cache adapter with memory fallback ready, and FastAPI endpoints online."
)

st.write(
    """
    ### Next Modules:
    - **Milestone 2**: CCXT Exchange Data Collectors & Validation Pipeline
    - **Milestone 3**: Polars Vectorized Feature Calculations (Momentum, Volatility, RS)
    - **Milestone 4**: Asset-Class Multi-Factor Scoring (Core, Altcoin, Meme)
    - **Milestone 5**: Interactive Live Scanner UI & Factor Explorer
    """
)
