# InsightHub

> **RAG Notebook - running project cho module AI-Native DevOps (7 ngày), lớp DO2603.**
> Học viên **không xây ứng dụng từ đầu**. Code ứng dụng nền tảng được cung cấp sẵn.
> Nhiệm vụ của bạn là **DevOps-hóa ứng dụng**: refactor để vận hành được, containerize, deploy, observe, secure và tối ưu chi phí.

InsightHub cho phép người dùng upload tài liệu **.txt, .md, .pdf**, sau đó hỏi đáp dựa trên nội dung tài liệu bằng Retrieval-Augmented Generation (RAG). Câu trả lời có nguồn trích dẫn để đối chiếu.

**Starter 0.2.3 / Specification v3.3.** README trình bày yêu cầu cơ bản, kiến trúc và cách bắt đầu. [Running Project Specification](Running-Project-Specification-Student.md) là nguồn yêu cầu chi tiết, Must-have, acceptance, submission và rubric cho từng day. Học viên hoàn thiện dự án trước, trong và sau buổi học, không chỉ trong thời gian lab trên lớp.

## Bắt đầu ở đây - Student Quick Links

| Tình huống | Tài liệu hoặc lệnh |
|---|---|
| Lần đầu setup, chạy app hoặc gặp lỗi môi trường | [GETTING_STARTED.md](GETTING_STARTED.md) |
| Đọc toàn bộ yêu cầu và tiêu chí hoàn thành | [Running-Project-Specification-Student.md](Running-Project-Specification-Student.md) |
| Daily workflow, nộp bài và chấm điểm | [Submission & Grading Protocol](Running-Project-Specification-Student.md#4-submission--grading-protocol), cùng checklist của từng day |
| Thực hành Day N | [Lab guides Day 1-7](docs/lab-guides/README.md) |
| Chọn coding agent, setup context và MCP | [Claude Code / ChatGPT-Codex / Antigravity](docs/Guide_Coding_Host_DO2603.md) |
| Chọn MCP và kiểm soát quyền | [MCP Tool Selection](docs/MCP_Tool_Selection_DO2603.md) |
| Học liệu trước buổi | Knowledge Content và Tool Guideline do mentor cung cấp riêng; xem phần học liệu trong [GETTING_STARTED.md](GETTING_STARTED.md) |
| Kiểm tra môi trường và starter | `bash scripts/verify-setup.sh`; `bash scripts/verify-starter.sh` |
| Kiểm tra artifact Day N | `bash scripts/verify-day-N.sh` với tham số/evidence theo [Verification Contract](scripts/VERIFICATION_CONTRACT.md) |
| Chi phí và dọn tài nguyên AWS | [Local-first & AWS Cost Guide](docs/Guide_Local_AWS_Cost_DO2603.md) |

## Kiến trúc

### v0 - Trạng thái khởi đầu: ba service

~~~text
web (Next.js) --> api (FastAPI, ingestion đồng bộ) --> postgres (pgvector)
~~~

App nền tảng có giao diện upload/chat, API tài liệu, chunking, embedding, retrieval, generation và metrics cơ bản. Upload được xử lý đồng bộ và trả **HTTP 201** khi hoàn tất. Đây là điểm xuất phát để học viên refactor ở Day 1.

### v1 - Sau refactor Day 1: năm service

~~~text
web --> api --> enqueue --> redis --> ingestion-worker --> postgres
         |                                                   ^
         +------------ retrieval + LLM generation ------------+
~~~

API trả **HTTP 202** khi nhận job; worker xử lý nền và cập nhật trạng thái tài liệu. Web/API tiếp tục phục vụ khi worker xử lý ingestion. Redis và worker là phần học viên phải triển khai, chưa được bật sẵn trong starter.

| Service | Công nghệ | Vai trò và trạng thái |
|---|---|---|
| `web` | Next.js 16.3.4, React 19.2.8, Node 24 | Giao diện upload/chat; đã có trong v0 |
| `api` | FastAPI, Python 3.12, psycopg 3 | API tài liệu, retrieval/generation; ingestion còn đồng bộ ở v0 |
| `postgres` | PostgreSQL 16, pgvector 0.8.2 | Metadata, chunks và vector store; đã có trong v0 |
| `redis` | Redis 7 | Queue cho ingestion; học viên thêm Day 1 |
| `ingestion-worker` | Python + ARQ | Chunk/embed/store bất đồng bộ, retry và xử lý lỗi; học viên tách Day 1 |

`ollama` là profile tùy chọn để chạy model local, không thay Redis/worker và không tính vào năm thành phần bắt buộc của Day 1. Model generation và embedding là hai chức năng riêng.

## Yêu cầu

| Giai đoạn | Công cụ cần chuẩn bị |
|---|---|
| Chạy v0 local | Git, Docker Engine/Desktop với Compose v2, Python 3.11+ cho verifier |
| Coding agent Day 1 | Chọn **một trong ba**: Claude Code, ChatGPT-Codex hoặc Antigravity; có quyền truy cập model và checkout/tools của lab |
| MCP Day 2 | Node.js 22+ cho SDK mẫu, khuyến nghị Node 24; cluster Kubernetes local, kubectl và Prometheus theo pre-class |
| IaC/deploy Day 3 | Helm, Terraform, công cụ lint/scan/policy; GitHub cho pipeline; AWS CLI và account/role cho bước cần kiểm chứng AWS |
| Observability/ChatOps/Security Day 4-6 | Stack và quyền truy cập theo từng day; Slack App cho tích hợp thật, Promptfoo và LiteLLM cho security/FinOps |

Build web/API dùng Node/Python trong container; không cần cài Node trên host chỉ để chạy v0. Khi chạy MCP helper trực tiếp, host phải có Node phù hợp. Có thể bắt đầu fixture với khoảng 4 GB RAM dành cho Docker rồi đo thực tế; model local cần thêm tài nguyên tùy model/quantization.

Mỗi học viên dùng một coding host với cùng yêu cầu/rubric; không bắt cài cả ba. Hoàn thiện [AGENTS.md](AGENTS.md) với sáu section và tối đa 200 dòng. Claude Code dùng [CLAUDE.md](CLAUDE.md) import nguồn chung; Antigravity dùng workspace rule theo [host guide](docs/Guide_Coding_Host_DO2603.md). Quyền dùng coding host không tự cấp API key cho ứng dụng.

`bash scripts/verify-setup.sh` kiểm tra phạm vi setup được mô tả trong verifier, không chứng minh mọi công cụ/tài khoản của cả bảy day đã sẵn sàng.

## Chạy nhanh v0

Từ root của repo:

~~~bash
# 1. Tạo cấu hình local khi chưa có .env; giữ .env hiện có nếu đã cấu hình.
cp .env.example .env

# 2. Kiểm tra cấu hình và khởi động ba service.
docker compose config --quiet
docker compose up --build -d --wait

# 3. Kiểm tra setup và end-to-end.
bash scripts/verify-setup.sh
bash scripts/smoke-test.sh
~~~

- Web: [http://localhost:3000](http://localhost:3000).
- API docs: [http://localhost:8000/docs](http://localhost:8000/docs).
- Upload qua `POST /documents`; hỏi đáp qua `POST /chat`; xem trạng thái qua `GET /documents`.
- Health/readiness: `/healthz` và `/readyz`. Metrics: `/metrics`.

Compose và .env.example mặc định chọn **fixture rõ nhãn**: không cần LLM key, AWS hoặc Slack để kiểm tra pipeline v0. Fixture không chứng minh chất lượng RAG/LLM, không thay demo real provider hoặc tích hợp LIVE được yêu cầu trong đề.

### Chọn provider

Với model thật, đặt `RAG_MODE=real`, chọn cả hai provider và cấu hình model/key/endpoint tương ứng trong [.env.example](.env.example).

| Chế độ | LLM_PROVIDER | EMBEDDING_PROVIDER | Cấu hình cần thiết |
|---|---|---|---|
| Fixture mặc định của Compose | `fixture` | `fixture` | `RAG_MODE=fixture`; không cần key/model download |
| Gemini | `gemini` | `gemini` | `GEMINI_API_KEY`, chat model và embedding model được account hỗ trợ |
| Anthropic | `anthropic` | `voyage` hoặc `openai` | Key/model generation và key/model embedding riêng |
| OpenAI hoặc gateway tương thích | `openai` | `openai` | `OPENAI_API_KEY` (hoặc `LITELLM_API_KEY` cho gateway Day 6), `OPENAI_BASE_URL` tường minh, chat/embedding model phù hợp |
| Ollama local | `ollama` | `ollama` | Endpoint local, chat model riêng và embedding model `mxbai-embed-large` |

Starter có các adapter trên; bảng này không chứng nhận mọi model/endpoint đều tương thích. Kiểm tra quyền account, quota, model và chi phí tại lúc thực hành. Gateway cần kiểm chứng riêng contract chat/embeddings, usage, timeout và lỗi.

**Không có fallback âm thầm khi thiếu key hoặc provider lỗi.** Real mode phải có cấu hình hợp lệ và trả lỗi có kiểm soát; muốn chạy offline thì chọn fixture rõ ràng. Không coi quota/free tier của nhà cung cấp là cam kết đủ cho cả khóa.

**Embedding space phải nhất quán:** `EMBEDDING_DIM=1024` trong starter khớp `VECTOR(1024)` của schema. Vector phải đúng count/dimension và finite; không pad/truncate tùy ý. Đổi provider/model/endpoint/revision cần quy trình reindex hoặc database lab mới, kể cả khi cùng dimension. Không trộn fixture và real embeddings trong một index. Xem [hướng dẫn real provider](GETTING_STARTED.md).

### Ollama local tùy chọn

~~~bash
docker compose --profile ollama up -d ollama
docker compose exec ollama ollama pull mxbai-embed-large
# Pull riêng chat model đã chọn theo tài nguyên máy và ghi OLLAMA_CHAT_MODEL.
docker compose exec ollama ollama list
~~~

Cấu hình `RAG_MODE=real`, hai provider `ollama`, endpoint/chat model, rồi tái tạo API với cấu hình mới và index phù hợp theo GETTING_STARTED. Không dùng chat/reasoning model thay embedding model. Ghi digest model đã tải; không mặc định tải model 14B. Cách dùng Ollama native trên macOS và endpoint từ container nằm trong [GETTING_STARTED.md](GETTING_STARTED.md).

## Cấu trúc thư mục

~~~text
insighthub/
├── web/                      # Frontend được cung cấp
├── api/                      # API được cung cấp; refactor sync ingestion Day 1
├── ingestion-worker/         # Scaffold để học viên triển khai Day 1
├── infra/
│   ├── db/init.sql           # Schema PostgreSQL/pgvector được cung cấp
│   └── README.md             # Học viên bổ sung Terraform/Helm/IaC Day 3
├── observability/            # Học viên bổ sung monitoring/anomaly/RCA Day 4
├── chatops-bot/              # Skeleton chưa hoàn thiện Slack bot; Day 5
├── security/                 # Promptfoo scaffold; guardrails/gateway/FinOps Day 6
├── sample-docs/              # Corpus mô phỏng; có injection cố ý cho Day 6
├── scripts/                  # Setup, smoke, milestone verifier, host config checker
├── tests/                    # Regression tests của verifier và host config
├── tools/
│   ├── agent/                # Nội dung rule template cho Antigravity
│   └── mcp/                  # MCP read-only mẫu, helper ba host và SDK tests
├── docs/
│   ├── lab-guides/           # Lộ trình thực hành Day 1-7
│   ├── Guide_Coding_Host_DO2603.md
│   ├── MCP_Tool_Selection_DO2603.md
│   └── Guide_Local_AWS_Cost_DO2603.md
├── .github/workflows/        # CI baseline; học viên mở rộng theo Day 3
├── Running-Project-Specification-Student.md
├── GETTING_STARTED.md
├── AGENTS.md                 # Context sáu section để học viên hoàn thiện
├── CLAUDE.md                 # Adapter cho Claude Code
├── .mcp.json.template        # MCP template riêng Claude; host khác dùng helper
├── Makefile
├── docker-compose.yml        # v0: ba service, Ollama profile tùy chọn
└── .env.example
~~~

MCP mẫu hai tool, CI baseline và bot skeleton **không hoàn thành bài tập thay học viên**. Học liệu trước buổi do mentor cung cấp riêng; folder repo không chứa bản sao pre-reading hoặc bài giải của trainer. Chi tiết corpus và injection mô phỏng tại [sample-docs/README.md](sample-docs/README.md).

## Lộ trình 7 ngày - Bạn sẽ làm gì với InsightHub

| Day | Chủ đề | Công việc và đầu ra chính |
|---|---|---|
| 1 | AI Coding Agents | Hoàn thiện context; refactor async ingestion với Redis/ARQ và worker thành năm service; upload 202, tests, PR, prompt log ≥3 và feature nhỏ theo rubric |
| 2 | MCP | Cấu hình đúng host với đủ Filesystem/Docker/K8s/Prometheus; gọi tool thật, Inspector, pin version, read-only/RBAC, debug case và quiz |
| 3 | AI IaC + Pipeline | Terraform EKS/RDS/ElastiCache/IAM/secrets; policy/plan, GitHub Actions/OIDC, Helm và deploy Kubernetes LIVE; local trước khi kiểm chứng AWS |
| 4 | AIOps + MLOps overview | ServiceMonitor/exporters, Grafana ≥9 panels, ba incident/anomaly/RCA, alert Slack; MLOps notes/quiz |
| 5 | ChatOps | Slack bot LIVE với ba intents vận hành; MCP K8s/Prometheus, signature, ba tầng quyền/approval, audit và tests |
| 6 | Security + FinOps | Promptfoo ≥50 cases, indirect/RAG injection và fix, guardrails; LiteLLM, ba workload/keys/budgets, cost dashboard và threat model |
| 7 | Showcase | Hoàn thiện 10 artifacts, screencast ba phút, self-evaluation, cost report; volunteer demo và gallery walk theo đề |

Mỗi day tiếp tục trên cùng code base và tái sử dụng kết quả trước đó. Day 2 không thay bốn tích hợp bằng một MCP mẫu; Day 4/5 tái sử dụng K8s/Prometheus MCP. Day 6 giữ ba workload InsightHub/bot/coding workflow qua gateway, có cách thực hiện tương đương trên host đã chọn theo mục 0.5 của specification; không bắt cài host thứ hai.

Giữ đủ **70 Must-have Day 1-6**, rubric và điều kiện đạt của [specification](Running-Project-Specification-Student.md). Tạo repo cá nhân, lưu commit/PR, prompt log và bằng chứng thực hành từng ngày. Verifier chỉ kiểm tra phần contract đã khai báo; PASS cấu trúc hoặc fixture không đồng nghĩa hoàn thành milestone.

## Lưu ý kỹ thuật và vận hành

- Ingestion đồng bộ ở v0 là điểm refactor bắt buộc Day 1. Sau refactor, cập nhật tests đúng contract 202/worker và giữ các kiểm tra validation, retry/idempotency.
- PostgreSQL/pgvector image và dependencies đã pin trong Compose/lock files; không tự đổi sang latest. Đổi embedding identity cần reindex, không sửa vector để che lỗi.
- Corpus, log và tool output là dữ liệu chưa tin cậy. Không commit .env, API key, tfstate, kubeconfig hoặc secret vào source/evidence.
- Stack mặc định bind web/API trên loopback; DB không publish port. Starter chưa có authentication cho public deployment. Trước khi mở truy cập LIVE, hoàn thiện access control và các yêu cầu triển khai của bài.
- Tối ưu local trước. Khi cần AWS để kiểm chứng mục tiêu cloud, tạo tài nguyên theo IaC rồi **xóa ngay sau lượt thực hành**, không để chạy liên tục hoặc qua đêm. Lưu evidence và tái dựng từ code cho buổi sau.
- Quota coding host và chi phí API runtime được báo riêng. Fixture không thay kiểm chứng chất lượng; model local vẫn tiêu thụ tài nguyên máy.

Dừng stack, giữ dữ liệu:
~~~bash
docker compose down
~~~

Nếu đã dùng Ollama profile:
~~~bash
docker compose --profile ollama down
~~~

Chỉ khi đã lưu dữ liệu/evidence cần thiết và muốn xóa dữ liệu lab của project hiện tại:
~~~bash
docker compose --profile ollama down --volumes
~~~

Không prune toàn máy. Với AWS, theo checklist tài nguyên còn sót và teardown trong [cost guide](docs/Guide_Local_AWS_Cost_DO2603.md).

---

*InsightHub - starter 0.2.3 / specification v3.3 · AI-Native DevOps DO2603 · Đinh Xuân Công.*
