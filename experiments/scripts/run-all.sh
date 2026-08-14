#!/usr/bin/env bash
#
# Non-interactive, resumable driver for the full experiment protocol.
# Same protocol as run-experiment.sh (5m warmup + 5m run + 30s gap, Prometheus
# collection per run), but it skips runs whose artifacts already exist, so an
# interrupted execution can be resumed by simply running it again.
#
# Usage:
#   BASE_URL=http://localhost:80 PROMETHEUS_URL=http://localhost:9090 \
#     bash experiments/scripts/run-all.sh
#
# Optional env: STRATEGIES, SCENARIOS, REPETITIONS, PYTHON

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
RESULTS_DIR="$PROJECT_ROOT/experiments/results"
SCENARIOS_DIR="$PROJECT_ROOT/experiments/scenarios"

STRATEGIES=${STRATEGIES:-"reactive predictive"}
SCENARIOS=${SCENARIOS:-"low medium high"}
REPETITIONS=${REPETITIONS:-5}
BASE_URL=${BASE_URL:-"http://localhost:80"}
PYTHON=${PYTHON:-python3}

mkdir -p "$RESULTS_DIR/raw" "$RESULTS_DIR/processed"

log() { echo "[$(date -u +%FT%TZ)] $*"; }

run_one() {
    local strategy=$1 scenario=$2 repetition=$3

    local processed="$RESULTS_DIR/processed/${strategy}_${scenario}_${repetition}_metrics.csv"
    local existing_raw
    existing_raw=$(ls "$RESULTS_DIR/raw/${strategy}_${scenario}_${repetition}_"*.json 2>/dev/null | head -1)

    if [ -n "$existing_raw" ] && [ -f "$processed" ]; then
        log "SKIP ${strategy}/${scenario}/${repetition} (already collected)"
        return 0
    fi

    local timestamp output_file start_time end_time k6_exit
    timestamp=$(date +%Y%m%d_%H%M%S)
    output_file="$RESULTS_DIR/raw/${strategy}_${scenario}_${repetition}_${timestamp}.json"

    log "RUN ${strategy}/${scenario}/${repetition}"
    start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    log "  warmup 5m"
    k6 run --quiet -e BASE_URL="$BASE_URL" "$SCRIPT_DIR/warmup.js" >/dev/null 2>&1

    sleep 5

    log "  load test"
    k6 run --quiet --out json="$output_file" \
        -e BASE_URL="$BASE_URL" \
        -e RESULTS_DIR="$RESULTS_DIR/raw" \
        "$SCENARIOS_DIR/${scenario}-load.js" >/dev/null 2>&1
    k6_exit=$?

    # Exit 99 = thresholds crossed (expected, valid data); other non-zero = real failure
    if [ "$k6_exit" -ne 0 ] && [ "$k6_exit" -ne 99 ]; then
        log "  ERROR k6 exit=$k6_exit"
        return 1
    fi
    [ "$k6_exit" -eq 99 ] && log "  thresholds crossed (exit 99) — data kept"

    end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    log "  collecting Prometheus metrics"
    "$PYTHON" "$SCRIPT_DIR/collect-metrics.py" \
        --start "$start_time" --end "$end_time" \
        --output "$processed" 2>&1 | sed 's/^/    /'

    log "  done -> $(basename "$output_file")"
    sleep 30
}

for strategy in $STRATEGIES; do
    log "=== strategy: $strategy ==="

    # Only one HPA family may target a deployment at a time (AmbiguousSelector)
    if [ "$strategy" = "reactive" ]; then
        kubectl delete -f "$PROJECT_ROOT/deploy/kubernetes/hpa/predictive/" --ignore-not-found=true >/dev/null 2>&1
        kubectl apply  -f "$PROJECT_ROOT/deploy/kubernetes/hpa/reactive/"   >/dev/null 2>&1
    else
        kubectl delete -f "$PROJECT_ROOT/deploy/kubernetes/hpa/reactive/"   --ignore-not-found=true >/dev/null 2>&1
        kubectl apply  -f "$PROJECT_ROOT/deploy/kubernetes/hpa/predictive/" >/dev/null 2>&1
    fi
    sleep 20

    for scenario in $SCENARIOS; do
        for rep in $(seq 1 "$REPETITIONS"); do
            run_one "$strategy" "$scenario" "$rep"
        done
    done
done

log "=== all runs finished ==="
