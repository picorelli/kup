#!/bin/bash

# Script para configurar o cluster Kubernetes para experimentos

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🚀 Configurando cluster para experimentos Predictive-HPA..."

# Verifica se kubectl está disponível
if ! command -v kubectl &> /dev/null; then
    echo "❌ kubectl não encontrado."
    exit 1
fi

# Verifica se o cluster está acessível
if ! kubectl cluster-info &> /dev/null; then
    echo "❌ Cluster não acessível."
    echo ""
    echo "Criando cluster com Kind..."
    
    if ! command -v kind &> /dev/null; then
        echo "Instalando Kind..."
        brew install kind || {
            echo "❌ Falha ao instalar Kind. Instale manualmente."
            exit 1
        }
    fi
    
    # Cria cluster com 3 nós (1 control-plane + 2 workers)
    kind create cluster --name predictive-hpa --config - <<EOF
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
- role: worker
- role: worker
EOF
fi

echo "✅ Cluster configurado"

# Instala Metrics Server
echo "📊 Instalando Metrics Server..."
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml || true

# Patch para permitir insecure TLS em ambiente local
kubectl patch deployment metrics-server -n kube-system --type='json' -p='[
  {"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-insecure-tls"},
  {"op": "add", "path": "/spec/template/spec/containers/0/args/-", "value": "--kubelet-preferred-address-types=InternalIP"}
]' || true

echo "✅ Metrics Server instalado"

# Instala monitoramento
"$SCRIPT_DIR/install-monitoring.sh"

echo ""
echo "✅ Cluster configurado com sucesso!"
echo ""
echo "📋 Próximos passos:"
echo "   1. Build das imagens: ./scripts/build-images.sh"
echo "   2. Instalação: ./scripts/install.sh --build --predictive"
