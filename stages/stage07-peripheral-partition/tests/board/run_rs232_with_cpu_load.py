#!/usr/bin/env python3
"""Bounded Linux CPU load during the UART pair test, without touching UART data."""
import subprocess
import sys
from pathlib import Path


def main():
    workers = []
    try:
        for _ in range(4):
            workers.append(subprocess.Popen(["nice", "-n", "19", "python3", "-c",
                "import time; end=time.monotonic()+150; x=1\nwhile time.monotonic()<end: x=(x*1664525+1013904223)&0xffffffff"],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
        print(f"LINUX CPU LOAD workers={len(workers)} nice=19 bounded=150s", flush=True)
        result = subprocess.run([sys.executable, str(Path(__file__).with_name("run_rs232_pair.py")), *sys.argv[1:]])
        return result.returncode
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.terminate()
        for worker in workers:
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill(); worker.wait(timeout=5)
        print("CPU LOAD CLEANUP PASS", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
