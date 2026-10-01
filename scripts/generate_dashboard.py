#!/usr/bin/env python3
"""
Dashboard Generator for K4-L3B Day 13 Monitoring & LLMOps Lab
Renders all 6 panels required by config/dashboard.yaml from data/logs.jsonl:
1. Latency (P50, P95, P99, TTFT P95, threshold <= 3000ms)
2. Traffic (requests per minute, count, threshold >= 1 rpm)
3. Errors & Retrieval Success (error rate %, retrieval success %, threshold <= 2%)
4. Cost over time (sum by minute, total USD, threshold <= $2.5)
5. Tokens (input/output tokens sum, threshold <= 50000)
6. Quality proxy (mean quality score, threshold >= 0.75)
"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import numpy as np


def parse_iso(ts_str: str) -> datetime:
    if ts_str.endswith("Z"):
        ts_str = ts_str[:-1] + "+00:00"
    return datetime.fromisoformat(ts_str)


def percentile(values: list[float | int], p: float) -> float:
    if not values:
        return 0.0
    k = (len(values) - 1) * (p / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return float(values[int(k)])
    sorted_vals = sorted(values)
    return float(sorted_vals[int(f)] * (c - k) + sorted_vals[int(c)] * (k - f))


def load_logs(log_path: Path) -> list[dict[str, Any]]:
    if not log_path.exists():
        return []
    records = []
    for line in log_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def generate_dashboard(log_path: Path, output_path: Path, title_suffix: str = "") -> None:
    records = load_logs(log_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Filter events
    requests_received = [r for r in records if r.get("event") == "request_received"]
    responses_sent = [r for r in records if r.get("event") == "response_sent"]
    requests_failed = [r for r in records if r.get("event") == "request_failed"]

    # 2. Extract metrics
    latencies = [r["latency_ms"] for r in responses_sent if "latency_ms" in r]
    ttfts = [r["ttft_ms"] for r in responses_sent if "ttft_ms" in r]
    costs = [r["cost_usd"] for r in responses_sent if "cost_usd" in r]
    tokens_in = [r["tokens_in"] for r in responses_sent if "tokens_in" in r]
    tokens_out = [r["tokens_out"] for r in responses_sent if "tokens_out" in r]
    qualities = [r["quality_score"] for r in responses_sent if "quality_score" in r]

    # Retrieval success
    retrieval_ops = [
        r for r in records
        if r.get("tool_name") == "retrieval" and "tool_success" in r
    ]
    successful_retrievals = [r for r in retrieval_ops if r.get("tool_success") is True]

    # Calculations
    p50_lat = percentile(latencies, 50) if latencies else 0
    p95_lat = percentile(latencies, 95) if latencies else 0
    p99_lat = percentile(latencies, 99) if latencies else 0
    p95_ttft = percentile(ttfts, 95) if ttfts else 0

    total_requests = len(requests_received)
    total_failed = len(requests_failed)
    error_rate = (total_failed / total_requests * 100) if total_requests else 0.0
    retrieval_success_rate = (len(successful_retrievals) / len(retrieval_ops) * 100) if retrieval_ops else 100.0

    total_cost = sum(costs)
    sum_tokens_in = sum(tokens_in)
    sum_tokens_out = sum(tokens_out)
    avg_quality = float(np.mean(qualities)) if qualities else 0.0

    # Setup Plot
    plt.style.use("seaborn-v0_8-whitegrid" if "seaborn-v0_8-whitegrid" in plt.style.available else "default")
    fig, axes = plt.subplots(2, 3, figsize=(18, 11))
    main_title = f"K4-L3B Day 13 Monitoring & LLMOps — Dashboard Overview (6 Panels){title_suffix}"
    fig.suptitle(main_title, fontsize=16, fontweight="bold", y=0.98)

    # PANEL 1: Latency & TTFT
    ax1 = axes[0, 0]
    ax1.set_title("Panel 1: Latency Percentiles & TTFT (Unit: ms)", fontsize=12, fontweight="bold")
    metric_labels = ["P50", "P95", "P99", "TTFT P95"]
    metric_vals = [p50_lat, p95_lat, p99_lat, p95_ttft]
    bars1 = ax1.bar(metric_labels, metric_vals, color=["#3498db", "#2980b9", "#e74c3c", "#f39c12"], width=0.5)
    ax1.axhline(3000, color="red", linestyle="--", linewidth=1.5, label="SLO Threshold: <= 3000ms")
    ax1.set_ylabel("Latency (ms)")
    for bar in bars1:
        yval = bar.get_height()
        ax1.text(bar.get_x() + bar.get_width() / 2, yval + 20, f"{yval:.1f}ms", ha="center", va="bottom", fontsize=10)
    ax1.set_ylim(0, max(max(metric_vals + [3200]) * 1.25, 3500))
    ax1.legend(loc="upper left")

    # PANEL 2: Traffic
    ax2 = axes[0, 1]
    ax2.set_title("Panel 2: Request Traffic (Unit: req/min)", fontsize=12, fontweight="bold")
    if requests_received:
        timestamps = [parse_iso(r["ts"]) for r in requests_received if "ts" in r]
        timestamps.sort()
        # Group into minute buckets
        minutes = [t.replace(second=0, microsecond=0) for t in timestamps]
        unique_mins, counts = np.unique(minutes, return_counts=True)
        ax2.plot(unique_mins, counts, marker="o", color="#2ecc71", linewidth=2, label="Traffic rate")
        ax2.axhline(1, color="orange", linestyle="--", label="Threshold: >= 1 rpm")
        ax2.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax2.set_ylabel("Requests / min")
        ax2.set_ylim(0, max(max(counts) * 1.3, 5))
        ax2.text(0.05, 0.85, f"Total Requests: {total_requests}", transform=ax2.transAxes, fontsize=11,
                 bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
    else:
        ax2.text(0.5, 0.5, "No traffic data", ha="center", va="center")
    ax2.legend(loc="upper left")

    # PANEL 3: Errors & Retrieval Success
    ax3 = axes[0, 2]
    ax3.set_title("Panel 3: Error Rate & Retrieval Success (Unit: %)", fontsize=12, fontweight="bold")
    err_labels = ["Error Rate %", "Retrieval Success %"]
    err_vals = [error_rate, retrieval_success_rate]
    bars3 = ax3.bar(err_labels, err_vals, color=["#e74c3c" if error_rate > 2 else "#2ecc71", "#1abc9c"], width=0.45)
    ax3.axhline(2, color="red", linestyle="--", label="Max Error Rate: <= 2%")
    ax3.axhline(90, color="blue", linestyle=":", label="Min Retrieval Success: >= 90%")
    ax3.set_ylabel("Percentage (%)")
    ax3.set_ylim(0, 115)
    for bar in bars3:
        yval = bar.get_height()
        ax3.text(bar.get_x() + bar.get_width() / 2, yval + 2, f"{yval:.1f}%", ha="center", va="bottom", fontsize=10)
    ax3.legend(loc="upper right")

    # PANEL 4: Cost
    ax4 = axes[1, 0]
    ax4.set_title("Panel 4: Cost Over Time (Unit: USD)", fontsize=12, fontweight="bold")
    if responses_sent:
        resp_times = [parse_iso(r["ts"]) for r in responses_sent if "ts" in r and "cost_usd" in r]
        resp_costs = [r["cost_usd"] for r in responses_sent if "ts" in r and "cost_usd" in r]
        cum_costs = np.cumsum(resp_costs)
        ax4.plot(resp_times, cum_costs, color="#9b59b6", marker=".", linewidth=2, label="Cumulative Cost")
        ax4.axhline(2.5, color="red", linestyle="--", label="Threshold: <= $2.50")
        ax4.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax4.set_ylabel("Cost (USD)")
        ax4.set_ylim(0, max(total_cost * 1.5, 3.0))
        ax4.text(0.05, 0.75, f"Total Cost: ${total_cost:.5f}", transform=ax4.transAxes, fontsize=11,
                 bbox=dict(boxstyle="round", facecolor="white", alpha=0.8))
    else:
        ax4.text(0.5, 0.5, "No cost data", ha="center", va="center")
    ax4.legend(loc="upper left")

    # PANEL 5: Tokens
    ax5 = axes[1, 1]
    ax5.set_title("Panel 5: Input & Output Tokens (Unit: tokens)", fontsize=12, fontweight="bold")
    tok_labels = ["Tokens In", "Tokens Out", "Total Tokens"]
    tok_vals = [sum_tokens_in, sum_tokens_out, sum_tokens_in + sum_tokens_out]
    bars5 = ax5.bar(tok_labels, tok_vals, color=["#34495e", "#7f8c8d", "#16a085"], width=0.5)
    ax5.axhline(50000, color="red", linestyle="--", label="Threshold: <= 50,000 tokens")
    ax5.set_ylabel("Tokens")
    ax5.set_ylim(0, max(max(tok_vals + [50000]) * 1.25, 55000))
    for bar in bars5:
        yval = bar.get_height()
        ax5.text(bar.get_x() + bar.get_width() / 2, yval + 500, f"{yval:,}", ha="center", va="bottom", fontsize=10)
    ax5.legend(loc="upper left")

    # PANEL 6: Quality Proxy
    ax6 = axes[1, 2]
    ax6.set_title("Panel 6: Quality Proxy (Score 0 to 1)", fontsize=12, fontweight="bold")
    if qualities:
        indices = list(range(1, len(qualities) + 1))
        ax6.plot(indices, qualities, color="#e67e22", marker="o", linewidth=1.5, alpha=0.7, label="Sample Quality")
        ax6.axhline(avg_quality, color="#d35400", linestyle="-", linewidth=2, label=f"Mean: {avg_quality:.2f}")
    ax6.axhline(0.75, color="green", linestyle="--", linewidth=1.5, label="Threshold: >= 0.75")
    ax6.set_xlabel("Request index")
    ax6.set_ylabel("Score (0.0 - 1.0)")
    ax6.set_ylim(0, 1.1)
    ax6.legend(loc="lower left")

    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
    plt.savefig(output_path, dpi=160)
    plt.close()
    print(f"[SUCCESS] Dashboard exported to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate 6-panel monitoring dashboard image")
    parser.add_argument("--logs", type=Path, default=Path("data/logs.jsonl"), help="Path to logs.jsonl")
    parser.add_argument("--output", type=Path, default=Path("submission/evidence/11-dashboard-overview.png"),
                        help="Path for output image")
    parser.add_argument("--title-suffix", type=str, default="", help="Suffix for dashboard title")
    args = parser.parse_args()

    generate_dashboard(args.logs, args.output, args.title_suffix)


if __name__ == "__main__":
    main()
