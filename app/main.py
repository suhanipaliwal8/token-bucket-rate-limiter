from fastapi import FastAPI, Response, status

from app.schemas import CheckRequest, CheckResponse
from app.store import InMemoryBucketStore

app = FastAPI(title="Token Bucket Rate Limiter Service")
store = InMemoryBucketStore()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/check", response_model=CheckResponse)
def check(body: CheckRequest, response: Response):
    decision = store.check(body.client_key)
    if not decision.allowed:
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
    return CheckResponse(
        decision="ALLOW" if decision.allowed else "DENY",
        remaining=decision.remaining,
        retry_after=decision.retry_after,
        reset_after=decision.reset_after,
    )