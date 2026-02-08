import requests
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

ROUTER_URL = "http://localhost:8080/route"


def send_request():
    start = time.time()
    try:
        response = requests.get(ROUTER_URL, timeout=5)
        latency = time.time() - start
        return latency, response.status_code
    except Exception:
        latency = time.time() - start
        return latency, 500


def run_load_test(concurrent_users=5, total_requests=50, delay=0.5):
    latencies = []
    statuses = {}

    with ThreadPoolExecutor(max_workers=concurrent_users) as executor:
        futures = []
        for _ in range(total_requests):
            futures.append(executor.submit(send_request))
            time.sleep(delay)

        for future in as_completed(futures):
            latency, status = future.result()
            latencies.append(latency)
            statuses[status] = statuses.get(status, 0) + 1

    print("\n=== Load Test Summary ===")
    print(f"Total Requests: {total_requests}")
    print(f"Success: {statuses.get(200, 0)} | Failures: {total_requests - statuses.get(200, 0)}")
    print(f"Avg Latency: {sum(latencies) / len(latencies):.2f}s")
    print(f"Max Latency: {max(latencies):.2f}s")
    print(f"Min Latency: {min(latencies):.2f}s")


if __name__ == "__main__":
    # ~1 min per strategy: 2000 requests x 0.03s delay (60s to submit)
    run_load_test(concurrent_users=5, total_requests=2_000, delay=0.03)
