# Khảo sát ảnh hưởng của số lượng Client đồng thời đến hiệu năng TCP Server

Dự án nghiên cứu thực nghiệm môn Lập trình mạng (Ngôn ngữ thực hiện: Python 3).

## 1. Cấu trúc thư mục (`project-root/`)

```text
project-root/
├── README.md                           # Hướng dẫn cài đặt, chạy và tái tạo thí nghiệm
├── requirements.txt                    # Thư viện Python cần thiết (psutil, matplotlib)
├── .gitignore                          # Bỏ qua các file cache/build không cần thiết
├── src/
│   ├── server/
│   │   ├── protocol.py                 # Đóng gói, phân tách message (Framing) và kiểm tra dữ liệu
│   │   └── server.py                   # TCP Echo Server đa luồng và đo CPU
│   └── load-generator/
│       ├── load_gen.py                 # Chương trình tạo tải đa Client (Warm-up 5s, Đo 20s)
│       └── test_cases.py               # Bộ kiểm thử 5 kịch bản chức năng và xử lý lỗi
├── experiments/
│   ├── configs/                        # File cấu hình cho các mức 1, 10, 50 Clients
│   ├── raw-data/                       # Dữ liệu thô (CSV/JSON) thu được từ các lần chạy
│   ├── analysis/
│   │   └── verify_and_stats.py         # Script kiểm chứng dữ liệu thô và tính 5 chỉ số
│   └── figures/
│       └── plot_charts.py              # Script vẽ biểu đồ kết quả thực nghiệm
└── docs/
    └── muc_1_va_3_1_nguyen_thai_loc.md # Bản thảo báo cáo Mục 1 và Mục 3.1
```

## 2. Cài đặt môi trường

Yêu cầu Python 3.9 trở lên. Cài đặt các thư viện phụ trợ:

```bash
py -m pip install -r requirements.txt
```

## 3. Hướng dẫn chạy và tái tạo thí nghiệm

### Bước 0: Kiểm thử đơn vị module giao thức (`protocol.py`)
Kiểm tra cơ chế đóng gói 1KB, đọc phân mảnh (fragmentation), tách gói gộp (coalescing), chặn gói vượt giới hạn và phát hiện ngắt kết nối bất thường:

```bash
py src/server/protocol.py
```

### Bước 1: Khởi chạy TCP Server (Terminal 1)
```bash
py src/server/server.py --host 127.0.0.1 --port 9000
```

### Bước 2: Chạy bộ kiểm thử chức năng và xử lý lỗi (Terminal 2)
```bash
py src/load-generator/test_cases.py --host 127.0.0.1 --port 9000
```

### Bước 3: Chạy chương trình tạo tải theo cấu hình (Terminal 2)
Mỗi cấu hình chạy lặp lại 3 lần (`--run 1`, `--run 2`, `--run 3`):

```bash
py src/load-generator/load_gen.py --config experiments/configs/config_1_client.json --run 1
py src/load-generator/load_gen.py --config experiments/configs/config_10_clients.json --run 1
py src/load-generator/load_gen.py --config experiments/configs/config_50_clients.json --run 1
```

### Bước 4: Kiểm chứng dữ liệu thô và vẽ biểu đồ
```bash
py experiments/analysis/verify_and_stats.py
py experiments/figures/plot_charts.py
```
