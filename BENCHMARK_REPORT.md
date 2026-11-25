# Benchmark & Observability Report — Day 14

**Họ tên:** Đỗ Thị Thanh Bình
**Ngày chạy:** 25/11/2026
**Môi trường:** Windows + WSL2 (Ubuntu), Python 3.12 (venv), Docker Desktop; WSL thấy __ CPU / __ GB RAM

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Ở tải bình thường (concurrency ≤ 50) p95 đo được 220–237 ms, nên 500 ms còn dư khoảng 2 lần để chịu dao động; trên 0,5 s người dùng bắt đầu thấy chậm. Đặt theo p95 chứ không theo average vì average che mất tail latency (mục 2.2). |
| Error rate `/ask` | < 2 % | Upstream LLM (mock) có tỉ lệ lỗi nền 1 % (`MOCK_ERROR_RATE=0.01`); các lần đo thực tế 0,33–1,33 %. Ngưỡng 2 % đủ rộng cho lỗi nền nhưng bắt được khi lỗi tăng gấp đôi. |
| Accuracy trên golden dataset | ≥ 85 % | Ngưỡng của quality gate trong CI (Exercise 7.3): thấp hơn mức này agent trả lời sai quá 3/23 câu. Kèm điều kiện không có câu bị regression so với bản trước. |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

300 request mỗi mức, file `reports/load_v2_c{1,10,50,100}.json`.

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.85 | 191.6 | 223.8 | 1707.2 | 1.00% | PASS |
| 10 | 40.33 | 191.5 | 220.2 | 1683.9 | 0.67% | PASS |
| 50 | 121.66 | 195.4 | 237.2 | 1662.8 | 1.33% | PASS |
| 100 | 67.41 | 290.7 | 2600.5 | 3719.8 | 0.33% | FAIL |

**Nhận xét:**
- Từ concurrency 1 → 10, RPS tăng gần đúng 10 lần (3.85 → 40.33) trong khi p50 gần như không đổi (~191 ms): mỗi request chủ yếu là *chờ* LLM (mock dùng `asyncio.sleep`), nên một process async phục vụ song song được nhiều request. Đúng với Little's law: RPS ≈ concurrency / latency.
- Từ 10 → 50, RPS chỉ tăng ~3 lần (40.33 → 121.66) thay vì 5 lần: bắt đầu bão hoà vì cả agent lẫn load tester đều chạy trên một process Python, phần CPU (parse JSON, ghi log, cập nhật metrics) trở thành nút thắt.
- Ở 100, hệ thống quá tải: RPS **giảm** còn 67.41, p50 tăng lên 290.7 ms và p95 nhảy lên 2600.5 ms do request phải xếp hàng chờ event loop → vi phạm SLO p95. Muốn chịu được mức này phải scale thêm worker/instance (phần 5).
- p99 ở mọi mức đều ~1.7 s dù p95 vẫn đạt: đó là ~3 % request bị chậm giả lập (`MOCK_SLOW_RATE=0.03`, +1500 ms). Error rate 0.33–1.33 % đến từ lỗi upstream giả lập (`MOCK_ERROR_RATE=0.01`, agent trả 503).

### 2.2 Tail latency

Concurrency 20, 300 request, file `reports/load_v2_slow_{0,0.03,0.1}.json`.

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 190.8 | 218.6 | 226.6 |
| 0.03 (mặc định) | 246.7 | 226.5 | 1704.6 |
| 0.1 | 302.4 | 1688.7 | 1712.9 |

