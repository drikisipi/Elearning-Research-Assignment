"""
Ứng dụng console TCP echo server đa luồng theo mô hình Thread-per-Client.
Nhận kết nối từ nhiều client đồng thời, xử lý bản tin qua module protocol,
bắt các lỗi kết nối hoặc timeout và ghi nhận mức sử dụng CPU của tiến trình server.
"""

import argparse
import csv
import os
import socket
import threading
import time
from datetime import datetime, timezone
from typing import Optional, Sequence, Tuple

import psutil

try:
    import protocol
except ImportError:
    from src.server import protocol

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_BACKLOG = 128
DEFAULT_CLIENT_TIMEOUT = 30.0
DEFAULT_CPU_INTERVAL = 1.0
ACCEPT_TIMEOUT = 1.0


class ServerState:
    """Lưu trữ trạng thái đồng thời của server một cách an toàn giữa các luồng."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.active_clients = 0

    def increment_clients(self) -> int:
        """Tăng số client đang kết nối và trả về giá trị mới."""
        with self._lock:
            self.active_clients += 1
            return self.active_clients

    def decrement_clients(self) -> int:
        """Giảm số client đang kết nối và trả về giá trị mới."""
        with self._lock:
            if self.active_clients > 0:
                self.active_clients -= 1
            return self.active_clients

    def get_active_clients(self) -> int:
        """Trả về số lượng client đang kết nối hiện tại."""
        with self._lock:
            return self.active_clients


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Phân tích các tham số dòng lệnh cho TCP server."""
    parser = argparse.ArgumentParser(
        description="TCP echo server đa luồng sử dụng giao thức đóng gói 4 byte độ dài."
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Địa chỉ IP lắng nghe kết nối (mặc định: {DEFAULT_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Cổng TCP lắng nghe kết nối (mặc định: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--client-timeout",
        type=float,
        default=DEFAULT_CLIENT_TIMEOUT,
        help=f"Thời gian chờ tối đa trên mỗi kết nối client tính bằng giây (mặc định: {DEFAULT_CLIENT_TIMEOUT}).",
    )
    parser.add_argument(
        "--cpu-interval",
        type=float,
        default=DEFAULT_CPU_INTERVAL,
        help=f"Chu kỳ ghi log mức sử dụng CPU tính bằng giây (mặc định: {DEFAULT_CPU_INTERVAL}).",
    )
    parser.add_argument(
        "--cpu-log",
        default=None,
        help="Đường dẫn file CSV tùy chọn để lưu log mức sử dụng CPU của server.",
    )
    return parser.parse_args(argv)


def handle_client(
    client_sock: socket.socket,
    client_addr: Tuple[str, int],
    state: ServerState,
    stop_event: threading.Event,
    client_timeout: float,
) -> None:
    """Xử lý vòng lặp nhận yêu cầu và phản hồi echo cho một kết nối client."""
    active_count = state.increment_clients()
    print(
        f"[INFO] Kết nối mới từ {client_addr[0]}:{client_addr[1]} "
        f"(đang phục vụ: {active_count})",
        flush=True,
    )

    if client_timeout > 0:
        client_sock.settimeout(client_timeout)

    try:
        while not stop_event.is_set():
            request = protocol.recv_message(client_sock)
            if request is None:
                print(
                    f"[INFO] Client {client_addr[0]}:{client_addr[1]} đã đóng kết nối.",
                    flush=True,
                )
                break

            protocol.send_message(client_sock, request["requestId"], request["payload"])
    except socket.timeout:
        print(
            f"[WARN] Hết thời gian chờ (timeout) từ {client_addr[0]}:{client_addr[1]}.",
            flush=True,
        )
    except protocol.ProtocolError as exc:
        print(
            f"[WARN] Dữ liệu không hợp lệ từ {client_addr[0]}:{client_addr[1]}: {exc}",
            flush=True,
        )
    except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError, OSError) as exc:
        print(
            f"[WARN] Lỗi kết nối với {client_addr[0]}:{client_addr[1]}: {exc}",
            flush=True,
        )
    except Exception as exc:
        print(
            f"[ERROR] Lỗi không mong muốn khi phục vụ {client_addr[0]}:{client_addr[1]}: {exc}",
            flush=True,
        )
    finally:
        try:
            client_sock.close()
        except OSError:
            pass
        state.decrement_clients()


def monitor_cpu(
    state: ServerState,
    stop_event: threading.Event,
    interval: float,
    cpu_log_path: Optional[str],
) -> None:
    """Theo dõi và ghi log mức sử dụng % CPU của tiến trình server định kỳ."""
    if interval <= 0:
        return

    process = psutil.Process(os.getpid())
    process.cpu_percent(interval=None)
    start_time = time.monotonic()

    csv_file = None
    csv_writer = None
    try:
        if cpu_log_path:
            parent_dir = os.path.dirname(os.path.abspath(cpu_log_path))
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)
            csv_file = open(cpu_log_path, "w", newline="", encoding="utf-8")
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["timestamp", "elapsed_sec", "cpu_percent", "active_clients"])
            csv_file.flush()

        while not stop_event.wait(interval):
            cpu_percent = process.cpu_percent(interval=None)
            active_clients = state.get_active_clients()
            elapsed = time.monotonic() - start_time
            timestamp = datetime.now(timezone.utc).isoformat()

            print(
                f"[CPU] cpu={cpu_percent:.1f}% active_clients={active_clients}",
                flush=True,
            )

            if csv_writer is not None and csv_file is not None:
                csv_writer.writerow(
                    [timestamp, f"{elapsed:.3f}", f"{cpu_percent:.2f}", active_clients]
                )
                csv_file.flush()
    finally:
        if csv_file is not None:
            csv_file.close()


