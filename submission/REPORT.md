# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Trần Tuấn Tú
- **MSSV:** 2A202602840
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/ngaiTu29s1/K4-L3-DAY13-TranTuanTu-2A202602840-Monitoring-LLMOps
- **Commit SHA cuối:** `b2c2f0caa84d8fdcd55c6523eb314da950382fc3`
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602840`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 0/100 (Thiếu correlation_id, context enrichment, PII chưa scrub) | **100/100** | Đạt điểm tuyệt đối ở cả 4 tiêu chí (JSON schema, correlation_id, enrichment, PII) |
| `validate_dashboard.py` | 6/6 panel | **6/6 panel** | Đủ 6 panel theo contract, có ngưỡng và query mẫu hợp lệ |
| `pytest` | 22 passed | **25 passed** | Bổ sung thêm unit test cho headers, custom request id và PII redaction |
| Số traces hợp lệ | 0 | >= 10 | Traces được ghi nhận trên Langfuse project cá nhân kèm metadata và child observations |
| Số PII leak | Phát hiện leak email, phone, card | **0 leak** | Toàn bộ email, SĐT Việt Nam (+84, 0x), CCCD 12 số, credit card đều được scrub trước khi ghi file |
| Latency P95 / TTFT P95 | N/A | **~155ms / 50ms** | Điều kiện baseline ổn định, đáp ứng tốt SLO (ngưỡng 3000ms) |
| Retrieval success rate | N/A | **100%** | Truy xuất thành công toàn bộ tài liệu domain khi chưa bị inject sự cố |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  - Được xử lý tập trung trong `CorrelationIdMiddleware` (`app/middleware.py`).
  - Trước mỗi request, middleware gọi `clear_contextvars()` để xóa context cũ, triệt tiêu nguy cơ rò rỉ correlation ID giữa các requests đồng thời.
  - Kiểm tra header `x-request-id`: nếu client có truyền thì giữ nguyên, nếu không thì tự sinh ID duy nhất định dạng `req-<8-hex>` (`f"req-{uuid.uuid4().hex[:8]}"`).
  - Bind correlation ID vào `structlog.contextvars` và gán vào `request.state.correlation_id`.
  - Khi hoàn thành request, middleware đính kèm correlation ID và thời gian xử lý vào response headers: `x-request-id` và `x-response-time-ms`.

- **Các metadata được ghi vào structured log:**
  - Toàn bộ log API đều có các trường định danh và ngữ cảnh: `ts` (ISO timestamp UTC), `level` (INFO/ERROR), `service` ("api"), `event` (`request_received`, `response_sent`, `request_failed`), `correlation_id`.
  - Các trường context enrichment được bind trước khi log `request_received`: `user_id_hash` (mã băm SHA256 12 ký tự của user_id nhằm bảo mật danh tính), `session_id`, `feature`, `model` (ví dụ `claude-sonnet-4-5`), `env` (`dev`/`prod`).
  - Khi gửi response (`response_sent`), bổ sung thêm các số liệu vận hành: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name` ("retrieval"), `tool_success` (True/False).

- **Cách bảo đảm PII được scrub trước khi ghi:**
  - Sử dụng module `app/pii.py` với từ điển regex `PII_PATTERNS` bao quát: email, số điện thoại Việt Nam (`(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)`), CCCD 12 số, thẻ tín dụng 16 số, hộ chiếu.
  - Trong `app/logging_config.py`, đăng ký processor `scrub_event` vào chuỗi processors của `structlog`.
  - Hàm `scrub_event` duyệt đệ quy toàn bộ giá trị text trong `event_dict` (bao gồm `payload.message_preview`, `payload.answer_preview`, `event`, ...) để chuyển các chuỗi nhạy cảm thành `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CREDIT_CARD]`, `[REDACTED_CCCD]`.
  - `scrub_event` nằm **TRƯỚC** `JsonlFileProcessor` và `JSONRenderer`, bảo đảm dữ liệu ghi xuống đĩa hoặc stdout đã được làm sạch 100%.