**Nhận xét:**
- Từ 0 → 0.03, avg chỉ tăng ~29 % (190.8 → 246.7 ms) và p95 gần như không đổi, nhưng **p99 tăng 7,5 lần** (226.6 → 1704.6 ms). Với 3 % request chậm, các request chậm nằm hoàn toàn trong 5 % đuôi nên chỉ p99 "thấy" được; avg thì bị 97 % request nhanh kéo xuống.
- Từ 0.03 → 0.1, số request chậm vượt quá 5 % nên p95 cũng nhảy lên 1688.7 ms (gấp ~7,5 lần), trong khi avg chỉ tăng thêm ~23 %.
- Chỉ số nhạy nhất với request chậm là **p99**, sau đó là p95 (khi tỉ lệ chậm vượt 5 %). **SLO không nên đặt theo average** vì average có thể vẫn "đẹp" (~250 ms) trong khi cứ 100 người dùng thì 3 người phải chờ gần 2 giây; SLO theo percentile mô tả đúng trải nghiệm của nhóm người dùng tệ nhất.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

Golden dataset 23 câu, file `reports/eval_v1.json`, `reports/eval_v2.json`, `reports/eval_v2_fixed.json`.

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.3% (1/23) | 91.3% (21/23) | 100.0% (23/23) |
| Avg tokens / câu | 57.7 | 109.3 | 113.7 |
| Tổng cost (USD) | 0.000412 | 0.000764 | 0.00079 |
| Cost / câu đúng (USD) | 0.00041235 | 0.00003639 | 0.00003436 |
| Quality gate | FAIL | PASS | PASS |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | `token`, `hết hạn`, `chữ ký` | Thêm vào `KNOWLEDGE_BASE` (`develop/utils/mock_llm.py`) tài liệu với keyword `jwt`: so sánh API key (chuỗi cố định, không hết hạn) với JWT (token có chữ ký số, chứa thông tin user và thời điểm hết hạn). |
| scaling-03 | `cpu`, `memory`, `custom metrics` | Thêm tài liệu với keyword `hpa`, `kubernetes`, `autoscal`: Kubernetes HPA scale số pod theo CPU, memory hoặc custom metrics. |

Nguyên nhân: retrieval của v2 tìm tài liệu theo keyword, mà `KNOWLEDGE_BASE` chưa có tài liệu nào chứa "jwt" hay "hpa", nên agent không có context và trả lời chung chung. Chỉ sửa tài liệu của agent, không sửa đáp án trong `golden_dataset.jsonl`. Eval cuối chạy với `--min-accuracy 1.0 --baseline reports/eval_v2.json`: 23/23, 0 câu regression, Quality gate PASS.

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**
- v2 thêm bước retrieval (RAG) nên prompt dài hơn: số token/câu tăng ~1,9 lần (57.7 → 109.3) và tổng cost tăng ~1,85 lần (0.000412 → 0.000764 USD); latency cũng tăng thêm thời gian của bước tìm tài liệu.
- Đổi lại accuracy tăng từ 4.3 % lên 91.3 %, nên **cost trên mỗi câu trả lời đúng của v2 rẻ hơn v1 khoảng 11 lần** (0.00041235 → 0.00003639 USD). Vì vậy so sánh hai phiên bản phải dùng "cost / câu đúng" chứ không dùng "cost / câu": v1 rẻ hơn trên mỗi request nhưng gần như toàn trả lời sai, tức là tốn tiền mà không mang lại giá trị.
- Sửa KB làm tokens tăng nhẹ (109.3 → 113.7) và tổng cost tăng 0.000026 USD, nhưng cost / câu đúng còn giảm tiếp (0.00003436 USD) vì thêm 2 câu đúng.

### Quality gate trong CI (Exercise 7.3)

`run_eval.py` trả **exit code 1** khi accuracy thấp hơn `--min-accuracy` hoặc có câu regression so với `--baseline`, và exit code 0 khi đạt. CI dựa vào exit code này: bước chạy eval trả 1 thì job fail, và khi bật branch protection "Require status checks to pass" thì Pull Request không merge được.

```yaml
# .github/workflows/eval.yml
name: quality-gate
on: [pull_request]
jobs:
  eval:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - name: Run agent + eval
        working-directory: 06-lab-complete/benchmark-observability/develop
        run: |
          pip install -r requirements.txt
          AGENT_VERSION=v2 MOCK_ERROR_RATE=0 python app.py &
          sleep 3
          python eval/run_eval.py --url http://localhost:8000 --min-accuracy 0.85
```

