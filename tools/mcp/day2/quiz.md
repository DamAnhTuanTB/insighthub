# Day 2 — Mini-quiz thực hành

Quiz local để tự kiểm tra kiến thức; không tự thay thế điểm quiz của giảng viên.
Chọn một đáp án cho mỗi câu. Đạt yêu cầu tự kiểm tra khi đúng ít nhất 7/10.
Gửi đáp án dạng `1A 2B ... 10C`; chưa có đáp án thì chưa ghi điểm hoàn thành.

1. Ba vai trò của MCP là gì?
   A. Host, Client, Server. B. Browser, Database, Queue. C. Model, Token, Prompt.
2. Tools, Resources và Prompts là gì?
   A. Ba loại credentials. B. Ba primitives của MCP. C. Ba Kubernetes workloads.
3. File cấu hình project có tự cấp quyền Kubernetes không?
   A. Có, chỉ cần Connected. B. Có, nếu đặt namespace. C. Không; RBAC trong cluster cấp và kiểm soát quyền.
4. Transport phù hợp cho MCP server chạy local bằng process là gì?
   A. stdio. B. SMTP. C. FTP.
5. Khi dùng Streamable HTTP từ xa, cần kiểm chứng thêm gì?
   A. Chỉ tên server. B. Auth, quyền truy cập và network scope. C. Không cần kiểm chứng.
6. Bộ verbs nào phù hợp với tài khoản chỉ đọc trong lab?
   A. get, list, watch. B. create, update, delete. C. exec, patch, delete.
7. Cách kiểm tra server/tool độc lập với LLM là gì?
   A. Chỉ nhìn Installed. B. Đoán từ tên package. C. Dùng MCP Inspector list/call tool.
8. Vì sao pin phiên bản/artifact thay vì dùng `@latest`?
   A. Tự tăng quyền. B. Tái lập môi trường và tránh thay đổi ngoài ý muốn. C. Không cần lockfile nữa.
9. Một gateway expose bốn tool có tự đáp ứng bốn backend Day 2 không?
   A. Không; cần mapping và gọi thật đủ Filesystem/Docker/K8s/Prometheus. B. Có. C. Có nếu gateway Connected.
10. `readOnlyHint=true` có phải là ranh giới bảo mật đủ mạnh không?
    A. Có, đó là RBAC. B. Có, model luôn tuân thủ. C. Không; quyền phải được server/OS/backend thực thi.