- **Cách kiểm chứng kết quả:**
  - Chạy `python scripts/validate_logs.py` kiểm tra file `data/logs.jsonl`.
  - Chạy test suite `python -m pytest tests/test_pii.py tests/test_validate_logs.py tests/test_chat_observability.py`.
  - Chạy script bonus tự động rà quét: `python scripts/scan_secrets_pii.py` xác nhận 0 file bị leak.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  - Đăng ký tài khoản và tạo project riêng trên Langfuse Cloud: `day13-k4-l3b-2A202602840`.
  - Cấu hình biến môi trường trong `.env` trỏ đúng key của project này (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`).
  - Giao diện Langfuse hiển thị rõ tên project cá nhân ở góc trên cùng bên trái và danh sách traces khớp với thời gian thực hiện bài lab.

- **Cấu trúc root/retrieval/generation observations:**
  - Sử dụng Langfuse SDK v4 API:
    - Root trace/agent: `@observe(name="lab-agent-run", as_type="agent")` khởi tạo span cha cho toàn bộ vòng đời xử lý của request.
    - Child observation 1 (retrieval): Dùng `client.start_as_current_observation(name="retrieval", as_type="retriever")` bao bọc hàm `retrieve(message)`. Ghi nhận metadata `doc_count` và preview truy vấn.
    - Child observation 2 (generation): Dùng `client.start_as_current_observation(name="generation", as_type="generation", model=self.model, prompt=...)` bao bọc hàm `self.llm.generate()`. Cập nhật `usage_details` (`input`, `output`, `total`), `cost_details` (`cost_usd`) và output sau khi LLM phản hồi.
  - Cây waterfall quan sát được:
    ```text
    day13-agent-request
    └── lab-agent-run
        ├── retrieval (retriever)
        └── generation (generation)
    ```

- **Cách nối trace với log:**
  - Trong `app/agent.py`, thông qua `propagate_attributes()`, trường `correlation_id` được ghi trực tiếp vào `metadata` của root trace.
  - Khi một log entry trong `data/logs.jsonl` có `correlation_id="req-531a89c2"`, kỹ sư chỉ cần nhập mã này vào ô tìm kiếm filter metadata trên giao diện Langfuse để mở đúng trace tương ứng.

- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1 (label: `baseline`, ban đầu gắn `production`)
- **Version/label candidate:** Version 2 (label: `candidate`)
- **Trace ID của mỗi version:**
  - Trace ID dùng Version 1 (baseline): `c514d47ec783c0a2ad8b7ed442f0ec65` (gắn liền correlation_id: `req-e07dd2bc`)
  - Trace ID dùng Version 2 (candidate): `12368f8dcf946a7de05a16a1e89289d2` (gắn liền correlation_id: `req-58148995`)
  - Trace ID dùng Version 1 sau Rollback: `5c8c4bfe4c55710928c014e01ab1ba99` (gắn liền correlation_id: `req-d8e8835f`)
- **Cách promote và rollback `production`:**
  - **Promote:** Trên giao diện Langfuse (Prompts $\rightarrow$ `day13-chat`), chuyển label `production` từ Version 1 sang Version 2. Ứng dụng tự động load prompt Version 2 mà không cần khởi động lại hoặc sửa code.
  - **Rollback:** Khi phát hiện Version 2 gây suy giảm chất lượng hoặc tăng token/cost, kỹ sư thao tác trên Langfuse UI: chuyển nhãn `production` quay trở lại trỏ vào Version 1. Mọi request tiếp theo sẽ ngay lập tức dùng lại prompt Version 1 an toàn.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  - Tạo dashboard runtime 6 panels bằng script `scripts/generate_dashboard.py` kết xuất ra ảnh `evidence/11-dashboard-overview.png`:
    1. **Latency:** Đo P50, P95, P99 của `latency_ms` và TTFT P95 của `ttft_ms` (ngưỡng P95 <= 3000ms).
    2. **Traffic:** Thống kê số lượng request theo phút (ngưỡng >= 1 req/min).
    3. **Errors:** Tỷ lệ lỗi tổng `error_rate_pct` (ngưỡng <= 2%) và tỷ lệ truy xuất thành công `retrieval_success_rate_pct` (ngưỡng >= 90%).
    4. **Cost:** Chi phí tích lũy theo phút và tổng chi phí toàn cửa sổ (ngưỡng <= $2.50).
    5. **Tokens:** Tổng lượng token tiêu thụ chia theo `tokens_in` và `tokens_out` (ngưỡng <= 50,000 tokens).
    6. **Quality:** Điểm chất lượng trung bình dựa trên heuristic quality proxy (ngưỡng >= 0.75).

- **SLO và lý do chọn:**
  - **SLO chính:** 99.5% request trong chu kỳ 28 ngày phải phản hồi thành công và có `latency_ms <= 3000ms`.
  - **Lý do:** Đối với trải nghiệm hội thoại AI API, thời gian chờ quá 3 giây gây cảm giác gián đoạn cho người dùng cuối. Ngưỡng 99.5% đảm bảo độ tin cậy cấp dịch vụ production mà vẫn chừa dư địa cho các biến động mạng hoặc tail latency.

- **Cách tính error budget:**
  - Với SLO 99.5% trong cửa sổ 28 ngày, Error Budget là $100\% - 99.5\% = 0.5\%$.
  - Nếu trong chu kỳ có 10,000 requests, hệ thống được phép tối đa $10,000 \times 0.5\% = 50$ requests bị lỗi hoặc có latency vượt quá 3000ms trước khi vi phạm cam kết chất lượng dịch vụ.

- **Ba alert và runbook tương ứng:**
  1. `HighLatencyP95` (Warning, Duration: 5m, Channel: Slack `#k4-l3b-alerts`):
     - Điều kiện: `p95(latency_ms) > 3000ms` duy trì 5 phút. Runbook: `docs/alerts.md#alert-1`.
  2. `HighErrorRate` (Critical, Duration: 2m, Channel: Slack `#k4-l3b-alerts`):
     - Điều kiện: `error_rate_pct > 2%` duy trì 2 phút. Runbook: `docs/alerts.md#alert-2`.
  3. `LowRetrievalSuccess` (Warning, Duration: 5m, Channel: Slack `#k4-l3b-alerts`):
     - Điều kiện: `retrieval_success_rate_pct < 90%` duy trì 5 phút. Runbook: `docs/alerts.md#alert-3`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Khoảng thời gian điều tra:** 2026-10-01T04:41:20Z – 2026-10-01T04:41:40Z
- **Triệu chứng từ metrics:**
  - Dashboard panel Latency ghi nhận tail latency P95 tăng vọt đột biến từ baseline ~155ms lên mức **13,289ms (~13.3 giây)**, vi phạm nghiêm trọng ngưỡng SLO `<= 3000ms`.
  - Panel Errors không ghi nhận mã lỗi 500 (tỷ lệ lỗi vẫn 0%), nhưng người dùng phải chờ rất lâu mới nhận được phản hồi.
- **Log line và correlation ID liên quan:**
  - Trích xuất từ `data/logs.jsonl`:
    ```json
    {"service": "api", "latency_ms": 2655, "ttft_ms": 50, "tokens_in": 35, "tokens_out": 119, "cost_usd": 0.00189, "quality_score": 0.8, "tool_name": "retrieval", "tool_success": true, "event": "response_sent", "session_id": "k4-l3b-challenge-s01", "feature": "monitoring", "correlation_id": "req-03d81af3", "env": "dev", "model": "claude-sonnet-4-5", "user_id_hash": "4a1a454d70a9", "level": "info", "ts": "2026-10-01T04:41:31.800430Z"}
    ```
  - Đại diện request bị ảnh hưởng: `correlation_id = req-03d81af3` (thuộc tính `feature="monitoring"`).
- **Trace ID và span gây ảnh hưởng:**
  - Tra cứu trace trên Langfuse theo `correlation_id=req-03d81af3` cho thấy **Trace ID: `1af7c5e9fa449fde1a0b28367d60db3b`**.
  - Trên cây waterfall, span con `retrieval` (type: span / retriever) kéo dài hơn **2,500ms (cộng dồn queue trễ 5.5s)**, trong khi span `generation` chỉ tốn ~150ms.
- **Root cause:**
  - Sự cố `rag_slow` được kích hoạt trên hệ thống (do logic mô phỏng `if STATE["rag_slow"]: time.sleep(2.5)` trong `app/mock_rag.py`). Khi có 5 requests đồng thời, các truy vấn RAG bị nghẽn I/O tuần tự dẫn tới tổng độ trễ tích lũy vượt 13 giây. Tầng retrieval là điểm nghẽn duy nhất; tầng LLM generation hoàn toàn bình thường.
- **Fix action:**
  - Khôi phục hoạt động bình thường bằng cách gọi lệnh tắt incident: `python scripts/inject_incident.py --disable` (hoặc POST `/incidents/rag_slow/disable`).
  - Trong môi trường production: khởi động lại cụm vector store, kiểm tra index caching và scale thêm read-replicas cho dịch vụ embedding/retrieval.
- **Preventive measure:**
  - Đặt timeout tối đa cho downstream retrieval call (ví dụ `timeout=1.5s`), nếu quá giờ thì kích hoạt fallback static context thay vì để request bị treo.
  - Cấu hình alert `HighLatencyP95` (duration: 5m) và alert `LowRetrievalSuccess` để on-call phát hiện sớm trước khi cạn kiệt Error Budget.
  - Thiết lập circuit breaker và cache Redis cho các câu hỏi phổ biến để giảm tải trực tiếp lên vector database.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  - Quyết định làm sạch PII bằng processor `scrub_event` đệ quy ngay trong chuỗi processor của `structlog` trước `JsonlFileProcessor`. Điều này đảm bảo tính nhất quán: dù developer có log thêm trường nào trong tương lai, mọi string data đều được tự động làm sạch trước khi ghi ra đĩa hoặc đẩy lên log aggregator.
- **Một lỗi/blocker đã gặp:**
  - Khi mới bắt đầu, chạy `validate_logs.py` có thể bị lỗi tính cả các dòng log cũ trước khi code được sửa, dẫn đến điểm không phản ánh đúng code mới.
- **Cách tìm nguyên nhân và xử lý:**
  - Xóa hoặc xoay vòng file `data/logs.jsonl` trước khi chạy benchmark chính thức, khởi động lại API server để contextvars được nạp mới từ đầu.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics** là đèn báo động (dashboard cảnh báo P95 latency tăng lúc 02:50).
  - **Logs** là danh bạ sự kiện (lọc các request chậm trong khung giờ đó, tìm ra `correlation_id=req-531a89c2`).
  - **Traces** là phim chụp X-quang chi tiết (mở trace trên Langfuse, thấy rõ span `retrieval` màu đỏ kéo dài 2.5s, còn span `generation` chỉ 150ms).
  - Nhờ chuỗi 3 mắt xích này, việc tìm nguyên nhân gốc rễ (Root Cause) diễn ra chính xác trong vài phút mà không cần phỏng đoán.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - Prompt trong LLM tương đương với mã nguồn logic ứng dụng. Quản lý version qua Langfuse cho phép truy vết chính xác request nào dùng prompt nào. Nếu version mới bị tăng số lượng output token (gây spike cost) hoặc tăng latency, việc rollback tức thì qua nhãn `production` giúp bảo vệ Error Budget và chi phí vận hành hệ thống.
- **Điều quan trọng nhất đã học:**
  - Kỹ năng tư duy Observability thực chiến: cách liên kết chặt chẽ giữa Structured Logging, Distributed Tracing và Metrics Dashboard thông qua `correlation_id` duy nhất xuyên suốt hệ thống AI.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  - Hệ thống hiện dùng `FakeLLM` và mock retrieval; trong môi trường thực tế cần tích hợp OpenTelemetry exporter và kết nối trực tiếp với cụm Vector DB (Qdrant/Pinecone) cùng API LLM thực tế (OpenAI/Anthropic).

## 9. Checklist trước khi nộp

- [x] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [x] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
