# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found
1. Dòng 17–18 — Hardcode thông tin nhạy cảm (`OPENAI_API_KEY` và `DATABASE_URL` chứa mật khẩu) trực tiếp trong mã nguồn. Khi push lên GitHub, ai cũng có thể đọc được; kẻ xấu sẽ đánh cắp API key để gọi dịch vụ tính tiền vào tài khoản của mình hoặc truy cập trái phép vào cơ sở dữ liệu.
2. Dòng 21–22 — Cấu hình viết cứng (`DEBUG = True`, `MAX_TOKENS = 500`) thay vì đọc từ biến môi trường. Khi muốn thay đổi cấu hình giữa môi trường dev và production, lập trình viên buộc phải sửa trực tiếp mã nguồn và deploy lại; đồng thời nếu sau này code mở rộng và dùng tới biến `DEBUG`, ứng dụng trên production sẽ mặc định chạy ở chế độ debug.
3. Dòng 33–38 — Dùng `print()` thay cho thư viện logging chuẩn, đặc biệt tại **dòng 34** lại in thẳng `OPENAI_API_KEY` ra màn hình console (và **dòng 38** in toàn bộ `response` ra log). Trên server thật, log thường được lưu tập trung hoặc gửi ra hệ thống giám sát; việc in secret và nội dung phản hồi vào log làm lộ API key cũng như dữ liệu nhạy cảm của người dùng cho bất kỳ ai có quyền đọc log, đồng thời `print()` thiếu cấp độ log (INFO, ERROR) và timestamp để truy vết sự cố.
4. Dòng 42–43 — Thiếu endpoint kiểm tra sức khỏe hệ thống (như `/health` hoặc `/healthz`). Khi chạy trên các nền tảng cloud/container (như Kubernetes, Render, Railway), hệ thống không có tín hiệu để biết ứng dụng đang hoạt động bình thường hay đã treo/crash để tự động khởi động lại (auto-restart) hoặc điều hướng traffic sang instance khác.
5. Dòng 49–53 — Cấu hình server chạy cứng cho môi trường local thay vì đọc từ biến môi trường:
   - `host="localhost"` (dòng 51): Chỉ lắng nghe kết nối nội bộ từ chính máy chủ đó, khiến người dùng bên ngoài hoặc reverse proxy của cloud platform không thể truy cập được ứng dụng.
   - `port=8000` (dòng 52): Không đọc biến `PORT` do các nền tảng như Railway/Render tự động cấp phát, dẫn đến lỗi không bind được cổng và deploy thất bại.
   - `reload=True` (dòng 53): Chạy thêm một tiến trình giám sát thay đổi của file gây tốn tài nguyên hệ thống, và mỗi khi có file thay đổi, server tự khởi động lại làm rơi toàn bộ các request đang xử lý dở.
6. Dòng 47–53 — Khối khởi chạy server không có cơ chế tắt an toàn (graceful shutdown) và không xử lý tín hiệu dừng từ hệ điều hành (`SIGTERM`). Khi cloud platform dừng container hoặc deploy phiên bản mới, ứng dụng bị ngắt đột ngột khiến các request đang xử lý dở bị cắt ngang và có thể gây mất mát hoặc sai lệch dữ liệu.

### Exercise 1.2: Kết quả chạy bản develop
Lệnh gọi (terminal B):

