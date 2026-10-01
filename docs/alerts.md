# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Latency P95 của `response_sent.latency_ms` (ngưỡng SLO <= 3000ms)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` kéo dài trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng phải chờ lâu hơn để nhận được câu trả lời từ AI API
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Latency trên Dashboard để xác nhận mức P50/P95/P99 và TTFT, xác định khoảng thời gian bắt đầu tăng đột biến.
  2. Lọc file `data/logs.jsonl` trong khoảng thời gian đó, lấy một `correlation_id` có `latency_ms > 3000`.
  3. Mở trace có cùng `correlation_id` trên Langfuse, so sánh waterfall giữa span `retrieval` và `generation` để xác định bước nào gây nghẽn.
- Mitigation tạm thời:
  - Nếu nghẽn ở retrieval: kiểm tra tải của vector database hoặc chuyển sang cache/fallback corpus.
  - Nếu nghẽn ở generation do prompt mới: thực hiện rollback prompt `production` về version ổn định trước đó trên Langfuse.
- Owner: `TranTuanTu-2A202602840`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `2m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Tỷ lệ request lỗi trên tổng request nhận được (ngưỡng tối đa 2%)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` kéo dài trong 2 phút
- Ảnh hưởng tới người dùng: Người dùng gặp lỗi HTTP 500, không nhận được câu trả lời từ AI API
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors trên Dashboard để kiểm tra `error_rate_pct` và phân bố các loại lỗi `error_type`.
  2. Lọc `data/logs.jsonl` tìm các event `request_failed`, ghi nhận thông tin `error_type`, `detail` và `correlation_id`.
  3. Mở trace có `correlation_id` tương ứng trên Langfuse để xem chi tiết exception stack trace và trạng thái span.
- Mitigation tạm thời:
  - Bật cơ chế retry với exponential backoff cho các downstream calls hoặc chuyển sang degraded mode.
  - Nếu đang chạy diễn tập sự cố, tắt incident bằng: `python scripts/inject_incident.py --disable`.
- Owner: `TranTuanTu-2A202602840`

## Alert 3

- Tên: `LowRetrievalSuccess`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Tỷ lệ truy vấn retrieval thành công (ngưỡng tối thiểu 90%)
- Điều kiện và thời gian duy trì: `retrieval_success_rate_pct < 90%` kéo dài trong 5 phút
- Ảnh hưởng tới người dùng: Hệ thống RAG không lấy được tài liệu phù hợp, dẫn đến chất lượng câu trả lời bị suy giảm hoặc phải dùng fallback
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors trên Dashboard, đối chiếu chỉ số `retrieval_success_rate_pct` so với ngưỡng 90%.
  2. Lọc `data/logs.jsonl` tìm các log có `tool_name="retrieval"` và `tool_success=False` để lấy `correlation_id`.
  3. Mở trace trên Langfuse tại span `retrieval` để phân tích query đầu vào và nguyên nhân không truy xuất được tài liệu.
- Mitigation tạm thời:
  - Kiểm tra trạng thái kết nối và chỉ mục của vector database/knowledge corpus.
  - Sử dụng fallback context tĩnh để tạm thời phục vụ người dùng trong lúc khôi phục index.
- Owner: `TranTuanTu-2A202602840`
