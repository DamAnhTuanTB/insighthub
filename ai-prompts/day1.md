# Day 1 AI Prompts

## Session metadata

- **Host / product**: ChatGPT-Codex with local checkout and tool execution.
- **CLI version**: `codex-cli 0.153.4` (observed with `codex --version`).
- **Configured model**: `gpt-5.6-sol`, reasoning effort `high`; this records the
  local Codex configuration, not an independently exposed immutable model snapshot.
- **Auth mode**: ChatGPT sign-in (observed with `codex login status`); no token or
  credential is stored in this evidence.
- **Environment**: macOS 26.6.2 (25G83), Apple Silicon `arm64`; Docker 29.3.1;
  container runtime Python 3.12.14.
- **Checkout**: `/Users/damanhtuan/Code/insighthub`, branch `day1-refactor`.
- **Context source**: root `AGENTS.md`, 6 sections and 42 lines.

## Provenance note

Mỗi mục trình bày **Prompt chính** theo cấu trúc constraint-first, được tổng hợp
từ yêu cầu, context đã đọc, quyết định review và hành động thực tế. Mục đích là
minh họa prompt 4 phần và giúp người học giải thích workflow. Diff, test output
và runtime evidence là kết quả thật.

## Prompt 1 - Xác định phạm vi Day 1

**Host**: ChatGPT-Codex

**Version / Model / Auth mode**: `codex-cli 0.153.4`; configured model
`gpt-5.6-sol` (`high`); ChatGPT sign-in.

**Context / Evidence**: `AGENTS.md`, `README.md`, `GETTING_STARTED.md`, specification mục 5 và verification contract.

**Time**: 2026-09-10 (Asia/Ho_Chi_Minh)

**Prompt chính**:

> **Mục tiêu:** Đọc tài liệu chính thức và lập checklist công việc Day 1, gồm các
> yêu cầu bắt buộc và điều kiện đạt Level 3/4.
>
> **Bối cảnh:** Đọc `AGENTS.md`, các tài liệu hướng dẫn Day 1 và verification
> contract. Dự án hiện có web, API và PostgreSQL.
>
> **Lưu ý:** Không đoán yêu cầu, không làm ngoài phạm vi Day 1 và không coi
> verifier PASS là đã đạt toàn bộ rubric.
>
> **Kết quả:** Checklist phải có năm service, xử lý tài liệu ở nền, upload trả
> HTTP 202 dưới 1 giây, tài liệu `ready` dưới 30 giây, chat hoạt động, tests,
> evidence và PR.

**Why it worked**:
- Buộc agent tìm nguồn yêu cầu chính thức thay vì đoán từ scaffold.
- Kết quả tách rõ Must-have, ngưỡng runtime, rubric và bằng chứng nộp bài.

**What I changed / reviewed**:
- Chấp nhận phạm vi năm service và contract 202.
- Giữ lưu ý rằng verifier chỉ kiểm tra một phần, không tự chứng nhận toàn bộ rubric.

## Prompt 2 - Triển khai refactor

**Host**: ChatGPT-Codex

**Version / Model / Auth mode**: Cùng phiên Codex và metadata ở trên; thay đổi
được giới hạn trong checkout dự án.

**Context / Evidence**: Code hiện hữu trong `api/app`, schema bất biến trong `infra/db/init.sql`, Compose 3 service và API tests.

**Time**: 2026-09-10 (Asia/Ho_Chi_Minh)

**Prompt chính**:

> **Mục tiêu:** Chuyển xử lý tài liệu sang chạy nền bằng Redis và ARQ, đồng thời
> thêm service `ingestion-worker`.
>
> **Bối cảnh:** Tận dụng lại `process_document` hiện có. API chỉ nhận file và đưa
> công việc vào hàng đợi; worker sẽ xử lý và lưu dữ liệu.
>
> **Lưu ý:** Không sửa database, không gọi dịch vụ trả phí và không ghi dữ liệu
> nhạy cảm vào log. File tối đa 10 MB, thử lại tối đa ba lần và không tạo dữ liệu
> trùng.
>
> **Kết quả:** Năm service đều healthy; upload trả HTTP 202 dưới 1 giây; tài liệu
> `ready` dưới 30 giây; chat, tests và verifier Day 1 đều hoạt động đúng.

**Why it worked**:
- Các constraint khóa phạm vi trước khi sửa, đặc biệt tránh viết lại ingestion atomic đang có.
- Tách orchestration queue khỏi processing giúp diff nhỏ và dễ kiểm chứng.

**What I changed / reviewed**:
- Chấp nhận tái sử dụng transaction/row lock hiện hữu.
- Chấp nhận enqueue bytes đã được giới hạn 10 MB để không đổi schema Day 1.
- Bổ sung rollback bản ghi pending nếu enqueue thất bại để tránh trạng thái treo giả.
- Bác bỏ phương án để ARQ dùng INFO log mặc định vì job arguments chứa filename
  và bytes tài liệu; thay bằng JSON event đã sanitize.

