
import csv
import json
import math
import statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = ROOT / "experiments" / "raw-data"
OUTPUT_DIR = ROOT / "experiments" / "analysis"

# Các tên cột có thể được sử dụng trong dữ liệu của nhóm.
ALIASES = {
    "run_id": ("run_id", "run", "iteration", "test_id"),
    "client_count": ("client_count", "num_clients", "clients"),
    "latency": ("latency_ms", "rtt_ms", "latency", "rtt"),
    "cpu": ("cpu_percent", "cpu", "cpu_usage"),
    "success": ("success", "is_success", "successful"),
    "timestamp": ("timestamp", "time"),
    "duration": ("duration_seconds", "duration_sec"),
}


def normalize_key(key):
    return str(key).strip().lower().replace("-", "_").replace(" ", "_")


def get_value(row, *names):
    normalized = {
        normalize_key(key): value
        for key, value in row.items()
    }

    for name in names:
        value = normalized.get(normalize_key(name))
        if value is not None and str(value).strip() != "":
            return value

    return None


def to_float(value):
    try:
        number = float(str(value).strip().replace(",", "."))
        return number if math.isfinite(number) else None
    except (ValueError, TypeError):
        return None


def to_bool(value):
    if isinstance(value, bool):
        return value

    if value is None:
        return None

    value = str(value).strip().lower()

    if value in ("true", "1", "yes", "success", "ok", "passed"):
        return True

    if value in ("false", "0", "no", "failed", "error", "timeout"):
        return False

    return None


def to_timestamp(value):
    """Chuyển timestamp dạng số hoặc ISO datetime về giây."""
    number = to_float(value)

    if number is not None:
        # Hỗ trợ Unix timestamp tính bằng milliseconds.
        if number > 1e12:
            return number / 1000
        return number

    if value is None:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).strip().replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.timestamp()

    except (ValueError, TypeError):
        return None


def calculate_p95(values):
    if not values:
        return None

    values = sorted(values)
    index = max(0, math.ceil(0.95 * len(values)) - 1)
    return values[index]


def load_data():
    """Đọc các file CSV/JSON và giữ lại tên file nguồn."""
    data = []

    if not RAW_DIR.exists():
        print(f"Không tìm thấy thư mục: {RAW_DIR}")
        return data

    files = sorted(
        list(RAW_DIR.glob("*.csv")) +
        list(RAW_DIR.glob("*.json"))
    )

    if not files:
        print("[CẢNH BÁO] Chưa có CSV/JSON trong raw-data.")
        return data

    for file in files:
        try:
            if file.suffix.lower() == ".csv":
                with open(
                    file, "r", encoding="utf-8-sig", newline=""
                ) as f:
                    records = list(csv.DictReader(f))

            else:
                with open(file, "r", encoding="utf-8") as f:
                    content = json.load(f)

                if isinstance(content, list):
                    records = content

                elif isinstance(content, dict):
                    records = []

                    for key in ("results", "records", "data", "requests"):
                        if isinstance(content.get(key), list):
                            records = content[key]
                            break

                    if not records:
                        records = [content]

                else:
                    print(f"[BỎ QUA] JSON không hợp lệ: {file.name}")
                    continue

            valid_records = 0

            for record in records:
                if not isinstance(record, dict):
                    continue

                row = dict(record)
                row["_source_file"] = file.stem
                data.append(row)
                valid_records += 1

            print(f"Đã đọc {file.name}: {valid_records} dòng")

        except (OSError, csv.Error, json.JSONDecodeError) as error:
            print(f"[LỖI] Không đọc được {file.name}: {error}")

    return data


