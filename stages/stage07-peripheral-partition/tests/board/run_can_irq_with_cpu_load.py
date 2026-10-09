#!/usr/bin/env python3
"""Run the IRQ pair test with four bounded, low-priority Linux CPU workers."""
import subprocess
import run_can_irq_pair as irq


def main():
    workers = []
    try:
        for _ in range(4):
            workers.append(subprocess.Popen(
                ["nice", "-n", "19", "python3", "-c",
                 "import hashlib,time; end=time.monotonic()+90\n"
                 "while time.monotonic()<end: hashlib.sha256(b'x'*65536).digest()"],
                stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT))
        print(f"LINUX CPU LOAD workers={len(workers)} maximum_seconds=90", flush=True)
        irq.main()
    finally:
        for worker in workers:
            if worker.poll() is None:
                worker.terminate()
            try:
                worker.wait(timeout=5)
            except subprocess.TimeoutExpired:
                worker.kill()
                worker.wait(timeout=5)
        print("LINUX CPU LOAD cleanup complete", flush=True)


if __name__ == "__main__":
    main()
