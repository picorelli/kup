# Predictor Service

Serviço de predição para escalonamento automático preditivo em Kubernetes. Utiliza modelos de machine learning para prever RPS e latência dos serviços.

## Visão Geral

O Predictor Service coleta métricas do Prometheus, treina modelos preditivos e expõe predições via API REST e métricas Prometheus para consumo pelo HPA.

## Arquitetura

```
┌─────────────────────────────────────────────────────────────┐
│                    Predictor Service                         │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐  │
│  │ Collectors  │  │   Models    │  │        API          │  │
│  │             │  │             │  │                     │  │
│  │ - Prometheus│  │ - Linear    │  │ - /api/v1/predict   │  │
│  │ - Kubernetes│  │ - RandomFor │  │ - /api/v1/services  │  │
│  │             │  │ - ARIMA     │  │ - /api/v1/models    │  │
│  │             │  │ - LSTM      │  │                     │  │
│  └──────┬──────┘  └──────┬──────┘  └──────────┬──────────┘  │
│         │                │                     │             │
│         └────────────────┼─────────────────────┘             │
│                          ▼                                   │
│              ┌─────────────────────┐                         │
│              │  Prediction Service │                         │
│              │  - Train models     │                         │
│              │  - Make predictions │                         │
│              │  - Expose metrics   │                         │
│              └─────────────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

## Modelos Disponíveis

| Modelo | Descrição | Requisitos | Min. Amostras |
|--------|-----------|------------|---------------|
| `linear` | Regressão Linear | scikit-learn | 5 |
| `random_forest` | Random Forest | scikit-learn | 10 |
| `arima` | ARIMA(5,1,0) | statsmodels | 15 |
| `lstm` | LSTM | tensorflow | 30 |
| `bi_lstm` | Bidirectional LSTM | tensorflow | 30 |

## Instalação

### Docker

```bash
docker build -t predictive-hpa-predictor:latest .
docker run -p 8080:8080 -p 9090:9090 predictive-hpa-predictor:latest
```

### Local

```bash
pip install -r requirements.txt
python main.py
```

## Configuração

### Variáveis de Ambiente

| Variável | Descrição | Padrão |
|----------|-----------|--------|
| `PROMETHEUS_URL` | URL do Prometheus | `http://prometheus:9090` |
| `NAMESPACE` | Namespace Kubernetes | `predictive-hpa` |
| `UPDATE_INTERVAL` | Intervalo de atualização (s) | `30` |
| `PREDICTION_HORIZON` | Horizonte de predição (s) | `30` |
| `HISTORY_WINDOW` | Janela histórica (s) | `120` |
| `DEFAULT_MODEL` | Modelo padrão | `random_forest` |
| `METRICS_PORT` | Porta métricas Prometheus | `9090` |
| `API_PORT` | Porta da API REST | `8080` |
| `LOG_LEVEL` | Nível de log | `INFO` |

## API Endpoints

### Health & Ready

```bash
# Health check
GET /health

# Readiness check
GET /ready
```

### Serviços

```bash
# Lista serviços descobertos
GET /api/v1/services

# Métricas de um serviço
GET /api/v1/services/{service_name}
```

### Predições

```bash
# Predição via GET
GET /api/v1/predict/{service_name}?metric=rps&horizon=30

# Predição via POST
POST /api/v1/predict
{
  "service_name": "service-a",
  "metric": "rps",
  "horizon": 30,
  "model": "random_forest"
}
```

### Modelos

```bash
# Lista modelos disponíveis
GET /api/v1/models

# Métricas do modelo
GET /api/v1/models/{service_name}/metrics?metric=rps
```

## Métricas Prometheus

O serviço expõe métricas na porta 9090:

```prometheus
# Predições
predicted_rps{service="service-a"} 150.5
predicted_latency_seconds{service="service-a"} 0.045

# Erros de predição
prediction_error_mse{service="service-a", metric="rps"} 25.3
prediction_error_mae{service="service-a", metric="rps"} 4.2
prediction_error_rmse{service="service-a", metric="rps"} 5.03

# Contadores
predictions_total{service="service-a", metric="rps", model="random_forest"} 100
active_services_count 3
```

## Estrutura do Código

```
predictor/
├── main.py              # Ponto de entrada
├── service.py           # Serviço principal
├── models/              # Modelos de ML
│   ├── base.py          # Classe base
│   ├── linear.py        # Linear Regression
│   ├── random_forest.py # Random Forest
│   ├── arima.py         # ARIMA
│   ├── lstm.py          # LSTM / Bi-LSTM
│   └── factory.py       # Factory pattern
├── collectors/          # Coletores de métricas
│   ├── prometheus.py    # Coletor Prometheus
│   └── kubernetes.py    # Coletor Kubernetes
└── api/                 # API REST
    ├── app.py           # Configuração FastAPI
    └── routes.py        # Endpoints
```

## Exemplo de Uso

### Python

```python
import requests

# Fazer predição
response = requests.get(
    "http://localhost:8080/api/v1/predict/service-a",
    params={"metric": "rps", "horizon": 30}
)
prediction = response.json()
print(f"RPS previsto: {prediction['prediction']}")
```

### cURL

```bash
# Listar serviços
curl http://localhost:8080/api/v1/services

# Fazer predição
curl "http://localhost:8080/api/v1/predict/service-a?metric=rps&horizon=30"

# Métricas do modelo
curl "http://localhost:8080/api/v1/models/service-a/metrics?metric=rps"
```

## Dependências

### Obrigatórias

- Python 3.10+
- FastAPI
- scikit-learn
- numpy
- prometheus-client
- kubernetes

### Opcionais

- statsmodels (para ARIMA)
- tensorflow (para LSTM/Bi-LSTM)

## Desenvolvimento

### Executar Testes

```bash
pytest tests/
```

### Lint

```bash
ruff check .
```

### Build Docker

```bash
docker build -t predictive-hpa-predictor:dev .
```
