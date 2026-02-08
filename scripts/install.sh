#!/bin/bash

# Script de instalação do Predictive-HPA

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Instalando Predictive-HPA..."

# Verifica se kubectl está disponível
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl não encontrado. Por favor, instale o kubectl primeiro."
    exit 1
fi

# Verifica se o cluster Kubernetes está acessível
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Não foi possível conectar ao cluster Kubernetes."
    echo ""
    echo "📋 Opções para criar um cluster local:"
    echo "   Docker Desktop: Habilite Kubernetes em Settings > Kubernetes"
    echo "   Minikube: minikube start"
    echo "   Kind: kind create cluster"
    exit 1
fi

echo "✅ Cluster Kubernetes acessível"

# Cria o namespace
echo "📦 Criando namespace..."
kubectl apply -f "$PROJECT_ROOT/deploy/kubernetes/base/namespace.yaml"

# Aplica RBAC
echo "🔐 Configurando permissões..."
kubectl apply -f "$PROJECT_ROOT/deploy/kubernetes/base/rbac.yaml"

# Aplica ConfigMap
echo "⚙️  Configurando parâmetros..."
kubectl apply -f "$PROJECT_ROOT/deploy/kubernetes/base/configmap.yaml"

# Constrói as imagens Docker (opcional)
if [ "$1" = "--build" ]; then
    echo "🔨 Construindo imagens Docker..."
    "$SCRIPT_DIR/build-images.sh"
    echo "✅ Imagens construídas com sucesso"
fi

# Aplica o predictor
echo "🔮 Deployando serviço de predição..."
kubectl apply -f "$PROJECT_ROOT/deploy/kubernetes/predictor/"

# Aplica os workloads
echo "📦 Deployando workloads..."
kubectl apply -f "$PROJECT_ROOT/deploy/kubernetes/workload/"

# Pergunta qual estratégia de HPA usar
if [ "$2" = "--reactive" ]; then
    echo "⚖️  Aplicando HPA reativo (baseline)..."
    kubectl apply -f "$PROJECT_ROOT/deploy/kubernetes/hpa/reactive/"
elif [ "$2" = "--predictive" ]; then
    echo "🔮 Aplicando HPA preditivo..."
    kubectl apply -f "$PROJECT_ROOT/deploy/kubernetes/hpa/predictive/"
else
    echo "⚠️  Nenhuma estratégia de HPA especificada."
    echo "   Use --reactive ou --predictive como segundo argumento."
fi

# Aguarda o deployment estar pronto
echo "⏳ Aguardando deployments estarem prontos..."
kubectl wait --for=condition=available --timeout=300s deployment/predictor -n predictive-hpa || true
kubectl wait --for=condition=available --timeout=300s deployment/service-a -n predictive-hpa || true
kubectl wait --for=condition=available --timeout=300s deployment/service-b -n predictive-hpa || true

echo "✅ Predictive-HPA instalado com sucesso!"
echo ""
echo "📋 Para verificar o status:"
echo "   kubectl get pods -n predictive-hpa"
echo "   kubectl logs -f deployment/predictor -n predictive-hpa"
echo ""
echo "📊 Para acessar métricas:"
echo "   kubectl port-forward service/predictor 8080:8080 -n predictive-hpa"
echo "   # Acesse http://localhost:8080/metrics"
echo ""
echo "🌐 Para acessar o router:"
echo "   kubectl port-forward service/router 8080:80 -n predictive-hpa"
