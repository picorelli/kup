FROM python:3.10-slim

WORKDIR /app

# Instala dependências do sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copia requirements e instala dependências Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia código-fonte
COPY . .

# Variáveis de ambiente padrão
ENV PROMETHEUS_URL=http://prometheus:9090
ENV NAMESPACE=predictive-hpa
ENV UPDATE_INTERVAL=30
ENV PREDICTION_HORIZON=30
ENV HISTORY_WINDOW=120
ENV DEFAULT_MODEL=random_forest
ENV METRICS_PORT=9090
ENV API_PORT=8080
ENV LOG_LEVEL=INFO

# Expõe portas
EXPOSE 8080 9090

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Comando de inicialização
CMD ["python", "main.py"]
