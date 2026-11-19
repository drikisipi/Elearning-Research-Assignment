"""
Ứng dụng console TCP echo server.
Nhận kết nối từ client, đọc bản tin qua module protocol và phản hồi giữ nguyên requestId và payload.
"""

import argparse
import socket
from typing import Optional, Sequence, Tuple

try:
    import protocol
except ImportError:
    from src.server import protocol

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_BACKLOG = 128


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Phân tích các tham số dòng lệnh cho TCP server."""
    parser = argparse.ArgumentParser(
        description="TCP echo server tối thiểu sử dụng giao thức đóng gói 4 byte độ dài."
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
    return parser.parse_args(argv)


def handle_client(client_sock: socket.socket, client_addr: Tuple[str, int]) -> None:
    """Xử lý vòng lặp nhận yêu cầu và phản hồi echo cho một kết nối client."""
    print(f"[INFO] Kết nối mới từ {client_addr[0]}:{client_addr[1]}", flush=True)
    try:
        while True:
            request = protocol.recv_message(client_sock)
            if request is None:
                print(
                    f"[INFO] Client {client_addr[0]}:{client_addr[1]} đã đóng kết nối.",
                    flush=True,
                )
                break

            request_id = request["requestId"]
            payload = request["payload"]
            protocol.send_message(client_sock, request_id, payload)
    except protocol.ProtocolError as exc:
        print(
            f"[WARN] Lỗi giao thức từ {client_addr[0]}:{client_addr[1]}: {exc}",
            flush=True,
        )
    except OSError as exc:
        print(
            f"[WARN] Lỗi kết nối với {client_addr[0]}:{client_addr[1]}: {exc}",
            flush=True,
        )
    finally:
        client_sock.close()


def run_server(host: str, port: int, backlog: int = DEFAULT_BACKLOG) -> None:
    """Khởi tạo TCP socket lắng nghe và tiếp nhận kết nối từ client."""
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server_sock.bind((host, port))
        server_sock.listen(backlog)
        print(f"[INFO] TCP server đang lắng nghe tại {host}:{port}", flush=True)

        while True:
            client_sock, client_addr = server_sock.accept()
            handle_client(client_sock, client_addr)
    except KeyboardInterrupt:
        print("\n[INFO] Đã nhận tín hiệu dừng, đang đóng TCP server.", flush=True)
    finally:
        server_sock.close()


def main() -> None:
    """Điểm vào chính của chương trình."""
    args = parse_args()
    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
