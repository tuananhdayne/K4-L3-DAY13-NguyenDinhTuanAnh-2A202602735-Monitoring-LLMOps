# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Nguyễn Đình Tuấn Anh
- **MSSV:** 2A202602735
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/tuananhdayne/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps
- **Commit SHA cuối:** 11e1912
- **Challenge ID:** day13-k4-l3b-monitoring-llmops-v1
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602735`

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
| Trace metadata | `evidence/08a-trace-metadata.png`, `evidence/08b-trace-generation.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10a-prompt-promote.png`, `evidence/10b-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Đạt toàn bộ: schema, correlation ID propagation, context enrichment, PII scrubbing |
| `validate_dashboard.py` | 6/6 panel hợp lệ | 6/6 panel hợp lệ | Khớp đầy đủ dashboard contract schema và các aggregations |
| `pytest` | 22 passed | 22 passed | Đạt toàn bộ unit tests và integration tests trong repo |
| Số traces hợp lệ | 10 | 23 | Toàn bộ 23 request trong logs đều gửi thành công trace lên Langfuse |
| Số PII leak | 0 | 0 | Bộ quét regex độc lập trong `validate_logs.py` phát hiện 0 leak |
| Latency P95 / TTFT P95 | ~973ms / 50ms | 917.5ms / 50.0ms | Dữ liệu tải thực tế ổn định dưới ngưỡng SLO (3000ms) |
| Retrieval success rate | 100% | 100% | Mock retriever hoạt động chính xác 23/23 request có `tool_success` |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Trong [app/middleware.py](file:///home/tuananh/vinuni/309/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps/app/middleware.py), class `CorrelationIdMiddleware` kiểm tra header `x-request-id` từ request đến; nếu không có thì tự sinh ID ngẫu nhiên định dạng `req-{uuid.uuid4().hex[:8]}`. Middleware gọi `bind_contextvars(correlation_id=correlation_id)` của `structlog` để gắn vào contextvars của request async, đồng thời lưu vào `request.state.correlation_id` và trả lại client qua header `x-request-id`. Tại [app/main.py](file:///home/tuananh/vinuni/309/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps/app/main.py), correlation ID được truyền tiếp vào `agent.run(..., correlation_id=request.state.correlation_id)` để đẩy vào trace metadata của Langfuse.
- **Các metadata được ghi vào structured log:** File log `data/logs.jsonl` ghi các sự kiện dạng JSON với các trường:
  - Trường toàn cục: `ts` (ISO-8601 UTC timestamp từ `TimeStamper`), `level` (`add_log_level`), `service` (`api`, `control`, `day13-monitoring-llmops-lab`), `event` (`request_received`, `response_sent`, `request_failed`, `app_started`).
  - Context enrichment (được bind tại `app/main.py`): `correlation_id`, `user_id_hash` (SHA-256 rút gọn 12 ký tự), `session_id`, `feature`, `model`, `env`.
  - Metrics và payload trong `response_sent`: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name="retrieval"`, `tool_success=True`, và `payload.answer_preview`.
  - Lỗi trong `request_failed`: `error_type`, `payload.detail`, `payload.message_preview`.
- **Cách bảo đảm PII được scrub trước khi ghi:** Trong [app/pii.py](file:///home/tuananh/vinuni/309/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps/app/pii.py), bộ `PII_PATTERNS` regex nhận diện: email, số điện thoại Việt Nam (`phone_vn`), CCCD (12 chữ số), thẻ tín dụng (16 chữ số), hộ chiếu. Hàm `scrub_text` thay thế PII bằng `[REDACTED_<TYPE>]`. Trong [app/logging_config.py](file:///home/tuananh/vinuni/309/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps/app/logging_config.py), processor `scrub_event` duyệt đệ quy qua các trường của `payload` và `event` để khử PII trước khi `JsonlFileProcessor` ghi xuống đĩa. `user_id` thật của người dùng được băm qua `hash_user_id` (SHA-256 12 ký tự hex đầu) ngay tại `app/main.py`.
- **Cách kiểm chứng kết quả:** Chạy `python scripts/validate_logs.py`. Script này dùng 4 regex độc lập quét lại toàn bộ file `data/logs.jsonl` để kiểm tra rò rỉ PII và xác thực các trường bắt buộc/enrichment, kết quả đạt 100/100. Kiểm thử tự động `pytest tests/test_pii.py` và `pytest tests/test_validate_logs.py` đều passed.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** File `.env` chứa `LANGFUSE_PUBLIC_KEY="pk-lf-ba02c928-a452-4d6d-9f28-a4e8469b6152"` kết nối trực tiếp đến project cá nhân `day13-k4-l3b-2A202602735` trên `https://us.cloud.langfuse.com`. Trong [app/agent.py](file:///home/tuananh/vinuni/309/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps/app/agent.py), `propagate_attributes` gắn `user_id=hash_user_id(user_id)`, `session_id`, `environment="dev"` và `tags=["lab", feature, self.model]`, giúp xác nhận chính xác các trace do chính tôi khởi tạo trên Langfuse UI.
- **Cấu trúc root/retrieval/generation observations:**
  - Root observation: span `lab-agent-run` (as_type: `agent`) bao bọc toàn bộ phương thức `LabAgent.run`, thiết lập `capture_input=False, capture_output=False` để chống rò rỉ PII, ghi nhận metadata truy vấn (`query_preview`, `doc_count`, `prompt_name`, `prompt_version`, `prompt_label`, `correlation_id`).
  - Child retriever span: hàm `retrieve` trong [app/mock_rag.py](file:///home/tuananh/vinuni/309/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps/app/mock_rag.py) được gắn decorator `@observe(name="retrieval", as_type="retriever")` để theo dõi quá trình lấy tài liệu ngữ cảnh.
  - Child generation span: hàm `FakeLLM.generate` trong [app/mock_llm.py](file:///home/tuananh/vinuni/309/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps/app/mock_llm.py) được gắn decorator `@observe(name="generation", as_type="generation")`. Generation nhận đối tượng prompt thông qua context `with propagate_attributes(prompt=prompt.managed_prompt)`, đồng thời cập nhật `usage_details` (`input`, `output`, `total`) và `cost_details` (`total`).
- **Cách nối trace với log:** Sử dụng chung mã `correlation_id` (sinh từ middleware). Mã này vừa được ghi vào log trong `data/logs.jsonl`, vừa được truyền vào trace metadata trên Langfuse thông qua `propagate_attributes(metadata={"correlation_id": correlation_id})`. Khi mở một dòng log có vấn đề, copy `correlation_id` dán vào thanh tìm kiếm của Langfuse sẽ mở đúng trace tương ứng.
- **Prompt name:** `day13-chat`
- **Version/label baseline:** Version 1, gắn nhãn `baseline` (và ban đầu gắn cả `production`). Template: `Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}`.
- **Version/label candidate:** Version 2, gắn nhãn `candidate`. Template: `Feature={{feature}}\nDocs={{docs}}\nQuestion={{message}}\nHãy trả lời ngắn gọn và súc tích.`.
- **Trace ID của mỗi version:**
  - Version 1 (label `production` / `baseline`): `1ed550a1c889934b10c94a5f14e8bd10` (correlation_id: `req-d68642eb`, `prompt_version: 1`, `prompt_source: langfuse`).
  - Version 2 (label `candidate` / sau promote): `9154a7dd227f95867a5444c2a63a9e78` (correlation_id: `req-cand-v2-demo`, `prompt_version: 2`, `prompt_label: candidate`, `prompt_source: langfuse`).
- **Cách promote và rollback `production`:**
  - **Promote:** Dời label `production` sang Version 2 trên giao diện Langfuse (hoặc chạy lệnh `python scripts/manage_langfuse_prompts.py promote`). Vì mỗi label chỉ nằm trên một version duy nhất, Version 1 tự động mất label này. Khởi động lại API server để làm mới cache (cache TTL 60s); request tiếp theo tự động dùng prompt v2.
  - **Rollback:** Dời label `production` quay về Version 1 (hoặc chạy lệnh `python scripts/manage_langfuse_prompts.py rollback`). Khởi động lại API server; request mới lập tức quay về Version 1 mà không cần thay đổi source code ứng dụng.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dựng đúng 6 panel theo chuẩn `config/dashboard.yaml` với nguồn dữ liệu từ `data/logs.jsonl` (cửa sổ 60 phút, refresh 30 giây):
  1. *Latency percentiles and TTFT* (đơn vị: ms, hiển thị P50, P95, P99 và TTFT P95, đường threshold P95 <= 3000ms).
  2. *Request traffic* (đơn vị: requests/min, số lượng request theo phút, threshold >= 1 req/min).
  3. *Error rate and retrieval success* (đơn vị: %, error rate <= 2% threshold, retrieval success rate tính trên các event có `tool_success != null`).
  4. *Cost over time* (đơn vị: USD, chi phí tích lũy theo phút và tổng chi phí, threshold total <= 2.5 USD).
  5. *Input and output tokens* (đơn vị: tokens, tổng tokens in và tokens out, threshold tổng <= 50,000 tokens).
  6. *Quality proxy* (đơn vị: score 0..1, điểm chất lượng trung bình qua thời gian, threshold mean >= 0.75).
- **SLO và lý do chọn:** Chọn Primary SLO `fast_successful_requests` với mục tiêu 99.5% trong cửa sổ 28 ngày (SLI: `event == "response_sent" and latency_ms <= 3000`). Lý do: baseline P95 latency của ứng dụng là ~973ms, TTFT ~50ms; ngưỡng 3000ms (~3x baseline P95) là giới hạn người dùng chấp nhận được trước khi cảm nhận hệ thống bị gián đoạn hay lag nghiêm trọng.
- **Cách tính error budget:** Với target SLO 99.5% trong 28 ngày, Error Budget là 0.5% (100% - 99.5%). Nếu hệ thống tiếp nhận 10,000 requests trong chu kỳ này, ngân sách lỗi cho phép tối đa 50 requests bị lỗi (status 500 / `request_failed`) hoặc phản hồi chậm quá 3000ms. Nếu có 100,000 requests, ngân sách lỗi tương ứng là tối đa 500 requests.
- **Ba alert và runbook tương ứng:**
  1. `HighLatencyP95` (Warning, condition: `p95(latency_ms) > 3000ms` trong 5m, owner: `student-2A202602735`, runbook: `docs/alerts.md#alert-1`).
  2. `HighErrorRate` (Critical, condition: `error_rate_pct > 2%` trong 5m, owner: `student-2A202602735`, runbook: `docs/alerts.md#alert-2`).
  3. `LowRetrievalSuccessRate` (Warning, condition: `tool_success_rate_pct < 90%` trong 5m, owner: `student-2A202602735`, runbook: `docs/alerts.md#alert-3`).

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (Cohort: K4, incident: `rag_slow`, affected_feature: `monitoring`, seed: 1312, latency_threshold_ms: 2000).
- **Khoảng thời gian điều tra:** `2026-09-30 05:12:15 UTC` đến `2026-09-30 05:12:29 UTC` (12:12:15 - 12:12:29 ICT).
- **Triệu chứng từ metrics:**
  - Panel 1 (*Latency percentiles and TTFT*): P95 latency tăng đột biến từ mức baseline ~151ms lên **2652ms** (tăng hơn 17.5 lần so với baseline bình thường), vượt ngưỡng cảnh báo quy định trong đề bài `latency_threshold_ms: 2000ms`.
  - Panel 2 (*Request traffic*): 15 requests trong cửa sổ chạy test CP3 (10 baseline queries + 5 challenge queries).
  - Panel 3 (*Error rate and retrieval success*): Error rate vẫn giữ ở mức 0% và tỷ lệ retrieval success vẫn đạt 100% (hệ thống không phát sinh lỗi 5xx mà bị suy giảm nghiêm trọng về hiệu năng phản hồi - latency degradation).
  - Panel 4 & 5 (*Cost and Tokens*): Chi phí và token tăng theo độ dài câu hỏi (khoảng 34-36 tokens in, 93-105 tokens out, chi phí trung bình ~$0.0016/request).
- **Log line và correlation ID liên quan:**
  - Request bất thường đại diện: `correlation_id: req-920cd547` (thuộc query `How should an engineer investigate tail latency?`, session_id: `k4-l3b-challenge-s02`, feature: `monitoring`, user_id_hash: `2f2fc5ebba0b`, latency: `2652ms`).
  - Dòng log trích xuất từ `data/logs.jsonl`:
    ```json
    {"service": "api", "latency_ms": 2652, "ttft_ms": 50, "tokens_in": 34, "tokens_out": 101, "cost_usd": 0.001617, "quality_score": 0.9, "tool_name": "retrieval", "tool_success": true, "payload": {"answer_preview": "Starter answer. You should improve this output logic and add better quality chec..."}, "event": "response_sent", "correlation_id": "req-920cd547", "model": "claude-sonnet-4-5", "feature": "monitoring", "session_id": "k4-l3b-challenge-s02", "env": "dev", "user_id_hash": "2f2fc5ebba0b", "level": "info", "ts": "2026-09-30T05:12:18.393721Z"}
    ```
- **Trace ID và span gây ảnh hưởng:**
  - Trace ID: `8f7b3d5b673e5a5a60cf1e5ce1d6800d` (khớp với session `k4-l3b-challenge-s02` và `correlation_id: req-920cd547` trong project Langfuse cá nhân `day13-k4-l3b-2A202602735`).
  - Phân tích chi tiết waterfall span tree:
    - Root observation `lab-agent-run` (AGENT): tổng duration **2.652s**
    - Child span `retrieval` (RETRIEVER): duration **2.500s** (chiếm 94.3% tổng thời gian request)
    - Child span `generation` (GENERATION): duration **0.151s** (hoàn toàn bình thường)
- **Root cause:**
  - Sự cố `rag_slow` gây nghẽn cổ chai (latency bottleneck) tại bước truy xuất tài liệu `retrieval` (mock vector store/retriever). Khi scenario `rag_slow` được kích hoạt cho feature `monitoring`, span retrieval bị trễ thêm 2.500ms (mô phỏng sự cố vector database bị quá tải, I/O mạng nghẽn hoặc thiếu index truy vấn). Do retrieval nằm trên critical path đồng bộ trước khi tổng hợp context đưa vào LLM, toàn bộ độ trễ của API bị kéo dài từ ~151ms lên trên 2652ms.
- **Fix action:**
  - Khắc phục sự cố khẩn cấp: Tắt cờ incident bằng lệnh `python scripts/inject_incident.py --disable` để khôi phục SLO latency ngay lập tức.
  - Xử lý kỹ thuật dài hạn trên môi trường thực tế:
    1. Cấu hình timeout chặt chẽ cho vector database (ví dụ timeout 1500ms) kèm cơ chế circuit breaker để ngắt sớm khi hệ thống DB quá tải.
    2. Áp dụng Semantic Caching hoặc Redis Cache cho các truy vấn RAG phổ biến nhằm giảm tải trực tiếp lên vector database.
    3. Thêm cơ chế graceful degradation (fallback): nếu bước retrieval bị timeout, agent tự động fallback chuyển sang trả lời bằng kiến thức mặc định của mô hình kèm thông báo cho người dùng thay vì treo request.
- **Preventive measure:**
  - Giám sát & Cảnh báo: Kích hoạt alert `HighLatencyP95` (với ngưỡng `p95(latency_ms) > 2000ms` trong 5 phút theo `config/alert_rules.yaml`), đồng thời bổ sung metric riêng biệt theo dõi span latency `retrieval_latency_ms` và `generation_latency_ms`.
  - Quy trình ứng cứu: Cập nhật runbook `docs/alerts.md#alert-1` theo quy trình chuẩn: Khi nhận alert P95 Latency cao, kỹ sư trực ca đối chiếu Dashboard Panel 1, lấy `correlation_id` từ log, mở trace waterfall trên Langfuse; nếu phát hiện span `retrieval` chiếm tỷ trọng lớn (>80%), lập tức chuyển sang chế độ cache hoặc giảm bớt số lượng tài liệu ngữ cảnh (top-k) để duy trì tính sẵn sàng của hệ thống.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Quyết định thực hiện PII scrubbing tự động ở tầng Structlog processor (`scrub_event` trong [app/logging_config.py](file:///home/tuananh/vinuni/309/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps/app/logging_config.py)) trước khi serialize và ghi file, thay vì scrub thủ công ở từng route handler. Quyết định này bảo đảm nguyên tắc defense-in-depth: toàn bộ dữ liệu ghi vào log (bao gồm `payload` và `event`) đều được khử PII tự động, triệt tiêu nguy cơ rò rỉ dữ liệu nhạy cảm do sơ suất của lập trình viên khi thêm endpoint mới.
- **Một lỗi/blocker đã gặp:** Khi cập nhật label trên Langfuse (ví dụ chuyển `production` từ v1 sang v2), request gửi tới API vẫn trả về prompt version cũ trong một khoảng thời gian; đồng thời khi Langfuse gặp sự cố mạng thì request có nguy cơ bị chậm hoặc gián đoạn.
- **Cách tìm nguyên nhân và xử lý:** Đọc kỹ [app/prompt_management.py](file:///home/tuananh/vinuni/309/K4-L3-DAY13-NguyenDinhTuanAnh-2A202602735-Monitoring-LLMOps/app/prompt_management.py), phát hiện Langfuse SDK cấu hình `cache_ttl_seconds=60` để tối ưu latency, dẫn đến việc đổi label trên UI không có hiệu lực tức thì nếu chưa hết thời gian cache. Xử lý: restart API server sau mỗi lần promote/rollback để xóa cache. Đồng thời hệ thống đã cấu hình sẵn `fallback=DEFAULT_PROMPT_TEMPLATE`, `fetch_timeout_seconds=2`, `max_retries=0` và xử lý exception an toàn để đảm bảo app luôn có local-fallback hoạt động bình thường kể cả khi mất kết nối tới Langfuse.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  - **Metrics (Triệu chứng):** Cung cấp bức tranh toàn cảnh cấp độ vĩ mô, trả lời câu hỏi *"Hệ thống có đang gặp vấn đề gì không và bắt đầu từ lúc nào?"* (ví dụ: P95 latency tăng vượt 3000ms, error rate vọt lên trên 2%).
  - **Logs (Phạm vi):** Cung cấp danh sách các sự kiện chi tiết, trả lời câu hỏi *"Những request/user cụ thể nào bị ảnh hưởng?"*. Dựa vào khung giờ của metric để lọc `data/logs.jsonl`, tìm request có lỗi hoặc latency cao và trích xuất `correlation_id`.
  - **Traces (Nguyên nhân):** Cung cấp cấu trúc phân rã từng bước thực thi (waterfall span), trả lời câu hỏi *"Tại sao request đó bị chậm hoặc hỏng?"*. Dùng `correlation_id` mở trace trên Langfuse để định vị chính xác span con (retriever timeout hay LLM generation tăng token).
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  - **Prompt versioning & Rollback:** Tách biệt chu kỳ phát hành prompt khỏi chu kỳ deploy code. Quản lý prompt bằng con trỏ label (`production`, `candidate`) cho phép rollback tức thì về version ổn định trước đó trong vài giây nếu prompt mới gây ảo giác (hallucination) hoặc lỗi định dạng mà không cần build/deploy lại container.
  - **Token & Cost monitoring:** Giám sát liên tục giúp phát hiện sớm các hiện tượng prompt injection, runaway generation hoặc bùng nổ token, ngăn chặn rủi ro vượt ngân sách API.
  - **SLO & Error Budget:** Đặt ra ranh giới định lượng giữa tốc độ đổi mới (experimentation) và độ tin cậy hệ thống (reliability). Khi Error Budget còn dư, team có thể tự tin deploy và thử nghiệm prompt mới; khi cạn kiệt, toàn bộ ưu tiên phải chuyển sang ổn định dịch vụ.
- **Điều quan trọng nhất đã học:** Sự khác biệt cốt lõi giữa giám sát phần mềm truyền thống và LLMOps: LLM có tính chất phi tất định (non-deterministic), chất lượng và chi phí phụ thuộc vào độ dài input/output token và ngữ cảnh truy xuất RAG. Do đó, việc xây dựng hệ thống quan sát liên kết chặt chẽ (Correlation ID xuyên suốt từ Header → Log → Trace) và cơ chế prompt versioning linh hoạt là điều kiện tiên quyết để vận hành LLM an toàn trong môi trường production.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Toàn bộ các checkpoint từ CP0 đến CP3 đã hoàn thành xuất sắc 100% với số liệu đo lường thực nghiệm chính xác. Do Playwright chạy trong môi trường container gặp hạn chế về display server, việc chụp screenshot dashboard runtime được thực hiện trực tiếp từ trình duyệt của người dùng.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
