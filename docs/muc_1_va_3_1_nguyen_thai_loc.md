# NỘI DUNG BÁO CÁO TUẦN 1 - NGUYỄN THÁI LỘC
*(Bản thảo dùng để ghép trực tiếp vào Mục 1 và Mục 3.1 của Báo cáo PDF cuối kỳ)*

---

## 1. Mục tiêu, Câu hỏi nghiên cứu và Phạm vi

### 1.1. Mục tiêu và Câu hỏi nghiên cứu
Mục tiêu của bài nghiên cứu là xây dựng một nguyên mẫu (prototype) TCP Server có khả năng phục vụ đồng thời nhiều Client, qua đó thực hiện đo lường thực nghiệm để đánh giá tác động của số lượng kết nối đồng thời đến hiệu năng hoạt động của hệ thống.

Bài nghiên cứu tập trung giải quyết câu hỏi cốt lõi sau:
> **Khi số lượng Client đồng thời tăng, độ trễ (latency), thông lượng (throughput) và mức sử dụng CPU của TCP Server thay đổi như thế nào?**

### 1.2. Phạm vi thực hiện
Để đảm bảo tính nhất quán và tập trung vào biến số duy nhất là **số lượng Client đồng thời**, phạm vi của hệ thống được xác định cụ thể như sau:

1. **Dịch vụ thử nghiệm (Echo Benchmark trên TCP):**
   - Mỗi Client logic thiết lập một kết nối TCP riêng biệt đến Server.
   - Client gửi các bản tin yêu cầu (request) chứa định danh `requestId` và dữ liệu `payload` có kích thước cố định `1 KB` (`1024 bytes`).
   - Server nhận bản tin, kiểm tra tính hợp lệ và phản hồi (response) lại đúng `requestId` cùng `payload` tương ứng.
   - Client đối chiếu dữ liệu phản hồi và ghi nhận thời gian gửi/nhận để tính độ trễ khứ hồi (Round-Trip Time - RTT).

2. **Mô hình kiến trúc và triển khai:**
   - Hệ thống gồm hai chương trình Console độc lập chạy trên hai tiến trình (process) riêng biệt: **TCP Server** (`src/server/server.py`) và **Load Generator** (`src/load-generator/load_gen.py`).
   - Nhóm lựa chọn một mô hình xử lý đồng thời duy nhất cho TCP Server là **Thread-per-Client** (mỗi kết nối Client được phục vụ bởi một luồng thực thi riêng thông qua thư viện `threading` của Python) để quan sát rõ chi phí quản lý luồng và chuyển ngữ cảnh khi số lượng kết nối tăng.

3. **Các thông số cố định và giới hạn phạm vi:**
   - Kích thước payload cố định: `1 KB` (`1024 bytes`).
   - Các mức tải khảo sát: `1`, `10` và `50` Clients đồng thời.
   - Chu kỳ mỗi lần đo: `5 giây` làm nóng (warm-up, không tính vào kết quả thống kê) và `20 giây` đo chính thức; mỗi kịch bản lặp lại `3 lần` trong cùng điều kiện cấu hình.
   - Các chỉ số thu thập bắt buộc: độ trễ trung bình (`avg latency`), độ trễ phân vị thứ 95 (`p95 latency`), thông lượng (`throughput`), tỷ lệ lỗi (`error rate`) và mức sử dụng `CPU` của tiến trình Server.
   - Nghiên cứu không mở rộng sang việc so sánh nhiều mô hình Server khác nhau, không thay đổi nhiều kích thước payload và không xây dựng giao diện đồ họa (GUI).

---

## 3. Kiến trúc Hệ thống và Thiết kế Giao thức

### 3.1. Thiết kế Giao thức Ứng dụng và Cơ chế Phân tách Bản tin (Message Framing)

#### a) Vấn đề phân mảnh và dính gói trên dòng byte TCP (TCP Byte Stream)
TCP là giao thức hướng dòng byte (byte-stream protocol), không bảo toàn ranh giới bản tin của tầng ứng dụng. Khi ứng dụng gọi hàm gửi `send()` và hàm nhận `recv()`, hệ điều hành và ngăn xếp mạng có thể xảy ra hai hiện tượng:
- **Phân mảnh (Fragmentation / Partial Read):** Một bản tin có kích thước lớn (ví dụ trên `1 KB`) có thể bị chia nhỏ khiến một lần gọi `recv()` chỉ trả về một phần của bản tin.
- **Gộp gói (Coalescing / Sticky Packets):** Nhiều bản tin nhỏ gửi liên tiếp có thể được gom chung trong bộ đệm nhận của hệ điều hành và trả về cùng lúc trong một lần gọi `recv()`.

