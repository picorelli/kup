import os
import random
from contextlib import asynccontextmanager

import numpy as np
import requests
from fastapi import FastAPI
from prometheus_client import start_http_server, Counter, Gauge
from sklearn.linear_model import LinearRegression


SERVICE_A_URL = os.environ.get("SERVICE_A_URL", "http://service-a:8000/process")
SERVICE_B_URL = os.environ.get("SERVICE_B_URL", "http://service-b:8000/process")

ROUTE_CALLS = Counter('router_calls_total', 'Total calls to router')
PREDICTED_LATENCY_A = Gauge('predict_router_latency_a_seconds', 'Predicted latency for service A')
PREDICTED_LATENCY_B = Gauge('predict_router_latency_b_seconds', 'Predicted latency for service B')

latency_history = {"A": [], "B": []}
models = {"A": LinearRegression(), "B": LinearRegression()}


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_http_server(9200)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/route")
def route():
    ROUTE_CALLS.inc()

    predicted_a = predicted_b = 1.0

    for service in ["A", "B"]:
        data = latency_history[service]
        if len(data) >= 5:
            X = np.array(range(len(data))).reshape(-1, 1)
            y = np.array(data)
            models[service].fit(X, y)
            predicted = models[service].predict([[len(data)]])[0]
            if service == "A":
                predicted_a = predicted
            else:
                predicted_b = predicted

    PREDICTED_LATENCY_A.set(predicted_a)
    PREDICTED_LATENCY_B.set(predicted_b)

    if predicted_a == predicted_b == 1.0:
        service = random.choice(["A", "B"])
    else:
        service = "A" if predicted_a <= predicted_b else "B"

    url = SERVICE_A_URL if service == "A" else SERVICE_B_URL
    response = requests.get(url)

    latency_history[service].append(response.json().get("processing_time", 1.0))
    latency_history[service] = latency_history[service][-50:]  # sliding window: keep last 50

    return {
        "called_service": service,
        "response": response.json(),
        "predicted_latency": {"A": predicted_a, "B": predicted_b},
    }
