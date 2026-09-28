# Day 5 AI Prompt and Review Log

## Request

Hoàn thiện Day 5 trên nhánh mới từ `main` đã pull; chỉ cần pass local, sau đó
test E2E Slack thật. Tận dụng kết nối Slack Day 4 nếu phù hợp.

## Accepted decisions

- Giữ HTTP Events API là transport chính để raw-body signature và timestamp
  replay defense được kiểm chứng đúng specification.
- Tách ACK khỏi xử lý dài bằng ARQ/Redis; `event_id` là deterministic job ID và
  Redis giữ seen-key có TTL để duplicate delivery vẫn bị chặn sau khi job hoàn
  tất. Payload nằm ở Redis riêng, còn ARQ arguments chỉ chứa event ID để worker
  log không lộ token/message body.
- Reuse đúng read-only Kubernetes và Prometheus MCP launchers của Day 2. Tool
  allowlist chỉ gồm query Prometheus và list pods trong namespace được cấu hình.
- Dùng intent parser deterministic cho bốn action thay vì cho model tự tạo tên
  tool hoặc arguments. Raw MCP output chỉ được xem là untrusted data.
- Read được phép tự động; scale cần token một lần gắn user/action/arguments và
  hết hạn sau 60 giây; delete bị chặn. Mutation sử dụng kubeconfig riêng.
- Structured audit chỉ chứa stable action, bounded arguments, decision và error
  code; các key nhạy cảm được redact và không ghi nội dung Slack.
- Local verifier dùng transport doubles có nhãn rõ ràng, signing secret ngẫu
  nhiên và không gửi Slack. Live Slack E2E được thực hiện riêng.
- Live E2E phát hiện app cũ cùng subscribe `message.channels` và `app_mention`,
  tạo hai event ID cho một mention. Ingress chỉ nhận `app_mention`; các event
  khác được ACK rồi audit là ignored. Socket Mode được tắt để Slack chuyển event
  tới HTTP endpoint có signature verification.

## Rejected decisions

- Không tái sử dụng Day 4 incoming webhook làm bot token/signing secret vì
  webhook chỉ hỗ trợ chiều Alertmanager gửi vào Slack.
- Không xử lý tool call bằng FastAPI BackgroundTasks vì mất job khi process
  restart và không có bounded retry/dedup bền vững.
- Không cho bot chạy shell tùy ý hoặc dùng read-only Day 2 identity cho mutation.
- Không log event body, message text, credentials, provider response hay raw
  exception.

## Validation plan

- Unit/contract tests: signature valid/invalid/stale, challenge-after-auth,
  ACK deadline, duplicate event, three intents, destructive deny, approval
  required and approval binding.
- `make day5-local-pass` must return verifier `PASS` with fresh correlated audit.
- Live E2E: cả ba mention nhận đúng một reply qua MCP thật; evidence chỉ giữ
  metadata và response không nhạy cảm.
