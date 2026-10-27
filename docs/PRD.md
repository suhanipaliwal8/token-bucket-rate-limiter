# Token Bucket Rate Limiter Service – PRD & Project Docs

Author: Suhani · Version 0.1 (draft) · October 27, 2026

## 1. Overview

### 1.1 Problem

APIs need protection from abuse, accidental overload, and noisy neighbours. Every team ends up re-implementing rate limiting inside each service, usually inconsistently. This project builds a standalone, networked rate limiter: any service sends it a client key and gets back a decision, ALLOW or DENY, in a few milliseconds.

### 1.2 Summary

The Token Bucket Rate Limiter Service is an HTTP API that decides whether a request from a given client key should be allowed. It supports two algorithms (token bucket and sliding window), per-client limits managed through an admin API, state that survives restarts, safe behaviour under concurrent requests, standard rate-limit response headers, and a load test proving 500+ requests per second.

### 1.3 Goals

- Return a correct ALLOW/DENY decision per client key, with remaining quota and reset information.
- Let operators set different limits per client at runtime, without redeploying.
- Never over-allow because of race conditions.
- Keep limiter state across restarts.
- Sustain 500+ decisions per second with low latency, and prove it with a repeatable load test.
- Be a strong portfolio piece: clear architecture, ADRs, tests, benchmarks.

### 1.4 Non-goals (v1)

- Authenticating end users of the protected APIs (the limiter trusts the key the caller sends).
- A full web UI (only a stretch-goal dashboard).
- Multi-region or multi-node correctness (stretch goal: distributed mode).
- Billing, quotas by calendar month, or usage analytics beyond basic metrics.

## 2. Users and Use Cases

| User | Need |
| --- | --- |
| Backend service (caller) | Ask "may this client proceed?" before doing work, and relay limit headers to its own clients. |
| Operator / admin | Create, update, view, and delete per-client limits at runtime. |
| Developer (Suhani, reviewers) | Read the code and docs and understand every design decision. |

Key scenarios:

1. A gateway calls the limiter for each incoming request using the API key as the client key.
2. An operator gives a premium client a higher limit through the admin endpoint.
3. A burst of 200 simultaneous requests for the same key arrives; exactly the allowed number succeed.
4. The service restarts; clients do not suddenly get a full bucket of fresh tokens.

## 3. Functional Requirements

| ID | Requirement | Priority |
| --- | --- | --- |
| FR-1 | `POST /v1/check` accepts a client key (and optional cost) and returns an ALLOW/DENY decision. | Must |
| FR-2 | Token bucket algorithm: capacity, refill rate, lazy refill based on elapsed time, burst allowed up to capacity. | Must |
| FR-3 | Sliding window algorithm selectable per client: at most N requests in any rolling window of W seconds. | Must |
| FR-4 | Admin endpoints to create, read, update, list, and delete per-client limit configs. | Must |
| FR-5 | A default config applies to keys with no explicit config. | Must |
| FR-6 | Limiter state and configs persist across restarts. | Must |
| FR-7 | Concurrent requests for the same key never cause more allows than the limit permits. | Must |
| FR-8 | Responses include rate-limit headers (`X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset`) and `Retry-After` on DENY. | Must |
| FR-9 | Admin endpoints are protected by an admin API key. | Must |
| FR-10 | `GET /healthz` for liveness and readiness checks. | Should |
| FR-11 | `GET /metrics` exposing allow/deny counts and latency. | Should |
| FR-12 | Input validation with clear 4xx error responses. | Must |

## 4. Non-Functional Requirements

| Category | Target |
| --- | --- |
| Throughput | 500+ checks/second sustained on a developer laptop, measured by a repeatable load test. |
| Latency | p99 under 20 ms for `/v1/check` at 500 req/s (target; confirm with measurement). |
| Correctness | Zero over-allows in the concurrency test suite. |
| Durability | After a clean shutdown no state is lost; after a crash, at most one snapshot interval of consumption is lost (see ADR-003). |
| Availability behaviour | Documented fail-open or fail-closed policy for callers (see ADR-006). |
| Maintainability | Algorithms are pure and unit-tested; web, storage, and algorithm code are separated. |
| Security | Admin key required, input size limits, key-length limits to avoid memory abuse. |
| Observability | Structured logs, basic metrics. |

