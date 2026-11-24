"""
run_experiments.py - Tu dong chay 3 muc (1, 10, 50 client) x 3 lan = 9 lan.

Moi lan: bat server moi (kem --cpu-log/--run-id/--client-count) -> chay load_gen -> tat server.
Dat file nay o: experiments/run_experiments.py
Chay tu thu muc goc repo:
    py experiments/run_experiments.py
Tuy chon:
    py experiments/run_experiments.py --levels 10 50 --runs 1 2 3 --port 9000
"""

import argparse
import os
import subprocess
import sys
import time

CONFIGS = {
    1: "experiments/configs/config_1_client.json",
    10: "experiments/configs/config_10_clients.json",
    50: "experiments/configs/config_50_clients.json",
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", type=int, nargs="+", default=[1, 10, 50])
    ap.add_argument("--runs", type=int, nargs="+", default=[1, 2, 3])
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=9000)
    ap.add_argument("--cooldown", type=float, default=3.0, help="Giay nghi giua cac lan chay")
    args = ap.parse_args()

    py = sys.executable
    os.makedirs("experiments/raw-data", exist_ok=True)

    for n in args.levels:
        for run in args.runs:
            cpu_log = f"experiments/raw-data/cpu_{n}_clients_run{run}.csv"
            print(f"\n=== {n} client | lan {run} ===")
            server = subprocess.Popen([
                py, "src/server/server.py", "--host", args.host, "--port", str(args.port),
                "--cpu-log", cpu_log, "--run-id", str(run), "--client-count", str(n),
            ])
            try:
                time.sleep(1.5)  # cho server len
                if server.poll() is not None:
                    print("[LOI] Server thoat som, kiem tra lai tham so/cong.")
                    sys.exit(1)
                rc = subprocess.call([py, "src/load-generator/load_gen.py",
                                      "--config", CONFIGS[n], "--run", str(run)])
                if rc != 0:
                    print(f"[CANH BAO] load_gen tra ve ma {rc} (muc {n}, lan {run})")
            finally:
                server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
            time.sleep(args.cooldown)

    print("\nXong. Kiem tra experiments/raw-data/ (du 9 file load_gen + 9 file cpu).")


if __name__ == "__main__":
    main()
