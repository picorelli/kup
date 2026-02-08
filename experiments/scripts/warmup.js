// Warmup script — 5 minutos com VUs fixos (não incluído nas métricas, protocolo TCC)
import http from 'k6/http';
import { sleep } from 'k6';

export const options = {
  vus: 10,
  duration: '5m',
};

const BASE_URL = __ENV.BASE_URL || 'http://localhost:8080';

export default function () {
  http.get(`${BASE_URL}/route`);
  sleep(0.1);
}
