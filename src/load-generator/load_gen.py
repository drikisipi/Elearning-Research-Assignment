"""
Ứng dụng console tạo tải (load generator) chạy ở tiến trình riêng biệt.
Tạo nhiều kết nối TCP đồng thời đến server, gửi bản tin 1 KB qua module protocol,
tách pha làm nóng (warm-up) và pha đo chính thức, rồi xuất dữ liệu thô ra file CSV.
"""

import argparse
import csv
import json
import math
import socket
import statistics
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import protocol  # noqa: E402

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_NUM_CLIENTS = 1
DEFAULT_WARMUP_SECONDS = 5.0
DEFAULT_DURATION_SECONDS = 20.0
DEFAULT_PAYLOAD_SIZE = protocol.DEFAULT_PAYLOAD_SIZE
DEFAULT_TIMEOUT_SECONDS = 5.0
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[2] / "experiments" / "raw-data"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Phân tích các tham số dòng lệnh cho chương trình tạo tải."""
    parser = argparse.ArgumentParser(
        description="Chương trình tạo tải TCP echo benchmark cho nhiều client đồng thời."
    )
    parser.add_argument(
        "--config",
        default=None,
        help="Đường dẫn file cấu hình JSON cho kịch bản chạy.",
    )
    parser.add_argument(
        "--run",
        type=int,
        default=1,
        help="Số thứ tự lần chạy lặp lại (mặc định: 1).",
    )
    parser.add_argument(
        "--host",
        default=None,
        help=f"Địa chỉ IP của TCP server (mặc định: {DEFAULT_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help=f"Cổng TCP của server (mặc định: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--clients",
        "--num-clients",
        dest="num_clients",
        type=int,
        default=None,
        help=f"Số lượng client đồng thời (mặc định: {DEFAULT_NUM_CLIENTS}).",
    )
    parser.add_argument(
        "--warmup",
        type=float,
        default=None,
        help=f"Thời gian làm nóng tính bằng giây (mặc định: {DEFAULT_WARMUP_SECONDS}).",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=None,
        help=f"Thời gian đo chính thức tính bằng giây (mặc định: {DEFAULT_DURATION_SECONDS}).",
    )
    parser.add_argument(
        "--payload-size",
        type=int,
        default=None,
        help=f"Kích thước payload tính bằng byte (mặc định: {DEFAULT_PAYLOAD_SIZE}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=None,
        help=f"Thời gian chờ socket của client tính bằng giây (mặc định: {DEFAULT_TIMEOUT_SECONDS}).",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Thư mục lưu file CSV dữ liệu thô (mặc định: {DEFAULT_OUTPUT_DIR}).",
    )
    return parser.parse_args(argv)


def load_config(args: argparse.Namespace) -> Dict[str, Any]:
    """Đọc file cấu hình JSON (nếu có) và gộp với các tham số dòng lệnh."""
    config_data: Dict[str, Any] = {}
    if args.config:
        with open(args.config, "r", encoding="utf-8") as f:
            raw = json.load(f)
        if not isinstance(raw, dict):
            raise ValueError("File cấu hình JSON phải là một đối tượng (object).")
        config_data = raw

    def pick(cli_val: Any, keys: Tuple[str, ...], default: Any) -> Any:
        if cli_val is not None:
            return cli_val
        for key in keys:
            if key in config_data and config_data[key] is not None:
                return config_data[key]
        return default

    host = str(pick(args.host, ("host", "ip"), DEFAULT_HOST))
    port = int(pick(args.port, ("port",), DEFAULT_PORT))
    num_clients = int(
        pick(args.num_clients, ("num_clients", "client_count", "clients"), DEFAULT_NUM_CLIENTS)
    )
    warmup = float(pick(args.warmup, ("warmup_seconds", "warmup"), DEFAULT_WARMUP_SECONDS))
    duration = float(pick(args.duration, ("duration_seconds", "duration"), DEFAULT_DURATION_SECONDS))
    payload_size = int(pick(args.payload_size, ("payload_size",), DEFAULT_PAYLOAD_SIZE))
    timeout = float(pick(args.timeout, ("timeout_seconds", "timeout"), DEFAULT_TIMEOUT_SECONDS))
    output_dir = Path(str(pick(args.output_dir, ("output_dir",), DEFAULT_OUTPUT_DIR)))

    if num_clients <= 0:
        raise ValueError("Số lượng client phải lớn hơn 0.")
    if warmup < 0 or duration <= 0:
        raise ValueError("Thời gian warm-up phải >= 0 và duration phải > 0.")

    return {
        "host": host,
        "port": port,
        "num_clients": num_clients,
        "warmup": warmup,
        "duration": duration,
        "payload_size": payload_size,
        "timeout": timeout,
        "output_dir": output_dir,
        "run": args.run,
    }


def _open_client_socket(host: str, port: int, timeout: float) -> socket.socket:
    """Mở một kết nối TCP mới với thời gian chờ đã cấu hình."""
    sock = socket.create_connection((host, port), timeout=timeout)
    sock.settimeout(timeout)
    return sock


def run_client_worker(
    client_id: int,
    cfg: Dict[str, Any],
    payload: str,
    start_barrier: threading.Barrier,
    results_out: List[List[Any]],
    results_lock: threading.Lock,
) -> None:
    """Thực thi vòng lặp gửi yêu cầu và kiểm tra phản hồi cho một client logic."""
    host = cfg["host"]
    port = cfg["port"]
    timeout = cfg["timeout"]
    warmup = cfg["warmup"]
    duration = cfg["duration"]
    num_clients = cfg["num_clients"]
    run_label = f"run_{cfg['run']}"

    local_rows: List[List[Any]] = []
    request_id = client_id * 1_000_000
    sock: Optional[socket.socket] = None

    try:
        sock = _open_client_socket(host, port, timeout)
    except OSError as exc:
        print(f"[WARN] Client {client_id} không thể kết nối tới {host}:{port}: {exc}", flush=True)
        try:
            start_barrier.abort()
        except threading.BrokenBarrierError:
            pass
        return

    try:
        start_barrier.wait(timeout=max(timeout, 10.0))
        t_start = time.monotonic()
        warmup_end = t_start + warmup
        measure_end = warmup_end + duration

        while True:
            now_mono = time.monotonic()
            if now_mono >= measure_end:
                break

            in_measure = now_mono >= warmup_end
            request_id += 1
            req_timestamp = f"{time.time():.3f}"
            t0 = time.perf_counter()

            try:
                if sock is None:
                    sock = _open_client_socket(host, port, timeout)
                protocol.send_message(sock, request_id, payload)
                response = protocol.recv_message(sock)
                protocol.verify_response(response, request_id, payload)
                latency_ms = (time.perf_counter() - t0) * 1000.0

                if in_measure:
                    local_rows.append(
                        [
                            req_timestamp,
                            run_label,
                            num_clients,
                            client_id,
                            request_id,
                            f"{latency_ms:.3f}",
                            1,
                            f"{duration:g}",
                        ]
                    )
            except (protocol.ProtocolError, OSError):
                if in_measure:
                    local_rows.append(
                        [
                            req_timestamp,
                            run_label,
                            num_clients,
                            client_id,
                            request_id,
                            "",
                            0,
                            f"{duration:g}",
                        ]
                    )
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                    sock = None
    except threading.BrokenBarrierError:
        print(f"[WARN] Client {client_id} dừng do đồng bộ kết nối thất bại.", flush=True)
    finally:
        if sock is not None:
            try:
                sock.close()
            except OSError:
                pass

    with results_lock:
        results_out.extend(local_rows)


def calculate_p95(values: List[float]) -> Optional[float]:
    """Tính phân vị thứ 95 của danh sách độ trễ."""
    if not values:
        return None
    sorted_vals = sorted(values)
    idx = max(0, math.ceil(0.95 * len(sorted_vals)) - 1)
    return sorted_vals[idx]


def save_csv(output_path: Path, rows: List[List[Any]]) -> None:
    """Lưu danh sách bản ghi đo được ra file CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    header = [
        "timestamp",
        "run_id",
        "client_count",
        "client_id",
        "request_id",
        "latency_ms",
        "success",
        "duration_seconds",
    ]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)


