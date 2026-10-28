# Token Bucket Rate Limiter Service
A standalone API that rate-limits other APIs.


## Load test

The load test checks correctness under concurrent load, not just speed. It sends traffic for one token-bucket client and one sliding-window client (the hardest case: many simultaneous requests for the same key) plus 1,000 spread-out keys, then verifies that the number of allowed requests stays inside mathematical bounds:

- **Token bucket:** allowed <= burst + rate x elapsed (a double-spent token would exceed this)
- **Sliding window:** allowed <= limit per window-length slice of time
- It also checks that every response carries the rate-limit headers and that throughput is at least 500 requests/second.

### Run it

```bash
pip install -r requirements-loadtest.txt
uvicorn app.main:app --no-access-log --log-level warning    # terminal 1, single process
locust -f loadtest/locustfile.py --headless -u 60 -r 60 -t 30s --host http://127.0.0.1:8000   # terminal 2
```

### Results

(paste the "Correctness and throughput verdict" block from your run here, plus the date and a one-line description of your machine)