Do đó, giao thức tầng ứng dụng bắt buộc phải có cơ chế phân tách bản tin (Message Framing) rõ ràng và tuyệt đối không được giả định một lần gọi `recv()` luôn trả về đúng một bản tin hoàn chỉnh.

#### b) Cấu trúc khung truyền (Wire Format)
Hệ thống sử dụng phương pháp **Length-Prefixed Framing** (tiền tố độ dài cố định 4 bytes) kết hợp với phần thân (Body) mã hóa dạng JSON UTF-8, được cài đặt tại module `src/server/protocol.py`:

```text
+-------------------------------+---------------------------------------------------+
|      Length Header (4B)       |                 Message Body (N Bytes)            |
|  Unsigned Int, Big-Endian !I  |   JSON UTF-8: {"requestId": <int>, "payload": ...}|
+-------------------------------+---------------------------------------------------+
|<--------- 4 bytes ----------->|<------------------- msg_length ------------------>|
```

Trong đó:
- **Length Header (`4 bytes`):** Số nguyên không dấu 32-bit theo thứ tự byte mạng (Big-Endian, định dạng `struct` là `"!I"`), biểu diễn chính xác số byte `msg_length` của phần `Message Body` theo sau.
- **Message Body (`msg_length bytes`):** Chuỗi JSON mã hóa UTF-8 gồm hai trường bắt buộc:
  - `requestId` (`int`, $\ge 0$): Số thứ tự định danh duy nhất của request trong phạm vi một Client, dùng để đối chiếu cặp request/response.
  - `payload` (`str`): Chuỗi dữ liệu ASCII có kích thước cố định `1024 bytes` (`1 KB`).
- **Giới hạn an toàn:** Để bảo vệ Server trước dữ liệu hỏng hoặc tấn công làm tràn bộ nhớ, giao thức quy định hằng số `MAX_PAYLOAD_SIZE = 4096` bytes (`4 KB`) và `MAX_MESSAGE_SIZE = 8192` bytes (`8 KB`). Mọi gói tin có `msg_length <= 0` hoặc `msg_length > MAX_MESSAGE_SIZE` đều bị từ chối ngay sau bước đọc Header.

#### c) Thuật toán nhận đủ byte (`recv_exact`) và kiểm tra tính toàn vẹn
Để giải quyết triệt để bài toán phân mảnh và dính gói, hàm `recv_exact(sock, num_bytes)` sử dụng vòng lặp tích lũy vào bộ đệm `bytearray` cho đến khi nhận đủ số byte yêu cầu:

```python
def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(num_bytes - len(buf))
        if not chunk:
            if len(buf) == 0:
                return b""
            raise ConnectionResetError(
                f"Kết nối đóng bất thường khi đang nhận dữ liệu ({len(buf)}/{num_bytes} bytes)."
            )
        buf.extend(chunk)
    return bytes(buf)
```

Quy trình nhận một bản tin hoàn chỉnh trong hàm `recv_message(sock)` diễn ra qua 4 bước chặt chẽ:
1. **Bước 1 (Đọc Header):** Gọi `recv_exact(sock, 4)` để lấy đúng 4 bytes đầu tiên. Nếu kết quả trả về rỗng (`b""`), kết nối đã được đóng hợp lệ (EOF).
2. **Bước 2 (Kiểm tra giới hạn độ dài):** Giải nén `msg_length` bằng `struct.unpack("!I", header_bytes)`. Nếu `msg_length <= 0` hoặc `msg_length > MAX_MESSAGE_SIZE`, hàm lập tức ném ngoại lệ `ProtocolError` mà không cấp phát bộ nhớ lớn.
3. **Bước 3 (Đọc phần thân Body):** Gọi `recv_exact(sock, msg_length)` để đọc chính xác số byte của bản tin hiện tại (không đọc lấn sang bản tin kế tiếp trong bộ đệm TCP). Nếu kết nối đứt giữa chừng, hàm ném `ConnectionResetError`.
4. **Bước 4 (Giải mã và xác thực):** Giải mã JSON UTF-8, kiểm tra sự tồn tại và kiểu dữ liệu của `requestId` cùng kích thước `payload`. Ở phía Client, hàm `verify_response()` tiếp tục đối chiếu `response["requestId"] == expected_request_id` và `response["payload"] == expected_payload` trước khi ghi nhận request thành công.