def run_server(
    host: str,
    port: int,
    client_timeout: float = DEFAULT_CLIENT_TIMEOUT,
    cpu_interval: float = DEFAULT_CPU_INTERVAL,
    cpu_log_path: Optional[str] = None,
    backlog: int = DEFAULT_BACKLOG,
) -> None:
    """Khởi tạo TCP socket lắng nghe, tạo luồng xử lý cho từng client và theo dõi CPU."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.settimeout(ACCEPT_TIMEOUT)

    state = ServerState()
    stop_event = threading.Event()
    cpu_thread: Optional[threading.Thread] = None

    try:
        server_sock.bind((host, port))
        server_sock.listen(backlog)
        print(
            f"[INFO] TCP server đang lắng nghe tại {host}:{port} "
            f"(client_timeout={client_timeout}s, cpu_interval={cpu_interval}s)",
            flush=True,
        )

        if cpu_interval > 0:
            cpu_thread = threading.Thread(
                target=monitor_cpu,
                args=(state, stop_event, cpu_interval, cpu_log_path),
                daemon=True,
            )
            cpu_thread.start()

        while not stop_event.is_set():
            try:
                client_sock, client_addr = server_sock.accept()
            except socket.timeout:
                continue

            worker = threading.Thread(
                target=handle_client,
                args=(client_sock, client_addr, state, stop_event, client_timeout),
                daemon=True,
            )
            worker.start()
    except KeyboardInterrupt:
        print("\n[INFO] Đã nhận tín hiệu dừng, đang đóng TCP server.", flush=True)
    finally:
        stop_event.set()
        try:
            server_sock.close()
        except OSError:
            pass
        if cpu_thread is not None:
            cpu_thread.join(timeout=2.0)


def main() -> None:
    """Điểm vào chính của chương trình."""
    args = parse_args()
    run_server(
        host=args.host,
        port=args.port,
        client_timeout=args.client_timeout,
        cpu_interval=args.cpu_interval,
        cpu_log_path=args.cpu_log,
    )


if __name__ == "__main__":
    main()