def calculate_stats(rows, run_id, clients):
    latencies = []
    cpu_values = []
    timestamps = []
    durations = []

    success_count = 0
    error_count = 0
    unknown_status_count = 0

    for row in rows:
        latency = to_float(get_value(row, *ALIASES["latency"]))

        if latency is not None and latency >= 0:
            latencies.append(latency)

        cpu = to_float(get_value(row, *ALIASES["cpu"]))

        if cpu is not None and cpu >= 0:
            cpu_values.append(cpu)

        status = to_bool(get_value(row, *ALIASES["success"]))

        if status is True:
            success_count += 1
        elif status is False:
            error_count += 1
        else:
            unknown_status_count += 1

        timestamp = to_timestamp(
            get_value(row, *ALIASES["timestamp"])
        )

        if timestamp is not None:
            timestamps.append(timestamp)

        duration = to_float(
            get_value(row, *ALIASES["duration"])
        )

        if duration is not None and duration > 0:
            durations.append(duration)

    total_requests = success_count + error_count

    # Ưu tiên thời gian đo được ghi rõ trong dữ liệu.
    duration_seconds = None

    if durations:
        duration_seconds = statistics.mean(durations)

    elif len(timestamps) >= 2:
        duration_seconds = max(timestamps) - min(timestamps)

    throughput = None

    if (
        duration_seconds is not None
        and duration_seconds > 0
        and total_requests > 0
    ):
        throughput = success_count / duration_seconds

    error_rate = None

    if total_requests > 0:
        error_rate = error_count / total_requests * 100

    return {
        "run_id": run_id,
        "client_count": clients,
        "total_requests": total_requests,
        "successful_requests": success_count,
        "failed_requests": error_count,
        "unknown_status_requests": unknown_status_count,
        "avg_latency_ms": (
            statistics.mean(latencies) if latencies else None
        ),
        "p95_latency_ms": calculate_p95(latencies),
        "throughput_rps": throughput,
        "error_rate_percent": error_rate,
        "cpu_mean_percent": (
            statistics.mean(cpu_values) if cpu_values else None
        ),
        "duration_seconds": duration_seconds,
        "latency_samples": len(latencies),
        "cpu_samples": len(cpu_values),
    }


def save_results(results):
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    csv_file = OUTPUT_DIR / "summary_stats.csv"
    json_file = OUTPUT_DIR / "summary_stats.json"

    if not results:
        print("[CẢNH BÁO] Không có kết quả hợp lệ để xuất.")
        return

    fields = list(results[0].keys())

    with open(
        csv_file, "w", newline="", encoding="utf-8-sig"
    ) as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(results)

    with open(json_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=4, ensure_ascii=False)

    print(f"\nĐã lưu: {csv_file}")
    print(f"Đã lưu: {json_file}")


def print_variation(results):
    print("\n===== TRUNG BÌNH VÀ ĐỘ LỆCH CHUẨN =====")

    by_clients = defaultdict(list)

    for result in results:
        by_clients[result["client_count"]].append(result)

    metrics = (
        "avg_latency_ms",
        "p95_latency_ms",
        "throughput_rps",
        "error_rate_percent",
        "cpu_mean_percent",
    )

    for clients, group in sorted(by_clients.items()):
        print(f"\nSố Client: {clients}")
        print(f"Số lần chạy ghi nhận: {len(group)}")

        if len(group) != 3:
            print("[CẢNH BÁO] Chưa đủ 3 lần chạy cho mức Client này.")

        for metric in metrics:
            values = [
                item[metric]
                for item in group
                if item[metric] is not None
            ]

            if not values:
                print(f"{metric}: Không có dữ liệu")
                continue

            mean = statistics.mean(values)
            std = statistics.stdev(values) if len(values) >= 2 else 0

            print(
                f"{metric}: Mean={mean:.2f}, "
                f"Std Dev={std:.2f}"
            )


def main():
    rows = load_data()

    if not rows:
        print("\nChưa có dữ liệu để phân tích.")
        return

    grouped = defaultdict(list)
    skipped = 0

    for row in rows:
        clients = to_float(
            get_value(row, *ALIASES["client_count"])
        )

        if clients is None or clients <= 0 or not clients.is_integer():
            print("[BỎ QUA] Dòng thiếu/sai client_count:", row)
            skipped += 1
            continue

        run_id = get_value(row, *ALIASES["run_id"])

        # Nếu file được tổ chức theo từng lần chạy riêng,
        # tên file được dùng làm mã lần chạy dự phòng.
        if run_id is None:
            source = row.get("_source_file")

            if source:
                run_id = source
            else:
                print("[BỎ QUA] Không xác định được run_id:", row)
                skipped += 1
                continue

        grouped[(str(run_id), int(clients))].append(row)

    results = []

    for (run_id, clients), group in sorted(grouped.items()):
        results.append(calculate_stats(group, run_id, clients))

    if not results:
        print("[CẢNH BÁO] Không có nhóm dữ liệu hợp lệ.")
        return

    print("\n===== KẾT QUẢ KIỂM CHỨNG =====")

    for result in results:
        print(result)

    print(f"\nSố nhóm lần chạy hợp lệ: {len(results)}")
    print(f"Số dòng bị bỏ qua: {skipped}")

    save_results(results)
    print_variation(results)


if __name__ == "__main__":
    main()
