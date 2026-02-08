# Deploy

Configurações de deploy para o Predictive-HPA em diferentes ambientes.

## Estrutura

```
deploy/
├── docker/              # Docker Compose para desenvolvimento local
│   └── docker-compose.yml
└── kubernetes/          # Manifests Kubernetes para experimentos
    ├── base/            # Recursos base (namespace, rbac, configmap)
    ├── predictor/       # Deploy do serviço de predição
    ├── workload/        # Deploy dos serviços de carga
    ├── hpa/             # Configurações HPA
    │   ├── reactive/    # HPA reativo (baseline)
    │   └── predictive/  # HPA preditivo (proposto)
    └── monitoring/      # Prometheus, Grafana (via Helm)
```

## Docker Compose (Desenvolvimento)

### Iniciar Ambiente

```bash
cd deploy/docker
docker-compose up -d
```

### Serviços Disponíveis

| Serviço | Porta | Descrição |
|---------|-------|-----------|
| Router | 8080 | Entrada de tráfego |
| Service A | 8000 | Serviço backend A |
| Service B | 8001 | Serviço backend B |
| Predictor | 8081 | Serviço de predição |
| Prometheus | 9090 | Coleta de métricas |
| Grafana | 3001 | Dashboards (host) |

### Acessar Serviços

```bash
# Router
curl http://localhost:8080/route

# Predictor API
curl http://localhost:8081/api/v1/services

# Prometheus
open http://localhost:9090

# Grafana (admin/admin)
open http://localhost:3001
```

### Parar Ambiente

```bash
docker-compose down
```

### Rebuild das Imagens

```bash
docker-compose build --no-cache
docker-compose up -d
```

## Kubernetes (Experimentos)

### Pré-requisitos

- Kubernetes 1.20+
- kubectl configurado
- Helm 3+ (para monitoramento)

### Instalação Rápida

```bash
# Usando script de instalação
./scripts/install.sh --build --predictive
```

### Instalação Manual

#### 1. Criar Namespace e RBAC

```bash
kubectl apply -f kubernetes/base/namespace.yaml
kubectl apply -f kubernetes/base/rbac.yaml
kubectl apply -f kubernetes/base/configmap.yaml
```

#### 2. Deploy do Predictor

```bash
kubectl apply -f kubernetes/predictor/
```

#### 3. Deploy dos Workloads

```bash
kubectl apply -f kubernetes/workload/
```

#### 4. Configurar HPA

```bash
# Opção A: HPA Reativo (baseline)
kubectl apply -f kubernetes/hpa/reactive/

# Opção B: HPA Preditivo (proposto)
kubectl apply -f kubernetes/hpa/predictive/
```

### Verificar Status

```bash
# Pods
kubectl get pods -n predictive-hpa

# Serviços
kubectl get svc -n predictive-hpa

# HPA
kubectl get hpa -n predictive-hpa

# Logs do predictor
kubectl logs -f deployment/predictor -n predictive-hpa
```

### Acessar Serviços

```bash
# Port-forward do predictor
kubectl port-forward svc/predictor 8080:8080 -n predictive-hpa

# Port-forward do router
kubectl port-forward svc/router 8080:80 -n predictive-hpa

# Port-forward do Prometheus
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n monitoring
```

## Configuração do HPA

### HPA Reativo (Baseline)

Escala baseado em CPU/memória:

```yaml
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 70
```

### HPA Preditivo (Proposto)

Escala baseado em métricas preditivas:

```yaml
metrics:
- type: External
  external:
    metric:
      name: predicted_rps
      selector:
        matchLabels:
          service: service-a
    target:
      type: AverageValue
      averageValue: "100"
```

## Monitoramento

### Instalar Stack de Monitoramento

```bash
./scripts/install-monitoring.sh
```

Isso instala:
- Prometheus (coleta de métricas)
- Grafana (dashboards)
- Prometheus Adapter (External Metrics API)

### Configurar Prometheus Adapter

O arquivo `monitoring/prometheus-adapter/config.yaml` define o mapeamento de métricas:

```yaml
rules:
  external:
    - seriesQuery: 'predicted_rps{service!=""}'
      name:
        matches: "predicted_rps"
        as: "predicted_rps"
      metricsQuery: 'predicted_rps{<<.LabelMatchers>>}'
```

### Verificar Métricas Externas

```bash
# Listar métricas externas disponíveis
kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1" | jq .

# Consultar métrica específica
kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1/namespaces/predictive-hpa/predicted_rps" | jq .
```

## Troubleshooting

### Predictor não conecta ao Prometheus

```bash
# Verificar conectividade
kubectl exec -it deployment/predictor -n predictive-hpa -- \
  curl -s http://prometheus:9090/-/healthy
```

### HPA não escala

```bash
# Verificar eventos do HPA
kubectl describe hpa service-a-predictive-hpa -n predictive-hpa

# Verificar métricas externas
kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1/namespaces/predictive-hpa/predicted_rps"
```

### Pods não iniciam

```bash
# Verificar eventos
kubectl get events -n predictive-hpa --sort-by='.lastTimestamp'

# Verificar logs
kubectl logs -f deployment/predictor -n predictive-hpa
```

## Limpeza

### Docker Compose

```bash
docker-compose down -v
```

### Kubernetes

```bash
# Remove tudo do namespace
kubectl delete namespace predictive-hpa

# Remove monitoramento
helm uninstall prometheus -n monitoring
kubectl delete namespace monitoring
```
