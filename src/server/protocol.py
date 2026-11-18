"""
Module: protocol.py
Phụ trách: Nguyễn Thái Lộc (Nhóm trưởng)
Mô tả:
- Định nghĩa giao thức ứng dụng (Application Protocol) cho dịch vụ TCP Echo Benchmark.
- Cơ chế phân tách message (Message Framing) sử dụng Length-Prefix 4 bytes (Big-Endian).
- Đảm bảo đọc vòng lặp tích lũy (recv_exact), không giả định 1 lần recv() trả về đủ 1 message.
- Hỗ trợ tạo payload cố định 1KB, kiểm tra tính hợp lệ của requestId, payload và chặn gói vượt giới hạn.
"""

import json
import socket
import struct
from typing import Any, Dict, Optional

HEADER_FORMAT = "!I"  # 4-byte unsigned integer, Big-Endian (Network Byte Order)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

DEFAULT_PAYLOAD_SIZE = 1024        # Kích thước payload chuẩn theo đề bài: 1 KB (1024 bytes)
MAX_PAYLOAD_SIZE = 4 * 1024        # Giới hạn payload tối đa cho phép: 4 KB
MAX_MESSAGE_SIZE = 8 * 1024        # Giới hạn tổng kích thước phần thân JSON tối đa: 8 KB


class ProtocolError(Exception):
    """Ngoại lệ phát sinh khi gói tin sai định dạng, thiếu trường hoặc vượt giới hạn."""
    pass


def generate_payload(size_bytes: int = DEFAULT_PAYLOAD_SIZE) -> str:
    """
    Tạo chuỗi payload ASCII có kích thước chính xác bằng `size_bytes` (mặc định 1024 bytes = 1 KB).
    """
    if size_bytes < 0 or size_bytes > MAX_PAYLOAD_SIZE:
        raise ValueError(f"Kích thước payload phải nằm trong khoảng 0..{MAX_PAYLOAD_SIZE} bytes.")
    pattern = "0123456789ABCDEF"
    repeats = (size_bytes // len(pattern)) + 1
    return (pattern * repeats)[:size_bytes]


def encode_message(request_id: int, payload: str) -> bytes:
    """
    Đóng gói bản tin gồm `requestId` và `payload` thành chuỗi byte theo cấu trúc:
    [4-byte Length Header (Big-Endian)][JSON UTF-8 Body]
    """
    if isinstance(request_id, bool) or not isinstance(request_id, int) or request_id < 0:
        raise ProtocolError(f"requestId không hợp lệ: {request_id}")
    if not isinstance(payload, str):
        raise ProtocolError("payload phải là kiểu chuỗi (str).")

    payload_bytes_len = len(payload.encode("utf-8"))
    if payload_bytes_len > MAX_PAYLOAD_SIZE:
        raise ProtocolError(
            f"Kích thước payload ({payload_bytes_len} bytes) vượt giới hạn cho phép ({MAX_PAYLOAD_SIZE} bytes)."
        )

    body_dict = {
        "requestId": request_id,
        "payload": payload,
    }
    body_bytes = json.dumps(body_dict, separators=(",", ":")).encode("utf-8")

    if len(body_bytes) > MAX_MESSAGE_SIZE:
        raise ProtocolError(
            f"Tổng kích thước message ({len(body_bytes)} bytes) vượt giới hạn ({MAX_MESSAGE_SIZE} bytes)."
        )

    header_bytes = struct.pack(HEADER_FORMAT, len(body_bytes))
    return header_bytes + body_bytes


def decode_body(body_bytes: bytes) -> Dict[str, Any]:
    """
    Giải mã phần thân JSON và kiểm tra các trường bắt buộc `requestId`, `payload`.
    """
    try:
        text = body_bytes.decode("utf-8")
        data = json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"Dữ liệu không phải JSON UTF-8 hợp lệ: {exc}") from exc

    if not isinstance(data, dict):
        raise ProtocolError("Cấu trúc message sau giải mã phải là một JSON object.")

    if "requestId" not in data or "payload" not in data:
        raise ProtocolError("Message thiếu trường bắt buộc 'requestId' hoặc 'payload'.")

    request_id = data["requestId"]
    payload = data["payload"]

    if isinstance(request_id, bool) or not isinstance(request_id, int) or request_id < 0:
        raise ProtocolError(f"Trường 'requestId' không hợp lệ: {request_id}")

    if not isinstance(payload, str):
        raise ProtocolError("Trường 'payload' phải là chuỗi ký tự.")

    payload_len = len(payload.encode("utf-8"))
    if payload_len > MAX_PAYLOAD_SIZE:
        raise ProtocolError(
            f"Payload nhận được ({payload_len} bytes) vượt giới hạn tối đa ({MAX_PAYLOAD_SIZE} bytes)."
        )

    return data


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """
    Đọc chính xác `num_bytes` từ TCP socket thông qua vòng lặp tích lũy buffer.
    Không giả định một lần gọi `sock.recv()` sẽ trả về đủ số byte yêu cầu.
    - Trả về `b""` nếu phía bên kia đóng kết nối ngay khi chưa gửi byte nào của message mới.
    - Ném `ConnectionResetError` nếu kết nối bị ngắt giữa chừng khi chưa nhận đủ `num_bytes`.
    """
    buf = bytearray()
    while len(buf) < num_bytes:
        chunk = sock.recv(num_bytes - len(buf))
        if not chunk:
            if len(buf) == 0:
                return b""
            raise ConnectionResetError(
                f"Kết nối đóng bất thường khi đang nhận dữ liệu (đã nhận {len(buf)}/{num_bytes} bytes)."
            )
        buf.extend(chunk)
    return bytes(buf)


