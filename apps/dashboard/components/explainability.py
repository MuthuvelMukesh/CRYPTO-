"""Explainability Card component showing linear factor breakdown and risk deductions."""

import streamlit as st


def render_explainability_card(asset_data: dict) -> None:
    """Render a transparent factor contribution and risk penalty breakdown card."""
    symbol = asset_data.get("Symbol", "ASSET")
    name = asset_data.get("Name", "")
    opp_score = asset_data.get("Opportunity", 50.0)
    model = asset_data.get("Model", "ALTCOIN")
    breakdown = asset_data.get("Breakdown", {})

    st.markdown(
        f"""
        <div class="quant-card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem;">
                <div>
                    <h3 style="margin: 0; color: #F8FAFC;">{name} ({symbol})</h3>
                    <span style="color: #64748B; font-size: 0.85rem;">Scoring Model: <b>{model}</b></span>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 2rem; font-weight: 800; color: #10B981; font-family: 'JetBrains Mono', monospace;">
                        {opp_score:.1f}
                    </div>
                    <span style="color: #94A3B8; font-size: 0.8rem; text-transform: uppercase; font-weight: 600;">Opportunity Score</span>
                </div>
            </div>
            <div style="border-top: 1px solid rgba(255,255,255,0.08); padding-top: 0.8rem; margin-bottom: 0.8rem;">
                <div style="color: #94A3B8; font-size: 0.85rem; font-weight: 600; margin-bottom: 0.5rem; text-transform: uppercase;">
                    Additive Factor Contribution Breakdown
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Render factor contributions
    cols = st.columns(3)
    idx = 0
    for factor_key, comp in breakdown.items():
        if factor_key.startswith("_"):
            continue
        if isinstance(comp, dict):
            fname = comp.get("name", factor_key).replace("_", " ").title()
            fscore = comp.get("score", 50.0)
            fweight = comp.get("weight", 0.0)
            fcontrib = comp.get("contribution", 0.0)

            col = cols[idx % 3]
            with col:
                st.markdown(
                    f"""
                    <div style="background: rgba(30, 41, 59, 0.4); border-radius: 8px; padding: 0.75rem; margin-bottom: 0.5rem; border: 1px solid rgba(255,255,255,0.05);">
                        <div style="display: flex; justify-content: space-between; font-size: 0.85rem; color: #CBD5E1;">
                            <b>{fname}</b>
                            <span style="color: #10B981; font-weight: 700;">+{fcontrib:.1f} pts</span>
                        </div>
                        <div style="font-size: 0.75rem; color: #64748B; margin-top: 0.2rem;">
                            Raw Score: {fscore:.0f}/100 &bull; Weight: {fweight*100:.0f}%
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )
            idx += 1

    # Render Penalties & Risk Adjustments
    penalties = breakdown.get("_penalties", [])
    if penalties:
        st.markdown(
            """
            <div style="margin-top: 0.5rem; color: #F87171; font-size: 0.85rem; font-weight: 600; text-transform: uppercase;">
                Active Risk Penalty Deductions
            </div>
            """,
            unsafe_allow_html=True,
        )
        for p in penalties:
            st.markdown(
                f"""
                <div style="background: rgba(239, 68, 68, 0.1); border-left: 3px solid #EF4444; padding: 0.5rem 0.8rem; border-radius: 4px; margin-bottom: 0.4rem; font-size: 0.85rem; color: #FCA5A5;">
                    <b>{p.get('flag')}</b>: <span style="font-weight: 700;">{p.get('deduction'):+.1f} pts</span> &mdash; {p.get('reason')}
                </div>
                """,
                unsafe_allow_html=True,
            )
