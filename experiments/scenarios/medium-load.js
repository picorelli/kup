// Cenário de Média Carga - 200 RPS constante
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

// Métricas customizadas
const errorRate = new Rate('errors');
const latency = new Trend('latency_ms');

export const options = {
  scenarios: {
    medium_load: {
      executor: 'constant-arrival-rate',
      rate: 200,          // 200 RPS
      timeUnit: '1s',
      duration: '5m',     // 5 minutos de execução
      preAllocatedVUs: 50,
      maxVUs: 200,
    },
  },
  thresholds: {
    http_req_duration: ['p(95)<500'],  // p95 < 500ms
    errors: ['rate<0.05'],              // Error rate < 5%
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
    'response time < 500ms': (r) => r.timings.duration < 500,
  });
  
  errorRate.add(!success);
}

export function handleSummary(data) {
  const outputDir = __ENV.RESULTS_DIR || 'experiments/results/raw';
  return {
    [`${outputDir}/medium-load-summary.json`]: JSON.stringify(data, null, 2),
  };
}
