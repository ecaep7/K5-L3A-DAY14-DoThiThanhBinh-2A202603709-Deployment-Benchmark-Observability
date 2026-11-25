"""
Cost guard (tiêu chí 8): cộng dồn chi phí theo ngày trong Redis, vượt DAILY_BUDGET_USD → 402.
"""
import time

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

# Giá USD / 1K tokens (tham khảo gpt-4o-mini)
PRICE_INPUT_PER_1K = 0.00015
PRICE_OUTPUT_PER_1K = 0.0006


def _today_key() -> str:
    return "cost:" + time.strftime("%Y-%m-%d", time.gmtime())


def check_budget() -> None:
    """Gọi TRƯỚC khi gọi LLM. Hết budget → 402."""
    spent = float(r.get(_today_key()) or 0)
    if spent >= settings.daily_budget_usd:
        raise HTTPException(
            status_code=402,
            detail={"error": "Daily budget exceeded",
                    "spent_usd": round(spent, 6),
                    "budget_usd": settings.daily_budget_usd},
        )


def record_cost(input_tokens: int, output_tokens: int) -> float:
    """Gọi SAU khi gọi LLM. Cộng chi phí request vào tổng ngày, trả về chi phí request."""
    cost = (input_tokens / 1000) * PRICE_INPUT_PER_1K + (output_tokens / 1000) * PRICE_OUTPUT_PER_1K
    key = _today_key()
    pipe = r.pipeline()
    pipe.incrbyfloat(key, cost)
    pipe.expire(key, 2 * 24 * 3600)   # tự xoá sau 2 ngày
    pipe.execute()
    return cost
