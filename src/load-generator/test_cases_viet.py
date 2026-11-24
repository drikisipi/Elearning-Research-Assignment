"""
test_cases.py - Bo kiem thu 5 kich ban chuc nang va xu ly loi cho TCP Echo Server.

Chay (khi server dang chay):
    py src/load-generator/test_cases_.py --host 127.0.0.1 --port 9000

Giao thuc gia dinh (theo ke hoach nhom): 4-byte do dai (big-endian) + body JSON
{"requestId": <int|str>, "payload": <str 1KB>}.
Neu protocol.py cua nhom khac (vd: payload la bytes/base64, header little-endian),
chi can sua cac hang so + ham build_request / parse_response o phan CAU HINH.
"""

import argparse
import json
import os
import random
import socket
import string
import struct
import sys
import threading
import time

# ----------------------------- CAU HINH -----------------------------
HEADER_FMT = ">I"                     # 4 byte, big-endian
HEADER_SIZE = struct.calcsize(HEADER_FMT)
PAYLOAD_SIZE = 1024                   # 1KB
OVERSIZE_LEN = 64 * 1024 * 1024       # do dai "vuot gioi han" gia lap (64MB)


def build_request(request_id, payload: str) -> bytes:
    return json.dumps({"requestId": request_id, "payload": payload}).encode("utf-8")


def parse_response(body: bytes):
    obj = json.loads(body.decode("utf-8"))
    return obj["requestId"], obj["payload"]
# --------------------------------------------------------------------


def random_payload(n=PAYLOAD_SIZE) -> str:
    return "".join(random.choices(string.ascii_letters + string.digits, k=n))


def recv_exact(sock, n):
    """Doc du n byte (khong gia dinh 1 lan recv() la du). Tra None neu peer dong ket noi."""
    buf = b""
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def send_frame(sock, body: bytes):
    sock.sendall(struct.pack(HEADER_FMT, len(body)) + body)


def recv_frame(sock):
    header = recv_exact(sock, HEADER_SIZE)
    if header is None:
        return None
    (length,) = struct.unpack(HEADER_FMT, header)
    return recv_exact(sock, length)


def connect(host, port, timeout):
    s = socket.create_connection((host, port), timeout=timeout)
    s.settimeout(timeout)
    return s


def echo_once(sock, request_id, payload=None):
    """Gui 1 request, tra (ok, ly_do)."""
    payload = payload if payload is not None else random_payload()
    send_frame(sock, build_request(request_id, payload))
    body = recv_frame(sock)
    if body is None:
        return False, "server dong ket noi"
    try:
        rid, pl = parse_response(body)
    except Exception as exc:
        return False, f"response khong hop le: {exc}"
    if rid != request_id:
        return False, f"requestId sai: gui {request_id}, nhan {rid}"
    if pl != payload:
        return False, "payload tra ve khac payload da gui"
    return True, "ok"


def server_alive(host, port, timeout):
    """Mo ket noi moi va echo thanh cong => server con song."""
    try:
        s = connect(host, port, timeout)
        try:
            ok, _ = echo_once(s, "alive-check")
            return ok
        finally:
            s.close()
    except OSError:
        return False


def abort_socket(sock):
    """Dong dot ngot (gui RST) de gia lap Client chet/mat mang."""
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
    except OSError:
        pass
    sock.close()


# ============================ 5 KICH BAN ============================

def test_1_one_and_many_clients(host, port, timeout):
    # 1a: 1 client, 5 request lien tiep
    s = connect(host, port, timeout)
    try:
        for i in range(5):
            ok, why = echo_once(s, f"single-{i}")
            if not ok:
                return False, f"1 client that bai o request {i}: {why}"
    finally:
        s.close()

    # 1b: 10 client dong thoi, moi client 10 request
    errors = []

    def worker(cid):
        try:
            c = connect(host, port, timeout)
            try:
                for i in range(10):
                    ok, why = echo_once(c, f"c{cid}-{i}")
                    if not ok:
                        errors.append(f"client {cid} req {i}: {why}")
                        return
            finally:
                c.close()
        except Exception as exc:
            errors.append(f"client {cid}: {exc}")

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    if errors:
        return False, "; ".join(errors[:3])
    return True, "1 client x5 req va 10 client dong thoi x10 req deu dung"


def test_2_request_id_and_payload(host, port, timeout):
    s = connect(host, port, timeout)
    try:
        for i in range(50):
            rid = random.randint(1, 10**9) if i % 2 else f"id-{i}"
            ok, why = echo_once(s, rid, random_payload())
            if not ok:
                return False, f"lan {i}: {why}"
    finally:
        s.close()
    return True, "50 request: requestId va payload 1KB khop 100%"


