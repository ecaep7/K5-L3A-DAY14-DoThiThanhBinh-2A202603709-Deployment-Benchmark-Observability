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

### 4.1 Screenshot

- [ ] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals)
- [ ] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian)
- [ ] Một trace lỗi trong Jaeger (có event `exception`)
- [ ] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing**

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | | | |
| B | `MOCK_SLOW_RATE=0.3` | | | |
| C | `LLM_MODEL=mock-llm-large` | | | |
| D | `docker pause` 1 instance | | | |
| E | `AGENT_VERSION=v1` | | | |

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

...

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: ...
- Tổng thời gian: ... ms
- Span chiếm nhiều thời gian nhất: ... (... ms, ...%)
- Dòng log tương ứng (grep theo `trace_id`):

```json

```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | | | | | |
| 3 | | | | | |

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

...

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. ...
  2. ...
  3. ...
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?

...
