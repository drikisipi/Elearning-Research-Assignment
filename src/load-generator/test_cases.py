"""Bộ kiểm thử chức năng và xử lý lỗi cho TCP echo server."""

import argparse
import json
import socket
import struct
import sys
import threading
import time
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

SERVER_DIR = Path(__file__).resolve().parents[1] / "server"
if str(SERVER_DIR) not in sys.path:
    sys.path.insert(0, str(SERVER_DIR))

import protocol  # noqa: E402

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_TIMEOUT = 5.0


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Đọc tham số địa chỉ IP, cổng và timeout."""
    parser = argparse.ArgumentParser(
        description="Bộ kiểm thử chức năng và xử lý lỗi cho TCP echo server."
    )
    parser.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Địa chỉ IP của TCP server (mặc định: {DEFAULT_HOST}).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Cổng TCP của server (mặc định: {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        help=f"Thời gian chờ socket tính bằng giây (mặc định: {DEFAULT_TIMEOUT}).",
    )
    return parser.parse_args(argv)


def test_single_client_echo(host: str, port: int, timeout: float) -> None:
    """Kiểm tra một client gửi nhận echo."""
    payload = protocol.generate_payload()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        for req_id in range(1, 6):
            protocol.send_message(sock, req_id, payload)
            response = protocol.recv_message(sock)
            protocol.verify_response(response, req_id, payload)


def test_multiple_concurrent_clients(
    host: str,
    port: int,
    timeout: float,
    num_clients: int = 10,
    requests_per_client: int = 10,
) -> None:
    """Kiểm tra nhiều client gửi nhận echo đồng thời."""
    payload = protocol.generate_payload()
    barrier = threading.Barrier(num_clients)
    errors: List[Tuple[int, str]] = []
    errors_lock = threading.Lock()

    def worker(client_idx: int) -> None:
        try:
            with socket.create_connection((host, port), timeout=timeout) as sock:
                sock.settimeout(timeout)
                barrier.wait(timeout=timeout)
                for step in range(requests_per_client):
                    req_id = client_idx * 1000 + step + 1
                    protocol.send_message(sock, req_id, payload)
                    response = protocol.recv_message(sock)
                    protocol.verify_response(response, req_id, payload)
        except Exception as exc:
            with errors_lock:
                errors.append((client_idx, repr(exc)))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(num_clients)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=timeout * 3)

    if errors:
        raise AssertionError(f"Có lỗi ở kiểm thử nhiều client đồng thời: {errors}")


def test_abnormal_disconnect(host: str, port: int, timeout: float) -> None:
    """Kiểm tra client ngắt kết nối giữa chừng khi đang gửi gói."""
    payload = protocol.generate_payload()
    raw_packet = protocol.encode_message(100, payload)
    sock = socket.create_connection((host, port), timeout=timeout)
    try:
        sock.settimeout(timeout)
        sock.sendall(raw_packet[:15])
    finally:
        sock.close()
    time.sleep(0.1)


def test_invalid_data_and_oversized_payload(host: str, port: int, timeout: float) -> None:
    """Kiểm tra server từ chối dữ liệu lỗi và gói tin vượt giới hạn."""
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        bad_body = b"{invalid-json"
        sock.sendall(struct.pack(protocol.HEADER_FORMAT, len(bad_body)) + bad_body)
        resp = protocol.recv_message(sock)
        if resp is not None:
            raise AssertionError("Server phải đóng kết nối khi nhận dữ liệu không phải JSON.")

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        incomplete_body = json.dumps({"requestId": 1}).encode("utf-8")
        sock.sendall(
            struct.pack(protocol.HEADER_FORMAT, len(incomplete_body)) + incomplete_body
        )
        resp = protocol.recv_message(sock)
        if resp is not None:
            raise AssertionError("Server phải đóng kết nối khi bản tin thiếu trường payload.")

    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        oversized_header = struct.pack(
            protocol.HEADER_FORMAT, protocol.MAX_MESSAGE_SIZE + 512
        )
        sock.sendall(oversized_header)
        resp = protocol.recv_message(sock)
        if resp is not None:
            raise AssertionError("Server phải đóng kết nối khi gói tin vượt quá giới hạn.")


def test_server_continues_after_errors(host: str, port: int, timeout: float) -> None:
    """Kiểm tra server vẫn phục vụ sau khi có client gặp lỗi."""
    payload = protocol.generate_payload()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        sock.settimeout(timeout)
        for req_id in (501, 502, 503):
            protocol.send_message(sock, req_id, payload)
            response = protocol.recv_message(sock)
            protocol.verify_response(response, req_id, payload)


def run_all_tests(host: str, port: int, timeout: float) -> bool:
    """Chạy toàn bộ các kịch bản kiểm thử."""
    cases = [
        ("Một client gửi nhận và khớp requestId, payload", test_single_client_echo),
        ("Nhiều client đồng thời (10 client)", test_multiple_concurrent_clients),
        ("Client đóng kết nối bất thường giữa chừng", test_abnormal_disconnect),
        (
            "Dữ liệu không hợp lệ và gói tin vượt giới hạn",
            test_invalid_data_and_oversized_payload,
        ),
        ("Server vẫn hoạt động sau khi có client gặp lỗi", test_server_continues_after_errors),
    ]

    all_passed = True
    for index, (name, fn) in enumerate(cases, start=1):
        try:
            fn(host, port, timeout)
            print(f"[PASS] ({index}/{len(cases)}) {name}", flush=True)
        except Exception as exc:
            all_passed = False
            print(f"[FAIL] ({index}/{len(cases)}) {name}: {exc}", flush=True)

    return all_passed


def main() -> None:
    """Điểm vào chính của chương trình."""
    args = parse_args()
    success = run_all_tests(args.host, args.port, args.timeout)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