```
$ curl -i -X POST "http://localhost:8000/ask?question=Hello"
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 07:50:45 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Log server (terminal A):

```
INFO:     Uvicorn running on http://localhost:8000 (Press CTRL+C to quit)
INFO:     Started reloader process [1997] using WatchFiles
INFO:     Started server process [1999]
[DEBUG] Got question: Hello
[DEBUG] Using key: sk-hardcoded-fake-key-never-do-this
[DEBUG] Response: Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.
INFO:     127.0.0.1:33622 - "POST /ask?question=Hello HTTP/1.1" 200 OK
```

**Nhận xét:** App chạy được và trả về 200, nhưng chưa sẵn sàng cho production: API key bị in thẳng ra log (dòng `Using key`), câu hỏi và câu trả lời của người dùng cũng bị ghi nguyên văn, và `reload=True` sinh thêm một tiến trình reloader [1997] chạy song song với server [1999].
### Exercise 1.3: Comparison table

| Feature | Develop | Production | Tại sao quan trọng? |
| :--- | :--- | :--- | :--- |
| Config | Viết cứng (`app.py` dòng 17–22) | Đọc từ biến môi trường (`config.py` dòng 17–32) | Dùng chung một bộ mã nguồn cho cả dev, staging và prod mà không cần sửa code khi đổi môi trường, chỉ cần thay đổi biến cấu hình tương ứng (như database, giới hạn token hay mức log). |
| Secrets | Key nằm trong code và bị in ra log (dòng 17, 34) | `os.getenv("OPENAI_API_KEY")`, không log secret (`app.py` dòng 110–115) | Tránh lộ API key hay mật khẩu khi đẩy code lên GitHub hoặc khi log được đẩy sang hệ thống giám sát tập trung, ngăn kẻ xấu đánh cắp tài nguyên và phát sinh chi phí ngoài ý muốn. |
| Host / Port | `localhost`, `8000` cứng (dòng 51–52) | `0.0.0.0`, đọc `PORT` từ env (`app.py` dòng 196–197) | `0.0.0.0` cho phép nhận kết nối từ bên ngoài container/server thay vì chỉ nội bộ máy chủ, còn đọc `PORT` từ biến môi trường giúp tương thích với cổng cấp phát động của các nền tảng cloud như Render hay Railway. |
| Health check | Không có (`/health` trả 404) | `/health` (liveness) và `/ready` (readiness), dòng 135–161 | Cloud platform và load balancer định kỳ gọi các endpoint này: `/health` kiểm tra app còn sống hay đã treo để tự động restart nếu không trả về 200, còn `/ready` xác nhận app đã nạp xong dữ liệu/kết nối và sẵn sàng nhận traffic từ người dùng. |
| Logging | `print()` cả nội dung câu hỏi/trả lời (dòng 33–38) | Log JSON, chỉ ghi độ dài (dòng 28–31, 110–122) | Log định dạng JSON có cấu trúc giúp các công cụ phân tích dễ dàng lọc và truy vết sự cố, trong khi việc chỉ ghi độ dài thay vì nội dung gốc giúp bảo vệ dữ liệu riêng tư của người dùng (PII). |
| Shutdown | Tắt đột ngột, không xử lý | `lifespan` + bắt `SIGTERM` (dòng 63–67, 180–189) | Khi deploy bản mới hoặc dừng container, hệ thống gửi tín hiệu `SIGTERM` để app ngừng nhận request mới nhưng vẫn hoàn tất nốt các request đang xử lý dở thay vì cắt ngang gây lỗi cho người dùng. |
| Reload | `reload=True` luôn bật, có tiến trình reloader | Chỉ bật khi `DEBUG=true` (dòng 198), chỉ 1 tiến trình | Tắt reload trên production giúp tiết kiệm CPU/RAM do không phải chạy thêm tiến trình theo dõi thay đổi file, đồng thời tránh việc server tự khởi động lại bất ngờ làm rớt các kết nối đang chạy. |

**Quan sát thực tế khi chạy `production/app.py`:**
Về mặt thiết kế, bản production cấu hình log dạng JSON và ẩn thông tin nhạy cảm/nội dung câu hỏi. Tuy nhiên khi chạy thử nghiệm thực tế, log terminal chỉ xuất hiện các dòng truy cập mặc định của Uvicorn (`INFO: 127.0.0.1:... "POST /ask HTTP/1.1" 200 OK`) mà không có dòng log JSON nào của ứng dụng (như `"event": "startup"` hay `"event": "agent_request"`): nguyên nhân là do `config.py` gọi `logging.warning()` trước khi `app.py` thiết lập `basicConfig`, khiến Python tự khởi tạo logger gốc ở mức `WARNING` với định dạng mặc định (`WARNING:root:...`) và bỏ qua cấu hình định dạng JSON ở mức `INFO` phía sau.
## Part 2: Docker

### Exercise 2.1

1. **Base image là gì?**
   * **Base image:** `python:3.11` (dòng 8: `FROM python:3.11`).
   * **Kích thước:** Theo ghi chú ngay phía trên dòng `FROM` (dòng 7), đây là bản phân phối Python đầy đủ (full Python distribution) có dung lượng khoảng **~1 GB** (đi kèm nhiều công cụ hệ điều hành và thư viện biên dịch không thực sự cần thiết khi chạy production, dùng để làm mốc đối chiếu khi tối ưu dung lượng sang multi-stage build ở Exercise 2.3).

2. **Working directory là gì?**
   * **Working directory:** `/app` (dòng 11: `WORKDIR /app`).
   * Toàn bộ các lệnh tiếp theo như `COPY` (dấu `.` đại diện cho `/app`), `RUN` hay `CMD` đều lấy thư mục `/app` bên trong container làm gốc thực thi.

3. **Vì sao `COPY requirements.txt` đứng trước `COPY app.py`?**
   * **Cơ chế Layer Cache của Docker:** Docker build image theo từng lớp (layer) tuần tự từ trên xuống dưới, mỗi lệnh (`FROM`, `COPY`, `RUN`...) tạo ra một layer. Trước khi chạy một bước, Docker kiểm tra xem tệp đầu vào hoặc câu lệnh tại bước đó có thay đổi so với lần build trước không. Nếu không đổi, Docker tái sử dụng ngay kết quả đã lưu trong cache; nhưng **một khi một layer bị thay đổi, toàn bộ các layer nằm bên dưới nó đều bị vô hiệu hóa cache (cache invalidation) và buộc phải chạy lại từ đầu**.
   * **Tối ưu hóa quá trình build:**
     * **Khi tách riêng và đặt `COPY requirements.txt` trước:** Mã nguồn (`app.py`) là thứ lập trình viên sửa liên tục, trong khi danh sách thư viện (`requirements.txt`) rất ít khi thay đổi. Khi bạn chỉ sửa 1 dòng trong `app.py` rồi chạy `docker build` lại, Docker thấy `requirements.txt` không đổi nên lấy ngay kết quả từ cache cho cả bước `COPY requirements.txt` lẫn bước `RUN pip install -r requirements.txt` (vốn tốn hàng chục giây hoặc vài phút tải và cài gói), chỉ chạy lại từ bước `COPY app.py` trở đi nên build xong chỉ trong vài giây.
     * **Nếu copy toàn bộ code trước (ví dụ `COPY . .` trước `pip install`):** Chỉ cần sửa một dấu phẩy trong `app.py` cũng làm thay đổi dữ liệu đầu vào của lớp `COPY`, kéo theo lớp `RUN pip install` bên dưới mất cache và phải tải, cài lại toàn bộ thư viện từ đầu ở mọi lần build.
   * **Liên hệ với database:** Cơ chế này hoạt động tương tự cơ chế query cache hoặc materialized view trong SQL — khi bảng dữ liệu đầu vào của một truy vấn nặng không thay đổi, hệ thống trả về luôn kết quả đã tính sẵn thay vì quét và tính toán lại toàn bộ dữ liệu.

4. **`CMD` khác `ENTRYPOINT` thế nào?**
   * **`ENTRYPOINT`** quy định tiến trình chính cố định mà container sẽ luôn thực thi khi khởi động (giống phần **đường dẫn chương trình gốc** trong một shortcut trên Windows, ví dụ `python`). Nếu muốn đổi `ENTRYPOINT` lúc chạy, người dùng phải truyền cờ tường minh `--entrypoint`.
   * **`CMD`** đóng vai trò cung cấp lệnh mặc định hoặc bộ tham số mặc định truyền vào cho `ENTRYPOINT` (giống phần **tham số mặc định** đằng sau tên chương trình trong shortcut). `CMD` rất linh hoạt: nếu bạn chạy `docker run agent-develop`, container sẽ chạy lệnh mặc định `python app.py` (dòng 26); nhưng nếu bạn truyền thêm lệnh ở cuối như `docker run agent-develop bash` hoặc `docker run agent-develop python test.py`, toàn bộ phần `CMD` mặc định sẽ bị ghi đè bởi lệnh mới đó.
### Exercise 2.2: Build và run

Lệnh (chạy từ gốc repo):

```
docker build -f 02-docker/develop/Dockerfile -t my-agent:develop .
docker run --rm -p 8000:8000 my-agent:develop
```

Kết quả gọi container:

```
$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
server: uvicorn
content-type: application/json

