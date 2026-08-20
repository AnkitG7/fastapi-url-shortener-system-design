# ======================================================
# scripts/load_test.py — High-Concurrency Async Load Tester
# ======================================================
# SYSTEM DESIGN CONCEPT: Performance Benchmarking & SLA Validation
# -------------------------------------------------
# Measures:
# 1. Throughput (Requests Per Second / RPS / QPS)
# 2. Latency Percentiles (P50, P95, P99, Mean, Max)
# 3. Cache Hit vs Cache Miss performance
# 4. Rate Limiting enforcement under high load
# 5. Connection pool & async concurrency limits
# ======================================================

import asyncio
import time
import statistics
from typing import List, Dict, Any
import httpx


class LoadTester:
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url

    async def run_benchmark(
        self,
        name: str,
        total_requests: int = 500,
        concurrency: int = 50,
        request_func=None,
    ) -> Dict[str, Any]:
        """
        Execute a concurrent benchmark scenario.
        """
        print(f"\n[BENCHMARK] Running: {name}")
        print(f"            Total Requests: {total_requests} | Concurrency: {concurrency}")

        latencies: List[float] = []
        status_codes: Dict[int, int] = {}
        sem = asyncio.Semaphore(concurrency)

        limits = httpx.Limits(max_keepalive_connections=concurrency, max_connections=concurrency * 2)
        timeout = httpx.Timeout(15.0, connect=5.0)

        async with httpx.AsyncClient(limits=limits, timeout=timeout) as client:
            async def worker():
                async with sem:
                    t0 = time.perf_counter()
                    try:
                        code = await request_func(client)
                        duration_ms = (time.perf_counter() - t0) * 1000
                        latencies.append(duration_ms)
                        status_codes[code] = status_codes.get(code, 0) + 1
                    except Exception as e:
                        duration_ms = (time.perf_counter() - t0) * 1000
                        latencies.append(duration_ms)
                        status_codes[500] = status_codes.get(500, 0) + 1

            start_time = time.perf_counter()
            tasks = [worker() for _ in range(total_requests)]
            await asyncio.gather(*tasks)
            total_duration = time.perf_counter() - start_time

        rps = total_requests / total_duration if total_duration > 0 else 0
        latencies.sort()

        p50 = statistics.median(latencies) if latencies else 0
        p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
        p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
        mean = statistics.mean(latencies) if latencies else 0
        max_lat = max(latencies) if latencies else 0

        results = {
            "name": name,
            "total_requests": total_requests,
            "concurrency": concurrency,
            "total_duration_sec": round(total_duration, 2),
            "requests_per_sec": round(rps, 2),
            "latency_mean_ms": round(mean, 2),
            "latency_p50_ms": round(p50, 2),
            "latency_p95_ms": round(p95, 2),
            "latency_p99_ms": round(p99, 2),
            "latency_max_ms": round(max_lat, 2),
            "status_codes": status_codes,
        }

        self._print_results(results)
        return results

    def _print_results(self, res: Dict[str, Any]) -> None:
        print("   " + "=" * 55)
        print(f"   [TIME] Total Duration : {res['total_duration_sec']}s")
        print(f"   [QPS]  Throughput     : {res['requests_per_sec']} req/sec (RPS)")
        print(f"   [LAT]  Latency Mean   : {res['latency_mean_ms']} ms")
        print(f"   [LAT]  Latency P50    : {res['latency_p50_ms']} ms")
        print(f"   [LAT]  Latency P95    : {res['latency_p95_ms']} ms")
        print(f"   [LAT]  Latency P99    : {res['latency_p99_ms']} ms")
        print(f"   [LAT]  Latency Max    : {res['latency_max_ms']} ms")
        print(f"   [CODE] Status Codes   : {res['status_codes']}")
        print("   " + "=" * 55)


async def main():
    tester = LoadTester(base_url="http://localhost:8000")

    # Setup: Create a sample URL to benchmark redirects
    async with httpx.AsyncClient() as client:
        res = await client.post(
            "http://localhost:8000/api/v1/shorten",
            json={"original_url": "https://fastapi.tiangolo.com", "custom_code": "load-test-target"},
            headers={"X-API-Key": "premium-key-xyz"},
        )
        if res.status_code not in (201, 409):
            print(f"[SETUP] Setup status: {res.status_code}")

    # ===================================================
    # SCENARIO 1: High-Concurrency Redirects (Redis Cache Hit)
    # ===================================================
    async def redirect_task(client: httpx.AsyncClient) -> int:
        r = await client.get("http://localhost:8000/load-test-target", follow_redirects=False)
        return r.status_code

    await tester.run_benchmark(
        name="Redirect Throughput (Redis Cache Hits)",
        total_requests=1000,
        concurrency=50,
        request_func=redirect_task,
    )

    # ===================================================
    # SCENARIO 2: Concurrent URL Shortening (PostgreSQL Writes)
    # ===================================================
    counter = 0
    async def create_task(client: httpx.AsyncClient) -> int:
        nonlocal counter
        counter += 1
        r = await client.post(
            "http://localhost:8000/api/v1/shorten",
            json={"original_url": f"https://example.com/item/{counter}"},
            headers={"X-API-Key": "premium-key-xyz"},
        )
        return r.status_code

    await tester.run_benchmark(
        name="URL Creation Throughput (PostgreSQL Writes + Cache Pre-warm)",
        total_requests=300,
        concurrency=20,
        request_func=create_task,
    )

    # ===================================================
    # SCENARIO 3: Rate Limiting Enforcement Under Load
    # ===================================================
    async def rate_limited_task(client: httpx.AsyncClient) -> int:
        # Anonymous client making rapid requests (Limit is 10 req/min)
        r = await client.get("http://localhost:8000/api/v1/urls")
        return r.status_code

    await tester.run_benchmark(
        name="Rate Limiting Under Attack (Anonymous IP Throttling)",
        total_requests=50,
        concurrency=10,
        request_func=rate_limited_task,
    )

    # ===================================================
    # SCENARIO 4: Health Check Readiness Probe Throughput
    # ===================================================
    async def health_task(client: httpx.AsyncClient) -> int:
        r = await client.get("http://localhost:8000/health/ready")
        return r.status_code

    await tester.run_benchmark(
        name="Readiness Probe Throughput (Postgres + Redis Pings)",
        total_requests=300,
        concurrency=20,
        request_func=health_task,
    )


if __name__ == "__main__":
    asyncio.run(main())
