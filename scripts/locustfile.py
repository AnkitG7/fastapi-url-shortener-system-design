# ======================================================
# scripts/locustfile.py — Production Locust Load Testing Suite
# ======================================================
# SYSTEM DESIGN CONCEPT: Multi-Persona Traffic Simulation
# -------------------------------------------------
# 1. READ-HEAVY REALISTIC TRAFFIC RATIO:
#    - 80% Redirect Traffic (Hot URL clicks & Cache hits)
#    - 15% URL Creation (Writes to DB + Cache pre-warming)
#    - 5% Analytics Queries (Aggregation reads)
#
# 2. RUN COMMANDS:
#    - Headless CLI run (30s test with 50 users):
#      locust -f scripts/locustfile.py --headless -u 50 -r 10 -t 30s --host http://localhost:8000
#
#    - Interactive Web UI:
#      locust -f scripts/locustfile.py --host http://localhost:8000
#      (Open http://localhost:8089 in browser)
# ======================================================

import random
from locust import HttpUser, task, between
import shortuuid


class URLShortenerUser(HttpUser):
    """
    Simulates real-world traffic with read/write weighted tasks.
    """
    # High-throughput pacing (50ms - 200ms sleep)
    wait_time = between(0.05, 0.2)

    # Common short codes populated during test
    created_codes = ["locust-target"]

    def on_start(self):
        """Setup initial hot URLs before running traffic."""
        headers = {"X-API-Key": "premium-key-xyz"}
        # Create seed URL for redirect benchmarks (catch 409 if already exists)
        with self.client.post(
            "/api/v1/shorten",
            json={
                "original_url": "https://fastapi.tiangolo.com",
                "custom_code": "locust-target",
            },
            headers=headers,
            catch_response=True,
            name="/api/v1/shorten [setup]",
        ) as response:
            if response.status_code in (201, 409):
                response.success()
            else:
                response.failure(f"Setup failed: {response.status_code}")

    # ---------------------------------------------------
    # Task 1: Redirect / Click Hot URLs (Weight: 80 - Read Heavy)
    # ---------------------------------------------------
    @task(80)
    def redirect_url(self):
        """
        Simulates clicking a short URL (Cache-Aside read + async telemetry).
        Expected status: 307 Temporary Redirect.
        """
        code = random.choice(self.created_codes)
        with self.client.get(
            f"/{code}",
            allow_redirects=False,
            catch_response=True,
            name="/{short_code} (Redirect)",
        ) as response:
            if response.status_code in (307, 200):
                response.success()
            elif response.status_code == 404:
                response.success()
            else:
                response.failure(f"Unexpected status: {response.status_code}")

    # ---------------------------------------------------
    # Task 2: Create Short URLs (Weight: 15 - Write Path)
    # ---------------------------------------------------
    @task(15)
    def create_short_url(self):
        """
        Simulates creating new short URLs.
        Tests PostgreSQL write throughput and Redis cache pre-warming.
        """
        rand_id = shortuuid.uuid()[:8]
        payload = {
            "original_url": f"https://example.com/products/{rand_id}",
        }
        headers = {"X-API-Key": "premium-key-xyz"}

        with self.client.post(
            "/api/v1/shorten",
            json=payload,
            headers=headers,
            catch_response=True,
            name="/api/v1/shorten (Create)",
        ) as response:
            if response.status_code == 201:
                data = response.json()
                if "short_code" in data and len(self.created_codes) < 200:
                    self.created_codes.append(data["short_code"])
                response.success()
            else:
                response.failure(f"Create failed with status {response.status_code}")

    # ---------------------------------------------------
    # Task 3: View URL Analytics (Weight: 5 - Aggregate Queries)
    # ---------------------------------------------------
    @task(5)
    def view_analytics(self):
        """
        Simulates querying aggregated analytics (24h count, referrers, user agents).
        """
        code = random.choice(self.created_codes)
        headers = {"X-API-Key": "premium-key-xyz"}
        with self.client.get(
            f"/api/v1/urls/{code}/analytics",
            headers=headers,
            catch_response=True,
            name="/api/v1/urls/{code}/analytics",
        ) as response:
            if response.status_code in (200, 404):
                response.success()
            else:
                response.failure(f"Analytics query failed: {response.status_code}")

    # ---------------------------------------------------
    # Task 4: Health Check Probe (Weight: 2 - Observability)
    # ---------------------------------------------------
    @task(2)
    def health_check(self):
        """
        Diagnostic probe checking PostgreSQL and Redis dependencies.
        """
        with self.client.get(
            "/health/ready",
            catch_response=True,
            name="/health/ready",
        ) as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Health probe failed: {response.status_code}")