{"status":"ok","uptime_seconds":12.7,"container":true}

$ curl -i -X POST "http://localhost:8000/ask?question=What%20is%20Docker"
HTTP/1.1 200 OK
server: uvicorn
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}
```

Dung lượng image:

```
$ docker images my-agent:develop
IMAGE              ID             DISK USAGE   CONTENT SIZE
my-agent:develop   5694a7d8ff93   1.67GB       426MB
```
### Exercise 2.3

1. **Stage 1 (`builder`, dòng 16–29) làm gì?**
   * Đóng vai trò là môi trường biên dịch tạm thời (image này không dùng để deploy): khởi tạo từ base image `python:3.11-slim`, cài đặt các công cụ biên dịch mức hệ điều hành (`gcc`, `libpq-dev`) để phục vụ việc build các gói thư viện phức tạp (như `numpy`), sau đó dùng `pip install --no-cache-dir --user` để cài toàn bộ thư viện trong `requirements.txt` vào thư mục `/root/.local` rồi dọn sạch cache tải gói của `apt`.

2. **Stage 2 (`runtime`, dòng 36–72) làm gì?**
   * Tạo ra image chạy thực tế gọn nhẹ và an toàn từ một nền `python:3.11-slim` sạch mới, chỉ sao chép thư mục thư viện đã biên dịch xong từ Stage 1 (`/root/.local` sang `/home/appuser/.local`) cùng mã nguồn ứng dụng (`main.py`, `utils/mock_llm.py`) và cấu hình `PATH`/`PYTHONPATH` để chạy server Uvicorn với 2 workers.
   * **Chạy app bằng user không có quyền root (dòng 40 & 58):** Tạo một user thường tên `appuser` (dòng 40), cấp quyền sở hữu thư mục `/app` và chuyển ngữ cảnh thực thi sang `USER appuser` (dòng 58). Đây là nguyên tắc bảo mật cốt lõi: nếu ứng dụng bị khai thác lỗ hổng, kẻ tấn công cũng không chiếm được quyền `root` bên trong container.
   * **Cơ chế tự kiểm tra sức khỏe `HEALTHCHECK` (dòng 68–69):** Cứ mỗi 30 giây (sau 5 giây khởi động đầu tiên), Docker tự động gửi request nội bộ tới `http://localhost:8000/health` (timeout 10 giây); nếu thất bại liên tiếp 3 lần, Docker đánh dấu trạng thái container là `unhealthy` (lưu ý: Docker engine mặc định không tự restart container khi chỉ bị `unhealthy`, kể cả khi đặt `restart: unless-stopped` vốn chỉ restart khi tiến trình thoát hẳn; các nền tảng điều phối như Kubernetes hay cloud platform mới dựa vào trạng thái `unhealthy` này để tự động restart hoặc ngừng điều hướng traffic vào container đó).

3. **Vì sao image production nhỏ hơn nhiều so với develop?**
   * **Khác biệt từ Base Image:** Bản `develop` dùng `python:3.11` đầy đủ (nặng tới `1591 MB` khi đo thực tế) chứa rất nhiều tiện ích hệ điều hành và thư viện phát triển không cần thiết, trong khi bản `production` dùng `python:3.11-slim` (`229 MB`) chỉ giữ lại nhân Python và các thư viện tối thiểu để chạy ứng dụng.
   * **Loại bỏ hoàn toàn bộ công cụ biên dịch (`gcc`, `libpq-dev`):** Image cuối cùng (`runtime`) **không hề chứa `gcc`**. Các trình biên dịch nặng này chỉ được cài ở Stage 1 (`builder`) để dịch mã nguồn thư viện; sang Stage 2, lệnh `COPY --from=builder` (dòng 45) chỉ bốc duy nhất thư mục thư viện đã build sẵn (`/root/.local`) sang `/home/appuser/.local`, bỏ lại toàn bộ công cụ biên dịch và cache ở Stage 1. Có thể hình dung giống như việc bạn biên dịch phần mềm trên một máy trạm chuyên dụng, sau đó chỉ chép file chạy thành phẩm sang máy chủ thật mà không mang theo cả bộ cài trình biên dịch cồng kềnh.

