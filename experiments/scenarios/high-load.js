// Cenário de Alta Carga - 1000 RPS com pico de 30s aos 2m30
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Métricas customizadas
const errorRate = new Rate('errors');
const latency = new Trend('latency_ms');

export const options = {
  scenarios: {
    // Carga base de 1000 RPS
    base_load: {
      executor: 'constant-arrival-rate',
      rate: 1000,
      timeUnit: '1s',
      duration: '5m',
      preAllocatedVUs: 200,
      maxVUs: 500,
    },
    // Pico: aos 2min30 (metade do experimento)
    spike_1: {
      executor: 'constant-arrival-rate',
      rate: 2000,         // Dobra a carga
      timeUnit: '1s',
      duration: '30s',
      startTime: '2m30s',
      preAllocatedVUs: 100,
      maxVUs: 300,
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<1000'],  // p95 < 1000ms
    errors: ['rate<0.10'],               // Error rate < 10%
  },
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export default function () {
  const startTime = Date.now();
  
  const response = http.get(`${BASE_URL}/route`);
  
  const duration = Date.now() - startTime;
  latency.add(duration);
  
  const success = check(response, {
    'status is 200': (r) => r.status === 200,
    'response time < 1000ms': (r) => r.timings.duration < 1000,
  });
  
  errorRate.add(!success);
}

export function handleSummary(data) {
  const outputDir = __ENV.RESULTS_DIR || 'experiments/results/raw';
  return {
    [`${outputDir}/high-load-summary.json`]: JSON.stringify(data, null, 2),
  };
}
