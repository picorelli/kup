import time
import random
from contextlib import asynccontextmanager

from fastapi import FastAPI
from prometheus_client import start_http_server, Summary


REQUEST_TIME = Summary('service_process_seconds', 'Time spent processing request')


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_http_server(9100)
    yield


app = FastAPI(lifespan=lifespan)


@app.get("/process")
@REQUEST_TIME.time()
def process():
    process_time = random.uniform(0.05, 0.15)
    time.sleep(process_time)
    return {"status": "success", "processing_time": process_time}