**So sánh dung lượng thực tế giữa 2 image:**

| Image | Tag | Dung lượng (MB) | Ghi chú |
| :--- | :--- | :--- | :--- |
| Develop | `agent-develop` | `1591 MB` | Single-stage, base `python:3.11` |
| Production | `agent-production` | `229 MB` | Multi-stage, base `python:3.11-slim` |
| **Chênh lệch giảm** | —

### Exercise 2.4: Docker Compose stack

Lệnh (chạy trong `02-docker/production/`):

```
touch .env.local
docker compose -p k5-day14-docker up -d --build
docker compose -p k5-day14-docker ps
```

**Sơ đồ kiến trúc:**

```mermaid
flowchart LR
    Client["Client (curl trên máy)"] -->|"HTTP :80"| nginx
    subgraph internal["Docker network: internal"]
        nginx["nginx<br/>reverse proxy + rate limit 10r/s"] -->|"agent:8000"| agent["agent<br/>FastAPI, uvicorn 2 workers"]
        agent -.->|"REDIS_URL (chưa dùng trong code)"| redis["redis:6379"]
        agent -.->|"QDRANT_URL (chưa dùng trong code)"| qdrant["qdrant:6333"]
    end
```

**Services được start:**

## Part 3: Cloud Deployment
### Exercise 3.1: Railway deployment (agent Part 6)
- URL: https://k5-l3a-day14-dothithanhbinh-2a202603709-deployme-production.up.railway.app
- Deploy bằng Railway CLI từ `06-lab-complete/` (`railway link` → `railway up`), thêm Redis trong cùng project, đặt `AGENT_API_KEY`, `REDIS_URL=${{Redis.REDIS_URL}}`, `ENVIRONMENT=production` trên dashboard, tạo domain public.
- Kiểm tra 4 lệnh CP6: `/health` 200, `/ready` 200, `/ask` không key 401, có key 200 (ảnh `screenshots/test.png`).
- Sự cố gặp phải:
  - Railway tự deploy cả repo từ GitHub → build bằng Dockerfile Go ở gốc repo → lỗi `go build`. Sửa: deploy đúng thư mục `06-lab-complete/` bằng CLI và ngắt kết nối GitHub của service.
  - Biến môi trường bị thêm nhầm vào service Redis, ghi đè `REDIS_URL` của Redis thành tham chiếu tự trỏ vào chính nó → agent nhận URL rỗng và crash (`Redis URL must specify one of the following schemes`). Sửa: chuyển biến sang service agent, khôi phục `REDIS_URL` của Redis về `redis://default:${{REDIS_PASSWORD}}@${{REDISHOST}}:${{REDISPORT}}`.

### Exercise 3.2: So sánh `railway.toml` và `render.yaml`
| | `railway.toml` | `render.yaml` |
|---|---|---|
| Phạm vi | Cấu hình **một service**: cách build và deploy | **Blueprint** cho cả hạ tầng: khai báo nhiều service (web + Key Value/Redis) trong một file |
| Build | `builder = "DOCKERFILE"` | `runtime: docker`, `dockerfilePath` |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` |
| Redis | Không khai báo trong file; thêm service Redis trên dashboard rồi tham chiếu `${{Redis.REDIS_URL}}` | Khai báo service `keyvalue` ngay trong file, nối bằng `fromService` (`property: connectionString`) |
| Secret | Đặt trên dashboard/CLI, file không chứa secret | `sync: false` (điền tay trên dashboard) hoặc `generateValue: true`; không ghi thẳng giá trị |
| Restart | `restartPolicyType = "ON_FAILURE"` | Render tự quản lý |

Khác nhau chính: Railway tách cấu hình build/deploy (file) khỏi hạ tầng (dashboard), còn Render mô tả toàn bộ hạ tầng như code trong một Blueprint, nên dựng lại môi trường dễ hơn nhưng file phải nằm đúng chỗ Render tìm (ở repo này `render.yaml` nằm trong thư mục con, phải chỉ đường dẫn khi tạo Blueprint).

### Exercise 3.3: Cloud Run CI/CD (chỉ đọc, không deploy)
`cloudbuild.yaml` mô tả pipeline 4 bước chạy tuần tự (`waitFor`) khi push lên `main`:
1. **test** — dùng `python:3.11-slim`, cài requirements và chạy `pytest`; test fail thì dừng toàn bộ pipeline.
2. **build** — build Docker image, gắn 2 tag `$COMMIT_SHA` và `latest`, dùng `--cache-from latest` để tận dụng layer cache.
3. **push** — đẩy image lên Container Registry.
4. **deploy** — `gcloud run deploy` image theo đúng `$COMMIT_SHA` lên region `asia-southeast1`, min 1 / max 10 instance, secret lấy từ Secret Manager (`--set-secrets`) thay vì ghi trong code.
`service.yaml` là cấu hình Knative tương ứng: autoscaling 1–10 instance, mỗi instance tối đa 80 request đồng thời, `livenessProbe` gọi `/health`, `startupProbe` gọi `/ready`, `AGENT_API_KEY` và `OPENAI_API_KEY` đọc từ `secretKeyRef`.
## Part 4: API Security
### Exercise 4.1: API Key authentication (bản develop)

Chạy server: `AGENT_API_KEY=secret-key-123 python app.py` (trong `04-api-gateway/develop/`)

**Kết quả test:**

```
# 1. Không có key
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 401 Unauthorized
{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}

# 2. Sai key
$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: wrong-key" -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 403 Forbidden
{"detail":"Invalid API key."}

