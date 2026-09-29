# Day 7 — Final state & showcase

Đối chiếu mục 11.3 của specification với artifact đã commit. Mỗi dòng trỏ tới
evidence có thể mở lại; trạng thái "Chờ owner" là việc máy không làm thay được.

## Final project state (mục 11.3)

| # | Artifact | Trạng thái | Evidence |
|---|---|---|---|
| 1 | Day 1: PR + context/adapter, ingestion-worker tách | Có | `AGENTS.md`, `CLAUDE.md`, `ingestion-worker/`, `evidence/day1.json`, `evidence/day1-review.md` |
| 2 | Day 2: MCP config theo host, 4 backend | Có, **quiz chưa làm** | `.mcp.json`, `evidence/day2-sdk-*.json`, `evidence/day2-inspector-*.png`; `evidence/day2.json` ghi `quiz_status: awaiting_student_answers` |
| 3 | Day 3: Terraform checkov no-HIGH | Có (local profile) | `evidence/day3-local-review.md` — AWS **chưa** xác minh theo thiết kế |
| 4 | Day 3: CI/CD green | Có | Workflow `Day 3 local IaC` (`.github/workflows/iac.yml`) success trên `main` |
| 5 | Day 4: Observability + 3 RCA | Có | `observability/grafana/insighthub-overview.json` (11 panel), `evidence/day4-incident-{1,2,3}.json`, `evidence/day4-alerting.json` (8 Slack notification, 0 fail) |
| 6 | Day 5: ChatOps bot live | Có, **thiếu screencast** | `evidence/day5-live.json` — 3 intent trả lời trong Slack qua MCP Kubernetes/Prometheus |
| 7 | Day 6: Promptfoo no-HIGH + threat model + cost dashboard | Có | `security/reports/eval-final.json` (62/62, 0 HIGH/CRITICAL; initial 52 open), `security/threat-model.md`, `observability/grafana/llm-cost.json` |
| 8 | Screencast 3' Loom | **Chờ owner** | Kịch bản: [`screencast.md`](screencast.md) |
| 9 | Cost report cả tuần | Có | [`cost-report.md`](cost-report.md), `evidence/day7-cost-report.json` |
| 10 | InsightHub LIVE `/healthz` → 200 | Có (bật lúc chấm) | 2026-09-29: `make up` → 5 service healthy, `/healthz` 200 `{"status":"ok","mode":"fixture"}`, `make smoke` PASS |

## Việc owner phải tự làm

1. Quay Loom 3' theo [`screencast.md`](screencast.md); Day 5 cũng yêu cầu một screencast riêng.
2. Trả lời quiz Day 2 (`tools/mcp/day2/quiz.md`) và quiz form của trainer.
3. Điền self-evaluation form của trainer, dùng bản nháp [`self-evaluation.md`](self-evaluation.md).
4. Chọn 1/4 roadmap (mục 13) và điền chi phí subscription coding host vào cost report.
5. Chụp ảnh tương tác Slack cho Day 5; gửi bản nộp theo [`submission.md`](submission.md).

## Xác minh tổng (2026-09-29)

Evidence Day 1–6 được sinh lại trên cùng source
`0a291d14082d4fcba353168fee15d0b75db22f440725bf1a10439159f33500af` rồi chạy
`verify.py day7` một lượt với mọi service live. Báo cáo: `evidence/day7-verify.json`.

| Check | Kết quả |
|---|---|
| day1–day6 | PASS, `runtime_verified=true` cả sáu |
| full-project-review | INCOMPLETE theo thiết kế — screencast, self-evaluation, submission cần người review |

Day 3 bind vào GitHub Actions run `36572814473`; Day 4 chạy lại đủ baseline 70
phút và ba incident riêng (chi tiết trong `evidence/day4-review.md`); Day 5 live
Slack giữ bản quan sát 2026-09-28 (`evidence/day5-live.json`), phần local contract
được chạy lại.

## Tái lập

Chốt source trước (fingerprint gồm `scripts/`, `Makefile`, ... — sửa sau khi sinh
evidence làm mọi ngày stale). Verify tổng cần đồng thời: stack Day 6
(`scripts/day6/up.sh`, API :8000/web :13000), bot Day 5 ở :18080, Prometheus
port-forward :9090 và một CI run trên đúng commit:

```bash
python3 scripts/day7/cost_report.py
.venv/bin/python -B scripts/verify.py day7 --evidence-dir evidence \
  --api-url http://127.0.0.1:8000 --web-url http://127.0.0.1:13000 \
  --prometheus-url http://127.0.0.1:9090 --bot-url http://127.0.0.1:18080 --bot-transport http \
  --ci-profile github --ci-repo DamAnhTuanTB/insighthub --ci-run-id <run-id> \
  --test-timeout 900 --timeout 30
```

Evidence phải dưới 24h khi verify (`--max-age-hours`).