`MOCK_ERROR_RATE=0` để lỗi upstream ngẫu nhiên không làm gate fail oan; gate chỉ đo chất lượng câu trả lời.

## 4. Observability stack (production)

Stack: `docker compose -p k5-day14-observability` (agent + Nginx + Prometheus + Grafana + Jaeger + Locust). Unit test alert rules bằng `promtool test rules`: **SUCCESS**.

**Sự cố khi dựng stack:** container agent crash loop (`ModuleNotFoundError: No module named 'uvicorn'`). Nguyên nhân: `production/Dockerfile` tạo user `agent` với home `/app` nhưng copy thư viện vào `/home/agent/.local`, nên Python tìm user site-packages ở `/app/.local` và không thấy thư viện. Sửa: thêm `ENV PYTHONUSERBASE=/home/agent/.local`. Ngoài ra lệnh mẫu `docker compose run locust` tự khởi động lại dependency và đưa agent về `replicas: 2`, làm sai benchmark "1 instance"; sửa bằng `docker compose run --no-deps`.

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): `screenshots/grafana-dashboard.png`
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): `screenshots/jaeger-slow-trace.png`
- [x] Một trace lỗi trong Jaeger: `screenshots/jaeger-error-trace.png`
- [x] Trang Alerts của Prometheus với 2 alert đang **firing**: `screenshots/prometheus-alert-firing.png`

### 4.2 Thí nghiệm "phá hệ thống"

Chạy A và B cùng lúc (sửa `.env`, `docker compose up -d`), Locust 30 users chạy nền; thời gian đo tự động bằng cách đọc `http://localhost:9090/api/v1/alerts` mỗi 5 giây.

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` (giá trị lúc firing ≈ 21%) | pending sau 15 s, **firing sau 75 s** | Error rate (Golden Signals) và Requests/s theo status code (503 tăng) |
| B | `MOCK_SLOW_RATE=0.3` | `AgentHighLatencyP95` (p95 ≈ 1.88 s) | pending sau 15 s, **firing sau 135 s** | Latency /ask p50/p95/p99: p95 và p99 vọt lên ~1.7 s trong khi p50 gần như không đổi |
| C | `LLM_MODEL=mock-llm-large` | Không chạy | – | – |
| D | `docker pause` 1 instance | Không chạy | – | – |
| E | `AGENT_VERSION=v1` | Không chạy | – | – |

Nhận xét: thời gian tới khi firing ≈ thời gian để cửa sổ `rate(...[1m])` vượt ngưỡng (~15 s) + thời gian `for` của rule (1 phút cho error rate, 2 phút cho p95). Trong lúc đổi cấu hình, 3 container agent bị tạo lại nên `AgentInstanceDown` chuyển sang **pending** sau 10 s nhưng **không firing** vì rule có `for: 30s` và các instance lên lại trước đó: đúng vai trò của `for` là chống báo động giả khi chỉ có gián đoạn ngắn.

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

Lỗi chất lượng (agent trả lời sai nhưng vẫn nhanh và trả 200) không làm metric hạ tầng đổi màu. Cách phát hiện: (1) chạy eval trên golden dataset trong CI trước mỗi lần deploy để chặn từ đầu (mục 3); (2) sau khi deploy, chạy eval định kỳ (canary/synthetic eval) trên production và đẩy accuracy thành metric để đặt alert khi tụt; (3) theo dõi metric chất lượng gián tiếp như retrieval hit ratio, độ dài câu trả lời, tỉ lệ người dùng đánh giá 👎. Riêng E còn thấy được qua panel Retrieval hit ratio (mất) và bảng "Phiên bản đang chạy" (đổi sang v1).

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất tìm được (Jaeger, lọc Min Duration 1s):

- `trace_id`: `a1efc7c8e5dedbec480d2d37127bbf8b`
- Tổng thời gian: 1683.4 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1654.1 ms, ≈ 98%); `agent.retrieve_context` chỉ 25.0 ms. Kết luận: chậm do upstream LLM, không phải code của agent.
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T13:17:06.331333+00:00", "level": "INFO", "service": "observable-agent", "instance": "db78b37d7ae6", "event": "llm_call", "trace_id": "a1efc7c8e5dedbec480d2d37127bbf8b", "span_id": "21125c95d00af371", "request_id": "4cbbea1e4107", "model": "mock-llm-small", "agent_version": "v2", "input_tokens": 72, "output_tokens": 40, "cost_usd": 3.5e-05, "llm_ms": 1652.9}
```

