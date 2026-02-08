#!/bin/bash

# Script para build de todas as imagens Docker

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo "🔨 Construindo imagens Docker..."

# Build do predictor
echo "📦 Construindo predictive-hpa-predictor..."
docker build -t predictive-hpa-predictor:latest "$PROJECT_ROOT/src/predictor"

# Build do service
echo "📦 Construindo predictive-hpa-service..."
docker build -t predictive-hpa-service:latest -f "$PROJECT_ROOT/src/workload/Dockerfile.service" "$PROJECT_ROOT/src/workload"

# Build do router
echo "📦 Construindo predictive-hpa-router..."
docker build -t predictive-hpa-router:latest -f "$PROJECT_ROOT/src/workload/Dockerfile.router" "$PROJECT_ROOT/src/workload"

echo "✅ Todas as imagens construídas com sucesso!"
echo ""
echo "📋 Imagens disponíveis:"
docker images | grep predictive-hpa
