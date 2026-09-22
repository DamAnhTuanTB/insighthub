# MLOps Overview - ghi chú Day 4

Bốn block theo yêu cầu mục 8.4 MH12. Đây là phần lecture 25 phút, không hands-on:
InsightHub hiện dùng fixture provider và không tự huấn luyện model nào.

---

## Block 1 - ML lifecycle map

Vòng đời model khác vòng đời ứng dụng ở chỗ nó có hai nhánh chạy song song và
gặp nhau ở khâu deploy.

```
DỮ LIỆU        Collect → Label → Validate → Feature store
                                                  │
MODEL                      Train → Evaluate → Register → Approve
                                                  │
VẬN HÀNH                        Deploy → Serve → Monitor → Drift detect
                                                              │
                                                     └──── retrain trigger ────┘
```

Khác biệt cốt lõi so với app: vòng lặp không khép lại bằng một bug fix mà bằng
một lần **retrain**, và quyết định retrain dựa trên dữ liệu production chứ không
dựa trên code diff. Một model không đổi một dòng code vẫn có thể xuống cấp.

Ánh xạ sang InsightHub: khâu `Serve` và `Monitor` chính là cái Day 4 vừa dựng
(Prometheus, anomaly band, RCA). Các khâu còn lại thuộc ML team, DevOps chỉ cung
cấp hạ tầng và tín hiệu.

---

## Block 2 - Bốn khái niệm core

### Registry
Nơi lưu artifact model đã version hoá, kèm metadata: dataset nào, hyperparameter
nào, metric đánh giá bao nhiêu, ai train, khi nào. Registry trả lời câu "model
đang chạy trên production được sinh ra từ đâu". Không có registry thì rollback
là đoán mò. Tương đương `source_sha256` + image digest ở phía app.

### Approval Gate
Chốt chặn giữa `Register` và `Deploy`. Model qua được eval tự động vẫn phải có
người chịu trách nhiệm bấm duyệt, vì metric offline không bắt được tác hại thật
(bias, an toàn, vi phạm hợp đồng dữ liệu). Đây là ranh giới **người quyết định**,
không phải cổng kỹ thuật — tự động hoá nó là tự bỏ lớp phòng vệ cuối.

### Drift
Phân phối dữ liệu production lệch khỏi phân phối lúc train.
- **Data drift**: đầu vào đổi. Ví dụ InsightHub: người dùng bắt đầu upload PDF
  scan tiếng Nhật trong khi model embed được train trên văn bản tiếng Việt.
  Quan hệ đầu vào → nhãn vẫn đúng, chỉ là đầu vào lạ.
- **Concept drift**: quan hệ đầu vào → nhãn đổi. Cùng một câu hỏi, câu trả lời
  đúng bây giờ đã khác vì nghiệp vụ thay đổi. Nguy hiểm hơn vì đầu vào trông vẫn
  bình thường, metric hạ tầng vẫn xanh.

Drift không phải sự cố hạ tầng. Latency, error rate, queue depth đều bình thường
trong khi chất lượng trả lời đã hỏng.

### Rollback
Quay về version model trước đó. Khác rollback app ở ba điểm:
1. Phải rollback **cả model lẫn preprocessing/embedding identity** đi kèm. Ở
   InsightHub, đổi embedding identity là phải reindex — rollback model mà giữ
   index cũ sẽ cho kết quả sai lặng lẽ.
2. Không có "hotfix" — không sửa một dòng rồi deploy lại được.
3. Rollback không xoá nguyên nhân: nếu là concept drift thì version cũ cũng sai,
   chỉ sai theo kiểu quen thuộc hơn.

---

## Block 3 - Ownership boundary DevOps vs ML Engineer

| Stage | DevOps own | ML Engineer own |
|---|---|---|
| Data collect / label | Hỗ trợ (storage, pipeline) | **PRIMARY** |
| Feature engineering | — | **PRIMARY** |
| Training | Hỗ trợ (compute, GPU quota) | **PRIMARY** |
| Evaluation | — | **PRIMARY** |
| Registry hạ tầng | **PRIMARY** | Hỗ trợ (metadata schema) |
| Approval Gate | Hỗ trợ (cơ chế, audit) | **PRIMARY** (quyết định) |
| Deploy / rollout | **PRIMARY** | Hỗ trợ |
| Serving hạ tầng | **PRIMARY** | — |
| Monitoring hạ tầng (RED/USE) | **PRIMARY** | — |
| Monitoring chất lượng model | Hỗ trợ (metric pipeline) | **PRIMARY** |
| Drift detection | Hỗ trợ (tín hiệu, alert) | **PRIMARY** (ngưỡng, diễn giải) |
| Retrain quyết định | — | **PRIMARY** |
| Rollback thực thi | **PRIMARY** | Hỗ trợ (chọn version) |

Câu chốt: **DevOps không bao giờ tự retrain model.** Khi drift alert nổ, việc của
DevOps là (1) xác nhận hạ tầng không phải nguyên nhân, (2) thu thập bằng chứng
metric + timestamp, (3) bàn giao cho ML team, (4) sẵn sàng thực thi rollback nếu
được yêu cầu. Tự retrain là vượt ranh giới trách nhiệm và tạo ra một model không
ai duyệt.

---

## Block 4 - App artifact vs Model artifact (4 chiều)

| Chiều | App artifact | Model artifact |
|---|---|---|
| **Tính tất định** | Cùng input → cùng output, mọi lần | Có thể khác do seed, batch, phiên bản thư viện; kết quả là phân phối |
| **Nguồn gốc** | Code + dependency. Build lại từ commit là ra đúng artifact | Code + **dataset** + hyperparameter + seed. Thiếu dataset thì không tái tạo được |
| **Kiểm thử** | Pass/fail nhị phân, coverage đo được | Metric liên tục trên tập held-out; không có "pass" tuyệt đối, chỉ có ngưỡng chấp nhận |
| **Điều kiện xuống cấp** | Chỉ hỏng khi code/dependency/hạ tầng đổi | Hỏng dù **không đổi gì**, vì thế giới bên ngoài đổi (drift) |

Hệ quả vận hành: app artifact hỏng thì có stack trace; model artifact hỏng thì
chỉ có metric tụt dần. Đó là lý do Day 4 đầu tư vào baseline và anomaly band —
với model, phát hiện lệch so với chính mình trong quá khứ là công cụ chính.
