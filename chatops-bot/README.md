# InsightHub ChatOps — Day 5

FastAPI chỉ xác thực raw-body Slack signature, chống replay, deduplicate `event_id`
và enqueue ARQ trước khi ACK. Worker riêng gọi Kubernetes/Prometheus MCP Day 2,
gửi câu trả lời qua Slack Web API và retry tối đa ba lần. Không có event body,
token, signing secret hay raw tool output nào được ghi audit.

## Local contract

Tạo môi trường và cài dependency khóa hash trước:

```bash
python3 -m venv .venv
.venv/bin/pip install -r chatops-bot/requirements.txt
make day5-local-pass
```

`day5-local-pass` dùng signing secret ngẫu nhiên, queue/tool doubles có nhãn fixture,
chạy toàn bộ behavioral tests rồi kiểm tra `/healthz`. Nó không gửi tin nhắn ra
Slack và không thay đổi Kubernetes.

## Live Slack trên máy local

Day 4 dùng incoming webhook cho Alertmanager. Day 5 cần một Slack App có hai
credential khác: `SLACK_SIGNING_SECRET` và bot token `SLACK_BOT_TOKEN`.

1. Copy `.env.example` thành `.env`, điền ba biến Slack và không commit file đó.
2. Bật OAuth scopes `app_mentions:read` và `chat:write`; subscribe `app_mention`,
   mời bot vào kênh thử nghiệm và tắt Socket Mode. Khi Socket Mode còn bật,
   Slack vẫn có thể verify Request URL nhưng sẽ chuyển events qua WebSocket thay
   vì endpoint HTTP Day 5.
3. Tạo identity MCP read-only riêng và chạy Redis:

   ```bash
   make day5-rbac
   CHATOPS_REDIS_PORT=6380 make day5-redis-up
   ```

   Dùng port khác nếu máy đã có Redis trên 6379 và đặt
   `CHATOPS_REDIS_URL=redis://127.0.0.1:6380/1`.

4. Chạy ingress ở terminal thứ nhất:

   ```bash
   set -a; source .env; set +a
   PYTHONPATH=chatops-bot .venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8080
   ```

5. Chạy worker ở terminal thứ hai. MCP mode cần Day 2 Kubernetes/Prometheus
   backends và port-forward Prometheus đã sẵn sàng:

   ```bash
   set -a; source .env; set +a
   PYTHONPATH=chatops-bot .venv/bin/arq app.worker.WorkerSettings
   ```

6. Expose port 8080 qua tunnel HTTPS và đặt Event Request URL thành
   `https://<public-host>/slack/events`.

Ba câu demo:

```text
@InsightHub api healthy?
@InsightHub ingest count today?
@InsightHub which pods failing?
```

`scale api to 2` chỉ phát token xác nhận 60 giây. Thao tác chỉ thực thi sau
`confirm <token>` và khi có `CHATOPS_MUTATION_KUBECONFIG` riêng, deployment nằm
trong allowlist và replicas thuộc 1–5. Các lệnh delete luôn bị từ chối.

Chi tiết yêu cầu: [Specification mục 9](../Running-Project-Specification-Student.md).
