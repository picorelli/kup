#!/bin/bash

# Script para executar experimento completo

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
RESULTS_DIR="$PROJECT_ROOT/experiments/results"
SCENARIOS_DIR="$PROJECT_ROOT/experiments/scenarios"

# Parâmetros
REPETITIONS=${REPETITIONS:-5}
WARMUP_DURATION="5m"
BASE_URL=${BASE_URL:-"http://localhost:80"}

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 Iniciando experimento Predictive-HPA${NC}"
echo ""

# Verifica se K6 está instalado
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}❌ K6 não encontrado. Instale com: brew install k6${NC}"
    exit 1
fi

# Cria diretório de resultados
mkdir -p "$RESULTS_DIR/raw"
mkdir -p "$RESULTS_DIR/processed"

# Função para executar cenário
run_scenario() {
    local scenario=$1
    local strategy=$2
    local repetition=$3
    
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local output_file="$RESULTS_DIR/raw/${strategy}_${scenario}_${repetition}_${timestamp}.json"
    
    echo -e "${YELLOW}📊 Executando: $strategy - $scenario - Repetição $repetition${NC}"

    local start_time
    start_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    # Warmup — usa script próprio compatível com constant-arrival-rate
    echo "  ⏳ Warmup ($WARMUP_DURATION)..."
    k6 run --quiet \
        -e BASE_URL="$BASE_URL" \
        "$SCRIPT_DIR/warmup.js" > /dev/null 2>&1 || true
    
    sleep 5

    # Execução principal
    echo "  🏃 Executando cenário..."
    local k6_exit=0
    k6 run --out json="$output_file" \
        -e BASE_URL="$BASE_URL" \
        -e RESULTS_DIR="$RESULTS_DIR/raw" \
        "$SCENARIOS_DIR/${scenario}-load.js" || k6_exit=$?

    # Exit 99 = thresholds crossed (expected, valid data); other non-zero = real failure
    if [ "$k6_exit" -ne 0 ] && [ "$k6_exit" -ne 99 ]; then
        echo -e "${RED}  ❌ K6 falhou com erro crítico (exit $k6_exit)${NC}"
        return 1
    fi
    if [ "$k6_exit" -eq 99 ]; then
        echo -e "${YELLOW}  ⚠️  Thresholds violados (exit 99) — dados capturados para análise${NC}"
    fi

    local end_time
    end_time=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

    echo -e "${GREEN}  ✅ Concluído: $output_file${NC}"

    # Coleta métricas do Prometheus para este intervalo
    collect_metrics "$strategy" "${scenario}_${repetition}" "$start_time" "$end_time"

    # Intervalo entre repetições
    if [ "$repetition" -lt "$REPETITIONS" ]; then
        echo "  ⏳ Aguardando 30 segundos antes da próxima repetição..."
        sleep 30
    fi
}

# Função para coletar métricas do Prometheus
collect_metrics() {
    local strategy=$1
    local scenario=$2
    local start_time=$3
    local end_time=$4
    
    echo "  📥 Coletando métricas do Prometheus..."
    python3 "$SCRIPT_DIR/collect-metrics.py" \
        --start "$start_time" \
        --end "$end_time" \
        --output "$RESULTS_DIR/processed/${strategy}_${scenario}_metrics.csv" || true
}

# Menu de seleção
echo "Selecione a estratégia:"
echo "  1) Reativo (baseline)"
echo "  2) Preditivo"
echo "  3) Ambos (comparação completa)"
read -p "Opção [1-3]: " strategy_option

case $strategy_option in
    1) strategies=("reactive") ;;
    2) strategies=("predictive") ;;
    3) strategies=("reactive" "predictive") ;;
    *) echo "Opção inválida"; exit 1 ;;
esac

echo ""
echo "Selecione o cenário:"
echo "  1) Baixa carga (50 RPS)"
echo "  2) Média carga (200 RPS)"
echo "  3) Alta carga (1000 RPS + picos)"
echo "  4) Todos os cenários"
read -p "Opção [1-4]: " scenario_option

case $scenario_option in
    1) scenarios=("low") ;;
    2) scenarios=("medium") ;;
    3) scenarios=("high") ;;
    4) scenarios=("low" "medium" "high") ;;
    *) echo "Opção inválida"; exit 1 ;;
esac

echo ""
echo -e "${GREEN}📋 Configuração:${NC}"
echo "   Estratégias: ${strategies[*]}"
echo "   Cenários: ${scenarios[*]}"
echo "   Repetições: $REPETITIONS"
echo "   URL base: $BASE_URL"
echo ""
read -p "Continuar? [y/N] " confirm
if [[ ! $confirm =~ ^[Yy]$ ]]; then
    exit 0
fi

# Execução
for strategy in "${strategies[@]}"; do
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    echo -e "${GREEN}  Estratégia: $strategy${NC}"
    echo -e "${GREEN}═══════════════════════════════════════${NC}"
    
    # Remove HPAs da outra estratégia para evitar AmbiguousSelector
    if [ "$strategy" = "reactive" ]; then
        kubectl delete -f "$PROJECT_ROOT/deploy/kubernetes/hpa/predictive/" --ignore-not-found=true || true
        kubectl apply -f "$PROJECT_ROOT/deploy/kubernetes/hpa/reactive/" || true
    else
        kubectl delete -f "$PROJECT_ROOT/deploy/kubernetes/hpa/reactive/" --ignore-not-found=true || true
        kubectl apply -f "$PROJECT_ROOT/deploy/kubernetes/hpa/predictive/" || true
    fi

    sleep 20  # Aguarda HPA estabilizar
    
    for scenario in "${scenarios[@]}"; do
        echo ""
        echo -e "${YELLOW}───────────────────────────────────────${NC}"
        echo -e "${YELLOW}  Cenário: $scenario${NC}"
        echo -e "${YELLOW}───────────────────────────────────────${NC}"
        
        for rep in $(seq 1 $REPETITIONS); do
            run_scenario "$scenario" "$strategy" "$rep"
        done
    done
done

echo ""
echo -e "${GREEN}✅ Experimento concluído!${NC}"
echo ""
echo "📊 Resultados salvos em: $RESULTS_DIR"
echo ""
echo "📋 Próximos passos:"
echo "   1. Analisar resultados: jupyter notebook analysis/notebooks/"
echo "   2. Executar teste estatístico: python analysis/scripts/wilcoxon_test.py"