## Prompt 3 - Yêu cầu live test bằng mắt

**Host**: ChatGPT-Codex

**Version / Model / Auth mode**: Cùng phiên Codex và metadata ở trên; Docker
local fixture, không gọi paid provider.

**Context / Evidence**: UI tại `http://localhost:3001`, file
`sample-docs/so-tay-van-hanh.md`, trạng thái worker và browser console.

**Time**: 2026-09-10 (Asia/Ho_Chi_Minh)

**Prompt chính**:

> **Mục tiêu:** Kiểm tra trực tiếp quy trình upload và hỏi đáp trên giao diện
> Chrome.
>
> **Bối cảnh:** Mở `http://localhost:3001` và dùng file
> `sample-docs/so-tay-van-hanh.md`.
>
> **Lưu ý:** Upload bằng giao diện. Dừng worker để quan sát trạng thái `pending`,
> sau đó bật lại. Không bỏ qua quyền của trình duyệt.
>
> **Kết quả:** Tài liệu chuyển từ `pending/0 chunks` sang `ready/1 chunk`. Chat
> trả lời có nguồn đúng, chế độ fixture được ghi rõ và console không có lỗi.

**Why it worked**:
- Câu hỏi đầu tiên phát hiện khoảng trống giữa automated test và kiểm tra UX thật.
- Các follow-up cấp đúng quyền cần thiết nhưng vẫn giữ permission gate của browser.

**What I changed / reviewed**:
- File chooser ban đầu bị Chrome từ chối; không bypass, chờ người dùng bật quyền.
- Quan sát bằng mắt cả `pending` và `ready`; gửi câu hỏi RAG và kiểm tra console.
- Worker được bật lại và cả năm service được để ở trạng thái healthy.

## Prompt 4 - Hoàn thiện evidence và PR

**Host**: ChatGPT-Codex

**Version / Model / Auth mode**: Cùng phiên Codex và metadata ở trên; GitHub CLI
đăng nhập account `DamAnhTuanTB`.

**Context / Evidence**: Day 1 code đã chạy local; repository còn ở `main`, thay
đổi chưa commit và GitHub chưa có PR.

**Time**: 2026-09-10 (Asia/Ho_Chi_Minh)

**Prompt chính**:

> **Mục tiêu:** Hoàn thiện hồ sơ nộp Day 1 và tạo PR trên GitHub.
>
> **Bối cảnh:** Code và live test đã xong nhưng thay đổi chưa được commit và chưa
> có PR. Dùng branch `day1-refactor`.
>
> **Lưu ý:** Không lưu thông tin bí mật, không bỏ test để làm kết quả PASS, không
> force-push và không tự merge PR. Kiểm tra diff và evidence trước khi commit.
>
> **Kết quả:** Tất cả tests và verifier đều PASS; evidence khớp mã nguồn; branch
> được push và PR mở vào `main` với đúng tiêu đề yêu cầu.

**Why it worked**:

- Phạm vi thực thi đã được xác nhận, cho phép hoàn tất cả local artifact lẫn
  side effect GitHub trong đúng phạm vi đã thống nhất.
- Gate tests trước commit ngăn evidence PASS bị stale so với source.

**What I changed / reviewed**:

- Bổ sung metadata từ lệnh thật: CLI version, configured model, auth status, OS
  và checkout; không ghi credential.
- Phát hiện `make verify-day1` gọi nhầm Python hệ thống, sửa target dùng venv và
  chạy lại thành công.
- Tạo commit `6a63334` ban đầu; phát hiện Git tự sinh email local nên amend
  author thành danh tính GitHub đã cấu hình, tạo commit cuối `1005d84`.
- Push branch và mở PR #1; giữ PR mở để người học/trainer review trước khi merge.

## Permission evidence (read / approval / deny)

| Tier | Evidence from this session |
|---|---|
| Read in scope | Codex đọc `AGENTS.md`, specification, source và tests bằng lệnh read-only trước khi sửa; không đọc hoặc ghi secret. |
| Reviewed mutation | Người dùng xác nhận phạm vi triển khai, thao tác file và hoàn tất quy trình Day 1; diff và tests được review trước commit/push. |
| Deny / no bypass | Chrome extension từ chối file chooser khi chưa có quyền file URL. Codex dừng, báo đúng quyền cần bật và chỉ tiếp tục sau khi người dùng xác nhận đã cấp quyền; không bypass permission. |

## Manual visual verification

- Dừng `ingestion-worker`, upload `sample-docs/so-tay-van-hanh.md` bằng file
  picker và quan sát UI hiển thị `pending`, `0 chunks`.
- Khởi động lại worker; UI tự chuyển sang `ready`, `1 chunk`.
- Gửi câu hỏi RAG; response không rỗng, sources chứa
  `so-tay-van-hanh.md`, latency 12 ms và fixture được gắn nhãn rõ.
- Browser console không có warning hoặc error; năm service được trả về trạng thái
  healthy sau kiểm tra.
