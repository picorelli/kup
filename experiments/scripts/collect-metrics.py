#!/usr/bin/env python3
"""
Script to collect metrics from Prometheus and export to CSV.
Queries run in parallel (ThreadPoolExecutor) to minimize collection time.
"""

import argparse
import csv
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List

import requests


PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")

QUERIES = {
    # Performance
    "latency_p50": 'histogram_quantile(0.50, sum(rate(http_request_duration_seconds_bucket[1m])) by (le, service))',
    "latency_p95": 'histogram_quantile(0.95, sum(rate(http_request_duration_seconds_bucket[1m])) by (le, service))',
    "latency_p99": 'histogram_quantile(0.99, sum(rate(http_request_duration_seconds_bucket[1m])) by (le, service))',
    "rps": 'sum(rate(http_requests_total[1m])) by (service)',
    "error_rate": 'sum(rate(http_requests_total{status=~"5.."}[1m])) / sum(rate(http_requests_total[1m]))',
    # Resources
    "cpu_usage": 'avg(rate(container_cpu_usage_seconds_total{namespace="predictive-hpa"}[1m])) by (pod)',
    "memory_usage": 'avg(container_memory_usage_bytes{namespace="predictive-hpa"}) by (pod)',
    "replicas": 'sum(kube_deployment_status_replicas{namespace="predictive-hpa"}) by (deployment)',
    # Predictions
    "predicted_rps": 'predicted_rps',
    "predicted_latency": 'predicted_latency_seconds',
    "prediction_error_mse": 'prediction_error_mse',
}


def query_prometheus(metric_name: str, query: str, start: str, end: str, step: str = "15s"):
    url = f"{PROMETHEUS_URL}/api/v1/query_range"
    params = {"query": query, "start": start, "end": end, "step": step}
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        if data["status"] == "success":
            return metric_name, data["data"]["result"]
        return metric_name, []
    except Exception as e:
        print(f"  Warning: {metric_name} failed: {e}")
        return metric_name, []


def collect_metrics(start: str, end: str, output: str):
    print(f"Collecting metrics from {start} to {end} (parallel)...")

    all_data: Dict = {}
    timestamps = set()

    # Run all queries in parallel
    with ThreadPoolExecutor(max_workers=len(QUERIES)) as executor:
        futures = {
            executor.submit(query_prometheus, name, query, start, end): name
            for name, query in QUERIES.items()
        }
        for future in as_completed(futures):
            metric_name, results = future.result()
            for result in results:
                labels = result.get("metric", {})
                label_str = "_".join(f"{k}={v}" for k, v in labels.items() if k != "__name__")
                full_name = f"{metric_name}_{label_str}" if label_str else metric_name
                for timestamp, value in result.get("values", []):
                    timestamps.add(timestamp)
                    if timestamp not in all_data:
                        all_data[timestamp] = {"timestamp": timestamp}
                    all_data[timestamp][full_name] = value

    if not all_data:
        print("Nenhum dado coletado!")
        return

    sorted_timestamps = sorted(timestamps)
    all_columns: set = set()
    for data in all_data.values():
        all_columns.update(data.keys())

    columns = ["timestamp", "datetime"] + sorted(c for c in all_columns if c not in ("timestamp", "datetime"))

    os.makedirs(os.path.dirname(output) or ".", exist_ok=True)
    with open(output, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for ts in sorted_timestamps:
            row = all_data.get(ts, {"timestamp": ts})
            row["datetime"] = datetime.fromtimestamp(ts).isoformat()
            writer.writerow({k: row.get(k, "") for k in columns})

    print(f"✅ {len(sorted_timestamps)} amostras → {output}")


def main():
    global PROMETHEUS_URL
    parser = argparse.ArgumentParser(description="Collect metrics from Prometheus")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--prometheus-url", default=PROMETHEUS_URL)
    args = parser.parse_args()
    PROMETHEUS_URL = args.prometheus_url
    collect_metrics(args.start, args.end, args.output)


if __name__ == "__main__":
    main()