## 5. API Specification (v1)

### 5.1 Check a request

`POST /v1/check`

Request body:

```json
{ "key": "client-123", "cost": 1 }
```

- `key` (string, required, 1 to 128 characters)
- `cost` (integer, optional, default 1, minimum 1)

ALLOW: HTTP 200

```json
{ "allowed": true, "limit": 100, "remaining": 87, "reset_after_ms": 1200, "retry_after_ms": 0 }
```

DENY: HTTP 429

```json
{ "allowed": false, "limit": 100, "remaining": 0, "reset_after_ms": 1200, "retry_after_ms": 340 }
```

Headers on both: `X-RateLimit-Limit`, `X-RateLimit-Remaining`, `X-RateLimit-Reset` (seconds). On DENY also `Retry-After` (seconds, rounded up).

### 5.2 Admin: manage limits

All require header `X-Admin-Key: <secret>`.

| Method and path | Purpose |
| --- | --- |
| `PUT /v1/admin/limits/{key}` | Create or replace a client's config. |
| `GET /v1/admin/limits/{key}` | Read one config. |
| `GET /v1/admin/limits` | List configs (paginated). |
| `DELETE /v1/admin/limits/{key}` | Remove config (client falls back to default). |

Config body:

```json
{ "algorithm": "token_bucket", "capacity": 100, "refill_rate": 10.0 }
```

or

```json
{ "algorithm": "sliding_window", "limit": 100, "window_seconds": 60 }
```

### 5.3 Operations

- `GET /healthz` returns 200 when the service is up and storage is reachable.
- `GET /metrics` returns counters and latency summary.

### 5.4 Errors

422 for invalid input, 401 for missing or wrong admin key, 404 for unknown config, 500 for internal errors. Error bodies follow one consistent shape: `{ "error": { "code": "...", "message": "..." } }`.

## 6. Architecture and Design

### 6.1 Components

1. **API layer** (FastAPI routes, Pydantic models): validation, auth, HTTP status codes, headers. No algorithm logic here.
2. **Limiter service layer**: looks up the config for a key, picks the algorithm, calls it under a per-key lock, returns a decision object.
3. **Algorithms** (pure Python, no I/O): `TokenBucket` and `SlidingWindow`. They take the current time as an input so tests can control the clock. Phase 1 (token bucket) is complete and is the base of this layer.
4. **State store**: in-memory dictionary of per-key state plus a lock per key. Hot path never touches the database.
5. **Persistence layer**: stores configs (written immediately) and state snapshots (written periodically and on shutdown).
6. **Metrics and logging**.

### 6.2 Request flow (`/v1/check`)

1. Validate the body.
2. Load the config for the key (cache, else default).
3. Acquire the key's lock.
4. Run the algorithm with the current monotonic or wall-clock time. Update state.
5. Release the lock.
6. Build the response and headers, increment metrics.
7. A background task snapshots dirty state to storage every few seconds.

### 6.3 Algorithms

**Token bucket.** State: `tokens` (float), `last_refill` (timestamp). On each check: `tokens = min(capacity, tokens + (now - last_refill) * refill_rate)`, then set `last_refill = now`. If `tokens >= cost`, subtract cost and ALLOW; otherwise DENY and compute `retry_after = (cost - tokens) / refill_rate`. Refill is lazy: no background timer per key.

**Sliding window.** Two options:

- *Log*: store timestamps of recent allowed requests, drop those older than the window, allow if count is under the limit. Exact, but memory grows with the limit.
- *Weighted counter*: keep the current and previous fixed-window counts and weight the previous one by how much of it still overlaps the window. Constant memory, approximate.

v1 uses the log variant for exactness and simplicity; the counter variant is documented as an optimisation (ADR-005).

### 6.4 Concurrency model