`llm_ms = 1652.9` trong log khớp với span `chat mock-llm-small` (1654.1 ms) trong Jaeger.

Trace lỗi: `d3bc5e56cc36b0674f2fe3de4ff0ee91` (105 ms, HTTP 503). Tìm bằng Attributes `error=true`; span `chat mock-llm-small` có `error.type=upstream_unavailable` và event `exception`: "Upstream LLM error: 503 Service Unavailable (mock)".

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

File `benchmark-results/scale_1_stats.csv`, `benchmark-results/scale_3_stats.csv` (dòng Aggregated).

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 66.30 | 190 | 240 | 1700 | 67/7900 |
| 3 | 65.65 | 190 | 250 | 1700 | 59/7825 |

**Giải thích kết quả:** Scale từ 1 lên 3 instance **không cải thiện** p95 hay RPS. Lý do:
- **Tải bị giới hạn bởi chính Locust:** mỗi user nghỉ 0,5–2 s giữa hai request, nên 100 user chỉ sinh ra được khoảng 100 / (1,25 s + ~0,2 s) ≈ 65–70 req/s, đúng với RPS đo được ở cả hai lần. Thêm instance không tạo thêm request.
- **1 instance chưa bão hoà:** p95 = 240 ms, còn xa SLO 500 ms; agent dùng async nên một container xử lý được nhiều request đang chờ LLM cùng lúc.
- **Nút thắt là LLM:** ~190 ms của p50 và ~1,7 s của p99 là thời gian chờ upstream LLM (panel LLM latency p95 ≈ 198 ms, trace ở 4.3 cho thấy 98% thời gian nằm ở span LLM). Scale agent không làm LLM nhanh hơn.
Muốn thấy lợi ích của scale cần tăng tải tới khi 1 instance bão hoà (nhiều user hơn hoặc giảm thời gian nghỉ), như ở develop concurrency 100 làm p95 lên 2600 ms.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Average latency che mất tail latency: với 3 % request chậm, avg chỉ tăng ~29 % nhưng p99 tăng 7,5 lần, nên SLO phải đặt theo p95/p99 và phải đo bằng load test chứ không suy ra từ vài request.
  2. Metric, trace và log bổ sung cho nhau: dashboard cho biết *có* vấn đề (p95 đỏ), Jaeger cho biết *ở bước nào* (98 % thời gian ở span LLM), log có `trace_id` cho chi tiết (token, cost, `llm_ms`) của đúng request đó.
  3. Observability hạ tầng không bắt được lỗi chất lượng: agent v1 trả lời sai 22/23 câu mà dashboard vẫn xanh; phải có eval + quality gate trong CI, và so sánh bằng "cost / câu đúng" thay vì "cost / request".
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Metric accuracy từ eval định kỳ trên production + alert khi tụt dưới 85 %.
  - Alert theo **error budget burn rate** (multi-window, ví dụ 1 h và 6 h) thay vì ngưỡng tức thời, để giảm alert fatigue.
  - Giám sát ở tầng Nginx/load balancer (504, upstream timeout) và synthetic check từ bên ngoài, vì lỗi 504 không xuất hiện trong metric của agent.
  - Alert retrieval hit ratio giảm đột ngột và alert cost theo ngày so với budget (không chỉ burn rate theo giờ).