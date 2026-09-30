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
- SLI/SLO liên quan: Primary SLO `fast_successful_requests` (SLI: `event == "response_sent" and latency_ms <= 3000`)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` liên tục trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng trải nghiệm phản hồi chậm, thời gian chờ tin nhắn lâu bất thường (lag), có nguy cơ timeout ở phía client
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** Mở panel **Latency percentiles and TTFT** trên dashboard để xác nhận xu hướng tăng của P50, P95, P99 và TTFT P95. Xác định thời điểm bắt đầu tăng đột biến.
  2. **Logs:** Lọc file `data/logs.jsonl` trong khung thời gian bị ảnh hưởng với điều kiện `latency_ms > 3000`. Chọn 1–2 bản ghi đại diện, ghi nhận `correlation_id`, `feature`, `session_id`.
  3. **Traces:** Mở Langfuse UI, tìm trace theo `correlation_id` đã tìm được. Quan sát waterfall view để định vị span gây nghẽn: xem thời gian kéo dài ở span `retrieval` (vector database/RAG), span `generation` (LLM suy luận), hay mạng.
- Mitigation tạm thời:
  - Nếu span `retrieval` bị chậm: kiểm tra trạng thái vector store; nếu đang bật incident thử nghiệm thì tắt bằng `python scripts/inject_incident.py --scenario rag_slow --disable`.
  - Nếu span `generation` bị chậm: kiểm tra prompt version mới deploy, nếu prompt dài hoặc model sinh token bất thường thì rollback prompt production về version trước.
  - Tạm thời bật cache hoặc hạ tải concurrency nếu hệ thống đang bị spike request.
- Owner: `student-2A202602735`

## Alert 2

- Tên: `HighErrorRate`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Guardrail `error_rate_pct_max: 2` (tỉ lệ lỗi hệ thống không vượt quá 2%)
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` (`count(event == "request_failed") / count(event == "request_received") * 100 > 2%`) duy trì trong 5 phút
- Ảnh hưởng tới người dùng: Người dùng nhận mã lỗi HTTP 500 hoặc thông báo hệ thống gián đoạn, không nhận được câu trả lời từ trợ lý AI
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** Kiểm tra panel **Error rate and retrieval success** trên dashboard để đo lường tỉ lệ lỗi tổng thể và số lượng request thất bại theo phút.
  2. **Logs:** Lọc `data/logs.jsonl` tìm các event `event == "request_failed"`. Kiểm tra các trường `error_type` (ví dụ `RuntimeError`, `TimeoutError`) và `payload.detail`. Thu thập `correlation_id` của request lỗi.
  3. **Traces:** Tìm trace theo `correlation_id` trên Langfuse. Kiểm tra root observation và các child span: xác định span nào trả về trạng thái lỗi/exception và xem chi tiết stack trace.
- Mitigation tạm thời:
  - Nếu lỗi do downstream service (như RAG vector store bị fail): kiểm tra dịch vụ downstream; nếu đang chạy incident practice thì tắt bằng `python scripts/inject_incident.py --scenario tool_fail --disable`.
  - Nếu lỗi do cấu hình prompt hoặc model: kiểm tra prompt management, rollback prompt production về version ổn định hoặc restart service API (`uvicorn app.main:app`).
  - Nếu API sập hoặc tài nguyên cạn kiệt: restart service container và kiểm tra lại endpoint `/health`.
- Owner: `student-2A202602735`

## Alert 3

- Tên: `LowRetrievalSuccessRate`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: Guardrail `retrieval_success_rate_pct_min: 90` (tỉ lệ truy xuất tri thức thành công tối thiểu 90%)
- Điều kiện và thời gian duy trì: `tool_success_rate_pct < 90%` (`count(tool_success == true) / count(tool_success != null) * 100 < 90%`) trong 5 phút
- Ảnh hưởng tới người dùng: Trợ lý AI không truy xuất được tài liệu phù hợp từ kho tri thức, phải trả về phản hồi fallback chung chung hoặc sai lệch, làm giảm chất lượng câu trả lời (quality score giảm sút)
- Ba bước kiểm tra đầu tiên:
  1. **Metrics:** Xem panel **Error rate and retrieval success** (chỉ số retrieval success rate %) và panel **Quality proxy** trên dashboard để kiểm tra mức độ suy giảm chất lượng song hành với retrieval failure.
  2. **Logs:** Lọc `data/logs.jsonl` với điều kiện `tool_name == "retrieval"` và `tool_success == false`. Trích xuất `correlation_id`, `payload.detail` và `message_preview`.
  3. **Traces:** Tra cứu `correlation_id` trên Langfuse. Xem chi tiết span `retrieval` để xác định nguyên nhân: vector store connection timeout, query parse error hay missing corpus.
- Mitigation tạm thời:
  - Kiểm tra trạng thái và tải của vector store; nếu có sự cố kết nối, restart worker kết nối database hoặc tắt incident practice (`python scripts/inject_incident.py --scenario tool_fail --disable`).
  - Kích hoạt cơ chế fallback RAG tĩnh (static fallback corpus) để người dùng vẫn nhận được câu trả lời tạm thời có độ tin cậy cơ bản.
  - Bổ sung retry logic với exponential backoff cho các lệnh truy vấn embedding/retriever.
- Owner: `student-2A202602735`
