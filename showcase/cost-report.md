# Cost report — tổng các lượt thực hành trong tuần

Nguồn máy đọc: `evidence/day7-cost-report.json`, sinh bởi
`python3 scripts/day7/cost_report.py`. Script chỉ đọc artifact đã commit và từ
chối báo 0 USD nếu evidence cho thấy có dùng AWS hoặc provider trả phí.

| Ngày | Thành phần | Chi phí (USD) | Cơ sở |
|---|---|---|---|
| 2–5 | LLM/embedding provider của ứng dụng | 0.00 | Provider fixture có nhãn (`evidence/day2.json`, `evidence/day3-local-deployment.yaml`, `evidence/day4-review.md`); bot Day 5 chỉ gọi MCP, không gọi LLM |
| 3–6 | AWS (EKS/RDS/ElastiCache/Budgets) | 0.00 | Không provision AWS; Day 3/4 review ghi `AWS verified: false`, Day 6 `aws_used: false` |
| 6 | LiteLLM → Ollama (security eval) | 0.00158 | 62 request, đơn giá nội bộ khai báo; `security/reports/cost-report.json` |
| **Tổng đo được** | | **0.00158** | Budget theo lượt lab 1.00 USD → **đạt budget** |

## Chưa đo (không cộng vào tổng)

| Thành phần | Owner cần điền |
|---|---|
| Provider ứng dụng Day 1 | Evidence Day 1 không ghi provider mode; xác nhận fixture hoặc thêm usage |
| Subscription coding host (IDE/CLI) | Báo riêng khỏi API cost theo specification; lấy từ billing của owner |
| Slack, tunnel HTTPS, GitHub | Xác nhận gói miễn phí hay trả phí |

## Kỷ luật chi phí đã áp dụng

- Không giữ dịch vụ AWS nào chạy giữa các buổi — không có tài nguyên AWS để teardown.
- CI Day 3 chạy trên self-hosted runner, không xin quyền AWS.
- Day 6 dùng Ollama local qua LiteLLM với 3 virtual key có `max_budget`; guardrail
  fail-closed đứng trước gateway.
- Đơn giá Day 6 là chargeback nội bộ khai báo, không phải hóa đơn provider.