# 3. Đúng key
$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: secret-key-123" -H "Content-Type: application/json" -d '{"question": "Hello"}'
HTTP/1.1 200 OK
{"question":"Hello","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận."}
```

Log server:

```
INFO:     127.0.0.1:54012 - "POST /ask HTTP/1.1" 401 Unauthorized
INFO:     127.0.0.1:56120 - "POST /ask HTTP/1.1" 403 Forbidden
INFO:     127.0.0.1:58388 - "POST /ask HTTP/1.1" 200 OK
```

**API key được check ở đâu?**
Trong hàm `verify_api_key` (dòng 39–54). Hàm đọc header `X-API-Key` qua `APIKeyHeader` (dòng 36) và được gắn vào endpoint `/ask` bằng `Depends(verify_api_key)` (dòng 70). Nhờ vậy việc kiểm tra key luôn chạy trước hàm xử lý chính, giống một filter/middleware: request không hợp lệ bị chặn trước khi gọi tới LLM. Các endpoint `/` và `/health` không gắn dependency này nên vẫn public.

**Điều gì xảy ra nếu sai key?**
Request bị chặn, không gọi tới LLM. Code phân biệt hai trường hợp: thiếu header → **401 Unauthorized**, có header nhưng sai giá trị → **403 Forbidden**. Lưu ý: Part 6 yêu cầu cả thiếu lẫn sai key đều trả **401**, nên không dùng nguyên logic này cho Part 6.

**Làm sao rotate key?**
Key đọc từ biến môi trường `AGENT_API_KEY` (dòng 35), nên chỉ cần đặt giá trị mới cho biến này trên server/platform rồi khởi động lại app, không phải sửa code. Hạn chế: app chỉ giữ **một** key, nên lúc đổi key mọi client dùng key cũ bị chặn ngay; muốn đổi key không gián đoạn thì phải cho phép tạm thời cả key cũ và key mới cùng hợp lệ trong một khoảng thời gian chuyển tiếp.

**Anti-pattern còn sót trong bản này:**
- Dòng 35: nếu không đặt `AGENT_API_KEY`, app tự dùng key mặc định `demo-key-change-in-production` viết sẵn trong code. Quên cấu hình trên production thì app vẫn chạy với một key ai cũng đọc được trên GitHub.
- Dòng 91: `print(f"API Key: {API_KEY}")` in key ra log khi khởi động (thấy rõ trong terminal: `API Key: secret-key-123`), lặp lại lỗi ghi secret ra log của Part 1.
### Exercise 4.2: JWT authentication (bản production)

Chạy trong `04-api-gateway/production/`: `pip install -r requirements.txt && python app.py`. Tài khoản demo: `student` / `demo123`, endpoint lấy token là `POST /auth/token`.

**JWT flow** (`auth.py`):
1. Client gửi username/password tới `POST /auth/token`. `authenticate_user` (dòng 70–75) kiểm tra với `DEMO_USERS`, sai thì trả 401.
2. `create_token` (dòng 35–43) tạo payload gồm `sub` (username), `role`, `iat`, `exp` (hết hạn sau 60 phút) và ký bằng `JWT_SECRET` với thuật toán HS256.
3. Mỗi lần gọi `/ask`, client gửi header `Authorization: Bearer <token>`. `verify_token` (dòng 46–67) kiểm tra chữ ký và hạn dùng rồi lấy ra `username` và `role`. Server **không cần tra database** ở mỗi request, nên JWT là cơ chế xác thực stateless.
4. Không có token → 401; token hết hạn → 401; token bị sửa hoặc ký sai → 403.

So với API key ở 4.1: API key là một khoá chung không có hạn dùng, còn JWT cấp riêng cho từng user, có hạn dùng và mang theo `role`, nên server áp được rate limit khác nhau cho user và admin.

**Kết quả test** (token đã che):

```
$ curl -i -X POST http://localhost:8000/auth/token -H "Content-Type: application/json" -d '{"username": "student", "password": "demo123"}'
HTTP/1.1 200 OK
{"access_token":"eyJhbGciOiJIUzI1NiIs...<đã che>","token_type":"bearer","expires_in_minutes":60,"hint":"Include in header: Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."}

# Không có token
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question": "Explain JWT"}'
HTTP/1.1 401 Unauthorized
www-authenticate: Bearer
{"detail":"Authentication required. Include: Authorization: Bearer <token>"}

