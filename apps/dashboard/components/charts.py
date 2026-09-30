"""Plotly visualization components for the quantitative dashboard."""

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def create_candlestick_chart(df: pd.DataFrame, symbol: str) -> go.Figure:
    """Create interactive multi-pane candlestick chart with EMAs and volume."""
    if df.empty:
        fig = go.Figure()
        fig.add_annotation(text="No candlestick data available", showarrow=False, font={"size": 16, "color": "#94A3B8"})
        fig.update_layout(paper_bgcolor="#0B0E17", plot_bgcolor="#0F1422")
        return fig

    # Calculate EMAs
    df = df.copy()
    df["EMA20"] = df["close"].ewm(span=20, adjust=False).mean()
    df["EMA50"] = df["close"].ewm(span=50, adjust=False).mean()

    # Subplot with 2 rows: Candle (row 1) and Volume (row 2)
    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
    )

    # 1. Candlestick
    fig.add_trace(
        go.Candlestick(
            x=df["time"],
            open=df["open"],
            high=df["high"],
            low=df["low"],
            close=df["close"],
            name="Price",
            increasing_line_color="#10B981",
            decreasing_line_color="#EF4444",
        ),
        row=1,
        col=1,
    )

    # 2. EMAs
    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["EMA20"],
            name="EMA 20",
            line={"color": "#F59E0B", "width": 1.5},
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Scatter(
            x=df["time"],
            y=df["EMA50"],
            name="EMA 50",
            line={"color": "#6366F1", "width": 1.5},
        ),
        row=1,
        col=1,
    )

    # 3. Volume Bars
    vol_colors = [
        "#10B981" if c >= o else "#EF4444"
        for c, o in zip(df["close"], df["open"], strict=False)
    ]
    fig.add_trace(
        go.Bar(
            x=df["time"],
            y=df["volume"],
            name="Volume",
            marker_color=vol_colors,
            opacity=0.7,
        ),
        row=2,
        col=1,
    )

    fig.update_layout(
        title=f"<b>{symbol}/USDT</b> Candlestick & Volume Dynamics",
        paper_bgcolor="#0B0E17",
        plot_bgcolor="#0F1422",
        font={"family": "Outfit, sans-serif", "color": "#94A3B8"},
        xaxis={"gridcolor": "#1E293B", "rangeslider": {"visible": False}},
        yaxis={"gridcolor": "#1E293B", "title": "Price (USDT)"},
        yaxis2={"gridcolor": "#1E293B", "title": "Volume"},
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
        legend={"orientation": "h", "y": 1.05, "x": 0.5, "xanchor": "center"},
        height=520,
    )

    return fig


def create_factor_radar_chart(scores: dict[str, float], symbol: str) -> go.Figure:
    """Create radar/spider chart of 0-100 multi-factor scores."""
    categories = [
        "Momentum",
        "Relative Strength",
        "Trend",
        "Volume",
        "Liquidity",
        "Quality",
        "Risk Factor",
    ]
    values = [
        scores.get("Momentum", 50.0),
        scores.get("Relative Strength", 50.0),
        scores.get("Trend", 50.0),
        scores.get("Volume", 50.0),
        scores.get("Liquidity", 50.0),
        scores.get("Quality", 50.0),
        scores.get("Risk", 50.0),
    ]

    # Close the radar loop
    categories += [categories[0]]
    values += [values[0]]

    fig = go.Figure()

    fig.add_trace(
        go.Scatterpolar(
            r=values,
            theta=categories,
            fill="toself",
            name=symbol,
            fillcolor="rgba(99, 102, 241, 0.25)",
            line={"color": "#6366F1", "width": 2},
        )
    )

    fig.update_layout(
        polar={
            "bgcolor": "#0F1422",
            "radialaxis": {
                "visible": True,
                "range": [0, 100],
                "gridcolor": "#1E293B",
                "tickfont": {"color": "#64748B"},
            },
            "angularaxis": {
                "gridcolor": "#1E293B",
                "tickfont": {"color": "#E2E8F0", "size": 11},
            },
        },
        paper_bgcolor="#0B0E17",
        title={"text": f"<b>{symbol}</b> Quantitative Factor Radar", "x": 0.5, "xanchor": "center"},
        font={"family": "Outfit, sans-serif", "color": "#94A3B8"},
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
        height=380,
    )

    return fig


def create_sector_rotation_chart(sector_df: pd.DataFrame) -> go.Figure:
    """Create 2D sector rotation scatter plot (7D Return vs 1D Return)."""
    fig = go.Figure()

    if sector_df.empty:
        return fig

    # Quadrant background markers
    fig.add_hline(y=0, line_dash="dash", line_color="#334155")
    fig.add_vline(x=0, line_dash="dash", line_color="#334155")

    for _, row in sector_df.iterrows():
        color = "#10B981" if row["rotation_status"] in ("LEADING", "ACCELERATING") else "#EF4444"
        fig.add_trace(
            go.Scatter(
                x=[row["return_7d"] * 100.0],
                y=[row["return_1d"] * 100.0],
                mode="markers+text",
                name=row["sector_name"],
                text=[row["sector_name"]],
                textposition="top center",
                marker={
                    "size": 16,
                    "color": color,
                    "opacity": 0.85,
                    "line": {"width": 1.5, "color": "#FFFFFF"},
                },
            )
        )

    fig.update_layout(
        title="<b>Sector Rotation Dynamics</b> (7D vs 1D Return %)",
        paper_bgcolor="#0B0E17",
        plot_bgcolor="#0F1422",
        font={"family": "Outfit, sans-serif", "color": "#94A3B8"},
        xaxis={"gridcolor": "#1E293B", "title": "7-Day Return (%)"},
        yaxis={"gridcolor": "#1E293B", "title": "1-Day Return (%)"},
        margin={"l": 40, "r": 40, "t": 60, "b": 40},
        showlegend=False,
        height=400,
    )

    return fig
