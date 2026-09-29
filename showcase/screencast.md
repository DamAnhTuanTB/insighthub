# Kịch bản screencast

Hai video riêng: **Day 5** (MH11, 3 phút) và **Day 7** (bắt buộc, 3 phút). Quay
bằng Loom trên tài khoản của owner. Chỉ chiếu kết quả đang chạy thật; không đọc
số liệu ngoài những gì màn hình đang hiển thị.

## Chuẩn bị (không quay)

```bash
make up                                   # API/web theo API_PORT/WEB_PORT trong .env
make day5-rbac
CHATOPS_REDIS_PORT=6380 make day5-redis-up
# Terminal A: ingress   (xem chatops-bot/README.md bước 4)
# Terminal B: arq worker (bước 5), Prometheus port-forward sẵn sàng
# Tunnel HTTPS -> 127.0.0.1:8080, cập nhật Event Request URL trong Slack App
```

Ẩn `.env`, token, webhook và kubeconfig khỏi màn hình trước khi bấm Record.

## Video 1 — Day 5 ChatOps (3:00)

| Thời gian | Màn hình | Lời nói gợi ý |
|---|---|---|
| 0:00–0:20 | `chatops-bot/app/` | Ingress xác thực chữ ký raw body, chống replay, dedup `event_id`, enqueue ARQ rồi mới ACK trong 3 giây. |
| 0:20–0:45 | `curl` với chữ ký sai tới `/slack/events` → 401 | Sai chữ ký bị từ chối trước khi parse JSON hay xử lý challenge. |
| 0:45–1:45 | Slack: `@InsightHub-bot api healthy?`, `ingest count today?`, `which pods failing?` | Worker gọi MCP Kubernetes/Prometheus của Day 2 với identity read-only. |
| 1:45–2:15 | Slack: `@InsightHub-bot scale api to 2` → bot trả token → `confirm <token>` | Token hết hạn sau 60 giây; mutation dùng `CHATOPS_MUTATION_KUBECONFIG` riêng, chỉ deployment trong allowlist, replicas 1–5; delete luôn bị từ chối. |
| 2:15–2:35 | Audit log JSON (`evidence/day5-audit.json` hoặc file audit live) | Mỗi dòng có timestamp, `event_id`, user, action, decision (`denied`/`approval_required`/…); đối số được sanitize, không có event body, token hay raw tool output. |
| 2:35–3:00 | `make test-day5` | Test chữ ký, permission tier, approval và dedup đều pass. |

## Video 2 — Day 7 final state (3:00)

| Thời gian | Màn hình | Lời nói gợi ý |
|---|---|---|
| 0:00–0:20 | `showcase/README.md` | InsightHub: RAG notebook đã DevOps-hóa qua 6 ngày; bảng final state. |
| 0:20–0:50 | Web: upload tài liệu → 202 → `ready` → hỏi, có sources | Upload async qua Redis/ingestion-worker (Day 1). `curl /healthz` → 200. |
| 0:50–1:10 | `AGENTS.md` + `ai-prompts/` | Context cho agent và prompt log ghi quyết định chấp nhận/từ chối. |
| 1:10–1:30 | GitHub Actions `Day 3 local IaC` xanh | Terraform + Helm, checkov 0 failed, policy, plan, apply, smoke. |
| 1:30–2:00 | Grafana `insighthub-overview` + `evidence/day4-incident-1.json` | Anomaly band mean+3σ; RCA chỉ trích sample lấy từ Prometheus. |
| 2:00–2:20 | Slack: một câu hỏi tới bot | ChatOps dùng lại MCP Day 2. |
| 2:20–2:45 | `security/reports/eval-final.json` + Grafana `llm-cost` | 62 case: initial 52 HIGH/CRITICAL open → final 0. |
| 2:45–3:00 | `showcase/cost-report.md` | Tổng đo được 0.00158 USD / budget 1 USD; không có AWS chạy. |

Sau khi quay: dán link vào `showcase/submission.md` và gửi Loom Day 7 vào
`#day7-screencasts` trước 0h Day 7.
