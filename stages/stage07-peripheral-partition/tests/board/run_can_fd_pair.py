#!/usr/bin/env python3
"""Temporary UP1/UP2 CAN FD tests; reuse IRQ resource guards and recovery."""
import argparse
from pathlib import Path
import re

import run_can_direct_pair as pair
import run_can_irq_pair as irq

FRAMES = 3000
PROFILE = 0


def validate_fd_result(text_a, text_b):
    targets = []
    for up, text, mask in ((1, text_a, 0x0600), (2, text_b, 0x6000)):
        before = re.search(rf"\[can-irq\] UP{up} before gate=0x([0-9a-f]+) "
                           r"reset=0x([0-9a-f]+) select=0x([0-9a-f]+)", text)
        if (not before or any(int(before[i], 16) & mask != mask for i in (1, 2)) or
                int(before[3], 16) & 0x3F80 != 15 << 7):
            raise RuntimeError(f"UP{up}: missing disabled clock/reset/divider evidence")
        counts = re.search(rf"\[can-irq\] UP{up} counts irq=(\d+) txirq=(\d+) rxirq=(\d+) "
                           r"err=0x([0-9a-f]+) overflow=(\d+) wrongcpu=(\d+) target=0x([0-9a-f]+)", text)
        if not counts:
            raise RuntimeError(f"UP{up}: missing IRQ counters")
        total, tx, rx = (int(counts[i]) for i in (1, 2, 3))
        target = int(counts[7], 16)
        if (tx != FRAMES or rx != FRAMES or total < FRAMES or int(counts[4], 16) or
                int(counts[5]) or int(counts[6]) or not target or target & (target - 1)):
            raise RuntimeError(f"UP{up}: invalid IRQ counters or target")
        targets.append(target)
        expected_db = 0x0D90011A if PROFILE == 4 else 0x0D90031A
        expected_tdc = 0x35 if PROFILE == 4 else 0
        config = re.search(rf"\[can-fd\] UP{up} config profile=(\d+) nbtp=0x([0-9a-f]+) "
                           r"dbtp=0x([0-9a-f]+) tdcr=0x([0-9a-f]+) brscfg=0x([0-9a-f]+)", text)
        if not config or tuple(int(config[i], 10 if i == 1 else 16) for i in range(1, 6)) != (
                PROFILE, 0x0C020C54, expected_db, expected_tdc, 7):
            raise RuntimeError(f"UP{up}: wrong FD bit timing/readback")
        for stage, length, dlc in ((1, 16, 10), (2, 32, 13), (3, 64, 15)):
            row = re.search(rf"\[can-fd\] UP{up} stage={stage} len={length} profile={PROFILE} "
                            rf"tx={stage * 1000} rx={stage * 1000} rxinfo=0x([0-9a-f]+)", text)
            if not row:
                raise RuntimeError(f"UP{up}: missing FD stage {stage}")
            info = int(row[1], 16)
            expected_flags = (1 << 21) | ((1 << 20) if PROFILE else 0)
            if info & (0xF << 20) != expected_flags or (info >> 24) & 15 != dlc:
                raise RuntimeError(f"UP{up}: incorrect received FDF/BRS/DLC at stage {stage}")
        brs_frames = FRAMES if PROFILE else 0
        expected = (f"[can-fd] UP{up} PASS profile={PROFILE} tx={FRAMES} rx={FRAMES} "
                    f"txbytes=112000 rxbytes=112000 rxfd={FRAMES} rxbrs={brs_frames} rc=0")
        if expected not in text or f"[can] UP{up} direct PASS tx=3000 rx=3000 txerr=0 rxerr=0" not in text:
            raise RuntimeError(f"UP{up}: wrong FD totals or CAN errors")
    if targets[0] == targets[1]:
        raise RuntimeError("two FD instances share a GIC target")
    print(f"FD VALIDATION PASS profile={PROFILE} lengths=16/32/64 targets={targets}", flush=True)


def main():
    global PROFILE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=int, choices=(0, 2, 4), default=0)
    parser.add_argument("--stop-a-first", action="store_true")
    args = parser.parse_args()
    PROFILE = args.profile
    pair.TEST_ROOT = Path("/root/m7-can-fd-20261009")
    pair.CLIENTS = (f"up-b-m7-can-fd{PROFILE}", f"up-a-m7-can-fd{PROFILE}")
    pair.CONFIGS = {name: pair.TEST_ROOT / f"{name}.conf" for name in pair.CLIENTS}
    pair.EXPECTED_FRAMES = FRAMES
    pair.STOP_CLIENTS = tuple(reversed(pair.CLIENTS)) if args.stop_a_first else pair.CLIENTS
    pair.TEST_DEADLINE = 60.0
    pair.prepare_linux_controllers = irq.prepare_without_linux_start
    pair.unbind_controllers = irq.unbind_and_disable_resources
    pair.restore_controllers = irq.restore_after_cpu_off
    pair.validate_result = validate_fd_result
    print(f"FD PROFILE {PROFILE}; STOP ORDER {pair.STOP_CLIENTS}", flush=True)
    pair.main()


if __name__ == "__main__":
    main()