def send_message(sock: socket.socket, request_id: int, payload: str) -> None:
    """
    Đóng gói và gửi toàn bộ message qua TCP socket.
    """
    framed_data = encode_message(request_id, payload)
    sock.sendall(framed_data)


def recv_message(sock: socket.socket) -> Optional[Dict[str, Any]]:
    """
    Nhận một message hoàn chỉnh từ TCP socket:
    1. Đọc đủ 4 bytes Header để biết độ dài `msg_length`.
    2. Kiểm tra `msg_length` có nằm trong phạm vi hợp lệ (1..MAX_MESSAGE_SIZE) hay không.
    3. Đọc đủ `msg_length` bytes tiếp theo của phần thân và giải mã.
    Trả về `None` nếu đầu bên kia đóng kết nối hợp lệ.
    """
    header_bytes = recv_exact(sock, HEADER_SIZE)
    if not header_bytes:
        return None

    (msg_length,) = struct.unpack(HEADER_FORMAT, header_bytes)
    if msg_length <= 0 or msg_length > MAX_MESSAGE_SIZE:
        raise ProtocolError(
            f"Độ dài message trong header không hợp lệ hoặc vượt giới hạn: {msg_length} bytes "
            f"(cho phép tối đa {MAX_MESSAGE_SIZE} bytes)."
        )

    body_bytes = recv_exact(sock, msg_length)
    if not body_bytes:
        raise ConnectionResetError("Kết nối đóng bất thường ngay sau khi gửi header.")

    return decode_body(body_bytes)


def verify_response(
    response: Optional[Dict[str, Any]],
    expected_request_id: int,
    expected_payload: str,
) -> bool:
    """
    Kiểm tra response từ Server có khớp chính xác cả `requestId` và `payload` hay không.
    Trả về True nếu hợp lệ, ngược lại ném ProtocolError.
    """
    if response is None:
        raise ProtocolError("Không nhận được response (Server đã đóng kết nối).")
    if response.get("requestId") != expected_request_id:
        raise ProtocolError(
            f"Sai lệch requestId: kỳ vọng {expected_request_id}, nhận được {response.get('requestId')}."
        )
    if response.get("payload") != expected_payload:
        raise ProtocolError("Nội dung payload trong response không khớp với payload đã gửi.")
    return True


def _run_self_tests() -> None:
    """
    Kiểm thử nội bộ module protocol.py (Tuần 1 - Nguyễn Thái Lộc):
    1. Đóng gói và giải mã gói chuẩn 1KB.
    2. Nhận đúng gói khi TCP bị phân mảnh (fragmentation - mỗi lần chỉ tới vài bytes).
    3. Tách đúng từng gói khi nhiều message bị gộp chung trong 1 lần gửi (coalescing).
    4. Phát hiện gói vượt giới hạn hoặc dữ liệu hỏng.
    5. Phát hiện ngắt kết nối giữa chừng.
    """
    payload_1kb = generate_payload(DEFAULT_PAYLOAD_SIZE)
    assert len(payload_1kb.encode("utf-8")) == 1024, "Payload phải đúng 1024 bytes."

    # 1 & 2. Kiểm thử phân mảnh TCP (gửi từng mảnh 7 bytes)
    s1, s2 = socket.socketpair()
    try:
        raw_packet = encode_message(101, payload_1kb)
        for i in range(0, len(raw_packet), 7):
            s1.sendall(raw_packet[i : i + 7])
        received = recv_message(s2)
        assert verify_response(received, 101, payload_1kb)
    finally:
        s1.close()
        s2.close()

    # 3. Kiểm thử dính gói TCP (gửi gộp 3 message trong 1 lần sendall)
    s1, s2 = socket.socketpair()
    try:
        combined = (
            encode_message(1, payload_1kb)
            + encode_message(2, payload_1kb)
            + encode_message(3, payload_1kb)
        )
        s1.sendall(combined)
        for expected_id in (1, 2, 3):
            msg = recv_message(s2)
            assert verify_response(msg, expected_id, payload_1kb)
    finally:
        s1.close()
        s2.close()

    # 4. Kiểm thử chặn gói vượt giới hạn header
    s1, s2 = socket.socketpair()
    try:
        fake_oversized_header = struct.pack(HEADER_FORMAT, MAX_MESSAGE_SIZE + 500)
        s1.sendall(fake_oversized_header)
        try:
            recv_message(s2)
            raise AssertionError("Phải ném ProtocolError khi header vượt giới hạn.")
        except ProtocolError:
            pass
    finally:
        s1.close()
        s2.close()

    # 5. Kiểm thử phát hiện đóng kết nối bất thường khi đang truyền dở
    s1, s2 = socket.socketpair()
    try:
        raw_packet = encode_message(999, payload_1kb)
        s1.sendall(raw_packet[:20])  # Chỉ gửi 20 bytes đầu rồi đóng đột ngột
        s1.close()
        try:
            recv_message(s2)
            raise AssertionError("Phải ném ConnectionResetError khi ngắt kết nối giữa chừng.")
        except ConnectionResetError:
            pass
    finally:
        s2.close()

    print("[OK] Tất cả bài kiểm thử protocol.py (Framing, 1KB payload, Fragmentation, Coalescing, Error handling) đều thành công.")


if __name__ == "__main__":
    _run_self_tests()
