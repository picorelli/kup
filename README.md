# Predictive-HPA

Comparação experimental entre escalonamento reativo (HPA nativo) e preditivo (ML) em Kubernetes.

Projeto de TCC — MBA USP/ESALQ em Engenharia de Software.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                     Kubernetes Cluster                       │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │  Predictor  │────▶│  Prometheus │◀────│   Workload  │   │
│  │   Service   │     │   Adapter   │     │  Services   │   │
│  └─────────────┘     └──────┬──────┘     └─────────────┘   │
│         │                   │                   ▲           │
│         ▼                   ▼                   │           │
│  ┌─────────────┐     ┌─────────────┐     ┌─────────────┐   │
│  │    ML       │     │    HPA v2   │────▶│  Replicas   │   │
│  │   Models    │     │             │     │             │   │
│  └─────────────┘     └─────────────┘     └─────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

## Estrutura

```
kup/
├── src/
│   ├── predictor/          # Serviço de predição (FastAPI + scikit-learn)
│   └── workload/           # Router + serviços de carga
├── deploy/
│   ├── docker/             # Docker Compose (dev local)
│   └── kubernetes/         # Manifests K8s (experimentos)
├── experiments/
│   ├── scenarios/          # Scripts K6 (low, medium, high)
│   ├── scripts/            # run-experiment.sh, collect-metrics.py
│   └── results/            # raw/ (JSON k6) + processed/ (CSV Prometheus)
├── analysis/
│   ├── scripts/            # calculate_metrics.py, wilcoxon_test.py
│   └── notebooks/          # Jupyter notebooks
├── monitoring/             # Prometheus, Grafana, Adapter configs
├── scripts/                # Setup, build, install
└── output/                 # preliminary_results.csv, wilcoxon_results.csv
```

## Quick Start

### Requisitos

- Python 3.10+
- Docker Desktop com Kubernetes habilitado
- K6 (`brew install k6`)
- kubectl

### Setup

```bash
# Build das imagens
./scripts/build-images.sh

# Instalar monitoring (Prometheus + Grafana + Adapter)
./scripts/install-monitoring.sh

# Instalar aplicação com HPA reativo
./scripts/install.sh --build --reactive

# Ou com HPA preditivo
./scripts/install.sh --build --predictive
```

### Executar experimentos

```bash
# Executar experimento completo (interativo: escolhe estratégia e cenário)
bash experiments/scripts/run-experiment.sh

# Agregar métricas
python analysis/scripts/calculate_metrics.py \
  --results-dir experiments/results \
  --output output/preliminary_results.csv

# Teste estatístico (Wilcoxon pareado)
python analysis/scripts/wilcoxon_test.py \
  --summary output/preliminary_results.csv \
  --output output/wilcoxon_results.csv
```

## Experimentos

### Cenários de carga

| Cenário | RPS | Características |
|---------|-----|-----------------|
| Baixa   | 50  | Constante       |
| Média   | 200 | Constante       |
| Alta    | 1.000 | Picos de 2.000 RPS por 30s |

### Protocolo

- Warmup: 5 minutos (não computado)
- Execução: 5 minutos por run
- Repetições: 5 por cenário por estratégia
- Coleta: Prometheus a cada 15 segundos
- Teste estatístico: Wilcoxon pareado (n=5)

### Modelos preditivos

| Modelo | Uso |
|--------|-----|
| Linear Regression | Warm-up (5-10 amostras) |
| Random Forest | Principal (10+ amostras) |

## Métricas

- **Latência**: P95, P99, média (ms)
- **Disponibilidade**: % de requisições com status 200
- **Recursos**: CPU média (cores), número de réplicas
- **Erro preditivo**: MSE, MAE, RMSE

## Resultados

Os resultados dos experimentos estão em `output/preliminary_results.csv` e `output/wilcoxon_results.csv`.
