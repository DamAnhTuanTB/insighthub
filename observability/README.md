# Observability và MLOps - Day 4

ServiceMonitor/exporter cho đủ 5 thành phần, Grafana 9+ panel, 3 anomaly rule và
3 incident/RCA, Slack alert, MLOps overview notes 4 block/quiz. Queue/worker Day 1
và deployment Day 3 phải có thật. [Spec mục 8](../Running-Project-Specification-Student.md).

**Toàn bộ chạy local.** Kubernetes là `kind` trong Docker trên máy, Prometheus /
Grafana / Alertmanager là pod trong cùng cluster đó. Đây **không phải** EKS,
Amazon Managed Prometheus hay Grafana Cloud, và không cần tài khoản AWS.

## Thành phần

| Thư mục / file | Vai trò |
|---|---|
| `kube-prometheus-stack/values-local.yaml` | Cấu hình stack: retention 15 ngày, resource limit, Alertmanager → Slack |
| `rules/day4-rules.yaml` | Recording + anomaly rule. **Nguồn sự thật duy nhất**, là artifact nộp verifier |
| `rules/day4-rules_test.yaml` | Unit test `promtool test rules` cho file trên |
| `grafana/insighthub-overview.json` | Dashboard RED/USE, 11 panel |
| `loadgen/` | Sinh tải đều để anomaly band có baseline thật |
| `RUNBOOK.md` | Mỗi alert trỏ tới đây: ý nghĩa, kiểm tra gì trước, khi nào là false positive |
| `mlops-overview-notes.md` | MH12 - 4 block |
| `day4-quiz.md` | MH11 - 10 câu self-check |

Rule trong cluster được sinh từ `rules/day4-rules.yaml` bằng
`scripts/day4/render-prometheusrule.py`, nên file được promtool kiểm và rule
Prometheus đang chạy không bao giờ lệch nhau.

## Tín hiệu của 5 thành phần

| Thành phần | Nguồn |
|---|---|
| api | `/metrics` cổng 8000, ServiceMonitor |
| ingestion-worker | `/metrics` cổng 9101 (queue depth, job duration, outcome), ServiceMonitor |
| postgres | `postgres_exporter`, ServiceMonitor |
| redis | `redis_exporter`, ServiceMonitor |
| web | Next.js không có `/metrics` → `blackbox_exporter` probe HTTP qua `Probe` CRD |

Bổ sung: `kube-state-metrics` và cAdvisor (qua kubelet) cho panel pod resource và
annotation deploy.

## Quy trình

```bash
make day4-monitoring-up          # cài kube-prometheus-stack vào namespace monitoring
make day4-app-up                 # deploy InsightHub kèm exporter + ServiceMonitor
make day4-rules                  # promtool check + test, rồi apply PrometheusRule
make day4-dashboard              # đẩy dashboard vào Grafana qua sidecar ConfigMap
SLACK_WEBHOOK_URL=... make day4-slack
make day4-loadgen-up             # bắt đầu tích baseline
make day4-forward                # port-forward Prometheus/Grafana/Alertmanager/API
make day4-status                 # kiểm tra target, band, alert
```

**Chờ ít nhất 70 phút** trước khi inject incident: band dùng cửa sổ 1 giờ lệch 10
phút, nên alert chỉ có ý nghĩa sau mốc đó. Thiếu baseline thì ghi nhận là chưa đủ,
không được hạ ngưỡng xuống vài phút.

```bash
make day4-incident-1             # LLM latency spike
make day4-incident-2             # queue backlog
make day4-incident-3             # error burst
make day4-samples                # lấy sample thật từ Prometheus cho từng incident
make day4-verify                 # scripts/verify.py day4
```

## Ranh giới trung thực

- Band là thống kê (mean + 3·stddev), **không phải** machine learning.
- Panel cost là ước tính từ đơn giá khai báo nhân với token quan sát được, **không
  phải** hoá đơn nhà cung cấp. Fixture mode không báo token LLM thật.
- Số liệu trong RCA chỉ được lấy bằng `scripts/day4/collect-samples.py`. Verifier
  truy vấn ngược từng sample và so khớp `1e-6`; số bịa sẽ làm verify FAIL.
- Chaos flag bị config từ chối nếu không ở fixture mode.

## Dọn dẹp

`make day4-down` chỉ gỡ namespace `monitoring`. Dữ liệu InsightHub và namespace
`insighthub-dev` không bị đụng tới.
