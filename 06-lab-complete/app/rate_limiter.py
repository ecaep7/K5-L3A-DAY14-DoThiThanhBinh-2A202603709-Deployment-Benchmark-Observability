"""
Rate limiting (tiêu chí 7): sliding window 60 giây, state trong Redis.
"""
import hashlib
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60


def check_rate_limit(key: str) -> None:
    # Không lưu API key thô làm tên key trong Redis — dùng hash
    bucket = "ratelimit:" + hashlib.sha256(key.encode()).hexdigest()[:16]
    now = time.time()

    pipe = r.pipeline()
    pipe.zremrangebyscore(bucket, 0, now - WINDOW_SECONDS)   # bỏ request cũ hơn 60s
    pipe.zcard(bucket)                                      # đếm request còn trong cửa sổ
    _, count = pipe.execute()

    if count >= settings.rate_limit_per_minute:
        oldest = r.zrange(bucket, 0, 0, withscores=True)
        retry_after = int(oldest[0][1] + WINDOW_SECONDS - now) + 1 if oldest else WINDOW_SECONDS
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(max(retry_after, 1))},
        )

    pipe = r.pipeline()
    pipe.zadd(bucket, {f"{now}-{uuid.uuid4().hex[:8]}": now})
    pipe.expire(bucket, WINDOW_SECONDS)
    pipe.execute()
