# Deployment Information

## Public URL
https://k5-l3a-day14-dothithanhbinh-2a202603709-deployme-production.up.railway.app

## Platform
Railway (deploy thư mục `06-lab-complete/` bằng `railway up`, build theo `railway.toml` → Dockerfile multi-stage). Redis là service Redis của Railway trong cùng project, kết nối qua mạng nội bộ.

## Test Commands

```bash
BASE=https://k5-l3a-day14-dothithanhbinh-2a202603709-deployme-production.up.railway.app

curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"   # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"    # 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'   # 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'   # 200
```

Kết quả thực tế: `200`, `200`, `401`, `200`.

## Environment Variables Set (trên Railway, không ghi trong code)
- `AGENT_API_KEY` — key ngẫu nhiên sinh bằng `secrets.token_urlsafe(24)`, chỉ lưu trên Railway
- `REDIS_URL` — tham chiếu `${{Redis.REDIS_URL}}` tới service Redis cùng project
- `ENVIRONMENT=production`
- `PORT` — Railway tự cấp (8080); app đọc qua `${PORT:-8000}` trong CMD của Dockerfile
- `RATE_LIMIT_PER_MINUTE`, `DAILY_BUDGET_USD` — dùng giá trị mặc định trong `app/config.py` (10 req/phút, $1/ngày)

## Screenshots
- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)