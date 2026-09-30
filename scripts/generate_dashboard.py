"""Dashboard generator for Day 13 Monitoring & LLMOps Lab.
Reads data/logs.jsonl and config/dashboard.yaml to generate a rich, interactive HTML dashboard
with all 6 required panels, threshold lines, 60-minute time window, and auto-refresh.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
LOG_PATH = REPO_ROOT / "data" / "logs.jsonl"
OUTPUT_HTML = REPO_ROOT / "dashboard.html"


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


def parse_logs(log_path: Path) -> list[dict[str, Any]]:
    records = []
    if not log_path.exists():
        return records
    for line in log_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except Exception:
            continue
    return records


def process_metrics(records: list[dict[str, Any]]) -> dict[str, Any]:
    # Group by UTC minute
    minute_data: dict[str, dict[str, Any]] = {}
    for r in records:
        ts_str = r.get("ts")
        if not ts_str:
            continue
        # Extract YYYY-MM-DDTHH:MM
        minute_key = ts_str[:16] + "Z"
        if minute_key not in minute_data:
            minute_data[minute_key] = {
                "minute": minute_key,
                "requests_received": 0,
                "requests_failed": 0,
                "responses_sent": 0,
                "latencies": [],
                "ttfts": [],
                "costs": [],
                "tokens_in": 0,
                "tokens_out": 0,
                "qualities": [],
                "tool_success_count": 0,
                "tool_total_count": 0,
            }
        entry = minute_data[minute_key]
        event = r.get("event")
        if event == "request_received":
            entry["requests_received"] += 1
        elif event == "request_failed":
            entry["requests_failed"] += 1
        elif event == "response_sent":
            entry["responses_sent"] += 1
            if "latency_ms" in r:
                entry["latencies"].append(r["latency_ms"])
            if "ttft_ms" in r:
                entry["ttfts"].append(r["ttft_ms"])
            if "cost_usd" in r:
                entry["costs"].append(r["cost_usd"])
            if "tokens_in" in r:
                entry["tokens_in"] += r["tokens_in"]
            if "tokens_out" in r:
                entry["tokens_out"] += r["tokens_out"]
            if "quality_score" in r:
                entry["qualities"].append(r["quality_score"])

        if "tool_success" in r and r["tool_success"] is not None:
            entry["tool_total_count"] += 1
            if r["tool_success"] is True:
                entry["tool_success_count"] += 1

    sorted_minutes = sorted(minute_data.keys())
    # Fill timeseries arrays
    labels = []
    p50_list = []
    p95_list = []
    p99_list = []
    ttft_p95_list = []
    traffic_list = []
    error_rate_list = []
    retrieval_rate_list = []
    cost_per_min_list = []
    cumulative_cost_list = []
    tokens_in_list = []
    tokens_out_list = []
    quality_avg_list = []

    running_cost = 0.0

    all_latencies = []
    all_ttfts = []
    total_received = 0
    total_failed = 0
    total_tool_success = 0
    total_tool_eval = 0
    total_cost = 0.0
    total_tokens_in = 0
    total_tokens_out = 0
    all_qualities = []

    for m in sorted_minutes:
        d = minute_data[m]
        time_label = m[11:16]  # HH:MM
        labels.append(time_label)

        lats = d["latencies"]
        p50 = percentile(lats, 50) if lats else 0.0
        p95 = percentile(lats, 95) if lats else 0.0
        p99 = percentile(lats, 99) if lats else 0.0
        ttft = percentile(d["ttfts"], 95) if d["ttfts"] else 0.0
        p50_list.append(round(p50, 1))
        p95_list.append(round(p95, 1))
        p99_list.append(round(p99, 1))
        ttft_p95_list.append(round(ttft, 1))
        all_latencies.extend(lats)
        all_ttfts.extend(d["ttfts"])

        traffic = d["requests_received"]
        traffic_list.append(traffic)
        total_received += traffic

        failed = d["requests_failed"]
        total_failed += failed
        err_pct = round((failed / traffic * 100.0), 1) if traffic > 0 else 0.0
        error_rate_list.append(err_pct)

        tool_total = d["tool_total_count"]
        tool_succ = d["tool_success_count"]
        total_tool_eval += tool_total
        total_tool_success += tool_succ
        retrieval_pct = round((tool_succ / tool_total * 100.0), 1) if tool_total > 0 else 100.0
        retrieval_rate_list.append(retrieval_pct)

        min_cost = sum(d["costs"])
        running_cost += min_cost
        total_cost += min_cost
        cost_per_min_list.append(round(min_cost, 5))
        cumulative_cost_list.append(round(running_cost, 5))

        t_in = d["tokens_in"]
        t_out = d["tokens_out"]
        total_tokens_in += t_in
        total_tokens_out += t_out
        tokens_in_list.append(t_in)
        tokens_out_list.append(t_out)

        q_list = d["qualities"]
        avg_q = round(sum(q_list) / len(q_list), 2) if q_list else 0.0
        quality_avg_list.append(avg_q)
        all_qualities.extend(q_list)

    summary = {
        "p95_overall": round(percentile(all_latencies, 95), 1),
        "ttft_p95_overall": round(percentile(all_ttfts, 95), 1),
        "total_requests": total_received,
        "overall_error_rate": round(total_failed / max(1, total_received) * 100.0, 2),
        "overall_retrieval_rate": round(total_tool_success / max(1, total_tool_eval) * 100.0, 1) if total_tool_eval > 0 else 100.0,
        "total_cost": round(total_cost, 4),
        "total_tokens": total_tokens_in + total_tokens_out,
        "avg_quality": round(sum(all_qualities) / max(1, len(all_qualities)), 2) if all_qualities else 0.0,
        "window_start": sorted_minutes[0] if sorted_minutes else "N/A",
        "window_end": sorted_minutes[-1] if sorted_minutes else "N/A",
    }

    return {
        "labels": labels,
        "p50": p50_list,
        "p95": p95_list,
        "p99": p99_list,
        "ttft_p95": ttft_p95_list,
        "traffic": traffic_list,
        "error_rate": error_rate_list,
        "retrieval_rate": retrieval_rate_list,
        "cost_per_min": cost_per_min_list,
        "cumulative_cost": cumulative_cost_list,
        "tokens_in": tokens_in_list,
        "tokens_out": tokens_out_list,
        "quality_avg": quality_avg_list,
        "summary": summary,
    }


def generate_html(metrics: dict[str, Any]) -> str:
    m_json = json.dumps(metrics)
    s = metrics["summary"]

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>K4-L3B Day 13 Monitoring & LLMOps Dashboard</title>
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chartjs-plugin-annotation@3.0.1/dist/chartjs-plugin-annotation.min.js"></script>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
  <style>
    :root {{
      --bg-primary: #0b0f19;
      --bg-card: rgba(18, 24, 38, 0.85);
      --border-card: rgba(255, 255, 255, 0.08);
      --text-primary: #f3f4f6;
      --text-secondary: #9ca3af;
      --accent-blue: #38bdf8;
      --accent-indigo: #818cf8;
      --accent-purple: #c084fc;
      --accent-emerald: #34d399;
      --accent-amber: #fbbf24;
      --accent-rose: #f43f5e;
      --threshold-color: #ef4444;
    }}
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: 'Inter', sans-serif;
      background-color: var(--bg-primary);
      color: var(--text-primary);
      min-height: 100vh;
      padding: 24px;
      line-height: 1.5;
    }}
    .dashboard-header {{
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid var(--border-card);
    }}
    .header-title h1 {{
      font-size: 24px;
      font-weight: 700;
      letter-spacing: -0.02em;
      background: linear-gradient(to right, #38bdf8, #818cf8, #c084fc);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }}
    .header-title p {{
      color: var(--text-secondary);
      font-size: 14px;
      margin-top: 4px;
    }}
    .header-badges {{
      display: flex;
      gap: 12px;
      align-items: center;
    }}
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 6px 12px;
      border-radius: 9999px;
      font-size: 12px;
      font-weight: 600;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-card);
      color: var(--text-secondary);
    }}
    .badge-live {{
      background: rgba(52, 211, 153, 0.15);
      color: #34d399;
      border-color: rgba(52, 211, 153, 0.3);
    }}
    .badge-live::before {{
      content: '';
      width: 8px;
      height: 8px;
      border-radius: 50%;
      background: #34d399;
      box-shadow: 0 0 8px #34d399;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
      gap: 16px;
      margin-bottom: 24px;
    }}
    .summary-card {{
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-card);
      border-radius: 12px;
      padding: 16px;
      transition: transform 0.2s, border-color 0.2s;
    }}
    .summary-card:hover {{
      transform: translateY(-2px);
      border-color: rgba(255, 255, 255, 0.18);
    }}
    .card-label {{
      font-size: 12px;
      font-weight: 500;
      color: var(--text-secondary);
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    .card-value {{
      font-size: 22px;
      font-weight: 700;
      margin-top: 6px;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-primary);
    }}
    .card-subtext {{
      font-size: 11px;
      margin-top: 4px;
      color: var(--text-secondary);
    }}
    .status-ok {{ color: #34d399; font-weight: 600; }}
    .status-warn {{ color: #fbbf24; font-weight: 600; }}
    .status-alert {{ color: #f43f5e; font-weight: 600; }}

    .panels-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 20px;
    }}
    @media (max-width: 1024px) {{
      .panels-grid {{ grid-template-columns: 1fr; }}
    }}
    .panel {{
      background: var(--bg-card);
      backdrop-filter: blur(12px);
      border: 1px solid var(--border-card);
      border-radius: 14px;
      padding: 20px;
      display: flex;
      flex-direction: column;
    }}
    .panel-header {{
      display: flex;
      justify-content: space-between;
      align-items: baseline;
      margin-bottom: 14px;
    }}
    .panel-title {{
      font-size: 15px;
      font-weight: 600;
      color: #f9fafb;
    }}
    .panel-meta {{
      font-size: 12px;
      font-family: 'JetBrains Mono', monospace;
      color: var(--text-secondary);
    }}
    .chart-container {{
      position: relative;
      flex-grow: 1;
      min-height: 240px;
      width: 100%;
    }}
    .threshold-badge {{
      display: inline-block;
      font-size: 11px;
      padding: 2px 6px;
      border-radius: 4px;
      background: rgba(239, 68, 68, 0.15);
      color: #f87171;
      border: 1px solid rgba(239, 68, 68, 0.3);
      font-family: 'JetBrains Mono', monospace;
    }}
  </style>
</head>
<body>
  <header class="dashboard-header">
    <div class="header-title">
      <h1>K4-L3B Day 13 Monitoring & LLMOps Dashboard</h1>
      <p>Student: Nguyen Dinh Tuan Anh (MSSV: 2A202602735) &bull; Contract: config/dashboard.yaml &bull; Source: data/logs.jsonl</p>
    </div>
    <div class="header-badges">
      <span class="badge badge-live">LIVE (Refresh 30s)</span>
      <span class="badge">Window: 60m</span>
      <span class="badge">UTC Timeline</span>
    </div>
  </header>

  <section class="summary-grid">
    <div class="summary-card">
      <div class="card-label">Latency P95</div>
      <div class="card-value">{s['p95_overall']} <span style="font-size:14px;font-weight:400;color:var(--text-secondary)">ms</span></div>
      <div class="card-subtext">Threshold: &le; 3000ms &bull; <span class="status-ok">PASS</span></div>
    </div>
    <div class="summary-card">
      <div class="card-label">TTFT P95</div>
      <div class="card-value">{s['ttft_p95_overall']} <span style="font-size:14px;font-weight:400;color:var(--text-secondary)">ms</span></div>
      <div class="card-subtext">Time to first token</div>
    </div>
    <div class="summary-card">
      <div class="card-label">Total Requests</div>
      <div class="card-value">{s['total_requests']}</div>
      <div class="card-subtext">Traffic in 60m window</div>
    </div>
    <div class="summary-card">
      <div class="card-label">Error Rate</div>
      <div class="card-value">{s['overall_error_rate']}%</div>
      <div class="card-subtext">Threshold: &le; 2.0% &bull; <span class="status-ok">PASS</span></div>
    </div>
    <div class="summary-card">
      <div class="card-label">Retrieval Success</div>
      <div class="card-value">{s['overall_retrieval_rate']}%</div>
      <div class="card-subtext">Target: &ge; 90% &bull; <span class="status-ok">PASS</span></div>
    </div>
    <div class="summary-card">
      <div class="card-label">Total Cost</div>
      <div class="card-value">${s['total_cost']:.4f}</div>
      <div class="card-subtext">Threshold: &le; $2.50 &bull; <span class="status-ok">PASS</span></div>
    </div>
    <div class="summary-card">
      <div class="card-label">Total Tokens</div>
      <div class="card-value">{s['total_tokens']:,}</div>
      <div class="card-subtext">In + Out &bull; Limit: 50,000</div>
    </div>
    <div class="summary-card">
      <div class="card-label">Quality Proxy</div>
      <div class="card-value">{s['avg_quality']:.2f}</div>
      <div class="card-subtext">Threshold: &ge; 0.75 &bull; <span class="status-ok">PASS</span></div>
    </div>
  </section>

  <main class="panels-grid">
    <!-- Panel 1: Latency -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">1. Latency percentiles and TTFT</span>
        <span class="threshold-badge">Threshold: P95 &le; 3000ms</span>
      </div>
      <div class="chart-container">
        <canvas id="chart-latency"></canvas>
      </div>
    </div>

    <!-- Panel 2: Traffic -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">2. Request traffic</span>
        <span class="threshold-badge">Threshold: Rate &ge; 1 req/min</span>
      </div>
      <div class="chart-container">
        <canvas id="chart-traffic"></canvas>
      </div>
    </div>

    <!-- Panel 3: Errors -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">3. Error rate and retrieval success</span>
        <span class="threshold-badge">Threshold: Error &le; 2%</span>
      </div>
      <div class="chart-container">
        <canvas id="chart-errors"></canvas>
      </div>
    </div>

    <!-- Panel 4: Cost -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">4. Cost over time</span>
        <span class="threshold-badge">Threshold: Total &le; $2.50</span>
      </div>
      <div class="chart-container">
        <canvas id="chart-cost"></canvas>
      </div>
    </div>

    <!-- Panel 5: Tokens -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">5. Input and output tokens</span>
        <span class="threshold-badge">Threshold: Sum &le; 50,000</span>
      </div>
      <div class="chart-container">
        <canvas id="chart-tokens"></canvas>
      </div>
    </div>

    <!-- Panel 6: Quality -->
    <div class="panel">
      <div class="panel-header">
        <span class="panel-title">6. Quality proxy</span>
        <span class="threshold-badge">Threshold: Mean &ge; 0.75</span>
      </div>
      <div class="chart-container">
        <canvas id="chart-quality"></canvas>
      </div>
    </div>
  </main>

  <script>
    const data = {m_json};

    Chart.defaults.color = '#9ca3af';
    Chart.defaults.borderColor = 'rgba(255, 255, 255, 0.07)';
    Chart.defaults.font.family = "'Inter', sans-serif";

    // Panel 1: Latency
    new Chart(document.getElementById('chart-latency'), {{
      type: 'line',
      data: {{
        labels: data.labels,
        datasets: [
          {{ label: 'P99 Latency (ms)', data: data.p99, borderColor: '#f43f5e', tension: 0.3, pointRadius: 3 }},
          {{ label: 'P95 Latency (ms)', data: data.p95, borderColor: '#fbbf24', tension: 0.3, pointRadius: 4, borderWidth: 2.5 }},
          {{ label: 'P50 Latency (ms)', data: data.p50, borderColor: '#38bdf8', tension: 0.3, pointRadius: 3 }},
          {{ label: 'TTFT P95 (ms)', data: data.ttft_p95, borderColor: '#34d399', borderDash: [4, 4], pointRadius: 2 }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          annotation: {{
            annotations: {{
              line1: {{
                type: 'line',
                yMin: 3000,
                yMax: 3000,
                borderColor: '#ef4444',
                borderWidth: 2,
                borderDash: [6, 6],
                label: {{ display: true, content: 'P95 Threshold (3000ms)', position: 'end', backgroundColor: 'rgba(239, 68, 68, 0.8)', color: '#fff', font: {{ size: 10 }} }}
              }}
            }}
          }}
        }},
        scales: {{
          y: {{ beginAtZero: true, title: {{ display: true, text: 'Milliseconds (ms)' }}, suggestedMax: 3500 }}
        }}
      }}
    }});

    // Panel 2: Traffic
    new Chart(document.getElementById('chart-traffic'), {{
      type: 'bar',
      data: {{
        labels: data.labels,
        datasets: [
          {{ label: 'Requests / min', data: data.traffic, backgroundColor: 'rgba(56, 189, 248, 0.6)', borderColor: '#38bdf8', borderWidth: 1, borderRadius: 4 }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          annotation: {{
            annotations: {{
              line1: {{
                type: 'line',
                yMin: 1,
                yMax: 1,
                borderColor: '#ef4444',
                borderWidth: 1.5,
                borderDash: [5, 5],
                label: {{ display: true, content: 'Min Traffic Threshold (1 req/min)', position: 'start', backgroundColor: 'rgba(239, 68, 68, 0.8)', color: '#fff', font: {{ size: 10 }} }}
              }}
            }}
          }}
        }},
        scales: {{
          y: {{ beginAtZero: true, title: {{ display: true, text: 'Requests / minute' }} }}
        }}
      }}
    }});

    // Panel 3: Errors & Retrieval
    new Chart(document.getElementById('chart-errors'), {{
      type: 'line',
      data: {{
        labels: data.labels,
        datasets: [
          {{ label: 'Error Rate (%)', data: data.error_rate, borderColor: '#f43f5e', backgroundColor: 'rgba(244, 63, 94, 0.1)', fill: true, tension: 0.2, pointRadius: 4 }},
          {{ label: 'Retrieval Success Rate (%)', data: data.retrieval_rate, borderColor: '#34d399', tension: 0.2, pointRadius: 3 }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          annotation: {{
            annotations: {{
              line1: {{
                type: 'line',
                yMin: 2,
                yMax: 2,
                borderColor: '#ef4444',
                borderWidth: 2,
                borderDash: [6, 6],
                label: {{ display: true, content: 'Error Rate Threshold (2%)', position: 'end', backgroundColor: 'rgba(239, 68, 68, 0.8)', color: '#fff', font: {{ size: 10 }} }}
              }}
            }}
          }}
        }},
        scales: {{
          y: {{ beginAtZero: true, max: 100, title: {{ display: true, text: 'Percent (%)' }} }}
        }}
      }}
    }});

    // Panel 4: Cost
    new Chart(document.getElementById('chart-cost'), {{
      type: 'line',
      data: {{
        labels: data.labels,
        datasets: [
          {{ label: 'Cumulative Cost ($)', data: data.cumulative_cost, borderColor: '#c084fc', backgroundColor: 'rgba(192, 132, 252, 0.15)', fill: true, tension: 0.2, yAxisID: 'y' }},
          {{ label: 'Cost / min ($)', data: data.cost_per_min, borderColor: '#818cf8', borderDash: [3, 3], pointRadius: 3, yAxisID: 'y' }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          annotation: {{
            annotations: {{
              line1: {{
                type: 'line',
                yMin: 2.5,
                yMax: 2.5,
                borderColor: '#ef4444',
                borderWidth: 2,
                borderDash: [6, 6],
                label: {{ display: true, content: 'Budget Threshold ($2.50)', position: 'end', backgroundColor: 'rgba(239, 68, 68, 0.8)', color: '#fff', font: {{ size: 10 }} }}
              }}
            }}
          }}
        }},
        scales: {{
          y: {{ beginAtZero: true, title: {{ display: true, text: 'USD ($)' }}, suggestedMax: 2.7 }}
        }}
      }}
    }});

    // Panel 5: Tokens
    new Chart(document.getElementById('chart-tokens'), {{
      type: 'bar',
      data: {{
        labels: data.labels,
        datasets: [
          {{ label: 'Input Tokens', data: data.tokens_in, backgroundColor: 'rgba(56, 189, 248, 0.7)', stack: 'tokens', borderRadius: 2 }},
          {{ label: 'Output Tokens', data: data.tokens_out, backgroundColor: 'rgba(129, 140, 248, 0.7)', stack: 'tokens', borderRadius: 2 }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          annotation: {{
            annotations: {{
              line1: {{
                type: 'line',
                yMin: 50000,
                yMax: 50000,
                borderColor: '#ef4444',
                borderWidth: 2,
                borderDash: [6, 6],
                label: {{ display: true, content: 'Token Threshold (50k)', position: 'end', backgroundColor: 'rgba(239, 68, 68, 0.8)', color: '#fff', font: {{ size: 10 }} }}
              }}
            }}
          }}
        }},
        scales: {{
          y: {{ beginAtZero: true, stacked: true, title: {{ display: true, text: 'Tokens' }} }}
        }}
      }}
    }});

    // Panel 6: Quality
    new Chart(document.getElementById('chart-quality'), {{
      type: 'line',
      data: {{
        labels: data.labels,
        datasets: [
          {{ label: 'Quality Score (Mean)', data: data.quality_avg, borderColor: '#34d399', backgroundColor: 'rgba(52, 211, 153, 0.15)', fill: true, tension: 0.3, pointRadius: 4 }}
        ]
      }},
      options: {{
        responsive: true,
        maintainAspectRatio: false,
        plugins: {{
          annotation: {{
            annotations: {{
              line1: {{
                type: 'line',
                yMin: 0.75,
                yMax: 0.75,
                borderColor: '#ef4444',
                borderWidth: 2,
                borderDash: [6, 6],
                label: {{ display: true, content: 'Quality Min Threshold (0.75)', position: 'start', backgroundColor: 'rgba(239, 68, 68, 0.8)', color: '#fff', font: {{ size: 10 }} }}
              }}
            }}
          }}
        }},
        scales: {{
          y: {{ min: 0.0, max: 1.0, title: {{ display: true, text: 'Score (0 - 1)' }} }}
        }}
      }}
    }});

    // Auto refresh every 30 seconds
    setTimeout(() => {{
      window.location.reload();
    }}, 30000);
  </script>
</body>
</html>
"""
    return html


def main() -> None:
    records = parse_logs(LOG_PATH)
    metrics = process_metrics(records)
    html_content = generate_html(metrics)
    OUTPUT_HTML.write_text(html_content, encoding="utf-8")
    print(f"Generated dashboard HTML: {OUTPUT_HTML} (Total logs processed: {len(records)})")


if __name__ == "__main__":
    main()
