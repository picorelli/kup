#!/usr/bin/env python3
"""
Collect validation data from the stack (predictor, router, services) and print
a Markdown summary. Requires the stack running: docker-compose -f deploy/docker/docker-compose.yml up -d

Usage: from repo root: python3 scripts/validate_and_collect.py
"""
import json
import sys
from datetime import date
from urllib.request import urlopen, Request
from urllib.error import URLError

PREDICTOR_BASE = "http://localhost:8081"
ROUTER_BASE = "http://localhost:8080"
SERVICE_A = "http://localhost:8000"
SERVICE_B = "http://localhost:8001"

NO_RESPONSE = "no response"


def get(url, timeout=5):
    try:
        req = Request(url, headers={"Accept": "application/json"})
        with urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode()
    except URLError as e:
        return None, str(e)
    except OSError as e:
        return None, str(e)


def _status_row(name, port, ok, obs="no response"):
    status = "Operational" if ok else "Failure / inactive"
    return "| {} | {} | {}   | {} |".format(name, port, status, obs)


def _collect_services_table(from_host, predictor, router):
    lines = []
    status, body = get(f"{predictor}/health")
    if status == 200:
        obs = "/health OK"
    else:
        obs = body[:50] if body else NO_RESPONSE
    lines.append(_status_row("Predictor", "8081", status == 200, obs))
    s_open, _ = get(f"{router}/openapi.json")
    s_route, _ = get(f"{router}/route")
    ok = s_open == 200 or s_route == 200
    if s_open == 200:
        obs = "API available"
    elif s_route == 200:
        obs = "/route OK"
    else:
        obs = NO_RESPONSE
    lines.append(_status_row("Router", "8080", ok, obs))
    for name, port in [("Service A", 8000), ("Service B", 8001)]:
        st, _ = get(f"http://{from_host}:{port}/process", timeout=3)
        obs = "/process OK" if st == 200 else "(run stack with docker-compose)"
        lines.append(_status_row(name, port, st == 200, obs))
    for name, port, path in [("Prometheus", 9090, "/-/healthy"), ("Grafana", 3001, "/api/health")]:
        st, _ = get(f"http://{from_host}:{port}{path}", timeout=2)
        lines.append(_status_row(name, str(port), st == 200, ""))
    return lines


def _collect_models_section(predictor):
    status, body = get(f"{predictor}/api/v1/models")
    if status != 200:
        return ["*Predictor unreachable or " + NO_RESPONSE + ". Ensure the stack is up (docker-compose up -d).*"]
    try:
        models = json.loads(body)
        return ["- {}".format(m) for m in models] if isinstance(models, list) else ["`{}`".format(body[:200])]
    except Exception:
        return ["`{}`".format(body[:300])]


def _collect_metrics_section(predictor):
    for svc in ["service-a", "service_a", "default"]:
        status, body = get(f"{predictor}/api/v1/models/{svc}/metrics?metric=rps")
        if status != 200:
            continue
        try:
            data = json.loads(body)
            lines = ["| Metric | Value |", "|--------|-------|"]
            for k in ["mse", "mae", "rmse", "mape", "samples"]:
                if k in data:
                    lines.append("| {} | {} |".format(k.upper(), data[k]))
            return lines
        except Exception:
            return ["Response: `{}`".format(body[:200])]
    return ["*No service metrics yet (predictor needs traffic and time to collect from Prometheus).*"]


def main():
    from_host = "localhost"
    predictor = f"http://{from_host}:8081"
    router = f"http://{from_host}:8080"

    out = [
        "## Validation data (run on {})".format(date.today().strftime("%Y-%m-%d")),
        "",
        "### Service status",
        "",
        "| Service    | Port | Status        | Note |",
        "|------------|------|---------------|------|",
    ]
    out.extend(_collect_services_table(from_host, predictor, router))
    out.extend(["", "### Available models (Predictor API)", ""])
    out.extend(_collect_models_section(predictor))
    out.extend(["", "### Model metrics (sample)", ""])
    out.extend(_collect_metrics_section(predictor))
    out.extend([
        "",
        "### Router test",
        "",
        "Run: `python3 experiments/scripts/load_test.py` and paste the summary below (Total Requests, Success/Failures, Avg/Min/Max Latency).",
        "",
        "*[Fill with load_test.py output after running.]*",
        "",
    ])
    print("\n".join(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
