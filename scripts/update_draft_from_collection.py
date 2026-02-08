#!/usr/bin/env python3
"""
Collect validation and load-test data, write results to output/*.csv and,
optionally, update a preliminary results draft markdown file.

Usage:
  python3 scripts/update_draft_from_collection.py <validate_output.md> <loadtest_output.txt> [draft.md]
  - Without draft: only writes output/preliminary_results.csv and output/model_metrics.csv
  - With draft: also updates the given .md file with the collected blocks
"""
import csv
import re
import sys
import json
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import urlopen, Request

PREDICTOR_BASE = "http://localhost:8081"
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "output"
PRELIMINARY_RESULTS_CSV = "preliminary_results.csv"


def get(url, timeout=3):
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except Exception:
        return None, None


def parse_validate_md(content: str) -> dict:
    """Extract status table, models and metrics from validate_and_collect.py output."""
    out = {"status_table": "", "models": "", "metrics": "", "raw": content}
    # Match table: "| Service" or "| Serviço" for backwards compatibility
    table_match = re.search(
        r"(\|\s*Service\s+\|.*?\n\|[-:\s|]+\|\n(?:.*?\n)+?)(?=\n\n|\n###|\Z)",
        content,
        re.DOTALL,
    )
    if not table_match:
        table_match = re.search(
            r"(\|\s*Serviço\s+\|.*?\n\|[-:\s|]+\|\n(?:.*?\n)+?)(?=\n\n|\n###|\Z)",
            content,
            re.DOTALL,
        )
    if table_match:
        out["status_table"] = table_match.group(1).strip()
    models_match = re.search(
        r"### (?:Modelos disponíveis|Available models).*?\n\n(.*?)(?=\n###|\n\*\*|\Z)",
        content,
        re.DOTALL,
    )
    if models_match:
        out["models"] = models_match.group(1).strip()
    metrics_match = re.search(
        r"### (?:Métricas de erro do modelo|Model metrics).*?\n\n(.*?)(?=\n###|\nRodar:|\nRun:|\Z)",
        content,
        re.DOTALL,
    )
    if metrics_match:
        out["metrics"] = metrics_match.group(1).strip()
    return out


def parse_validate_for_csv(content: str) -> dict:
    """Extract per-service status (1=Operational, 0=Failure) and models list for CSV."""
    row = {
        "predictor_status": 0,
        "router_status": 0,
        "service_a_status": 0,
        "service_b_status": 0,
        "prometheus_status": 0,
        "grafana_status": 0,
        "models_available": "",
    }
    for line in content.split("\n"):
        if "| Predictor |" in line and ("Operational" in line or "Operacional" in line):
            row["predictor_status"] = 1
        if "| Router |" in line and ("Operational" in line or "Operacional" in line):
            row["router_status"] = 1
        if "| Service A |" in line and ("Operational" in line or "Operacional" in line):
            row["service_a_status"] = 1
        if "| Service B |" in line and ("Operational" in line or "Operacional" in line):
            row["service_b_status"] = 1
        if "| Prometheus |" in line and ("Operational" in line or "Operacional" in line):
            row["prometheus_status"] = 1
        if "| Grafana |" in line and ("Operational" in line or "Operacional" in line):
            row["grafana_status"] = 1
    models_match = re.search(
        r"### (?:Modelos disponíveis|Available models).*?\n\n(.*?)(?=\n###|\n\*\*|\Z)",
        content,
        re.DOTALL,
    )
    if models_match:
        block = models_match.group(1)
        models = re.findall(r"^-\s+(\S+)", block, re.MULTILINE)
        row["models_available"] = ";".join(models) if models else ""
    return row


def parse_loadtest(content: str) -> tuple:
    """Return (markdown text, dict for CSV)."""
    text = content.strip()
    row = {
        "total_requests": "",
        "success": "",
        "failures": "",
        "avg_latency_s": "",
        "max_latency_s": "",
        "min_latency_s": "",
    }
    m_total = re.search(r"Total Requests:\s*(\d+)", text)
    m_success = re.search(r"Success:\s*(\d+)", text)
    m_failures = re.search(r"Failures:\s*(\d+)", text)
    m_avg = re.search(r"Avg Latency:\s*([\d.]+)s", text)
    m_max = re.search(r"Max Latency:\s*([\d.]+)s", text)
    m_min = re.search(r"Min Latency:\s*([\d.]+)s", text)
    if m_total:
        row["total_requests"] = m_total.group(1)
    if m_success:
        row["success"] = m_success.group(1)
    if m_failures:
        row["failures"] = m_failures.group(1)
    if m_avg:
        row["avg_latency_s"] = m_avg.group(1)
    if m_max:
        row["max_latency_s"] = m_max.group(1)
    if m_min:
        row["min_latency_s"] = m_min.group(1)
    return text, row


