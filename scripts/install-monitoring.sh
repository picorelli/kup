#!/bin/bash

# Script para instalar stack de monitoramento

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "📊 Instalando stack de monitoramento..."

# Verifica se helm está disponível
if ! command -v helm &> /dev/null; then
    echo "⚠️  Helm não encontrado. Instalando..."
    brew install helm || {
        echo "❌ Falha ao instalar Helm. Instale manualmente."
        exit 1
    }
fi

# Adiciona repositório do Prometheus
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

# Instala Prometheus + Grafana via kube-prometheus-stack
echo "📦 Instalando kube-prometheus-stack..."
helm upgrade --install prometheus prometheus-community/kube-prometheus-stack \
    --namespace monitoring \
    --create-namespace \
    --set prometheus.prometheusSpec.scrapeInterval=5s \
    --set prometheus.prometheusSpec.evaluationInterval=5s \
    --set grafana.adminPassword=admin \
    --wait

# Instala Prometheus Adapter com helm-values.yaml (formato correto para o chart)
echo "📦 Instalando Prometheus Adapter..."
helm upgrade --install prometheus-adapter prometheus-community/prometheus-adapter \
    --namespace monitoring \
    --set prometheus.url=http://prometheus-kube-prometheus-prometheus.monitoring.svc \
    --set prometheus.port=9090 \
    -f "$PROJECT_ROOT/monitoring/prometheus-adapter/helm-values.yaml" \
    --wait

# Verifica se External Metrics API está respondendo
echo "🔍 Verificando External Metrics API..."
sleep 10
kubectl get --raw "/apis/external.metrics.k8s.io/v1beta1" > /dev/null 2>&1 \
    && echo "✅ External Metrics API disponível" \
    || echo "⚠️  External Metrics API ainda não disponível — aguarde alguns minutos e verifique com: kubectl get --raw /apis/external.metrics.k8s.io/v1beta1"

echo "✅ Stack de monitoramento instalado!"
echo ""
echo "📋 Acessar Grafana:"
echo "   kubectl port-forward svc/prometheus-grafana 3000:80 -n monitoring"
echo "   Usuário: admin | Senha: admin"
echo ""
echo "📋 Acessar Prometheus:"
echo "   kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 -n monitoring"
