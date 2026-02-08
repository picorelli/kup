#!/usr/bin/env python3
"""
Compute performance metrics combining:
  - k6 JSON raw files (latency p50/p95/p99, error rate, RPS)
  - Prometheus CSVs (replicas, CPU, predicted_rps)

Usage:
  python calculate_metrics.py --results-dir experiments/results --output output/preliminary_results.csv
"""

import argparse
import json
import os
from pathlib import Path

import numpy as np
import pandas as pd


# ── k6 JSON parsing ───────────────────────────────────────────────────────────

def parse_k6_json(json_path: Path) -> dict:
    """
    Parse k6 streaming JSON output and extract key metrics.
    Each line is either a Metric definition or a Point.
    Returns dict with latency percentiles, error_rate, rps.
    """
    durations_ms = []
    failed_count = 0
    total_count = 0
    start_ts = None
    end_ts = None

    try:
        with open(json_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue

                metric = obj.get("metric", "")
                obj_type = obj.get("type", "")

                if obj_type == "Point":
                    ts = obj.get("data", {}).get("time")
                    if ts:
                        if start_ts is None:
                            start_ts = ts
                        end_ts = ts

                    if metric == "http_req_duration":
                        val = obj.get("data", {}).get("value")
                        if val is not None:
                            durations_ms.append(float(val))

                    elif metric == "http_req_failed":
                        val = obj.get("data", {}).get("value")
                        if val is not None:
                            total_count += 1
                            if float(val) == 1.0:
                                failed_count += 1

    except Exception as e:
        print(f"  Warning: error reading {json_path.name}: {e}")
        return {}

    if not durations_ms:
        return {}

    arr = np.array(durations_ms)
    duration_s = 300  # 5 min experiment (fallback)
    rps = len(arr) / duration_s

    error_rate = (failed_count / total_count * 100) if total_count > 0 else 0.0
    availability = 100.0 - error_rate

    return {
        "latency_p50":   float(np.percentile(arr, 50)),
        "latency_p95":   float(np.percentile(arr, 95)),
        "latency_p99":   float(np.percentile(arr, 99)),
        "latency_mean":  float(np.mean(arr)),
        "latency_max":   float(np.max(arr)),
        "rps_observed":  float(rps),
        "error_rate":    float(error_rate),
        "availability":  float(availability),
        "samples_k6":    len(arr),
    }


# ── Prometheus CSV parsing ────────────────────────────────────────────────────

def parse_prometheus_csv(csv_path: Path) -> dict:
    """
    Extract replica counts and CPU usage from Prometheus CSV.
    Returns dict with max/mean replicas for service-a and service-b.
    """
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        print(f"  Warning: error reading {csv_path.name}: {e}")
        return {}

    metrics = {}

    # Replicas
    for svc in ("service-a", "service-b"):
        col = f"replicas_deployment={svc}"
        if col in df.columns:
            data = pd.to_numeric(df[col], errors="coerce").dropna()
            if not data.empty:
                metrics[f"replicas_{svc}_max"]  = float(data.max())
                metrics[f"replicas_{svc}_mean"] = float(data.mean())

    # Total replicas (sum of both services)
    rep_cols = [c for c in df.columns if c.startswith("replicas_deployment=service")]
    if rep_cols:
        total = df[rep_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        metrics["replicas_total_max"]  = float(total.max())
        metrics["replicas_total_mean"] = float(total.mean())

    # CPU (sum across all service-a/b pods)
    cpu_cols = [c for c in df.columns
                if c.startswith("cpu_usage_pod=service-")]
    if cpu_cols:
        cpu = df[cpu_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        metrics["cpu_total_mean"] = float(cpu.mean())
        metrics["cpu_total_max"]  = float(cpu.max())

    # Predicted RPS (if available)
    pred_cols = [c for c in df.columns if "predicted_rps" in c]
    if pred_cols:
        pred = pd.to_numeric(df[pred_cols[0]], errors="coerce").dropna()
        if not pred.empty:
            metrics["predicted_rps_mean"] = float(pred.mean())

    return metrics


# ── Main processing ───────────────────────────────────────────────────────────

def process_experiment_results(results_dir: str, output: str):
    base = Path(results_dir)
    raw_dir  = base / "raw"
    proc_dir = base / "processed"

    # Index k6 JSON files by (strategy, scenario, repetition)
    k6_index: dict = {}
    for f in raw_dir.glob("*.json"):
        if "summary" in f.name:
            continue
        parts = f.stem.split("_")
        if len(parts) >= 3:
            key = (parts[0], parts[1], parts[2])
            k6_index[key] = f

    # Index Prometheus CSVs
    prom_index: dict = {}
    for f in proc_dir.glob("*.csv"):
        parts = f.stem.replace("_metrics", "").split("_")
        if len(parts) >= 3:
            key = (parts[0], parts[1], parts[2])
            prom_index[key] = f

    all_keys = sorted(set(k6_index) | set(prom_index))
    if not all_keys:
        print("No result files found.")
        return

    all_metrics = []
    for key in all_keys:
        strategy, scenario, repetition = key
        print(f"Processing: {strategy}_{scenario}_{repetition}")

        row: dict = {
            "strategy":   strategy,
            "scenario":   scenario,
            "repetition": repetition,
        }

        if key in k6_index:
            row.update(parse_k6_json(k6_index[key]))
        if key in prom_index:
            row.update(parse_prometheus_csv(prom_index[key]))

        all_metrics.append(row)

    summary = pd.DataFrame(all_metrics)
    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    summary.to_csv(output, index=False)

    print(f"\nSummary saved to: {output}")
    print(f"   {len(all_metrics)} experiments processed\n")

    # Print preview
    cols = ["strategy", "scenario", "repetition",
            "latency_p95", "latency_p99", "error_rate",
            "replicas_total_max", "availability"]
    display_cols = [c for c in cols if c in summary.columns]
    print(summary[display_cols].sort_values(["scenario", "strategy", "repetition"]).to_string(index=False))


def main():
    parser = argparse.ArgumentParser(description="Compute experiment metrics")
    parser.add_argument("--results-dir", required=True, help="Base results directory (contains raw/ and processed/)")
    parser.add_argument("--output", required=True, help="Output CSV summary file")
    args = parser.parse_args()
    process_experiment_results(args.results_dir, args.output)


if __name__ == "__main__":
    main()