The check-and-consume step (read tokens, compare, subtract) must be atomic per key. v1 runs as a single process with one lock per key, which protects against parallel requests on the same key without blocking different keys. Running several worker processes would break this guarantee because each would hold its own state. That limitation is explicit and is what motivates the shared-store distributed stretch goal.

### 6.5 Data model

`limit_configs`

| Column | Type | Notes |
| --- | --- | --- |
| key | text, primary key | client key |
| algorithm | text | `token_bucket` or `sliding_window` |
| capacity / limit | integer | bucket size or window limit |
| refill\_rate | float, nullable | tokens per second |
| window\_seconds | integer, nullable | sliding window only |
| updated\_at | timestamp |  |

`limiter_state`

| Column | Type | Notes |
| --- | --- | --- |
| key | text, primary key |  |
| tokens | float, nullable | token bucket |
| last\_refill | float, nullable | token bucket |
| window\_log | JSON, nullable | sliding window timestamps |
| updated\_at | timestamp |  |

### 6.6 Suggested repository layout

```
rate-limiter/
  app/
    main.py            # FastAPI app creation, startup/shutdown
    api/               # routes: check.py, admin.py, health.py
    core/              # algorithms: token_bucket.py, sliding_window.py
    service/           # limiter.py (locks, config lookup, orchestration)
    storage/           # models, repository, snapshotter
    config.py          # settings from environment
  tests/               # unit, concurrency, API, persistence
  loadtest/            # locustfile.py, results/
  docs/                # this document, ADRs, benchmark report
  pytest.ini
  README.md
```

## 7. Architecture Decision Records

**ADR-001: Standalone HTTP service, not a library.** Callers in any language can use it, and limits are managed centrally. Cost: a network hop per decision, which the latency target accounts for.

**ADR-002: FastAPI for the API layer.** Lightweight, async-capable, Pydantic validation built in, automatic OpenAPI docs. Django would add an ORM and middleware this service does not need.

**ADR-003: In-memory hot path with periodic snapshot persistence.** Hitting a database on every check would make the 500 req/s target depend on database round-trips. Instead, state lives in memory and is snapshotted every few seconds and on shutdown. Trade-off: a crash can lose up to one interval of consumption, so clients may briefly get a few extra tokens. Acceptable for rate limiting; not acceptable for billing. Alternative considered: a PostgreSQL row lock per check (`SELECT ... FOR UPDATE`), which is exact but much slower. It remains an option if stronger durability is wanted.

**ADR-004: Per-key locks.** A single global lock is simplest but serialises unrelated clients. Per-key locks keep contention local. Lock objects are cleaned up with idle state.

**ADR-005: Sliding window log first.** Exact answers and easy tests; memory cost is acceptable at v1 limits. Revisit with the weighted counter if memory becomes a problem.

**ADR-006: Fail-open by default for callers.** If the limiter is unreachable, callers should let traffic through rather than take down their own service. This is a caller-side recommendation, documented in the README and configurable per integration.

**ADR-007: DENY is HTTP 429.** Proxies and clients already understand 429 plus `Retry-After`. The JSON body still carries the full decision.

**ADR-008: Algorithms take time as a parameter.** Makes tests deterministic with no sleeping, and keeps the algorithms pure.

## 8. Technology Stack

| Area | Choice | Familiarity |
| --- | --- | --- |
| Language | Python 3.11+ | Strong |
| API framework | FastAPI + Uvicorn + Pydantic | Introductory: used for CRUD endpoints, not yet for background tasks or lifespan events |
| Persistence | PostgreSQL (SQLite acceptable for early phases) | Used in Django projects; locking and transactions still being learned |
| Testing | pytest, plus `threading` or `asyncio` for concurrency tests | pytest started in Phase 1 |
| Load testing | Locust (Python-based) | New |
| Version control | Git + GitHub with PRs | In use |
| Stretch | Redis, Lua scripting, Docker | New; to be taught minimally when reached |

New concepts to learn along the way: locks and critical sections, race conditions, FastAPI lifespan and background tasks, write-behind persistence, load-testing metrics (throughput, percentiles), HTTP rate-limit headers.

