# Day 4 quiz - 10 câu self-check (mục 8.9)

Yêu cầu MH11: đạt ≥ 4/5 câu MLOps. Ghi cả phần AIOps để đối chiếu với hệ thống
thật đã dựng.

## AIOps

**1. ServiceMonitor scrape mấy service? 30s interval đủ chưa?**
Bốn ServiceMonitor (api, worker, postgres-exporter, redis-exporter) cộng một
Probe cho web qua blackbox — phủ đủ 5 thành phần. 30s đủ cho lab: alert dùng
`for: 2m`, tức 4 lần scrape liên tiếp phải cùng vi phạm mới nổ, đủ chống flapping.
Với sự cố cần phát hiện dưới 1 phút thì 30s là không đủ, nhưng đánh đổi là
cardinality và dung lượng TSDB.

**2. Anomaly band 3·stddev - false positive rate trong 1h?**
Với phân phối chuẩn, 3σ cho ~0.27% mẫu nằm ngoài band. Baseline 1h với recording
rule 30s ≈ 120 mẫu → kỳ vọng ~0.3 lần vượt ngưỡng đơn lẻ mỗi giờ. Nhưng `for: 2m`
yêu cầu vượt liên tục 4 mẫu, nên false positive thực tế thấp hơn nhiều bậc. Điều
kiện sàn tuyệt đối (`> 0.5s`, `> 5 jobs`, `> 5%`) chặn nốt trường hợp baseline
quá phẳng khiến stddev ≈ 0 và band sát mép.

**3. Ba incident - cái nào dễ phát hiện nhất? Vì sao?**
Queue backlog. Nó là gauge trực tiếp, không cần histogram hay tỉ lệ, không phụ
thuộc lưu lượng, và biên độ thay đổi lớn (0 → hàng chục). Error burst khó hơn vì
là tỉ lệ — lưu lượng thấp làm mẫu số nhỏ và tỉ lệ nhiễu. LLM latency khó nhất vì
p95 từ histogram cần đủ request trong cửa sổ 5 phút mới ổn định.

**4. RCA report có cite metric + timestamp không? Confidence > 0.7?**
Có. Mỗi sample trong `evidence/day4-incident-*.json` gồm `metric`, `labels`,
`timestamp` RFC3339 và `value`, được `scripts/day4/collect-samples.py` lấy trực
tiếp từ Prometheus. Verifier truy vấn ngược từng sample và so khớp `1e-6`, nên
một con số bịa sẽ làm verifier FAIL chứ không lọt.

**5. Correlation > Detection - apply ở incident nào?**
Rõ nhất ở incident 3. Detection chỉ nói "5xx tăng". Correlation mới chỉ ra
`pg_up` về 0 **trước** khi error ratio tăng, và `up{job="insighthub-api"}` vẫn
bằng 1 — tức API còn sống, dependency mới là thứ chết. Một mình error ratio không
phân biệt được "API hỏng" với "API khoẻ nhưng DB mất".

## MLOps

**6. App vs Model artifact khác nhau ở 4 chiều nào?**
Tính tất định, nguồn gốc tái tạo, cách kiểm thử, và điều kiện xuống cấp. Chi tiết
ở block 4 của `mlops-overview-notes.md`.

**7. Drift data vs Drift concept - khác nhau thế nào?**
Data drift: phân phối **đầu vào** lệch, quan hệ đầu vào→nhãn giữ nguyên. Concept
drift: quan hệ **đầu vào→nhãn** đổi, đầu vào có thể trông y hệt. Concept drift
nguy hiểm hơn vì không phát hiện được bằng cách theo dõi phân phối input.

**8. Nếu team có model riêng và drift fire, DevOps làm gì?**
Bốn việc: (1) loại trừ hạ tầng bằng RED/USE — latency, error, saturation có bình
thường không; (2) thu thập bằng chứng có metric + timestamp trong cửa sổ drift;
(3) bàn giao ML team kèm ngữ cảnh deploy gần nhất; (4) chuẩn bị rollback về
version trong registry nếu ML team yêu cầu. Không tự thay model, không tự chỉnh
ngưỡng drift.

**9. Khi nào DevOps tự retrain model?**
**Không bao giờ.** Retrain là quyết định của ML Engineer, cần dataset, eval và
Approval Gate. DevOps tự retrain sẽ tạo ra model không ai duyệt, không truy được
nguồn gốc, và phá vỡ chuỗi trách nhiệm.

**10. Ownership boundary table - stage nào DevOps own PRIMARY?**
Bốn stage: Registry (hạ tầng), Deploy/rollout, Serving hạ tầng, Monitoring hạ
tầng RED/USE — cộng thực thi Rollback. Mọi stage liên quan tới dữ liệu, chất
lượng model và quyết định retrain đều do ML Engineer own.
