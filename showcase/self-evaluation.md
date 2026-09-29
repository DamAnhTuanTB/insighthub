# Self-evaluation — bản nháp (mục 12)

Bản nháp để owner điền Google Form của trainer. Câu 1–3 được gợi ý từ evidence
đã commit, đối chiếu rubric từng ngày; **owner quyết định mức cuối cùng**. Câu
4–8 là ý kiến cá nhân nên để trống.

## 1. Tổng số artifact nộp được (1–7)

Gợi ý: **6/7** có evidence `mode: real` (Day 1–6). Day 7 thành 7/7 sau khi nộp
Loom screencast.

## 2. Artifact có thể tự đánh giá Level 4

| Artifact | Căn cứ theo rubric L4 | Cần owner xác nhận |
|---|---|---|
| Day 1 — AI-Augmented Code Quality | `AGENTS.md` 57 dòng (≤ 200) có mục Forbidden; worker retry 3 lần exponential + log JSON có cấu trúc; prompt log `ai-prompts/day1.md` | Ruff pass trên nhánh cuối |

Chưa đủ căn cứ cho L4 (L3 vững):

- **Day 6 — Security**: L4 đòi pass OWASP LLM + Agentic Top 10; `security/coverage.md`
  phủ 6 nhóm rủi ro (direct/indirect injection, RAG poisoning, PII, excessive
  agency, benign regression), chưa đủ 10 mục. L3 đạt: 62/62 case, 0 HIGH/CRITICAL
  (initial 52 open), guardrail bật, có threat model.
- **Day 6 — FinOps**: L4 đòi giảm cost per success trên cùng workload; cost
  report chưa có số so sánh trước/sau. L3 đạt: đúng budget, có dashboard
  `llm-cost` và 3 virtual key có `max_budget`.

## 3. Artifact có rủi ro dưới Level 3

| Artifact | Rủi ro | Căn cứ |
|---|---|---|
| Day 3 — IaC (Dim 2) | L3 yêu cầu **IRSA**; profile local không có IRSA | `evidence/day3-local-review.md`: "AWS verified: false", không claim IRSA |
| Day 3 — CI/CD (Dim 3) | L3 yêu cầu **OIDC AWS**; workflow không xin quyền AWS | Như trên; pipeline vẫn green với format/lint/scan/policy/plan/apply/smoke |
| Day 2 — Daily checkpoint | Quiz chưa có đáp án | `evidence/day2.json`: `quiz_status: awaiting_student_answers` |
| Day 5 — ChatOps | Thiếu screencast (MH11); L4 cần deploy K8s production, hiện bot chạy uvicorn local + tunnel | `evidence/day5-live.json` (L3: MCP backend, 3 intent, audit — đạt) |

Day 4 ở mức L3 vững (alert fire thật, 3 RCA trích sample Prometheus, dashboard
11 panel, baseline 124 phút). L4 cần Grafana Sift nên không áp dụng cho stack local.

## 4–8. Owner tự điền

4. Pillar học nhiều nhất: ☐ A. Develop ☐ B. Operate ☐ C. Govern
5. Tool sẽ tiếp tục dùng:
6. Câu hỏi cho trainer Day 7:
   *(gợi ý: profile local có được chấp nhận thay IRSA/OIDC cho L3 Day 3 không?)*
7. Roadmap (1/4): ☐ MLOps ☐ Autonomous Coding Agents ☐ Agentic Security ☐ A2A
8. Feedback: 3 điều giá trị nhất / 1 điều muốn đổi / gợi ý khoá sau:
