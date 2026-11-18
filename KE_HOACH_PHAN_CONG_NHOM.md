# KẾ HOẠCH PHÂN CÔNG NHÓM
**Đề tài:** Khảo sát ảnh hưởng của số lượng Client đồng thời đến hiệu năng TCP Server  
**Ngôn ngữ thực hiện:** Python 3 (Console App – Echo Benchmark)  
**Quy mô nhóm:** 6 thành viên  
**Thời lượng:** 4 tuần | **Độ dài báo cáo:** 4–6 trang nội dung chính (không tính bìa, tài liệu tham khảo, phụ lục)

---

## 1. BẢNG PHÂN CÔNG VAI TRÒ & MODULE CHI TIẾT 

| STT | Thành viên | Vai trò chính | File / Thư mục phụ trách (`project-root/`) | Công việc Kỹ thuật (Python) vừa sức, rõ ràng | Phần Báo cáo PDF (4–6 trang) & Hồ sơ nộp (`docs/`) |
| :--: | :--- | :--- | :--- | :--- | :--- |
| **1** | **Nguyễn Thái Lộc**<br>*(Nhóm trưởng)* | **Thiết kế Protocol & Quản lý chung** | - `src/server/protocol.py` *(dùng chung)*<br>- `README.md` | - Viết hàm đóng gói & tách gói TCP (`send_msg`, `recv_msg`) dùng Header 4-byte độ dài + JSON/bytes (`requestId`, `payload` 1KB).<br>- Đảm bảo đọc vòng lặp `while` đến khi đủ byte (**không giả định 1 lần `recv()` đủ gói**) và chặn gói vượt quá giới hạn kích thước.<br>- Viết `README.md` hướng dẫn chạy. | - **Mục 1:** Mục tiêu, Câu hỏi research & Phạm vi (~0.5 trang).<br>- **Mục 3.1:** Thiết kế Protocol & Cơ chế phân tách message Framing (~0.5 trang). |
| **2** | **Nguyễn Tuấn Khang** | **Lập trình TCP Server** | - `src/server/server.py` | - Viết Console App TCP Server (dùng mô hình `threading` hoặc `ThreadPoolExecutor` trong Python).<br>- Nhận request từ nhiều Client, trả về Echo response giữ nguyên `requestId` và `payload`.<br>- Bắt ngoại lệ `socket.timeout`, Client đóng kết nối đột ngột, dữ liệu lỗi để **Server không bị sập**.<br>- Ghi log mức sử dụng **% CPU** của process Server (dùng thư viện `psutil`). | - **Mục 2:** Cơ sở lý thuyết TCP & Mô tả rõ mô hình Server đã chọn (~0.75 trang).<br>- **Mục 3.2:** Kiến trúc TCP Server & Cơ chế xử lý lỗi/timeout (~0.5 trang). |
| **3** | **Trần Quốc Bảo** | **Lập trình Load Generator** | - `src/load-generator/load_gen.py` | - Viết Console App tạo tải chạy ở **process riêng biệt**.<br>- Cho phép truyền cấu hình: `IP`, `port`, `num_clients` (`1`, `10`, `50`), `warmup=5s`, `duration=20s`.<br>- Mỗi Client mở 1 socket riêng, gửi gói 1KB, kiểm tra khớp `requestId` & `payload` trả về, đo thời gian gửi/nhận (RTT) và xuất file dữ liệu thô ra `experiments/raw-data/`. | - **Mục 3.3:** Thiết kế chương trình tạo tải Load Generator (~0.5 trang).<br>- **Mục 4.1:** Phương pháp thực nghiệm, cấu hình máy, môi trường chạy & cách đo (~0.5 trang). |
| **4** | **Nguyễn Văn Việt** | **Kiểm thử (Test) & Chạy Thực nghiệm** | - `src/load-generator/test_cases.py`<br>- `experiments/configs/`<br>- `experiments/raw-data/` | - **Viết script kiểm thử 5 kịch bản (Mục 4 đề bài):** (1) 1 & nhiều Client, (2) đúng `requestId`/payload, (3) Client ngắt kết nối bất thường, (4) dữ liệu không hợp lệ/payload vượt giới hạn, (5) Server vẫn hoạt động sau khi 1 Client lỗi.<br>- Tạo 3 file config (`1`, `10`, `50` Clients) và bấm máy chạy thực nghiệm đủ **3 mức × 3 lần lặp = 9 lần chạy**, thu thập CSV/JSON vào `experiments/raw-data/`. | - **Mục 4.2:** Kết quả kiểm thử chức năng & kiểm thử chịu lỗi của Server (~0.75 trang). |
| **5** | **Lê Tiến Đạt** | **Kiểm chứng Số liệu & Vẽ Biểu đồ** | - `experiments/analysis/verify_and_stats.py`<br>- `experiments/figures/plot_charts.py` | - Viết script đọc CSV/JSON từ `experiments/raw-data/` để **kiểm chứng lại ít nhất 3 trường hợp** (số request thành công, throughput, error rate) và tính đủ **5 chỉ số**: `avg latency`, `p95 latency`, `throughput`, `error rate`, `CPU` (tính trung bình & độ lệch giữa 3 lần chạy).<br>- Viết script vẽ **2–3 biểu đồ** (Latency, Throughput, CPU theo số Client) lưu vào `experiments/figures/`. | - **Mục 5:** Bảng kết quả thực nghiệm, biểu đồ và nhận xét độ dao động giữa 3 lần chạy (~1 trang). |
| **6** | **Trần Đức Anh** | **Phân tích, Tổng hợp Báo cáo & Slide/Video** | - `docs/report.pdf`<br>- `docs/slides/` | - Tổng hợp nội dung từ các thành viên, biên tập thành file báo cáo hoàn chỉnh **4–6 trang PDF**.<br>- Soạn **Slide thuyết trình (hoặc kịch bản Video ngắn)** theo yêu cầu Mục 5.5 của đề.<br>- Kiểm tra lại việc chạy thử theo `README.md` trước khi nộp. | - **Mục 6:** Phân tích xu hướng, Giới hạn thực nghiệm & Kết luận (~1 trang).<br>- **Mục 7:** Tài liệu tham khảo ($\ge 3$ nguồn), Khai báo AI & Bảng đóng góp thành viên. |

---

## 2. LỘ TRÌNH 4 TUẦN 

### Tuần 1: Chốt câu hỏi, phạm vi, protocol, cách đo và dựng Server/Load Generator tối thiểu
* **Nguyễn Thái Lộc:** Chốt định dạng message 1KB, viết xong `protocol.py` (hàm gửi/nhận đủ byte, chặn gói quá cỡ) và viết nháp Mục 1, Mục 3.1.
* **Nguyễn Tuấn Khang:** Viết `server.py` bản tối thiểu nhận kết nối và echo lại message thông qua `protocol.py`. Viết nháp Mục 2.
* **Trần Quốc Bảo:** Viết `load_gen.py` bản tối thiểu kết nối 1 Client gửi/nhận thành công với Server.
* **Nguyễn Văn Việt:** Tạo 3 file cấu hình JSON (`client_1.json`, `client_10.json`, `client_50.json`) trong `experiments/configs/` và thống nhất các cột của file CSV kết quả.
* **Lê Tiến Đạt & Trần Đức Anh:** Chuẩn bị khung script đọc CSV (`verify_and_stats.py`, `plot_charts.py`), dựng sườn file Word/LaTeX báo cáo trong `docs/` và tìm sẵn $\ge 3$ nguồn tài liệu tham khảo (slide môn học + sách TCP Python).

### Tuần 2: Hoàn thành prototype, kiểm thử kết nối, response, timeout và disconnect
* **Nguyễn Tuấn Khang:** Hoàn thiện xử lý đa luồng cho `server.py`, thêm xử lý timeout, disconnect bất thường, dữ liệu lỗi và tích hợp đo `% CPU` bằng `psutil`. Hoàn thành Mục 3.2.
* **Trần Quốc Bảo:** Hoàn thiện `load_gen.py` chạy đa luồng nhiều Client (1, 10, 50), tách pha **Warm-up 5s** (bỏ qua khi tính điểm) và **Measure 20s** (ghi log CSV). Hoàn thành Mục 3.3 & 4.1.
* **Nguyễn Văn Việt:** Viết và chạy `test_cases.py` kiểm tra đủ 5 gạch đầu dòng trong **Mục 4 (Kiểm thử)** của đề bài. Viết Mục 4.2.
* **Nguyễn Thái Lộc:** Kiểm tra ghép code giữa Server – Protocol – Load Generator, đảm bảo chạy mượt trên máy local.

### Tuần 3: Chạy các mức Client, lưu dữ liệu thô, kiểm tra kết quả và tạo biểu đồ
* **Nguyễn Văn Việt (chính) & Trần Quốc Bảo (hỗ trợ):** Chạy chính thức 3 kịch bản (`1`, `10`, `50` Clients), mỗi kịch bản lặp **3 lần** trên cùng 1 máy với cùng điều kiện. Lưu toàn bộ file CSV thô vào `experiments/raw-data/`.
* **Lê Tiến Đạt:** Chạy script `verify_and_stats.py` kiểm chứng lại số request thành công, throughput, error rate từ dữ liệu thô; tính trung bình và độ dao động của 5 chỉ số (`avg latency`, `p95 latency`, `throughput`, `error rate`, `CPU`). Chạy `plot_charts.py` xuất biểu đồ vào `experiments/figures/` và viết Mục 5.
* **Trần Đức Anh:** Cùng nhóm đọc số liệu và biểu đồ để viết phần Phân tích, Giới hạn thực nghiệm và Kết luận (Mục 6).

### Tuần 4: Phân tích, hoàn thiện báo cáo / README / Slide hoặc Video và chuẩn bị Demo
* **Trần Đức Anh:** Ghép toàn bộ các mục thành file `docs/report.pdf` (căn chỉnh gọn trong **4–6 trang nội dung chính**), bổ sung trích dẫn tài liệu tham khảo, khai báo sử dụng AI, bảng đóng góp và làm Slide thuyết trình / Video demo ngắn.
* **Nguyễn Thái Lộc:** Hoàn thiện `README.md` hướng dẫn từng lệnh chạy Server, Load Generator, Test và Script phân tích để giảng viên tái tạo thí nghiệm dễ dàng.
* **Cả nhóm (6 thành viên):** Chạy demo thử và nắm vững toàn bộ luồng hoạt động của code, số liệu và kết luận (đúng yêu cầu cuối cùng ở Mục 8 đề bài).

---

## 3. BẢNG ĐÓNG GÓP THÀNH VIÊN 

| STT | Họ và Tên | Vai trò | Công việc thực hiện cụ thể | Tỷ lệ đóng góp |
| :--: | :--- | :--- | :--- | :--: |
| 1 | **Nguyễn Thái Lộc** *(Nhóm trưởng)* | Protocol & Quản lý chung | Thiết kế protocol, code module phân tách message (`protocol.py`), viết `README.md`, viết Mục 1 & Mục 3.1 báo cáo. | **100%** |
| 2 | **Nguyễn Tuấn Khang** | TCP Server | Lập trình TCP Server đa Client (`server.py`), xử lý disconnect/timeout/dữ liệu lỗi, đo CPU Server, viết Mục 2 & Mục 3.2. | **100%** |
| 3 | **Trần Quốc Bảo** | Load Generator | Lập trình công cụ tạo tải (`load_gen.py`), quản lý pha warm-up 5s / đo 20s, kiểm tra `requestId` & payload, viết Mục 3.3 & 4.1. | **100%** |
| 4 | **Nguyễn Văn Việt** | Kiểm thử & Thực nghiệm | Viết script kiểm thử 5 kịch bản lỗi (`test_cases.py`), tạo file cấu hình, chạy thực nghiệm 1–10–50 Clients (×3 lần), viết Mục 4.2. | **100%** |
| 5 | **Lê Tiến Đạt** | Phân tích & Biểu đồ | Viết script kiểm chứng dữ liệu thô (`verify_and_stats.py`) và vẽ biểu đồ (`plot_charts.py`), tính 5 chỉ số & độ dao động, viết Mục 5. | **100%** |
| 6 | **Trần Đức Anh** | Báo cáo & Slide/Demo | Viết Mục 6 (Phân tích, Giới hạn, Kết luận), Tài liệu tham khảo, tổng hợp báo cáo PDF (4–6 trang) và chuẩn bị Slide/Video demo. | **100%** |
| **Tổng** | **6 thành viên** | | **Hoàn thành 100% yêu cầu đề bài** | **100%** |

---

## 4. QUY TẮC PHỐI HỢP GIT ĐƠN GIẢN CHO NHÓM
1. **Nhánh làm việc:** Chỉ cần nhánh `main` và mỗi thành viên tạo 1 nhánh theo tên mình (ví dụ: `loc`, `khang`, `bao`, `viet`, `dat`, `ducanh`) hoặc pull/push sau khi thông báo trong nhóm chat.
2. **Thống nhất môi trường Python:** Chỉ cần dùng thư viện chuẩn của Python (`socket`, `threading`, `json`, `csv`, `time`, `statistics`) và 2 thư viện ngoài rất nhẹ trong `requirements.txt` là `psutil` (đo CPU) và `matplotlib` (vẽ biểu đồ).
3. **Không commit file rác:** File `.gitignore` đã được cấu hình sẵn để chặn `__pycache__/`, `.venv/`, `.vscode/`.
