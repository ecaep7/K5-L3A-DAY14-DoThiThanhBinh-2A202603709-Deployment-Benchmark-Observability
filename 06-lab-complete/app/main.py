"""
Production AI Agent — Part 6 Final Project.
Chạy: uvicorn app.main:app --workers 2
"""
import json
import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import redis
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import redis_healthy
from utils.mock_llm import ask as llm_ask


# ── Structured logging: mỗi dòng log là 1 JSON object ─────────────────
class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        entry = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "lvl": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        entry.update(getattr(record, "extra_fields", {}))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


logger = logging.getLogger("agent")
logger.setLevel(logging.INFO)
_handler = logging.StreamHandler()
_handler.setFormatter(JsonFormatter())
logger.handlers = [_handler]
logger.propagate = False   # không đi qua root logger → không bị định dạng khác chen vào


def log(event: str, level: int = logging.INFO, **fields) -> None:
    logger.log(level, event, extra={"extra_fields": {"event": event, **fields}})


START_TIME = time.time()
_is_ready = False


# ── Lifecycle: startup / graceful shutdown ─────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    global _is_ready
    # Không bắt buộc Redis lúc khởi động — /ready sẽ báo 503 nếu Redis chưa sẵn sàng
    _is_ready = True
    log("startup", environment=settings.environment, port=settings.port)
    yield
    # uvicorn đã ngừng nhận request mới và chờ request đang chạy xong trước khi tới đây
    _is_ready = False
    log("shutdown", uptime_s=round(time.time() - START_TIME, 1))


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def access_log(request: Request, call_next):
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        log("request", method=request.method, path=request.url.path, status=status,
            ms=round((time.perf_counter() - started) * 1000, 1))


@app.exception_handler(redis.RedisError)
async def redis_error_handler(request: Request, exc: redis.RedisError):
    # Không lộ stack trace ra ngoài; ghi lỗi vào log JSON
    log("redis_error", level=logging.WARNING, path=request.url.path, error=type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Storage temporarily unavailable"})


class AskRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=2000)
    user_id: str | None = None


# ── Health checks ──────────────────────────────────────────────────────
@app.get("/health")
def health():
    """Liveness: luôn 200 khi process còn chạy, không phụ thuộc Redis."""
    return {
        "status": "ok",
        "uptime_seconds": round(time.time() - START_TIME, 1),
        "environment": settings.environment,
    }


@app.get("/ready")
def ready():
    """Readiness: 503 khi đang tắt hoặc Redis không kết nối được."""
    if not _is_ready:
        raise HTTPException(status_code=503, detail="Shutting down")
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis not available")
    return {"ready": True}


# ── Agent endpoint ─────────────────────────────────────────────────────
@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)      # 429 khi vượt giới hạn
    check_budget()                 # 402 khi hết budget

    answer = llm_ask(body.question)

    input_tokens = len(body.question.split()) * 2
    output_tokens = len(answer.split()) * 2
    cost = record_cost(input_tokens, output_tokens)
    log("ask", question_len=len(body.question), cost_usd=round(cost, 8))

    return {"question": body.question, "answer": answer}
