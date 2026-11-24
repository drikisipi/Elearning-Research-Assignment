# 4.2. Kết quả kiểm thử chức năng và kiểm thử chịu lỗi của Server

Nhóm xây dựng bộ kiểm thử tự động `src/load-generator/test_cases.py` gồm 5 kịch bản theo yêu cầu kiểm thử của đề. Bộ kiểm thử dùng lại các hàm đóng gói và tách message của `protocol.py` (Mục 3.1) để mở kết nối TCP thật tới Server, gửi gói tin gồm `requestId` và payload 1KB rồi đối chiếu response với dữ liệu đã gửi. Server và bộ kiểm thử chạy ở hai tiến trình riêng trên cùng một máy Windows, Python 3, địa chỉ `127.0.0.1:9000`, thời gian chờ socket 5 giây.

| STT | Kịch bản | Cách kiểm tra | Kết quả |
|:--:|:--|:--|:--:|
| 1 | Một Client, khớp `requestId` và payload | 1 Client gửi lần lượt 5 request (`requestId` 1 đến 5); mỗi response phải có `requestId` và payload giống hệt request | Đạt |
| 2 | Nhiều Client đồng thời | 10 Client kết nối, chờ nhau ở một rào đồng bộ rồi cùng gửi, mỗi Client 10 request với `requestId` riêng; mọi response phải khớp | Đạt |
| 3 | Client đóng kết nối bất thường | Client chỉ gửi 15 byte đầu của một gói (chưa đủ gói) rồi đóng socket | Đạt |
| 4 | Dữ liệu không hợp lệ, gói vượt giới hạn | Gửi lần lượt: (a) nội dung không phải JSON, (b) JSON thiếu trường `payload`, (c) header khai báo độ dài lớn hơn giới hạn tối đa 512 byte. Với mỗi trường hợp, Server phải đóng kết nối | Đạt |
| 5 | Server còn hoạt động sau khi có Client lỗi | Mở kết nối mới, gửi 3 request (`requestId` 501 đến 503); response phải khớp | Đạt |

*Bảng 4.1. Kết quả 5 kịch bản kiểm thử: 5/5 đạt.*



*Hình 4.1. Kết quả chạy `test_cases.py`.!*





**Nhận xét.**
- Với 1 Client và 10 Client đồng thời, Server trả về đúng `requestId` và payload, không lẫn response giữa các Client. Kịch bản 2 cho các Client bắt đầu cùng lúc nên kiểm tra được việc xử lý đồng thời thật sự.
- Với dữ liệu sai định dạng, thiếu trường và gói vượt giới hạn, Server đóng kết nối vi phạm thay vì xử lý tiếp hoặc chờ đủ dữ liệu. Việc chặn gói vượt giới hạn ngay từ header giúp Server không phải cấp phát bộ nhớ theo độ dài do Client tự khai báo.
- Kịch bản 5 chạy sau các kịch bản lỗi (3 và 4) và Server vẫn phục vụ đúng, nên lỗi của một Client không làm sập hay treo Server.
- Giới hạn: kịch bản 3 không tự kiểm tra Server, mà dựa vào kịch bản 5 để xác nhận Server còn hoạt động. Bộ kiểm thử chỉ ở quy mô nhỏ (tối đa 10 Client) trên một máy, không thay thế thực nghiệm hiệu năng ở Mục 5.
