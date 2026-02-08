#!/usr/bin/env bash
# Bring up Docker stack, collect validation and load-test data per strategy
# (none = predictor off, linear, random_forest, arima), write results to output/*.csv.
#
# Usage: from repo root:
#   ./scripts/run_and_collect_results.sh              # run all strategies
#   ./scripts/run_and_collect_results.sh linear       # run only one strategy
#
# Output: output/preliminary_results.csv (with column "strategy"), output/model_metrics.csv

set -e
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
COMPOSE_FILE="deploy/docker/docker-compose.yml"
VALIDATE_OUT="/tmp/kup_validate_$$.md"
LOADTEST_OUT="/tmp/kup_loadtest_$$.txt"
DRAFT="docs/content/preliminary-results/Draft_Preliminary_Results.md"

# Strategies: none (predictor off), then one run per model
STRATEGIES="${1:-none linear random_forest arima}"
if [ -n "$1" ]; then
  STRATEGIES="$1"
fi

cleanup() { rm -f "$VALIDATE_OUT" "$LOADTEST_OUT"; }
trap cleanup EXIT

echo "=== Bringing up Docker stack (all services) ==="
docker-compose -f "$COMPOSE_FILE" up -d 2>&1 || true

echo "=== Waiting for router (and optionally predictor) ==="
for i in $(seq 1 12); do
  if curl -sf -m 3 http://localhost:8080/route >/dev/null 2>&1; then
    echo "Router ready."
    break
  fi
  echo "Attempt $i/12..."
  sleep 5
done

for strategy in $STRATEGIES; do
  echo ""
  echo "========== Strategy: $strategy =========="
  if [ "$strategy" = "none" ]; then
    echo "Stopping predictor (baseline without models)..."
    docker-compose -f "$COMPOSE_FILE" stop predictor 2>&1 || true
    sleep 3
  else
    echo "Starting predictor with DEFAULT_MODEL=$strategy..."
    export DEFAULT_MODEL="$strategy"
    docker-compose -f "$COMPOSE_FILE" up -d --force-recreate predictor 2>&1 || true
    unset DEFAULT_MODEL
    for i in $(seq 1 12); do
      if curl -sf -m 3 http://localhost:8081/health >/dev/null 2>&1; then
        echo "Predictor ready."
        break
      fi
      echo "Waiting for predictor $i/12..."
      sleep 5
    done
  fi

  echo "=== Collecting validation (scripts/validate_and_collect.py) ==="
  python3 scripts/validate_and_collect.py > "$VALIDATE_OUT" 2>&1 || true

  echo "=== Running load test (experiments/scripts/load_test.py) ==="
  python3 experiments/scripts/load_test.py > "$LOADTEST_OUT" 2>&1 || true

  echo "=== Writing results to output/*.csv (strategy=$strategy) ==="
  if [ -f "$DRAFT" ]; then
    python3 scripts/update_draft_from_collection.py "$VALIDATE_OUT" "$LOADTEST_OUT" "$DRAFT" "$strategy"
  else
    python3 scripts/update_draft_from_collection.py "$VALIDATE_OUT" "$LOADTEST_OUT" "$strategy"
  fi

  if [ "$strategy" = "none" ]; then
    echo "Starting predictor again for next strategy..."
    docker-compose -f "$COMPOSE_FILE" start predictor 2>&1 || true
    sleep 5
  fi
done

echo ""
echo "=== Updating draft MD table from CSV (if draft exists) ==="
python3 scripts/update_draft_table_from_csv.py 2>&1 || true

echo ""
echo "=== Done. Results in: output/preliminary_results.csv (column strategy) and output/model_metrics.csv ==="
