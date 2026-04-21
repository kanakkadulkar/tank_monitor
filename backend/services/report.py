"""
services/report.py
Generates a dynamic HTML report from live analysis data.
Serves as the /report endpoint content.
"""

from datetime import datetime


def generate_report_html(analysis: dict, db_stats: dict = None) -> str:
    """
    Build a self-contained HTML report from the current analysis state.

    Parameters
    ----------
    analysis : dict from analyze_tank_data()
    db_stats : optional dict with {total_readings, total_anomalies, last_ts, ...}
    """
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Extract data
    current = analysis.get("current_level", {})
    roc = analysis.get("roc_state", {})
    stl = analysis.get("stl", {})
    anomalies = analysis.get("anomalies", [])
    flow = analysis.get("flow", {})
    insights = analysis.get("insights", [])
    hourly = analysis.get("hourly_summary", [])

    db_stats = db_stats or {}
    total_readings = db_stats.get("total_readings", "N/A")

    # Anomaly breakdown by class
    class_counts = {}
    for a in anomalies:
        cls = a.get("anomaly_class", "unclassified")
        class_counts[cls] = class_counts.get(cls, 0) + 1

    # Build HTML
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Tank Monitor — Analysis Report</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Segoe UI', -apple-system, sans-serif;
    background: #0b0e14; color: #c9d1d9;
    padding: 2rem; line-height: 1.6;
  }}
  .container {{ max-width: 960px; margin: 0 auto; }}
  h1 {{
    font-size: 2rem; letter-spacing: .08em;
    color: #58a6ff; margin-bottom: .3rem;
  }}
  h2 {{
    font-size: 1.15rem; letter-spacing: .06em;
    color: #79c0ff; margin: 2rem 0 .8rem;
    padding-bottom: .4rem; border-bottom: 1px solid #21262d;
  }}
  .subtitle {{
    font-size: .85rem; color: #8b949e;
    margin-bottom: 2rem;
  }}
  .card-grid {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 1rem; margin-bottom: 1.5rem;
  }}
  .card {{
    background: #161b22; border: 1px solid #21262d;
    border-radius: 10px; padding: 1.2rem;
  }}
  .card-label {{
    font-size: .7rem; text-transform: uppercase;
    letter-spacing: .1em; color: #8b949e; margin-bottom: .3rem;
  }}
  .card-value {{
    font-size: 1.8rem; font-weight: 600;
    font-family: 'Consolas', monospace;
  }}
  .cyan  {{ color: #58a6ff; }}
  .green {{ color: #3fb950; }}
  .amber {{ color: #d29922; }}
  .red   {{ color: #f85149; }}
  table {{
    width: 100%; border-collapse: collapse;
    font-size: .85rem; margin-bottom: 1.5rem;
  }}
  th {{
    text-align: left; padding: .6rem .8rem;
    background: #161b22; color: #8b949e;
    font-weight: 400; font-size: .75rem;
    text-transform: uppercase; letter-spacing: .08em;
    border-bottom: 1px solid #21262d;
  }}
  td {{
    padding: .5rem .8rem;
    border-bottom: 1px solid #161b22;
  }}
  tr:nth-child(even) {{ background: rgba(255,255,255,.02); }}
  .insight {{
    background: #161b22; border-left: 3px solid #58a6ff;
    border-radius: 6px; padding: .6rem 1rem;
    margin-bottom: .5rem; font-size: .85rem;
  }}
  .insight.warn {{ border-left-color: #d29922; }}
  .insight.crit {{ border-left-color: #f85149; }}
  .method-box {{
    background: #161b22; border: 1px solid #21262d;
    border-radius: 10px; padding: 1rem 1.2rem;
    margin-bottom: .5rem;
  }}
  .method-name {{ color: #58a6ff; font-weight: 600; margin-bottom: .3rem; }}
  .method-desc {{ color: #8b949e; font-size: .82rem; }}
  .footer {{
    margin-top: 3rem; padding-top: 1rem;
    border-top: 1px solid #21262d;
    font-size: .75rem; color: #484f58;
    text-align: center;
  }}
</style>
</head>
<body>
<div class="container">

<h1>🛢 Tank Monitor Report</h1>
<p class="subtitle">Generated: {now} · Adaptive anomaly detection with STL + MAD + CUSUM</p>

<!-- ── Current Status ── -->
<h2>📊 Current Tank Status</h2>
<div class="card-grid">
  <div class="card">
    <div class="card-label">Water Level</div>
    <div class="card-value cyan">{current.get('water_level_pct', 'N/A')}%</div>
  </div>
  <div class="card">
    <div class="card-label">Sensor Distance</div>
    <div class="card-value">{current.get('distance_mm', 'N/A')} mm</div>
  </div>
  <div class="card">
    <div class="card-label">Flow State</div>
    <div class="card-value {'green' if roc.get('state') == 'Filling' else 'amber' if roc.get('state') == 'Emptying' else ''}">{roc.get('state', 'N/A')}</div>
  </div>
  <div class="card">
    <div class="card-label">Rate of Change</div>
    <div class="card-value">{roc.get('roc', 'N/A')}</div>
  </div>
  <div class="card">
    <div class="card-label">Total Readings</div>
    <div class="card-value">{total_readings}</div>
  </div>
  <div class="card">
    <div class="card-label">Anomalies Detected</div>
    <div class="card-value {'red' if len(anomalies) > 0 else 'green'}">{len(anomalies)}</div>
  </div>
</div>

{_flow_section(flow)}

<!-- ── Insights ── -->
<h2>💡 AI Insights</h2>
{_insights_html(insights)}

<!-- ── STL Decomposition ── -->
<h2>📈 STL Decomposition Summary</h2>
{_stl_section(stl)}

<!-- ── Detection Methodology ── -->
<h2>🔬 Detection Methodology</h2>
<div class="method-box">
  <div class="method-name">STL Residual MAD (Median Absolute Deviation)</div>
  <div class="method-desc">
    Decomposes the signal into Trend + Seasonal + Residual using robust STL.
    Anomalies are detected on the residual component using adaptive MAD scoring.
    Threshold = 99.5th percentile of |residual - median|. Zero fixed parameters.
  </div>
</div>
<div class="method-box">
  <div class="method-name">Adaptive CUSUM (Cumulative Sum Control Chart)</div>
  <div class="method-desc">
    Tracks cumulative deviations from the baseline (median of residuals).
    Allowance k = MAD of training residuals. Detection threshold h = 99th percentile
    of cumulative absolute deviations. Resets after each detection.
  </div>
</div>
<div class="method-box">
  <div class="method-name">Hybrid Decision</div>
  <div class="method-desc">
    An observation is flagged anomalous if EITHER MAD OR CUSUM triggers.
    Classification into 7 anomaly types (sensor_freeze, spike, overflow,
    sudden_drain, refill, slow_leak) uses contextual rules on ROC and recent variance.
  </div>
</div>

<!-- ── Anomaly Breakdown ── -->
<h2>⚠ Anomaly Classification Breakdown</h2>
{_anomaly_table(anomalies, class_counts)}

<!-- ── Hourly Summary ── -->
<h2>🕐 Hourly Usage Summary</h2>
{_hourly_table(hourly)}

<div class="footer">
  Tank Monitor · Adaptive STL + MAD + CUSUM Pipeline · Report auto-generated
</div>

</div>
</body>
</html>"""


def _flow_section(flow: dict) -> str:
    if not flow:
        return ""
    return f"""
<h2>🌊 Flow Analysis</h2>
<div class="card-grid">
  <div class="card">
    <div class="card-label">Flow Rate</div>
    <div class="card-value">{flow.get('current_flow_rate', 'N/A')} mm/s</div>
  </div>
  <div class="card">
    <div class="card-label">Direction</div>
    <div class="card-value">{flow.get('flow_direction', 'N/A')}</div>
  </div>
  <div class="card">
    <div class="card-label">Est. Time to Empty</div>
    <div class="card-value">{flow.get('est_time_to_empty') or '—'}</div>
  </div>
  <div class="card">
    <div class="card-label">Est. Time to Full</div>
    <div class="card-value">{flow.get('est_time_to_full') or '—'}</div>
  </div>
  <div class="card">
    <div class="card-label">Trend</div>
    <div class="card-value">{flow.get('trend', 'stable')}</div>
  </div>
</div>"""


def _insights_html(insights: list) -> str:
    if not insights:
        return '<p style="color:#8b949e;font-size:.85rem;">No insights available yet.</p>'
    html = ""
    for ins in insights:
        cls = "crit" if "⚠" in ins or "🔴" in ins else "warn" if "🟡" in ins else ""
        html += f'<div class="insight {cls}">{ins}</div>\n'
    return html


def _stl_section(stl: dict) -> str:
    if not stl:
        return '<p style="color:#8b949e;font-size:.85rem;">Insufficient data for STL decomposition.</p>'
    return f"""
<div class="card-grid">
  <div class="card">
    <div class="card-label">MAD</div>
    <div class="card-value cyan">{stl.get('mad', 'N/A')}</div>
  </div>
  <div class="card">
    <div class="card-label">MAD Threshold (99.5%ile)</div>
    <div class="card-value amber">{stl.get('mad_threshold', 'N/A')}</div>
  </div>
  <div class="card">
    <div class="card-label">STL Period</div>
    <div class="card-value">{stl.get('period', 'N/A')}h</div>
  </div>
  <div class="card">
    <div class="card-label">Data Points</div>
    <div class="card-value">{len(stl.get('original', []))}</div>
  </div>
</div>"""


def _anomaly_table(anomalies: list, class_counts: dict) -> str:
    if not anomalies:
        return '<p style="color:#3fb950;font-size:.85rem;">✓ No anomalies detected — system nominal.</p>'

    # Summary row
    summary = " · ".join(f"{cls}: {cnt}" for cls, cnt in sorted(class_counts.items()))
    rows = ""
    for i, a in enumerate(anomalies[:50]):  # cap at 50
        rows += f"""<tr>
  <td>{i+1}</td>
  <td>{a.get('date', '—')}</td>
  <td>{a.get('value', 0):.2f}</td>
  <td>{a.get('anomaly_class', 'unclassified')}</td>
  <td>{a.get('conf_tier', '—')}</td>
</tr>"""

    return f"""
<p style="font-size:.85rem;color:#8b949e;margin-bottom:.8rem;">{summary}</p>
<table>
  <thead><tr>
    <th>#</th><th>Timestamp</th><th>Distance (mm)</th><th>Class</th><th>Tier</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""


def _hourly_table(hourly: list) -> str:
    if not hourly:
        return '<p style="color:#8b949e;font-size:.85rem;">No hourly data available.</p>'
    rows = ""
    for row in hourly:
        rows += f"""<tr>
  <td>{row.get('hour', '—')}</td>
  <td>{row.get('mean', 0):.2f}</td>
  <td>{row.get('min', 0):.2f}</td>
  <td>{row.get('max', 0):.2f}</td>
  <td>{row.get('count', 0)}</td>
</tr>"""

    return f"""
<table>
  <thead><tr>
    <th>Hour</th><th>Avg (mm)</th><th>Min</th><th>Max</th><th>Samples</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""