def run_load_test(cfg: Dict[str, Any]) -> Path:
    """Khởi chạy toàn bộ kịch bản tạo tải và trả về đường dẫn file CSV kết quả."""
    num_clients = cfg["num_clients"]
    payload = protocol.generate_payload(cfg["payload_size"])
    start_barrier = threading.Barrier(num_clients)
    results: List[List[Any]] = []
    results_lock = threading.Lock()

    print(
        f"[INFO] Bắt đầu tạo tải: target={cfg['host']}:{cfg['port']}, "
        f"clients={num_clients}, warmup={cfg['warmup']}s, duration={cfg['duration']}s, "
        f"payload={cfg['payload_size']}B, run={cfg['run']}",
        flush=True,
    )

    threads = [
        threading.Thread(
            target=run_client_worker,
            args=(idx, cfg, payload, start_barrier, results, results_lock),
        )
        for idx in range(num_clients)
    ]

    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    output_name = f"load_{num_clients}_clients_run{cfg['run']}.csv"
    output_path = Path(cfg["output_dir"]) / output_name
    save_csv(output_path, results)

    latencies = [float(row[5]) for row in results if row[6] == 1 and row[5] != ""]
    total_requests = len(results)
    success_count = sum(1 for row in results if row[6] == 1)
    error_count = total_requests - success_count
    avg_lat = statistics.mean(latencies) if latencies else 0.0
    p95_lat = calculate_p95(latencies) or 0.0
    throughput = success_count / cfg["duration"] if cfg["duration"] > 0 else 0.0
    error_rate = (error_count / total_requests * 100.0) if total_requests > 0 else 0.0

    print(
        f"[DONE] Đã lưu {total_requests} dòng vào {output_path} | "
        f"ok={success_count}, err={error_count}, avg={avg_lat:.3f}ms, "
        f"p95={p95_lat:.3f}ms, throughput={throughput:.2f} rps, error_rate={error_rate:.2f}%",
        flush=True,
    )
    return output_path


def main() -> None:
    """Điểm vào chính của chương trình."""
    args = parse_args()
    cfg = load_config(args)
    run_load_test(cfg)


if __name__ == "__main__":
    main()
