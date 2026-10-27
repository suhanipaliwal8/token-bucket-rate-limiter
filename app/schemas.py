from typing import Literal

from pydantic import BaseModel, Field


class CheckRequest(BaseModel):
    client_key: str = Field(min_length=1, max_length=128)


class CheckResponse(BaseModel):
    decision: Literal["ALLOW", "DENY"]
    remaining: int
    retry_after: float
    reset_after: float


class ClientConfigIn(BaseModel):
    rate: float = Field(gt=0, le=100000)
    burst: int = Field(gt=0, le=1000000)


class ClientConfigOut(BaseModel):
    client_key: str
    rate: float
    burst: int