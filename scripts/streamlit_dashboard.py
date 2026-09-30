"""Streamlit Dashboard for Day 13 Monitoring & LLMOps Lab.
Run in a separate virtualenv if streamlit is installed:
  streamlit run scripts/streamlit_dashboard.py
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"

try:
    import pandas as pd
    import plotly.graph_objects as go
    import streamlit as st
except ImportError:
    # Print instructions if dependencies not installed
    print("To run Streamlit dashboard, install: pip install streamlit pandas plotly")


def percentile(data: list[float | int], p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    k = (len(s) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(s[int(k)])
    d0 = s[int(f)] * (c - k)
    d1 = s[int(c)] * (k - f)
    return float(round(d0 + d1, 2))


def load_log_data() -> pd.DataFrame:
    records = []
    if LOG_PATH.exists():
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except Exception:
                    pass
    if not records:
        return pd.DataFrame()
    df = pd.DataFrame(records)
    if "ts" in df.columns:
        df["minute"] = df["ts"].str[:16] + "Z"
    return df


def render_dashboard():
    st.set_page_config(page_title="Day 13 LLMOps Dashboard", layout="wide")
    st.title("K4-L3B Day 13 Monitoring & LLMOps Dashboard")
    st.caption("Contract: config/dashboard.yaml | Data: data/logs.jsonl | Refresh: 30s | Window: 60m")

    df = load_log_data()
    if df.empty:
        st.warning("Chưa có dữ liệu log trong data/logs.jsonl.")
        return

    # Aggregate by minute
    grouped = df.groupby("minute")

    minutes = sorted(df["minute"].unique())
    p50_list, p95_list, p99_list, ttft_p95_list = [], [], [], []
    traffic_list, error_rate_list, retrieval_rate_list = [], [], []
    cost_min_list, cost_cum_list = [], []
    tokens_in_list, tokens_out_list = [], []
    quality_avg_list = []

    running_cost = 0.0

    for m in minutes:
        sub = df[df["minute"] == m]
        # Latency
        resp = sub[sub["event"] == "response_sent"]
        lats = resp["latency_ms"].dropna().tolist()
        ttfts = resp["ttft_ms"].dropna().tolist()
        p50_list.append(percentile(lats, 50))
        p95_list.append(percentile(lats, 95))
        p99_list.append(percentile(lats, 99))
        ttft_p95_list.append(percentile(ttfts, 95))

        # Traffic
        req_count = len(sub[sub["event"] == "request_received"])
        traffic_list.append(req_count)

        # Errors & retrieval
        fail_count = len(sub[sub["event"] == "request_failed"])
        err_rate = (fail_count / req_count * 100.0) if req_count > 0 else 0.0
        error_rate_list.append(err_rate)

        tools = sub[sub["tool_success"].notna()]
        succ_tools = len(tools[tools["tool_success"] == True])
        ret_rate = (succ_tools / len(tools) * 100.0) if len(tools) > 0 else 100.0
        retrieval_rate_list.append(ret_rate)

        # Cost
        c_min = resp["cost_usd"].dropna().sum()
        running_cost += c_min
        cost_min_list.append(c_min)
        cost_cum_list.append(running_cost)

        # Tokens
        t_in = resp["tokens_in"].dropna().sum()
        t_out = resp["tokens_out"].dropna().sum()
        tokens_in_list.append(t_in)
        tokens_out_list.append(t_out)

        # Quality
        q_avg = resp["quality_score"].dropna().mean()
        quality_avg_list.append(0.0 if math.isnan(q_avg) else q_avg)

    # Top metrics row
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    all_resp = df[df["event"] == "response_sent"]
    all_lats = all_resp["latency_ms"].dropna().tolist()
    c1.metric("P95 Latency", f"{percentile(all_lats, 95):.0f} ms", delta="<= 3000ms")
    c2.metric("Total Requests", len(df[df["event"] == "request_received"]))
    all_fails = len(df[df["event"] == "request_failed"])
    all_reqs = max(1, len(df[df["event"] == "request_received"]))
    c3.metric("Error Rate", f"{(all_fails / all_reqs * 100):.1f}%", delta="<= 2.0%")
    c4.metric("Retrieval Success", f"{(retrieval_rate_list[-1] if retrieval_rate_list else 100):.1f}%", delta=">= 90%")
    c5.metric("Total Cost", f"${running_cost:.4f}", delta="<= $2.50")
    c6.metric("Quality Avg", f"{all_resp['quality_score'].mean():.2f}", delta=">= 0.75")

    st.markdown("---")
    row1_c1, row1_c2 = st.columns(2)

    # Panel 1: Latency
    with row1_c1:
        st.subheader("1. Latency percentiles and TTFT (ms)")
        fig1 = go.Figure()
        fig1.add_trace(go.Scatter(x=minutes, y=p99_list, name="P99 Latency", line=dict(color="#f43f5e")))
        fig1.add_trace(go.Scatter(x=minutes, y=p95_list, name="P95 Latency", line=dict(color="#fbbf24", width=3)))
        fig1.add_trace(go.Scatter(x=minutes, y=p50_list, name="P50 Latency", line=dict(color="#38bdf8")))
        fig1.add_trace(go.Scatter(x=minutes, y=ttft_p95_list, name="TTFT P95", line=dict(color="#34d399", dash="dot")))
        fig1.add_hline(y=3000, line_dash="dash", line_color="red", annotation_text="P95 Threshold (3000ms)")
        fig1.update_layout(yaxis_title="ms", margin=dict(l=20, r=20, t=30, b=20), height=320)
        st.plotly_chart(fig1, use_container_width=True)

    # Panel 2: Traffic
    with row1_c2:
        st.subheader("2. Request traffic (req/min)")
        fig2 = go.Figure()
        fig2.add_trace(go.Bar(x=minutes, y=traffic_list, name="Requests", marker_color="#38bdf8"))
        fig2.add_hline(y=1, line_dash="dash", line_color="red", annotation_text="Threshold (1 req/min)")
        fig2.update_layout(yaxis_title="requests_per_minute", margin=dict(l=20, r=20, t=30, b=20), height=320)
        st.plotly_chart(fig2, use_container_width=True)

    row2_c1, row2_c2 = st.columns(2)

    # Panel 3: Errors
    with row2_c1:
        st.subheader("3. Error rate and retrieval success (%)")
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(x=minutes, y=error_rate_list, name="Error Rate %", line=dict(color="#f43f5e", width=2)))
        fig3.add_trace(go.Scatter(x=minutes, y=retrieval_rate_list, name="Retrieval Success %", line=dict(color="#34d399", width=2)))
        fig3.add_hline(y=2, line_dash="dash", line_color="red", annotation_text="Error Rate Threshold (2%)")
        fig3.update_layout(yaxis_title="percent", yaxis=dict(range=[0, 100]), margin=dict(l=20, r=20, t=30, b=20), height=320)
        st.plotly_chart(fig3, use_container_width=True)

    # Panel 4: Cost
    with row2_c2:
        st.subheader("4. Cost over time (USD)")
        fig4 = go.Figure()
        fig4.add_trace(go.Scatter(x=minutes, y=cost_cum_list, name="Cumulative Cost", line=dict(color="#c084fc", width=2)))
        fig4.add_trace(go.Bar(x=minutes, y=cost_min_list, name="Cost per min", marker_color="#818cf8"))
        fig4.add_hline(y=2.5, line_dash="dash", line_color="red", annotation_text="Budget Threshold ($2.50)")
        fig4.update_layout(yaxis_title="usd", margin=dict(l=20, r=20, t=30, b=20), height=320)
        st.plotly_chart(fig4, use_container_width=True)

    row3_c1, row3_c2 = st.columns(2)

    # Panel 5: Tokens
    with row3_c1:
        st.subheader("5. Input and output tokens")
        fig5 = go.Figure()
        fig5.add_trace(go.Bar(x=minutes, y=tokens_in_list, name="Input Tokens", marker_color="#38bdf8"))
        fig5.add_trace(go.Bar(x=minutes, y=tokens_out_list, name="Output Tokens", marker_color="#818cf8"))
        fig5.add_hline(y=50000, line_dash="dash", line_color="red", annotation_text="Threshold (50,000 tokens)")
        fig5.update_layout(barmode="stack", yaxis_title="tokens", margin=dict(l=20, r=20, t=30, b=20), height=320)
        st.plotly_chart(fig5, use_container_width=True)

    # Panel 6: Quality
    with row3_c2:
        st.subheader("6. Quality proxy (score 0..1)")
        fig6 = go.Figure()
        fig6.add_trace(go.Scatter(x=minutes, y=quality_avg_list, name="Quality Score (mean)", line=dict(color="#34d399", width=2)))
        fig6.add_hline(y=0.75, line_dash="dash", line_color="red", annotation_text="Quality Min Threshold (0.75)")
        fig6.update_layout(yaxis_title="score_0_to_1", yaxis=dict(range=[0, 1]), margin=dict(l=20, r=20, t=30, b=20), height=320)
        st.plotly_chart(fig6, use_container_width=True)


if __name__ == "__main__":
    render_dashboard()
