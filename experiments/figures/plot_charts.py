
import csv
import math
import statistics
from pathlib import Path

import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[2]

INPUT_FILE = ROOT / "experiments" / "analysis" / "summary_stats.csv"
OUTPUT_DIR = ROOT / "experiments" / "figures"


def load_data():
    """Đọc kết quả thống kê từ verify_and_stats.py."""
    if not INPUT_FILE.exists():
        print("[CẢNH BÁO] Không tìm thấy summary_stats.csv")
        print("Hãy chạy verify_and_stats.py trước.")
        return []

    try:
        with open(INPUT_FILE, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))

        if not rows:
            print("[CẢNH BÁO] File summary_stats.csv không có dữ liệu.")
            return []

        required_columns = {"client_count"}

        missing = required_columns - set(rows[0].keys())

        if missing:
            print("[LỖI] Thiếu cột:", ", ".join(missing))
            return []

        return rows

    except (OSError, csv.Error) as error:
        print("[LỖI] Không đọc được dữ liệu:", error)
        return []


def to_float(value):
    """Chuyển giá trị sang số, bỏ qua dữ liệu không hợp lệ."""
    try:
        number = float(value)

        if math.isfinite(number):
            return number

    except (ValueError, TypeError):
        pass

    return None


def calculate_average(rows, metric):
    """
    Tính trung bình và độ lệch chuẩn của từng mức Client.
    """
    grouped = {}

    for row in rows:
        clients = to_float(row.get("client_count"))
        value = to_float(row.get(metric))

        if clients is None or value is None:
            continue

        if clients <= 0 or not clients.is_integer():
            continue

        grouped.setdefault(int(clients), []).append(value)

    clients_list = sorted(grouped.keys())

    averages = []
    deviations = []

    for clients in clients_list:
        values = grouped[clients]

        averages.append(statistics.mean(values))

        # Chỉ tính độ lệch chuẩn mẫu khi có ít nhất 2 lần chạy.
        if len(values) >= 2:
            deviations.append(statistics.stdev(values))
        else:
            deviations.append(0)

    return clients_list, averages, deviations


def draw_chart(rows, metric, title, ylabel, filename):
    clients, averages, deviations = calculate_average(
        rows, metric
    )

    if not clients:
        print("[CẢNH BÁO] Không đủ dữ liệu để vẽ:", title)
        return

    plt.figure(figsize=(8, 5))

    plt.errorbar(
        clients,
        averages,
        yerr=deviations,
        marker="o",
        linewidth=2,
        capsize=5,
        label="Mean ± Standard Deviation"
    )

    plt.title(title)
    plt.xlabel("Number of concurrent clients")
    plt.ylabel(ylabel)

    plt.xticks(clients)
    plt.grid(True, linestyle="--", alpha=0.5)
    plt.legend()

    plt.tight_layout()

    output_file = OUTPUT_DIR / filename

    plt.savefig(output_file, dpi=200)
    plt.close()

    print("Đã lưu biểu đồ:", output_file)

    for client, mean, std in zip(
        clients, averages, deviations
    ):
        print(
            f"  {client} clients: "
            f"Mean={mean:.2f}, Std Dev={std:.2f}"
        )


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    rows = load_data()

    if not rows:
        return

    charts = [
        (
            "avg_latency_ms",
            "Average Latency vs Number of Clients",
            "Average Latency (ms)",
            "latency_vs_clients.png"
        ),
        (
            "throughput_rps",
            "Throughput vs Number of Clients",
            "Throughput (requests/second)",
            "throughput_vs_clients.png"
        ),
        (
            "cpu_mean_percent",
            "CPU Usage vs Number of Clients",
            "CPU Usage (%)",
            "cpu_vs_clients.png"
        )
    ]

    print("\n===== TẠO BIỂU ĐỒ =====")

    for metric, title, ylabel, filename in charts:
        draw_chart(
            rows,
            metric,
            title,
            ylabel,
            filename
        )

    print("\nHoàn thành quá trình vẽ biểu đồ.")


if __name__ == "__main__":
    main()