## 9. Test and Load Plan

### 9.1 Unit tests

- Token bucket: starts full, consumes, denies when empty, refills proportionally, never exceeds capacity, handles cost greater than 1, correct `retry_after`.
- Sliding window: allows up to the limit, denies the next, allows again as old entries expire, boundary cases at the exact window edge.

### 9.2 Concurrency tests

- Fire many parallel checks for one key with capacity N and no refill; assert exactly N allows.
- Different keys in parallel do not interfere.

### 9.3 API tests

- Status codes, headers, validation errors, admin auth, default config fallback, config update takes effect on the next check.

### 9.4 Persistence tests

- Write state, shut down gracefully, restart, and confirm tokens are not reset to full.
- Configs survive restart.

### 9.5 Load test

- Locust scenario with a mix of keys (many keys plus a few hot keys).
- Ramp to 500+ req/s, hold for several minutes.
- Record: sustained req/s, p50, p95, p99 latency, error rate, correctness (allows never exceed theoretical maximum).
- Save results and a short benchmark report in `docs/`.

**Acceptance:** 500+ req/s sustained, zero over-allows, p99 within target, no errors other than expected 429s.

## 10. Phased Roadmap

Each phase ends with passing tests, a Git branch and pull request, and a commit message.

| Phase | Objective | Status |
| --- | --- | --- |
| 1 | Pure token bucket algorithm with pytest tests | Done (PR #1 merged) |
| 2 | Limiter service layer: key-to-state map, default config, per-key locks, concurrency tests | Next |
| 3 | FastAPI app with `POST /v1/check`, response headers, 429 behaviour | Planned |
| 4 | Admin API for per-client configs with admin key auth | Planned |
| 5 | Persistence: configs in the database, state snapshots, restart tests | Planned |
| 6 | Sliding window algorithm and per-client algorithm selection | Planned |
| 7 | Health, metrics, structured logging, error handling polish | Planned |
| 8 | Load test with Locust, tuning, benchmark report | Planned |
| 9 | README, architecture diagram, final docs, release | Planned |
| Stretch A | Distributed mode with Redis (atomic Lua script) | Optional |
| Stretch B | Live dashboard (counts, top denied keys) | Optional |

## 11. Risks and Mitigations

| Risk | Impact | Mitigation |
| --- | --- | --- |
| Race conditions under concurrency | Over-allows | Per-key locks, dedicated concurrency tests from Phase 2 |
| Snapshot writes slow the hot path | Missed latency target | Write in a background task, batch updates, only dirty keys |
| Memory growth from many keys | Crashes | Evict idle keys, cap key length, optional max-keys setting |
| Clock changes or drift | Wrong refills | Use monotonic time for elapsed calculations inside a process; store wall-clock only for persistence |
| Laptop benchmark noise | Unreliable numbers | Multiple runs, report median and spread, document hardware |
| Scope creep into stretch goals | Core unfinished | Stretch goals only after Phase 9 |

## 12. Stretch Goals

**Distributed mode.** Several limiter instances share one store (Redis). The check-and-consume step runs as a single atomic Lua script so it stays race-safe across processes. This directly removes the single-process limitation from section 6.4.

**Live dashboard.** A small page showing requests per second, allow versus deny ratio, and most-denied keys, fed by the metrics data.

## 13. Definition of Done (v1)

- All Must requirements implemented and tested.
- Load test shows 500+ req/s sustained with zero over-allows.
- README explains setup, API usage, and design trade-offs.
- ADRs and this document are up to date.
- Repo has a clean Git history with one pull request per phase.

## 14. Open Questions

1. PostgreSQL from the start, or SQLite until Phase 5?
2. Snapshot interval: 1 second, 5 seconds, or configurable?
3. Should DENY return 429 only, or also support a 200-with-flag mode for callers that prefer it?
4. Is a `cost` greater than capacity rejected as invalid, or always denied?
5. Idle-key eviction: time-based, size-based, or both?
