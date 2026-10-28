from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Response, status

from app import client_config, snapshots
from app.db import close_db, init_db
from app.headers import rate_limit_headers
from app.schemas import (
    CheckRequest,
    CheckResponse,
    ClientConfigIn,
    ClientConfigOut,
)
from app.store import InMemoryBucketStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    store.import_buckets(snapshots.load_snapshot())
    store.import_windows(snapshots.load_window_snapshot())
    worker = snapshots.SnapshotWorker(store)
    worker.start()
    yield
    worker.stop()
    close_db()
    

app = FastAPI(title="Token Bucket Rate Limiter Service", lifespan=lifespan)
store = InMemoryBucketStore()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/check", response_model=CheckResponse)
def check(body: CheckRequest, response: Response):
    result = store.check(body.client_key)
    for name, value in rate_limit_headers(result).items():
        response.headers[name] = value
    if not result.allowed:
        response.status_code = status.HTTP_429_TOO_MANY_REQUESTS
    return CheckResponse(
        decision="ALLOW" if result.allowed else "DENY",
        remaining=result.remaining,
        retry_after=result.retry_after,
        reset_after=result.reset_after,
    )

@app.put("/admin/clients/{client_key}", response_model=ClientConfigOut)
def set_client_config(client_key: str, body: ClientConfigIn):
    cfg = client_config.upsert(client_key, body.rate, body.burst, body.algorithm)
    store.set_config(cfg)
    return ClientConfigOut(
        client_key=cfg.client_key,
        rate=cfg.rate,
        burst=cfg.burst,
        algorithm=cfg.algorithm,
    )


@app.get("/admin/clients/{client_key}", response_model=ClientConfigOut)
def get_client_config(client_key: str):
    cfg = client_config.get(client_key)
    if cfg is None:
        raise HTTPException(
            status_code=404, detail="No custom config; default limits apply"
        )
    return ClientConfigOut(
        client_key=cfg.client_key,
        rate=cfg.rate,
        burst=cfg.burst,
        algorithm=cfg.algorithm,
    )
@app.delete("/admin/clients/{client_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_client_config(client_key: str):
    if not client_config.delete(client_key):
        raise HTTPException(
            status_code=404, detail="No custom config for this client"
        )
    store.remove_config(client_key)