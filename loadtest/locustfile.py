"""Load test for the rate limiter.

Run from the project root (server must be running):

    locust -f loadtest/locustfile.py --headless -u 60 -r 60 -t 30s \
        --host http://127.0.0.1:8000
"""
import math
import random
import time

import requests
from locust import HttpUser, constant, events, task

RUN_ID = int(time.time())  # new keys every run, so earlier runs can't interfere
TB_KEY = f"load-tb-{RUN_ID}"
SW_KEY = f"load-sw-{RUN_ID}"
RATE = 50    # tokens per second
BURST = 100  # bucket capacity / sliding-window limit (window = BURST / RATE = 2 s)
TARGET_RPS = 500


class Tally:
    """Counts ALLOW/DENY results for one hot key."""

    def __init__(self):
        self.allowed = 0
        self.denied = 0
        self.first = None  # when the first request was sent
        self.last = None   # when the last response arrived

    def record(self, status_code, sent_at, received_at):
        if status_code == 200:
            self.allowed += 1
        else:
            self.denied += 1
        if self.first is None or sent_at < self.first:
            self.first = sent_at
        if self.last is None or received_at > self.last:
            self.last = received_at


tallies = {TB_KEY: Tally(), SW_KEY: Tally()}


def do_check(user, key, name):
    sent_at = time.time()
    with user.client.post(
        "/check", json={"client_key": key}, name=name, catch_response=True
    ) as resp:
        received_at = time.time()
        if resp.status_code not in (200, 429):
            resp.failure(f"unexpected status {resp.status_code}")
        elif not all(
            h in resp.headers
            for h in ("X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset")
        ):
            resp.failure("missing rate-limit headers")
        else:
            resp.success()  # both ALLOW (200) and DENY (429) are correct behavior
            if key in tallies:
                tallies[key].record(resp.status_code, sent_at, received_at)


class TokenBucketHotKeyUser(HttpUser):
    weight = 2
    wait_time = constant(0)

    @task
    def check(self):
        do_check(self, TB_KEY, "/check [token bucket, hot key]")


class SlidingWindowHotKeyUser(HttpUser):
    weight = 2
    wait_time = constant(0)

    @task
    def check(self):
        do_check(self, SW_KEY, "/check [sliding window, hot key]")


class SpreadUser(HttpUser):
    weight = 1
    wait_time = constant(0)

    @task
    def check(self):
        key = f"load-spread-{random.randint(1, 1000)}"
        do_check(self, key, "/check [1000 spread keys]")


@events.test_start.add_listener
def configure_clients(environment, **kwargs):
    for key, algorithm in ((TB_KEY, "token_bucket"), (SW_KEY, "sliding_window")):
        r = requests.put(
            f"{environment.host}/admin/clients/{key}",
            json={"rate": RATE, "burst": BURST, "algorithm": algorithm},
            timeout=10,
        )
        r.raise_for_status()


def report(name, tally, low, high):
    ok = low <= tally.allowed <= high
    print(
        f"{name:<16} allowed={tally.allowed:>6}  denied={tally.denied:>7}  "
        f"expected {low:.0f}..{high:.0f}  {'PASS' if ok else 'FAIL'}"
    )
    return ok


@events.test_stop.add_listener
def verify_correctness(environment, **kwargs):
    tb, sw = tallies[TB_KEY], tallies[SW_KEY]
    if tb.first is None or sw.first is None:
        print("No requests were recorded, so nothing can be verified.")
        environment.process_exit_code = 1
        return

    print("\n=== Correctness and throughput verdict ===")
    results = []

    # Token bucket: at most burst + rate * elapsed tokens ever existed.
    elapsed = tb.last - tb.first
    results.append(
        report(
            "token bucket",
            tb,
            low=BURST + RATE * elapsed - RATE * 0.5 - 5,
            high=BURST + RATE * elapsed + 1,
        )
    )

    # Sliding window: at most BURST allowed in any slice as long as the window.
    window = BURST / RATE
    elapsed = sw.last - sw.first
    results.append(
        report(
            "sliding window",
            sw,
            low=BURST * max(1, math.floor(elapsed / window) - 1),
            high=BURST * math.ceil(elapsed / window),
        )
    )

    # Throughput over the whole run.
    stats = environment.stats.total
    overall = max(tb.last, sw.last) - min(tb.first, sw.first)
    rps = stats.num_requests / overall
    ok = rps >= TARGET_RPS
    results.append(ok)
    print(f"{'throughput':<16} {rps:,.0f} requests/s (target >= {TARGET_RPS})  "
          f"{'PASS' if ok else 'FAIL'}")

    # No unexpected statuses or missing headers.
    ok = stats.num_failures == 0
    results.append(ok)
    print(f"{'failures':<16} {stats.num_failures}  {'PASS' if ok else 'FAIL'}")

    if not all(results):
        environment.process_exit_code = 1

    for key in (TB_KEY, SW_KEY):  # clean up the configs this run created
        requests.delete(f"{environment.host}/admin/clients/{key}", timeout=10)