def test_3_abrupt_disconnect(host, port, timeout):
    # (a) gui nua goi roi dong dot ngot
    s = connect(host, port, timeout)
    body = build_request("partial", random_payload())
    s.sendall(struct.pack(HEADER_FMT, len(body)) + body[: len(body) // 2])
    abort_socket(s)
    # (b) ket noi roi dong ngay
    s2 = connect(host, port, timeout)
    abort_socket(s2)
    # (c) chi gui header roi dong
    s3 = connect(host, port, timeout)
    s3.sendall(struct.pack(HEADER_FMT, 500))
    s3.close()
    time.sleep(0.5)
    if not server_alive(host, port, timeout):
        return False, "server khong con phuc vu sau khi client ngat dot ngot"
    return True, "ngat giua goi / ngat ngay / chi gui header: server van echo binh thuong"


def _probe_bad_input(host, port, timeout, raw: bytes):
    """Gui du lieu xau; tra ve 'closed' | 'reply' | 'timeout'."""
    s = connect(host, port, timeout)
    try:
        s.sendall(raw)
        try:
            data = s.recv(65536)
        except socket.timeout:
            return "timeout"
        except OSError:
            return "closed"
        return "closed" if not data else "reply"
    finally:
        s.close()


def test_4_invalid_data(host, port, timeout):
    notes = []
    # (a) body khong phai JSON, do dai header dung
    junk = b"this-is-not-json-\xff\xfe" * 10
    notes.append("JSON loi->" + _probe_bad_input(host, port, timeout, struct.pack(HEADER_FMT, len(junk)) + junk))
    # (b) header khai bao do dai vuot gioi han
    notes.append("do dai vuot gioi han->" + _probe_bad_input(host, port, timeout, struct.pack(HEADER_FMT, OVERSIZE_LEN)))
    # (c) payload that su lon (> 1KB nhieu lan) trong JSON hop le
    big = build_request("big", "X" * (2 * 1024 * 1024))
    notes.append("payload 2MB->" + _probe_bad_input(host, port, timeout, struct.pack(HEADER_FMT, len(big)) + big))
    time.sleep(0.5)
    alive = server_alive(host, port, timeout)
    detail = "; ".join(notes)
    if not alive:
        return False, f"server khong con phuc vu sau du lieu xau ({detail})"
    return True, f"server van song sau du lieu xau ({detail})"


def test_5_server_survives_bad_client(host, port, timeout):
    healthy = connect(host, port, timeout)
    try:
        ok, why = echo_once(healthy, "before")
        if not ok:
            return False, f"client khoe loi truoc khi co client xau: {why}"
        # nhieu client xau cung luc
        for _ in range(5):
            b = connect(host, port, timeout)
            b.sendall(struct.pack(HEADER_FMT, 999999) + b"garbage")
            abort_socket(b)
        time.sleep(0.5)
        ok, why = echo_once(healthy, "after")
        if not ok:
            return False, f"client khoe bi anh huong boi client xau: {why}"
    finally:
        healthy.close()
    if not server_alive(host, port, timeout):
        return False, "server khong nhan ket noi moi sau khi nhieu client loi"
    return True, "client khoe van echo dung + server nhan ket noi moi sau 5 client loi"


TESTS = [
    ("TC1", "1 va nhieu Client ket noi dong thoi", test_1_one_and_many_clients),
    ("TC2", "Dung requestId va payload", test_2_request_id_and_payload),
    ("TC3", "Client ngat ket noi bat thuong", test_3_abrupt_disconnect),
    ("TC4", "Du lieu khong hop le / vuot gioi han", test_4_invalid_data),
    ("TC5", "Server van hoat dong sau khi Client loi", test_5_server_survives_bad_client),
]


def main():
    ap = argparse.ArgumentParser(description="Kiem thu chuc nang va xu ly loi TCP Echo Server")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--timeout", type=float, default=5.0)
    ap.add_argument("--out", default=None, help="Luu ket qua ra file JSON (vd: experiments/raw-data/test_results.json)")
    args = ap.parse_args()

    if not server_alive(args.host, args.port, args.timeout):
        print(f"[LOI] Khong ket noi/echo duoc toi {args.host}:{args.port}. Hay chay server truoc.")
        sys.exit(2)

    results = []
    for code, name, fn in TESTS:
        t0 = time.time()
        try:
            ok, detail = fn(args.host, args.port, args.timeout)
        except Exception as exc:  # loi bat ngo trong chinh script kiem thu
            ok, detail = False, f"ngoai le: {exc!r}"
        results.append({"id": code, "name": name, "passed": ok, "detail": detail,
                        "seconds": round(time.time() - t0, 2)})
        print(f"[{'PASS' if ok else 'FAIL'}] {code} - {name}\n        {detail}")

    passed = sum(r["passed"] for r in results)
    print(f"\nKet qua: {passed}/{len(results)} kich ban dat")

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=2)
        print(f"Da luu: {args.out}")
    sys.exit(0 if passed == len(results) else 1)


if __name__ == "__main__":
    main()