# Có token
$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"question": "Explain JWT"}'
HTTP/1.1 200 OK
{"question":"Explain JWT","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

**Lỗi phát hiện khi chạy:**
- `budget_remaining_usd` trả về **số tiền đã tiêu** chứ không phải số còn lại: `app.py` dòng 160 gán `usage.total_cost_usd` (tổng chi phí đã dùng). Giá trị tăng dần qua các request (1.9e-05 → 0.000207 → 0.000226) trong khi lẽ ra phải giảm dần từ $1.
- Header `server: uvicorn` vẫn có trong mọi response dù middleware (dòng 84–85) cố xoá: uvicorn gắn header này ở tầng giao thức, sau khi middleware đã chạy. Muốn ẩn thật phải truyền `server_header=False` vào `uvicorn.run(...)`.
- Dòng 22 của `auth.py` có giá trị mặc định `JWT_SECRET` viết cứng trong code: quên đặt biến môi trường thì ai đọc repo cũng tự ký được token hợp lệ.

### Exercise 4.3: Rate limiting

**Algorithm:** Sliding window (dạng *sliding window log*). Mỗi user có một `deque` lưu timestamp các request (`rate_limiter.py` dòng 27). Mỗi lần check, code bỏ các timestamp cũ hơn 60 giây (dòng 39–40), đếm phần còn lại, nếu đã đủ limit thì trả 429 kèm header `Retry-After` (dòng 45–62); chưa đủ thì ghi timestamp mới (dòng 65).

**Limit:** user 10 request/60 giây, admin 100 request/60 giây (dòng 86–87).

**Bypass cho admin:** code không bypass hoàn toàn mà chọn limiter theo `role` lấy từ JWT (`app.py` dòng 141): admin dùng `rate_limiter_admin` với hạn mức 100/phút. Muốn bỏ hẳn giới hạn cho admin thì chỉ cần không gọi `limiter.check()` khi `role == "admin"`.

**Kết quả test** (10 request liên tiếp, rồi 1 request `curl -i`):

```
Request 1: 200
Request 2: 200
...
Request 9: 200
Request 10: 429

$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"question": "one more"}'
HTTP/1.1 429 Too Many Requests
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795596636
retry-after: 22
{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":22}}
```

**Quan sát về sliding window:** trong lần test đầu, sau khi bị 429, một request gửi lúc 08:48:22 lại được 200 với `requests_remaining: 0`, vì request "Explain JWT" lúc 08:47:10 vừa ra khỏi cửa sổ 60 giây và trả lại đúng 1 chỗ. Khác với fixed window (reset toàn bộ đầu mỗi phút), ở sliding window mỗi request hết hạn riêng lẻ, đúng 60 giây sau khi gửi. Ngoài ra request bị 429 không được ghi vào cửa sổ (dòng 45 kiểm tra trước, dòng 65 mới ghi), nên bị chặn không làm kéo dài thời gian chờ.

**Hạn chế:** state nằm trong RAM của một process. Restart app thì mất bộ đếm; chạy nhiều instance thì mỗi instance đếm riêng, nên user thực tế được gọi N × 10 request/phút. Bản production thật cần lưu bộ đếm trong Redis (làm ở Part 6).

### Exercise 4.4: Cost guard

**Bản có sẵn (`cost_guard.py`)** hoạt động theo hai bước bao quanh lần gọi LLM:
1. **Trước khi gọi LLM** (`check_budget`, dòng 60–91): nếu tổng chi phí toàn hệ thống trong ngày ≥ $10 → **503** (bảo vệ tổng ngân sách); nếu chi phí của user trong ngày ≥ $1 → **402 Payment Required**; nếu user đã dùng ≥ 80% → ghi log cảnh báo.
2. **Sau khi gọi LLM** (`record_usage`, dòng 93–110): cộng số token input/output thực tế của request (giá theo GPT-4o-mini, dòng 20–21) vào bản ghi của user và vào tổng toàn hệ thống.
Bản ghi có trường `day`; sang ngày mới thì `_get_record` tạo bản ghi mới (dòng 56–57), coi như reset hằng ngày.

**Cách làm theo yêu cầu đề ($10/tháng/user, lưu trong Redis):**
- Key theo user và tháng: `budget:{user_id}:{YYYY-MM}`. Sang tháng mới thì key khác, nên tự động "reset đầu tháng" mà không cần job dọn dẹp.
- Trước khi gọi LLM: đọc chi phí hiện tại; nếu `hiện tại + chi phí ước tính > 10` thì từ chối (402).
- Ghi chi phí bằng `INCRBYFLOAT` (cộng nguyên tử ngay trong Redis) và đặt `EXPIRE` khoảng 32 ngày để key tháng cũ tự xoá.
- Vì state nằm trong Redis nên mọi instance của agent dùng chung một bộ đếm; restart app không mất số đã tiêu.

**Điểm cần lưu ý ở lời giải mẫu:** bước "đọc rồi mới cộng" (`GET` rồi `INCRBYFLOAT`) không nguyên tử. Hai request đồng thời có thể cùng đọc thấy còn ngân sách rồi cùng cộng, vượt $10 một chút. Cách chặt hơn là cộng trước bằng `INCRBYFLOAT`, nếu kết quả vượt ngân sách thì trừ lại và trả 402.

**Vì sao cần cả rate limit lẫn cost guard:** rate limit bảo vệ **tốc độ** (chống spam, chống quá tải), cost guard bảo vệ **tiền**. Một user gọi đúng 10 request/phút nhưng mỗi câu hỏi rất dài vẫn có thể tiêu hết ngân sách mà không hề chạm rate limit; ngược lại cost guard không chặn được hàng nghìn request rẻ làm nghẽn server.
## Part 5: Scaling & Reliability
### Exercise 5.1: Health checks

Chạy `python app.py` trong `05-scaling-reliability/develop/` (endpoint đã có sẵn, dòng 104–168).

```
$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
{"status":"ok","uptime_seconds":15.8,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T08:55:14.634277+00:00","checks":{"memory":{"status":"ok","used_percent":10.6}}}

$ curl -i http://localhost:8000/ready
HTTP/1.1 200 OK
{"ready":true,"in_flight_requests":1}
```

**Liveness (`/health`) khác readiness (`/ready`) ở đâu:**
- `/health` trả lời "process còn sống không?". Platform gọi định kỳ; không trả 200 hoặc timeout thì platform **restart** container. Endpoint này chỉ nên kiểm tra bản thân process (ở đây: uptime, mức dùng RAM qua `psutil`), không nên phụ thuộc dịch vụ ngoài: nếu Redis chết mà `/health` cũng fail thì platform restart agent liên tục mà không giải quyết được gì.
- `/ready` trả lời "đã sẵn sàng nhận traffic chưa?". Load balancer dùng để quyết định có **chuyển request vào** instance này không. Trả 503 khi đang khởi động, đang tắt (`_is_ready = False`, dòng 55) hoặc khi dependency như Redis/DB chưa kết nối được. Instance chỉ bị rút khỏi vòng phục vụ chứ không bị restart.
- `in_flight_requests: 1` là chính request `/ready` đang được xử lý, vì middleware (dòng 72–81) đếm mọi request, kể cả request kiểm tra.

### Exercise 5.2: Graceful shutdown

Gửi một request `/ask` (mock LLM trễ ~3 giây), sau 1 giây gửi SIGTERM cho server:

```
$ PID=$(pgrep -f "python app.py")
$ curl -s -w "\nHTTP %{http_code}\n" -X POST "http://localhost:8000/ask?question=Long%20task" &
$ sleep 1
$ kill -TERM $PID
$ wait
{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
HTTP 200
```

Log server:

```
INFO:     Shutting down
INFO:     127.0.0.1:41540 - "POST /ask?question=Long%20task HTTP/1.1" 200 OK
INFO:     Waiting for application shutdown.
2026-11-25 08:55:37,566 INFO 🔄 Graceful shutdown initiated...
2026-11-25 08:55:37,566 INFO ✅ Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [3443]
2026-11-25 08:55:37,567 INFO Received signal 15 — uvicorn will handle graceful shutdown
```

**Kết quả:** request đang chạy dở **hoàn thành với 200** dù server đã nhận SIGTERM, không bị cắt ngang.

**Phân tích thứ tự log:**
1. Uvicorn nhận SIGTERM → ngừng nhận request mới (`Shutting down`).
2. Uvicorn chờ request `/ask` đang chạy xong (tối đa `timeout_graceful_shutdown=30`, dòng 198).
3. Sau đó mới gọi phần shutdown của `lifespan` (dòng 54–66): đặt `_is_ready = False` để `/ready` trả 503 và chờ request còn lại. Vì uvicorn đã chờ xong ở bước 2, `_in_flight_requests` lúc này bằng 0 nên vòng lặp chờ (dòng 61–64) không chạy lần nào.
4. `handle_sigterm` (dòng 175–183) in log **cuối cùng**, sau khi server đã tắt: uvicorn tạm thay signal handler riêng trong lúc chạy, tự xử lý tắt xong mới chuyển tín hiệu lại cho handler cũ. Nghĩa là phần "tắt an toàn" thực sự do uvicorn + `lifespan` đảm nhận; handler tự viết chỉ để ghi log.

Nếu không có graceful shutdown (ví dụ bị `SIGKILL`, hoặc app không chờ), request đang xử lý sẽ bị cắt và client nhận lỗi kết nối, đúng lúc deploy bản mới.

### Exercise 5.3: Stateless design

**Vì sao state trong RAM hỏng khi chạy nhiều instance:** mỗi instance là một process riêng với bộ nhớ riêng. Nếu lưu `conversation_history = {}` trong RAM, request 1 của user vào instance A thì history nằm ở A; request 2 bị load balancer chuyển sang instance B thì B không thấy gì, conversation bị mất. Restart hay deploy lại cũng làm mất toàn bộ state.

**Cách bản production làm (`05-scaling-reliability/production/app.py`):**
- Session lưu trong Redis với key `session:{session_id}` và TTL 1 giờ (`save_session`, dòng 59–65; `load_session`, dòng 68–73). Instance nào cũng đọc/ghi cùng một chỗ.
- Mỗi response trả `served_by: INSTANCE_ID` (dòng 155) để thấy request nào do instance nào xử lý.
- `/ready` ping Redis, mất Redis thì trả 503 (dòng 208–215).

**Điểm cần lưu ý trong code mẫu:**
- Nếu không kết nối được Redis lúc khởi động, app **lặng lẽ chuyển sang lưu trong RAM** (dòng 42–45) và vẫn chạy bình thường. Khi đó chạy nhiều instance sẽ mất session mà không báo lỗi rõ ràng; production nên fail hẳn (hoặc `/ready` trả 503) thay vì fallback âm thầm.
- `append_to_history` (dòng 76–90) đọc session, sửa trong Python rồi ghi đè lại. Hai request cùng session đến hai instance cùng lúc có thể ghi đè lên nhau làm mất một message. Dùng cấu trúc list của Redis (`RPUSH` + `LTRIM`) thì mỗi lần thêm là một thao tác nguyên tử.

### Exercise 5.4: Load balancing

Chạy trong `05-scaling-reliability/production/`:

```
touch .env.local
docker compose -p k5-day14-scaling up -d --build --scale agent=3
docker compose -p k5-day14-scaling ps
```

```
NAME                      IMAGE                    SERVICE   STATUS                            PORTS
k5-day14-scaling-agent-1  k5-day14-scaling-agent   agent     Up 5 seconds (health: starting)   8000/tcp
k5-day14-scaling-agent-2  k5-day14-scaling-agent   agent     Up 4 seconds (health: starting)   8000/tcp
k5-day14-scaling-agent-3  k5-day14-scaling-agent   agent     Up 5 seconds (health: starting)   8000/tcp
k5-day14-scaling-nginx-1  nginx:alpine             nginx     Up 4 seconds                      0.0.0.0:8080->80/tcp
k5-day14-scaling-redis-1  redis:7-alpine           redis     Up 16 seconds (healthy)           6379/tcp
```

Gửi 10 request qua Nginx (cổng 8080, endpoint `/chat`), in ra instance xử lý:

```
Request 1 -> instance-3b9c78
Request 2 -> instance-94280c
Request 3 -> instance-e3d336
Request 4 -> instance-3b9c78
Request 5 -> instance-94280c
Request 6 -> instance-e3d336
Request 7 -> instance-3b9c78
Request 8 -> instance-94280c
Request 9 -> instance-e3d336
Request 10 -> instance-3b9c78
```

Log (`docker compose -p k5-day14-scaling logs agent | grep "POST /chat"`): agent-1 nhận 4 request, agent-2 và agent-3 mỗi container 3 request.

**Nhận xét:**
- Nginx phân tán request theo **round-robin** (mặc định của `upstream`): 3 instance lần lượt nhận request theo vòng lặp cố định.
- Trong `nginx.conf` chỉ khai báo một dòng `server agent:8000;`. DNS nội bộ của Docker trả về IP của cả 3 container agent cho tên `agent`, Nginx đưa cả 3 vào nhóm upstream rồi chia đều.
- Mỗi container luôn nhận request từ cùng một cổng nguồn của Nginx (ví dụ agent-1 luôn `:40294`) vì `keepalive 16`: Nginx giữ kết nối tới từng agent để dùng lại thay vì mở kết nối mới mỗi request.
- Nếu một instance chết, `proxy_next_upstream error timeout http_503` + `proxy_next_upstream_tries 3` cho phép Nginx thử chuyển request sang instance khác.

### Exercise 5.5: Test stateless

```
$ python test_stateless.py
Session ID: 3e02d47d-6024-44bd-94bf-a869cf47b947

Request 1: [instance-94280c]  Q: What is Docker?
Request 2: [instance-e3d336]  Q: Why do we need containers?
Request 3: [instance-3b9c78]  Q: What is Kubernetes?
Request 4: [instance-94280c]  Q: How does load balancing work?
Request 5: [instance-e3d336]  Q: What is Redis used for?

Total requests: 5
Instances used: {'instance-94280c', 'instance-e3d336', 'instance-3b9c78'}

--- Conversation History ---
Total messages: 10
  [user]: What is Docker?...
  [assistant]: Container là cách đóng gói app để chạy ở mọi nơi. Build once...
  [user]: Why do we need containers?...
  ...
  [user]: What is Redis used for?...
  [assistant]: Đây là câu trả lời từ AI agent (mock). Trong production, đây...

✅ Session history preserved across all instances via Redis!
```

**Giải thích:** 5 câu hỏi trong cùng một session được **cả 3 instance** xử lý luân phiên, nhưng history vẫn đủ 10 message (5 câu hỏi + 5 câu trả lời) theo đúng thứ tự. Lý do: không instance nào giữ session trong RAM; mỗi request đọc session từ Redis (`session:{session_id}`), thêm message rồi ghi lại. Nếu lưu trong RAM, instance-e3d336 ở request 2 sẽ không thấy câu hỏi 1 mà instance-94280c đã nhận.

Lưu ý: script không tự tắt instance nào (khác mô tả trong CODE_LAB), nên bài này chứng minh session dùng chung giữa các instance, chưa chứng minh trường hợp một instance chết giữa chừng.
## Part 6: Final Project — check_production_ready.py output

Chạy `python check_production_ready.py` (đầy đủ, có Docker) trong `06-lab-complete/`:

```
✅ Docker: image < 500 MB — 297 MB

📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
  Result: 12/12 tiêu chí đạt · 43/43 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

## AI log
Công cụ AI đã dùng: **Claude** (trợ lý chính, cả buổi)

| Phần | Đã nhờ AI làm gì | Tôi tự làm / tự kiểm tra |
|---|---|---|
| Setup | Claude hướng dẫn WSL2, Docker Desktop WSL integration, tạo venv Python 3.12 bằng `uv` (đề ghim `pydantic==2.9.0` không có wheel cho Python 3.14) | Tự chạy lệnh, tự fork/clone repo |
| Part 1 | Claude góp ý danh sách anti-pattern (sửa số dòng, bỏ ý chưa đúng về `DEBUG`), giải thích lỗi logging bị nuốt và `.env` không được nạp| Tự tìm anti-pattern, tự chạy app, đối chiếu với log thật |
| Part 2 | Claude hướng dẫn build/đo image, chép output sang markdown, dựng sơ đồ Mermaid, chỉ ra HEALTHCHECK không tự restart| Tự build, tự đo kích thước image, kiểm tra sơ đồ với `docker-compose.yml` |
| Part 4–5 | Claude giải thích JWT, sliding window, thứ tự log khi graceful shutdown; soạn câu trả lời từ output của tôi | Tự chạy mọi lệnh curl/vòng lặp 429, tự test SIGTERM, scale 3 instance |
| Part 6 | Claude viết code 12 file trong `06-lab-complete/` và kiểm tra với `check_production_ready.py` trước khi gửi; giải thích từng file | Tự chạy script chấm trên máy (PASS 12/12), đọc lại code |
| Part 3 / CP6 | Claude hướng dẫn Railway CLI; thao tác dashboard Railway| Tự tạo và dán `AGENT_API_KEY` (Claude không nhập key), tự chạy 4 lệnh kiểm tra |
| Part 7 | Claude viết script chạy load test/eval/stack observability, phát hiện lỗi `PYTHONUSERBASE` trong Dockerfile và lỗi `--no-deps` của lệnh Locust, soạn nhận xét báo cáo từ số liệu của tôi; tạo tải và tìm trace trong Jaeger | Tự chạy script trên máy, mọi số liệu lấy từ JSON/CSV tôi chạy ra, tự chụp ảnh |