def fetch_model_metrics() -> list:
    """Query Predictor API and return list of dicts for table and CSV."""
    rows = []
    status, body = get(f"{PREDICTOR_BASE}/api/v1/services")
    if status != 200:
        return rows
    try:
        services = json.loads(body)
    except Exception:
        return rows
    if not isinstance(services, list):
        return rows
    for svc in services:
        for metric, label in [("rps", "RPS"), ("latency", "Latency")]:
            status, body = get(f"{PREDICTOR_BASE}/api/v1/models/{svc}/metrics?metric={metric}")
            if status != 200:
                continue
            try:
                data = json.loads(body)
                rows.append({
                    "model": data.get("model_type", "-"),
                    "service": svc,
                    "metric": label,
                    "mse": data.get("mse", ""),
                    "mae": data.get("mae", ""),
                    "rmse": data.get("rmse", ""),
                    "mape": data.get("mape", ""),
                    "samples": data.get("samples", ""),
                })
            except Exception:
                continue
    return rows


def build_table_rows(rows: list) -> str:
    if not rows:
        return "| *(no metrics available; predictor needs traffic and discovered services)* | | | | | | | |"
    lines = []
    for r in rows:
        mse = r["mse"] if r["mse"] != "" else "-"
        mae = r["mae"] if r["mae"] != "" else "-"
        rmse = r["rmse"] if r["rmse"] != "" else "-"
        mape = r["mape"] if r["mape"] != "" else "-"
        samples = r["samples"] if r["samples"] != "" else "-"
        lines.append("| {} | {} | {} | {} | {} | {} | {} | {} |".format(
            r["model"], r["service"], r["metric"], mse, mae, rmse, mape, samples
        ))
    return "\n".join(lines)


def write_csv_results(timestamp: str, validate_row: dict, loadtest_row: dict, strategy: str = ""):
    """Append one row to output/preliminary_results.csv. strategy: 'none', 'linear', 'random_forest', 'arima', or ''."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / PRELIMINARY_RESULTS_CSV
    headers = [
        "timestamp",
        "strategy",
        "predictor_status", "router_status", "service_a_status", "service_b_status",
        "prometheus_status", "grafana_status",
        "load_test_total", "load_test_success", "load_test_failures",
        "load_test_avg_latency_s", "load_test_max_latency_s", "load_test_min_latency_s",
    ]
    file_exists = path.exists()
    # Migrate old CSV: add "strategy" if missing, or remove "models_available" if present
    if file_exists:
        with open(path, "r", newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            old_rows = list(reader)
            old_fieldnames = reader.fieldnames or []
        need_rewrite = old_rows and (
            "strategy" not in old_fieldnames or "models_available" in old_fieldnames
        )
        if need_rewrite:
            with open(path, "w", newline="", encoding="utf-8") as f:
                w = csv.DictWriter(f, fieldnames=headers)
                w.writeheader()
                for row in old_rows:
                    if "strategy" not in row:
                        row["strategy"] = ""
                    row.pop("models_available", None)
                    w.writerow({k: row.get(k, "") for k in headers})
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            w.writeheader()
        w.writerow({
            "timestamp": timestamp,
            "strategy": strategy,
            "predictor_status": validate_row.get("predictor_status", ""),
            "router_status": validate_row.get("router_status", ""),
            "service_a_status": validate_row.get("service_a_status", ""),
            "service_b_status": validate_row.get("service_b_status", ""),
            "prometheus_status": validate_row.get("prometheus_status", ""),
            "grafana_status": validate_row.get("grafana_status", ""),
            "load_test_total": loadtest_row.get("total_requests", ""),
            "load_test_success": loadtest_row.get("success", ""),
            "load_test_failures": loadtest_row.get("failures", ""),
            "load_test_avg_latency_s": loadtest_row.get("avg_latency_s", ""),
            "load_test_max_latency_s": loadtest_row.get("max_latency_s", ""),
            "load_test_min_latency_s": loadtest_row.get("min_latency_s", ""),
        })
    print("Results written to:", path, file=sys.stderr)


def write_csv_model_metrics(timestamp: str, rows: list):
    """Append rows to output/model_metrics.csv."""
    if not rows:
        return
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_DIR / "model_metrics.csv"
    headers = ["timestamp", "model", "service", "metric", "mse", "mae", "rmse", "mape", "samples"]
    file_exists = path.exists()
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        if not file_exists:
            w.writeheader()
        for r in rows:
            w.writerow({
                "timestamp": timestamp,
                "model": r["model"],
                "service": r["service"],
                "metric": r["metric"],
                "mse": r["mse"],
                "mae": r["mae"],
                "rmse": r["rmse"],
                "mape": r["mape"],
                "samples": r["samples"],
            })
    print("Model metrics written to:", path, file=sys.stderr)


def update_draft(draft_path: Path, parsed: dict, loadtest_block: str, table_rows: str):
    """Update the draft file with the collected blocks."""
    draft = draft_path.read_text(encoding="utf-8")
    status_table = parsed["status_table"] or "| Service | Port | Status | Note |\n|---------|------|--------|------|\n| - | - | - | - |"
    models_block = parsed["models"] or "-"
    metrics_block = parsed["metrics"] or "-"
    new_section = """**Service status:**

