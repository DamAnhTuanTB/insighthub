# Day 1 Refactor Review

Refactor thay đường upload đồng bộ bằng hai bước: API tạo document `pending` và enqueue một ARQ job có ID ổn định; ingestion-worker gọi lại `process_document` hiện hữu trong thread. Cách này giữ transaction, row lock, savepoint, embedding identity và unique chunk index đã được kiểm thử, đồng thời loại provider/database processing khỏi request path.

Rủi ro chính là DB insert thành công nhưng Redis enqueue thất bại. API xử lý bằng cách xóa đúng bản ghi còn `pending` và trả lỗi `queue_unavailable` đã sanitize. Queue job mang bytes đã được giới hạn 10 MB; đây là lựa chọn Day 1 để không đổi schema, nhưng production nên dùng object storage cùng transactional outbox. Job ID gắn với document ID và processing thành công là no-op khi chạy lại, nên retry không nhân đôi chunks.

Worker chạy tối đa ba attempt, delay lũy thừa 1 giây rồi 2 giây. Mỗi lần lỗi, ingestion core ghi trạng thái `failed` và dọn chunks theo transaction; lần sau có thể chuyển lại `ready`. Worker không ghi filename, content, vector, credential hoặc raw provider error. Event hoàn tất là JSON một dòng có timestamp, document ID và status để verifier đối chiếu với upload mới.

Validation gồm unit tests cho 202, queue failure cleanup, bounded upload và sanitized error; integration tests giữ atomicity, retry/concurrency, vector identity, real-provider adapter mock và chat regression; milestone tests chạy black-box qua năm service. Không sửa schema và không xóa assertion dữ liệu cũ. Runtime verification phải được chạy lại sau mọi thay đổi source vì evidence hash có chủ ý chống stale artifact.

Manual UI verification tạm dừng worker trước khi upload
`sample-docs/so-tay-van-hanh.md`: giao diện hiển thị `pending` với 0 chunks. Sau
khi worker được bật lại, polling tự chuyển tài liệu sang `ready` với 1 chunk.
Chat trả response có nguồn từ file vừa upload và browser console không có warning
hoặc error. Stack được để lại với cả năm service healthy.

Các quyết định review chính: giữ ingestion transaction/row lock hiện hữu; dùng
job ID ổn định theo document ID; xóa row pending nếu enqueue thất bại; từ chối
ARQ INFO logging mặc định vì có thể render filename/content; chưa thêm object
storage/outbox vì Day 1 cấm đổi schema và fixture đã giới hạn payload 10 MB.
