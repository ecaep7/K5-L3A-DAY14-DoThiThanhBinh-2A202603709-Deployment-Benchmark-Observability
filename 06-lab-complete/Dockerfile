# ---------- Stage 1: builder — cài dependencies ----------
FROM python:3.11-slim AS builder

WORKDIR /build
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# ---------- Stage 2: runtime — chỉ copy kết quả ----------
FROM python:3.11-slim AS runtime

RUN groupadd -r agent && useradd -r -g agent -d /home/agent -m agent

WORKDIR /app
COPY --from=builder /root/.local /home/agent/.local
COPY app/ ./app/
COPY utils/ ./utils/
RUN chown -R agent:agent /app /home/agent/.local

USER agent

ENV PYTHONUSERBASE=/home/agent/.local \
    PATH=/home/agent/.local/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8000

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:${PORT:-8000}/health', timeout=3)" || exit 1

# exec → uvicorn là PID 1, nhận SIGTERM trực tiếp khi `docker stop`
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]