{status_table}

**Available models (GET /api/v1/models):** {models}

**Model metrics:** {metrics}

**Router test (load_test.py):**

```
{loadtest}
```""".format(
        status_table=status_table,
        models=models_block,
        metrics=metrics_block,
        loadtest=loadtest_block,
    )
    start_marker = "**Status dos serviços:**"
    start_marker_en = "**Service status:**"
    end_marker = "*Inserir após rodar experimentos completos"
    end_marker_en = "*Insert after running experiments"
    start_idx = draft.find(start_marker)
    if start_idx == -1:
        start_idx = draft.find(start_marker_en)
    end_idx = draft.find(end_marker)
    if end_idx == -1:
        end_idx = draft.find(end_marker_en)
    if start_idx == -1 or end_idx == -1:
        print("Markers not found in draft; CSV was written.", file=sys.stderr)
        return
    before = draft[:start_idx]
    after = draft[end_idx:]
    draft_new = before + new_section + "\n\n" + after
    placeholders = [
        "| *(dados reais preenchidos pelo script run_and_collect.sh)* |",
        "| *(no metrics available; predictor needs traffic and discovered services)* |",
        "| *(real data filled by run_and_collect script)* |",
    ]
    for ph in placeholders:
        if ph in draft_new:
            draft_new = draft_new.replace(ph, table_rows if table_rows else ph, 1)
            break
    draft_path.write_text(draft_new, encoding="utf-8")
    print("Draft updated:", draft_path, file=sys.stderr)


def main():
    if len(sys.argv) < 3:
        print("Usage: update_draft_from_collection.py <validate_output.md> <loadtest_output.txt> [draft.md] [strategy]", file=sys.stderr)
        sys.exit(1)
    validate_path = Path(sys.argv[1])
    loadtest_path = Path(sys.argv[2])
    draft_path = None
    strategy = ""
    if len(sys.argv) >= 4:
        if sys.argv[3].endswith(".md"):
            draft_path = Path(sys.argv[3])
            if len(sys.argv) >= 5:
                strategy = sys.argv[4]
        elif sys.argv[3] in ("none", "linear", "random_forest", "arima"):
            strategy = sys.argv[3]

    validate_content = validate_path.read_text(encoding="utf-8")
    loadtest_content = loadtest_path.read_text(encoding="utf-8")

    parsed = parse_validate_md(validate_content)
    validate_row = parse_validate_for_csv(validate_content)
    loadtest_block, loadtest_row = parse_loadtest(loadtest_content)
    model_metrics = fetch_model_metrics()
    table_rows = build_table_rows(model_metrics)

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_csv_results(timestamp, validate_row, loadtest_row, strategy)
    write_csv_model_metrics(timestamp, model_metrics)

    if draft_path and draft_path.exists():
        update_draft(draft_path, parsed, loadtest_block, table_rows)
    elif draft_path:
        print("Draft file not found:", draft_path, file=sys.stderr)


if __name__ == "__main__":
    main()
